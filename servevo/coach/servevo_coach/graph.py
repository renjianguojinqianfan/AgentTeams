"""陪练官 LangGraph Agent：ReAct 循环 + Tool Calling + Working Memory。

迁移自 interview-agent `graphs/adaptive_interview.py`（AGPL-3.0），
会话语境改为客服陪练：主岗应答 vs 刁钻客户剧本。
保留：带回边 StateGraph（真 Agent 循环）、LLM 决策工具调用、结构化 Working Memory、
decision_trace 可审计、HITL interrupt（陪练剧本审批）。
简化：去掉 checkpointer/streaming/vector 依赖（servevo 红线），工具执行串行。

流程：
START -> init_context -> agent_loop <-> [execute_tool -> merge_tool_results] (循环)
agent_loop -> finalize -> END (Agent 决定结束)
"""

from __future__ import annotations

import asyncio
import json
import logging
import operator
import time
from typing import Annotated, Any, TypedDict, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.errors import GraphInterrupt
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from servevo_eval.errors import ErrorCode
from servevo_eval.structured_output import LLMStructuredInvoker

from .entities import CoachReport, KnowledgeRevision, ScenarioRecord
from .strategy import should_end_session
from .tools import (
    COACH_TOOLS,
    CoachToolContext,
    adjust_strategy_impl,
    evaluate_answer_impl,
    generate_scenario_impl,
    lookup_reference_impl,
)

logger = logging.getLogger(__name__)

_END_SIGNAL = "END_COACH"
_MAX_AGENT_STEPS = 30
_TOOL_TIMEOUT_SECONDS = 60


def _mock_main_agent(scenario: str, category: str) -> str:
    """确定性 mock 主岗应答器（四准则：与真实 Worker 同签名，供 host 侧闭环验证）。

    真实接入时注入 async main_agent(scenario, category) -> str 桥接 Worker/rag。
    """
    return (
        f"您好，关于 [{category}] 的问题，我为您核实一下：{scenario[:40]}。"
        "根据知识库，建议先按故障处理步骤检查；若仍无法解决会为您转人工登记。"
    )


class _State(TypedDict, total=False):
    """陪练 Agent 状态（Working Memory）。"""

    session_id: str
    mode: str                # coach | regression
    skill_id: str
    difficulty: str
    max_turns: int
    session_context: str

    qa_history: list[dict[str, Any]]
    category_scores: dict[str, list[int]]
    turn_count: int
    current_question: str | None
    current_category: str | None

    messages: list[BaseMessage]
    agent_step_count: int
    finished: bool

    final_report: CoachReport | None
    decision_trace: list[dict[str, Any]]

    pending_approval: dict[str, Any] | None

    # 回归模式输入（预置测试集）
    regression_cases: list[dict[str, Any]] | None
    regression_index: int


_CONFIG_CHAT_CLIENT = "chat_client"
_CONFIG_INVOKER = "invoker"
_CONFIG_CTX = "ctx"


