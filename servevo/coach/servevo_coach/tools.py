"""陪练 Agent 工具：generate_scenario / evaluate_answer / lookup_reference / adjust_strategy。

迁移自 interview-agent `graphs/tools/interview_tools.py`（AGPL-3.0），
会话语境改为客服陪练，知识检索复用 servevo_rag（文件型，绕 pgvector 红线）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from servevo_eval.errors import ErrorCode
from servevo_eval.structured_output import LLMStructuredInvoker

from .prompt_loader import load_prompt
from .strategy import StrategyUpdate, compute_strategy_update

logger = logging.getLogger(__name__)


class GeneratedScenario(BaseModel):
    """LLM 生成的刁钻客户陪练剧本。"""

    scenario: str
    type: str = "CUSTOMER"
    category: str = ""
    followUp: str = ""


class AnswerEvaluation(BaseModel):
    """LLM 对主岗应答的即时评估（0-10）。"""

    score: int = Field(ge=0, le=10, description="0-10 分")
    feedback: str = ""
    shouldFollowUp: bool = False
    followUpSuggestion: str = ""


@dataclass
class CoachToolContext:
    """运行时注入的工具依赖（通过 RunnableConfig.configurable 传递）。"""

    chat_client: ChatOpenAI
    invoker: LLMStructuredInvoker
    kb_dir: str                # servevo/knowledge/<skill>/v<N>/references
    skill_id: str
    session_context: str = ""


_GENERATE_SYSTEM_PROMPT = "coach-generate-scenario-system"
_GENERATE_USER_PROMPT = "coach-generate-scenario-user"
_EVALUATE_SYSTEM_PROMPT = "coach-evaluate-answer-system"
_EVALUATE_USER_PROMPT = "coach-evaluate-answer-user"


async def generate_scenario_impl(
    category: str,
    difficulty: str,
    context: str,
    tool_ctx: CoachToolContext,
) -> GeneratedScenario:
    """按指定考察面与刁钻程度生成一个陪练剧本。"""
    system_tpl = await load_prompt(_GENERATE_SYSTEM_PROMPT)
    user_tpl = await load_prompt(_GENERATE_USER_PROMPT)
    system_prompt = system_tpl.format()
    user_prompt = user_tpl.format(
        category=category,
        difficulty=difficulty,
        context=context,
        sessionContext=tool_ctx.session_context[:2000] if tool_ctx.session_context else "无",
    )
    return await tool_ctx.invoker.invoke(
        llm=tool_ctx.chat_client,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output_model=GeneratedScenario,
        error_code=ErrorCode.COACH_SCENARIO_FAILED if hasattr(ErrorCode, "COACH_SCENARIO_FAILED") else ErrorCode.QC_EVALUATION_FAILED,
        error_prefix="陪练出题失败：",
        log_context="陪练出题",
    )


async def evaluate_answer_impl(
    question: str,
    answer: str,
    category: str,
    tool_ctx: CoachToolContext,
) -> AnswerEvaluation:
    """即时评估主岗对某剧本的应答。"""
    system_tpl = await load_prompt(_EVALUATE_SYSTEM_PROMPT)
    user_tpl = await load_prompt(_EVALUATE_USER_PROMPT)
    system_prompt = system_tpl.format()
    user_prompt = user_tpl.format(
        question=question,
        answer=answer,
        category=category,
    )
    return await tool_ctx.invoker.invoke(
        llm=tool_ctx.chat_client,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output_model=AnswerEvaluation,
        error_code=ErrorCode.QC_EVALUATION_FAILED,
        error_prefix="陪练即时评估失败：",
        log_context="陪练即时评估",
    )


async def lookup_reference_impl(
    category: str,
    tool_ctx: CoachToolContext,
) -> str:
    """检索知识包参考资料（文件型，复用 servevo_rag.knowledge）。"""
    try:
        from servevo_rag.knowledge import load_knowledge

        chunks = load_knowledge(tool_ctx.kb_dir)
        if not chunks:
            return f"知识包 {tool_ctx.kb_dir} 为空"
        # 简单按 category 词过滤 + 全量拼接兜底
        matched = [c for c in chunks if category in c.section or category in c.source]
        subset = matched if matched else chunks
        text = "\n\n".join(f"[{c.source}::{c.section}]\n{c.content}" for c in subset)
        return text[:3000] if len(text) > 3000 else text
    except Exception as e:
        logger.warning("陪练 lookup_reference 失败: category=%s, error=%s", category, e)
        return f"参考资料加载失败: {e}"


def adjust_strategy_impl(
    category_scores: dict[str, list[int]],
    current_difficulty: str,
    turn_count: int,
    max_turns: int,
) -> StrategyUpdate:
    """计算下一题陪练策略（纯函数）。"""
    return compute_strategy_update(category_scores, current_difficulty, turn_count, max_turns)


# ==================== 工具参数 Schemas ====================


class GenerateScenarioArgs(BaseModel):
    category: str = Field(description="考察维度（如 产品咨询/保修/退换货/价格/故障/政策）")
    difficulty: str = Field(description="客户刁钻程度（junior/mid/senior）")
    context: str = Field(default="", description="额外上下文（如上一轮表现摘要）")


class EvaluateAnswerArgs(BaseModel):
    question: str = Field(description="陪练剧本/客户问题文本")
    answer: str = Field(description="主岗的应答")
    category: str = Field(default="通用", description="所属考察维度")


class LookupReferenceArgs(BaseModel):
    category: str = Field(description="考察维度（如 保修/退换货/政策）")


class AdjustStrategyArgs(BaseModel):
    scores_summary: str = Field(description="当前各维度得分摘要（JSON）")


generate_scenario_tool = StructuredTool(
    name="generate_scenario",
    description="按指定考察维度与明显'客户刁钻程度'生成一个陪练剧本（客户的刁钻问题）。",
    args_schema=GenerateScenarioArgs,
)

evaluate_answer_tool = StructuredTool(
    name="evaluate_answer",
    description="即时评估主岗对某剧本的应答质量。",
    args_schema=EvaluateAnswerArgs,
)

lookup_reference_tool = StructuredTool(
    name="lookup_reference",
    description="检索知识包参考资料（产品/保修/退换/价格/政策）。出剧本或评估前了解正确信息时调用。",
    args_schema=LookupReferenceArgs,
)

adjust_strategy_tool = StructuredTool(
    name="adjust_strategy",
    description="根据主岗当前各维度表现，计算下一步陪练策略。",
    args_schema=AdjustStrategyArgs,
)

COACH_TOOLS = [
    generate_scenario_tool,
    evaluate_answer_tool,
    lookup_reference_tool,
    adjust_strategy_tool,
]