class CoachGraph:
    """陪练官 Agent：编译一次，多会话复用。"""

    def __init__(self, kb_dir: str, skill_id: str = "product-knowledge", approval_mode: bool = False,
                 main_agent: Any | None = None) -> None:
        self._kb_dir = kb_dir
        self._skill_id = skill_id
        self._approval_mode = approval_mode
        # 主岗应答器（可注入真实 Worker 桥接；缺省用确定性 mock，满足四准则"mock 与真实工具同 Schema"）
        self._main_agent = main_agent or _mock_main_agent
        self._compiled = self._build()

    async def run(
        self,
        chat_client: ChatOpenAI,
        invoker: LLMStructuredInvoker,
        session_id: str,
        mode: str = "coach",
        session_context: str = "",
        difficulty: str = "mid",
        max_turns: int = 6,
        regression_cases: list[dict[str, Any]] | None = None,
    ) -> CoachReport:
        """执行一轮完整陪练/回归，返回报告。"""
        configurable: dict[str, Any] = {
            _CONFIG_CHAT_CLIENT: chat_client,
            _CONFIG_INVOKER: invoker,
            _CONFIG_CTX: CoachToolContext(
                chat_client=chat_client,
                invoker=invoker,
                kb_dir=self._kb_dir,
                skill_id=self._skill_id,
                session_context=session_context,
            ),
        }
        config: RunnableConfig = {"configurable": configurable}
        initial: _State = {
            "session_id": session_id,
            "mode": mode,
            "skill_id": self._skill_id,
            "difficulty": difficulty,
            "max_turns": max_turns,
            "session_context": session_context,
            "qa_history": [],
            "category_scores": {},
            "turn_count": 0,
            "messages": [],
            "agent_step_count": 0,
            "finished": False,
            "decision_trace": [],
            "pending_approval": None,
            "regression_cases": regression_cases,
            "regression_index": 0,
        }
        result = await self._compiled.ainvoke(initial, config=config)
        result = self._apply_interrupt_if_any(result)
        report = result.get("final_report")
        if report is None:
            raise RuntimeError(f"陪练子图未产出报告: sessionId={session_id}")
        return report

    def _apply_interrupt_if_any(self, result: dict[str, Any]) -> dict[str, Any]:
        """非流式路径识别 interrupt()。"""
        state = dict(result)
        interrupts = result.get("__interrupt__") if isinstance(result, dict) else None
        if interrupts:
            state["pending_approval"] = interrupts[0].value
            state.pop("__interrupt__", None)
        else:
            state["pending_approval"] = None
        return state

    def _build(self) -> Any:
        builder: StateGraph[_State] = StateGraph(_State)
        builder.add_node("init_context", self._init_context)
        builder.add_node("agent_loop", self._agent_loop)
        builder.add_node("execute_tool", self._execute_tool)
        builder.add_node("merge_tool_results", self._merge_tool_results)
        builder.add_node("finalize", self._finalize)

        builder.add_edge(START, "init_context")
        builder.add_edge("init_context", "agent_loop")
        builder.add_conditional_edges("agent_loop", self._route_agent_output)
        builder.add_edge("execute_tool", "merge_tool_results")
        builder.add_edge("merge_tool_results", "agent_loop")  # 回边：循环
        builder.add_edge("finalize", END)
        return builder.compile()

    # ==================== 节点 ====================

    async def _init_context(self, state: _State, config: RunnableConfig) -> dict[str, Any]:
        mode = state.get("mode", "coach")
        max_turns = state.get("max_turns", 6)
        difficulty = state.get("difficulty", "mid")
        session_context = state.get("session_context", "")
        category_scores = state.get("category_scores", {})

        scores_summary = json.dumps(
            {k: f"avg={sum(v) / len(v):.1f}, count={len(v)}" for k, v in category_scores.items()}
            if category_scores
            else {"无数据": "尚未开始"},
            ensure_ascii=False,
        )
        ctx_summary = session_context[:500] + "..." if len(session_context) > 500 else (session_context or "无")

        if mode == "regression":
            system_content = (
                "你是陪练官（回归模式）。目标：按预置测试集逐题回归复测主岗应答，"
                "评估是否通过（score>=7 视为通过）。调用 evaluate_answer 评估已给出的应答，"
                "全部评完输出 END_COACH。不要出题。"
            )
        else:
            system_content = f"""你是资深客服陪练官。根据主岗实时表现，自主决定每轮陪练行动。

当前陪练上下文：
- 技能方向：{self._skill_id}
- 当前客户刁钻程度：{difficulty}
- 已完成题数：{state.get("turn_count", 0)}/{max_turns}
- 各维度得分：{scores_summary}
- 会话上下文：{ctx_summary}

你可以调用工具：generate_scenario, evaluate_answer, lookup_reference, adjust_strategy。
当陪练应该结束时，回复文本 "END_COACH"（不调用工具）。
如果还没有出第一题，请先调用 generate_scenario 出一个刁钻客户的陪练剧本。"""

        messages = state.get("messages", [])
        if not messages:
            messages = [SystemMessage(content=system_content)]
        else:
            messages = [SystemMessage(content=system_content)] + [
                m for m in messages if not isinstance(m, SystemMessage)
            ]

        return {
            "messages": messages,
            "agent_step_count": 0,
            "finished": False,
            "decision_trace": [
                {
                    "step": 0,
                    "action": "init_context",
                    "args": {"mode": mode, "difficulty": difficulty, "max_turns": max_turns},
                    "result": {},
                    "duration_ms": 0,
                }
            ],
        }

    async def _agent_loop(self, state: _State, config: RunnableConfig) -> dict[str, Any]:
        chat_client: ChatOpenAI = config["configurable"][_CONFIG_CHAT_CLIENT]
        messages = state.get("messages", [])
        step_count = state.get("agent_step_count", 0)

        if step_count >= _MAX_AGENT_STEPS:
            logger.warning("Agent 步数达上限 %d，强制结束", _MAX_AGENT_STEPS)
            return {"finished": True}

        # 回归模式：逐题处理预置测试集，不靠 LLM 出题
        mode = state.get("mode", "coach")
        if mode == "regression":
            cases = state.get("regression_cases") or []
            idx = state.get("regression_index", 0)
            if idx >= len(cases):
                return {"finished": True}
            case = cases[idx]
            scenario = case.get("scenario", case.get("question", ""))
            answer = case.get("answer", "")
            category = case.get("category", "通用")
            # 构造 evaluate_answer 工具调用，走 execute_tool 分发
            ai = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "evaluate_answer",
                        "args": {"question": scenario, "answer": answer, "category": category},
                        "id": f"reg-{idx}",
                        "type": "tool_call",
                    }
                ],
            )
            return {
                "messages": list(messages) + [ai],
                "current_question": scenario,
                "current_category": category,
                "regression_index": idx + 1,
                "finished": False,
            }

        if should_end_session(
            state.get("turn_count", 0),
            state.get("max_turns", 6),
            state.get("category_scores", {}),
        ):
            return {"finished": True}

        # coach 模式确定性编排：已有待评估剧本 → 自动 evaluate_answer（主岗应答用注入的 main_agent）
        if mode == "coach" and state.get("current_question"):
            pending = state.get("current_question", "")
            category = state.get("current_category", "通用")
            try:
                answer = self._main_agent(pending, category) if self._main_agent else ""
            except Exception as e:
                logger.warning("主岗应答生成失败: %s", e)
                answer = ""
            ai = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "evaluate_answer",
                        "args": {"question": pending, "answer": answer, "category": category},
                        "id": f"coach-eval-{step_count}",
                        "type": "tool_call",
                    }
                ],
            )
            return {
                "messages": list(messages) + [ai],
                "finished": False,
            }

        llm_with_tools = chat_client.bind_tools(COACH_TOOLS)
        try:
            response: AIMessage = await asyncio.wait_for(
                llm_with_tools.ainvoke(messages),
                timeout=_TOOL_TIMEOUT_SECONDS,
            )
        except (TimeoutError, Exception):
            logger.warning("陪练 Agent LLM 决策失败/超时，强制结束")
            return {"finished": True}

        new_messages = list(messages) + [response]
        trace = list(state.get("decision_trace", []))
        tool_calls_info = (
            [{"name": tc["name"], "args": tc["args"]} for tc in response.tool_calls]
            if response.tool_calls
            else []
        )
        trace_entry = {
            "step": step_count + 1,
            "action": "agent_loop",
            "args": {"tool_calls": tool_calls_info},
            "result": {},
            "duration_ms": 0,
        }

        content = response.content if isinstance(response.content, str) else ""
        if _END_SIGNAL in content:
            return {"messages": new_messages, "finished": True, "decision_trace": trace + [{**trace_entry, "result": {"signal": "END_COACH"}}]}
        if not response.tool_calls:
            return {"messages": new_messages, "finished": True, "decision_trace": trace + [{**trace_entry, "result": {"signal": "no_tool_calls"}}]}

        return {"messages": new_messages, "agent_step_count": step_count + 1, "decision_trace": trace + [trace_entry]}

    async def _execute_tool(self, state: _State, config: RunnableConfig) -> dict[str, Any]:
        ctx: CoachToolContext = config["configurable"][_CONFIG_CTX]
        messages = state.get("messages", [])
        last_ai = messages[-1] if messages and isinstance(messages[-1], AIMessage) else None
        if not last_ai or not last_ai.tool_calls:
            return {"messages": list(messages), "tool_result": ""}

        tool_call = last_ai.tool_calls[0]
        tool_name = tool_call["name"]
        tool_args = tool_call.get("args", {})
        tool_id = tool_call.get("id", "")

        t0 = time.monotonic()
        try:
            result = await self._dispatch_tool(tool_name, tool_args, ctx, state)
            duration_ms = int((time.monotonic() - t0) * 1000)
            tool_message = ToolMessage(content=str(result), tool_call_id=tool_id, name=tool_name)
            side_effect = self._apply_tool_side_effects(tool_name, tool_args, result, state)
            trace = list(state.get("decision_trace", []))
            trace.append({
                "step": state.get("agent_step_count", 0),
                "action": tool_name,
                "args": tool_args,
                "result": str(result)[:200],
                "duration_ms": duration_ms,
            })
            return {
                "messages": list(messages) + [tool_message],
                "tool_result": str(result),
                "decision_trace": trace,
                **side_effect,
            }
        except GraphInterrupt:
            raise
        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.warning("陪练工具执行失败: tool=%s, error=%s", tool_name, e)
            tool_message = ToolMessage(content=f"工具执行失败: {e}", tool_call_id=tool_id, name=tool_name)
            return {"messages": list(messages) + [tool_message], "tool_result": f"error: {e}"}

    async def _merge_tool_results(self, state: _State, config: RunnableConfig) -> dict[str, Any]:
        # 简化：工具结果已通过 _execute_tool 写回 messages/side_effect，无需额外合并
        return {}

    async def _finalize(self, state: _State, config: RunnableConfig) -> dict[str, Any]:
        qa_history = state.get("qa_history", [])
        category_scores = state.get("category_scores", {})
        mode = state.get("mode", "coach")

        all_scores = [q["score"] for q in qa_history if q.get("score") is not None]
        overall_score = int(sum(s for s in all_scores if s is not None) / len(all_scores)) if all_scores else 0

        scenarios = [
            ScenarioRecord(
                scenario_index=q.get("scenario_index", i),
                scenario=q.get("scenario", q.get("question", "")),
                category=q.get("category", "通用"),
                difficulty=q.get("difficulty", "mid"),
                agent_answer=q.get("agent_answer"),
                score=q.get("score"),
                feedback=q.get("feedback"),
                key_points=list(q.get("key_points", [])),
            )
            for i, q in enumerate(qa_history)
        ]

        # 回归模式统计
        regression_passed = sum(1 for q in qa_history if (q.get("score") or 0) >= 7) if mode == "regression" else 0
        regression_total = len(qa_history) if mode == "regression" else 0

        report = CoachReport(
            session_id=state.get("session_id", ""),
            mode=mode,
            total_scenarios=len(qa_history),
            overall_score=overall_score,
            scenarios=scenarios,
            strengths=[],
            improvements=[],
            knowledge_revisions=[],
            decision_trace=list(state.get("decision_trace", [])),
            regression_passed=regression_passed,
            regression_total=regression_total,
            degraded_reasons=[],
        )
        return {"final_report": report, "finished": True}

    # ==================== 路由 ====================

    def _route_agent_output(self, state: _State) -> str:
        if state.get("finished"):
            return "finalize"
        messages = state.get("messages", [])
        if messages and isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
            return "execute_tool"
        return "finalize"

    # ==================== 工具调度 ====================

    async def _dispatch_tool(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        ctx: CoachToolContext,
        state: _State,
    ) -> str:
        if tool_name == "generate_scenario":
            result = await generate_scenario_impl(
                category=tool_args.get("category", "通用"),
                difficulty=tool_args.get("difficulty", state.get("difficulty", "mid")),
                context=tool_args.get("context", ""),
                tool_ctx=ctx,
            )
            scenario = result.scenario
            # HITL：剧本出题后暂停审批（approval_mode 开启才 interrupt）
            if self._approval_mode:
                approval = interrupt(
                    {
                        "scenario": scenario,
                        "category": result.category,
                        "type": "generate_scenario_approval",
                        "prompt": "这个陪练剧本是否合适？",
                    }
                )
                if isinstance(approval, dict) and approval.get("approved") is False:
                    logger.info("陪练剧本被驳回，重新生成")
                    result2 = await generate_scenario_impl(
                        category=tool_args.get("category", "通用"),
                        difficulty=tool_args.get("difficulty", state.get("difficulty", "mid")),
                        context=tool_args.get("context", "") + "\n注意：上一剧本被驳回，请换一个刁钻角度。",
                        tool_ctx=ctx,
                    )
                    scenario = result2.scenario
            return json.dumps(
                {"scenario": scenario, "type": result.type, "category": result.category},
                ensure_ascii=False,
            )

        if tool_name == "evaluate_answer":
            answer = tool_args.get("answer", "")
            question = tool_args.get("question", "")
            category = tool_args.get("category", "通用")
            # coach 模式：主岗应答缺省时用注入的 main_agent 生成（真实接入即 Worker 应答）
            if not answer and self._main_agent is not None:
                try:
                    answer = self._main_agent(question or state.get("current_question", ""), category)
                except Exception as e:
                    logger.warning("主岗应答生成失败，评估空应答: %s", e)
            eval_result = await evaluate_answer_impl(
                question=question or state.get("current_question", ""),
                answer=answer,
                category=category,
                tool_ctx=ctx,
            )
            return json.dumps(
                {
                    "score": eval_result.score,
                    "feedback": eval_result.feedback,
                    "shouldFollowUp": eval_result.shouldFollowUp,
                    "followUpSuggestion": eval_result.followUpSuggestion,
                },
                ensure_ascii=False,
            )

        if tool_name == "lookup_reference":
            return await lookup_reference_impl(category=tool_args.get("category", ""), tool_ctx=ctx)

        if tool_name == "adjust_strategy":
            strategy = adjust_strategy_impl(
                category_scores=state.get("category_scores", {}),
                current_difficulty=state.get("difficulty", "mid"),
                turn_count=state.get("turn_count", 0),
                max_turns=state.get("max_turns", 6),
            )
            return json.dumps(
                {
                    "suggested_difficulty": strategy.suggested_difficulty,
                    "suggested_category": strategy.suggested_category,
                    "reason": strategy.reason,
                },
                ensure_ascii=False,
            )

        return f"未知工具: {tool_name}"

    def _apply_tool_side_effects(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        result: str,
        state: _State,
    ) -> dict[str, Any]:
        effects: dict[str, Any] = {}

        if tool_name == "generate_scenario":
            try:
                parsed = json.loads(result)
                effects["current_question"] = parsed.get("scenario", "")
                effects["current_category"] = parsed.get("category", "通用")
                # coach 模式：追加一条待评分记录（evaluate_answer 会回填 score/feedback）
                if state.get("mode") != "regression":
                    qa_history = list(state.get("qa_history", []))
                    qa_history.append({
                        "scenario_index": len(qa_history),
                        "scenario": parsed.get("scenario", ""),
                        "category": parsed.get("category", "通用"),
                        "difficulty": state.get("difficulty", "mid"),
                        "agent_answer": None,
                        "score": None,
                        "feedback": None,
                    })
                    effects["qa_history"] = qa_history
            except (json.JSONDecodeError, TypeError):
                pass

        elif tool_name == "evaluate_answer":
            try:
                parsed = json.loads(result)
                score = parsed.get("score", 0)
                feedback = parsed.get("feedback", "")
                category = state.get("current_category") or tool_args.get("category", "通用")
                qa_history = list(state.get("qa_history", []))
                # 回归模式：用预置/传入 case 补全 history 记录
                if state.get("mode") == "regression":
                    qa_history.append({
                        "scenario_index": len(qa_history),
                        "scenario": state.get("current_question", ""),
                        "category": category,
                        "difficulty": state.get("difficulty", "mid"),
                        "agent_answer": tool_args.get("answer", ""),
                        "score": score,
                        "feedback": feedback,
                    })
                else:
                    if qa_history:
                        last = dict(qa_history[-1])
                        last["agent_answer"] = tool_args.get("answer", "")
                        last["score"] = score
                        last["feedback"] = feedback
                        qa_history[-1] = last
                effects["qa_history"] = qa_history
                effects["turn_count"] = state.get("turn_count", 0) + 1
                cat_scores = {c: list(s) for c, s in state.get("category_scores", {}).items()}
                cat_scores.setdefault(category, []).append(score)
                effects["category_scores"] = cat_scores
                # 该剧本已评估，清除待评估标记，让 LLM 决定下一题
                effects["current_question"] = None
                effects["pending_evaluated"] = True
            except (json.JSONDecodeError, TypeError):
                pass

        elif tool_name == "adjust_strategy":
            try:
                parsed = json.loads(result)
                new_diff = parsed.get("suggested_difficulty")
                if new_diff and new_diff != state.get("difficulty"):
                    effects["difficulty"] = new_diff
            except (json.JSONDecodeError, TypeError):
                pass

        return effects