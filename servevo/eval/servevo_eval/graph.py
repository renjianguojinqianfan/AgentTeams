"""质检评估 LangGraph 子图：分批评估 + 并发限流 + 二次汇总 + 两级降级。

迁移自 interview-agent `graphs/evaluation.py`（AGPL-3.0），语义改为客服质检：
- 维度改为质检 rubric（prompts/*.st）
- 输出模型含 confidence（low → 只标注不评分 + needs_review 需人工复核）
- 报告含 missing_evidence 段（确定性聚合 + degraded_reasons）

流程：prepare(截断+分批) -> Send fan-out evaluate_batch(Semaphore 限流，失败降级)
-> merge(纯函数合并) -> summarize(二次汇总，失败降级) -> build_report(纯函数组装)。
"""

from __future__ import annotations

import asyncio
import logging
import operator
from typing import Annotated, Any, TypedDict, cast

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field

from .entities import (
    BatchReport,
    BatchResult,
    EvaluationReport,
    QaBatch,
    QaRecord,
    QuestionEvaluationItem,
    Summary,
)
from .errors import ErrorCode
from .prompt_loader import load_prompt
from .service import (
    EVALUATION_BATCH_SIZE,
    MAX_MERGED_LIST_ITEMS,
    build_category_summary,
    build_qa_records_text,
    build_question_highlights,
    build_report,
    merge_list_items,
    merge_overall_feedback,
    merge_question_evaluations,
    split_batches,
    truncate_context,
    truncate_reference,
)
from .structured_output import LLMStructuredInvoker

logger = logging.getLogger(__name__)


class QuestionEvaluationOutput(BaseModel):
    """LLM 单题质检输出。

    score 核心必填；其余字段 qwen 系常缺省，可选化避免单字段缺失放大为整批零分。
    confidence: high/medium/low。low 时下游"只标注不评分"并标记需人工复核。
    questionIndex 缺失以 -1 标记，由 _to_batch_report 按批内位置回填。
    """

    questionIndex: int = -1
    score: int
    confidence: str = "high"
    feedback: str = ""
    referenceAnswer: str = ""
    keyPoints: list[str] = Field(default_factory=list)


class BatchEvaluationOutput(BaseModel):
    """LLM 批次质检输出。

    overallScore 下游无消费者（总分由逐题分数重算），容许 float 并在
    _to_batch_report 取整，避免 LLM 输出小数导致整批校验失败而误降级。
    """

    overallScore: int | float = 0
    overallFeedback: str = ""
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    questionEvaluations: list[QuestionEvaluationOutput] = Field(default_factory=list)


class SummaryEvaluationOutput(BaseModel):
    """LLM 二次汇总输出。"""

    overallFeedback: str = ""
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)


class _EvaluationState(TypedDict, total=False):
    """子图状态。batch_results 用 Annotated add 累积各批结果。"""

    session_id: str
    qa_records: list[QaRecord]
    context_text: str
    reference_context: str
    batches: list[QaBatch]
    batch: QaBatch
    batch_results: Annotated[list[BatchResult], operator.add]
    batch_errors: Annotated[list[str], operator.add]
    merged_evaluations: list[QuestionEvaluationItem]
    fallback_summary: Summary
    summary: Summary
    report: EvaluationReport


_CONFIG_CHAT_CLIENT = "chat_client"
_CONFIG_SEMAPHORE = "semaphore"


class EvaluationGraph:
    """统一质检子图：编译一次，多次调用。

    chat_client 与 semaphore 通过 RunnableConfig.configurable 传入（不进 state）。
    """

    def __init__(
        self,
        invoker: LLMStructuredInvoker,
        batch_size: int = EVALUATION_BATCH_SIZE,
        semaphore_limit: int = 3,
        batch_system_prompt: str = "qc-evaluation-system",
        batch_user_prompt: str = "qc-evaluation-user",
        summary_system_prompt: str = "qc-evaluation-summary-system",
        summary_user_prompt: str = "qc-evaluation-summary-user",
    ) -> None:
        self._invoker = invoker
        self._batch_size = batch_size
        self._semaphore_limit = max(1, semaphore_limit)
        self._batch_system_prompt = batch_system_prompt
        self._batch_user_prompt = batch_user_prompt
        self._summary_system_prompt = summary_system_prompt
        self._summary_user_prompt = summary_user_prompt
        self._compiled = self._build()

    async def evaluate(
        self,
        chat_client: ChatOpenAI,
        session_id: str,
        qa_records: list[QaRecord],
        context_text: str | None = None,
        reference_context: str | None = None,
    ) -> EvaluationReport:
        """执行质检子图，返回最终报告。"""
        semaphore = asyncio.Semaphore(self._semaphore_limit)
        config: RunnableConfig = {
            "configurable": {
                _CONFIG_CHAT_CLIENT: chat_client,
                _CONFIG_SEMAPHORE: semaphore,
            }
        }
        initial: _EvaluationState = {
            "session_id": session_id,
            "qa_records": qa_records,
            "context_text": context_text or "",
            "reference_context": reference_context or "",
            "batch_results": [],
            "batch_errors": [],
        }
        result = await self._compiled.ainvoke(initial, config=config)
        report = cast("EvaluationReport | None", result.get("report"))
        if report is None:
            raise RuntimeError(f"质检子图未产出报告: sessionId={session_id}")
        return report

    def _build(self) -> Any:
        builder = StateGraph(_EvaluationState)
        builder.add_node("prepare", self._prepare)
        builder.add_node("evaluate_batch", self._evaluate_batch)
        builder.add_node("merge", self._merge)
        builder.add_node("summarize", self._summarize)
        builder.add_node("build_report", self._build_report_node)
        builder.add_edge(START, "prepare")
        builder.add_conditional_edges("prepare", self._route_batches)
        builder.add_edge("evaluate_batch", "merge")
        builder.add_edge("merge", "summarize")
        builder.add_edge("summarize", "build_report")
        builder.add_edge("build_report", END)
        return builder.compile()

    async def _prepare(self, state: _EvaluationState, config: RunnableConfig) -> dict[str, Any]:
        qa_records = state.get("qa_records", [])
        batches = split_batches(qa_records, batch_size=self._batch_size)
        return {
            "context_text": truncate_context(state.get("context_text")),
            "reference_context": truncate_reference(state.get("reference_context")),
            "batches": batches,
        }

    def _route_batches(self, state: _EvaluationState) -> list[Send] | str:
        batches = state.get("batches", [])
        if not batches:
            return "merge"
        context_text = state.get("context_text", "")
        reference_context = state.get("reference_context", "")
        return [
            Send(
                "evaluate_batch",
                {
                    "batch": batch,
                    "context_text": context_text,
                    "reference_context": reference_context,
                },
            )
            for batch in batches
        ]

    async def _evaluate_batch(self, state: _EvaluationState, config: RunnableConfig) -> dict[str, Any]:
        batch = state["batch"]
        context_text = state.get("context_text", "")
        reference_context = state.get("reference_context", "")
        chat_client = config["configurable"][_CONFIG_CHAT_CLIENT]
        semaphore: asyncio.Semaphore = config["configurable"][_CONFIG_SEMAPHORE]
        output: BatchEvaluationOutput | None = None

        try:
            system_tpl = await load_prompt(self._batch_system_prompt)
            user_tpl = await load_prompt(self._batch_user_prompt)
            system_prompt = system_tpl.format()
            user_prompt = user_tpl.format(
                contextText=context_text,
                qaRecords=build_qa_records_text(batch.records),
                referenceContext=reference_context if reference_context else "无",
            )
            async with semaphore:
                output = await self._invoker.invoke(
                    llm=chat_client,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_model=BatchEvaluationOutput,
                    error_code=ErrorCode.QC_EVALUATION_FAILED,
                    error_prefix="批次质检失败：",
                    log_context="批次质检",
                )
            logger.debug(
                "LLM 质检结果 batch [%d, %d): %d evaluations, scores=%s",
                batch.start_index,
                batch.end_index,
                len(output.questionEvaluations),
                [e.score for e in output.questionEvaluations],
            )
            if not output.questionEvaluations:
                logger.warning(
                    "LLM 返回空 questionEvaluations (batch [%d, %d))，重试一次",
                    batch.start_index,
                    batch.end_index,
                )
                async with semaphore:
                    output = await self._invoker.invoke(
                        llm=chat_client,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        output_model=BatchEvaluationOutput,
                        error_code=ErrorCode.QC_EVALUATION_FAILED,
                        error_prefix="批次质检失败（重试）：",
                        log_context="批次质检重试",
                    )
                if not output.questionEvaluations:
                    raise ValueError(
                        f"LLM 重试后仍返回空 questionEvaluations (batch [{batch.start_index}, {batch.end_index}))"
                    )
            report = self._to_batch_report(output, start_index=batch.start_index)
        except Exception as e:
            logger.warning(
                "批次质检失败，零分兜底: start=%s, end=%s, error=%s",
                batch.start_index,
                batch.end_index,
                e,
            )
            return {
                "batch_results": [BatchResult(batch.start_index, batch.end_index, None)],
                "batch_errors": [f"批次[{batch.start_index},{batch.end_index}): {e}"],
            }

        return {"batch_results": [BatchResult(batch.start_index, batch.end_index, report)]}

    async def _merge(self, state: _EvaluationState, config: RunnableConfig) -> dict[str, Any]:
        batch_results = state.get("batch_results", [])
        return {
            "merged_evaluations": merge_question_evaluations(batch_results),
            "fallback_summary": Summary(
                overall_feedback=merge_overall_feedback(batch_results),
                strengths=merge_list_items(batch_results, strengths_mode=True),
                improvements=merge_list_items(batch_results, strengths_mode=False),
            ),
        }

    async def _summarize(self, state: _EvaluationState, config: RunnableConfig) -> dict[str, Any]:
        qa_records = state.get("qa_records", [])
        merged_evaluations = state.get("merged_evaluations", [])
        fallback = state.get("fallback_summary", Summary.empty())

        if not qa_records:
            return {"summary": fallback}

        chat_client = config["configurable"][_CONFIG_CHAT_CLIENT]
        try:
            system_tpl = await load_prompt(self._summary_system_prompt)
            user_tpl = await load_prompt(self._summary_user_prompt)
            system_prompt = system_tpl.format()
            user_prompt = user_tpl.format(
                contextText=state.get("context_text", ""),
                referenceContext=state.get("reference_context", "") or "无",
                categorySummary=build_category_summary(qa_records, merged_evaluations),
                questionHighlights=build_question_highlights(qa_records, merged_evaluations),
                fallbackOverallFeedback=fallback.overall_feedback,
                fallbackStrengths="\n".join(fallback.strengths),
                fallbackImprovements="\n".join(fallback.improvements),
            )
            output: SummaryEvaluationOutput = await self._invoker.invoke(
                llm=chat_client,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_model=SummaryEvaluationOutput,
                error_code=ErrorCode.QC_EVALUATION_FAILED,
                error_prefix="总结质检失败：",
                log_context="总结质检",
            )
            summary = self._to_summary(output, fallback)
        except Exception as e:
            logger.warning("二次汇总失败，降级到批次聚合结果: error=%s", e)
            summary = fallback

        return {"summary": summary}

    async def _build_report_node(self, state: _EvaluationState, config: RunnableConfig) -> dict[str, Any]:
        report = build_report(
            session_id=state.get("session_id", ""),
            qa_records=state.get("qa_records", []),
            evaluations=state.get("merged_evaluations", []),
            summary=state.get("summary", Summary.empty()),
            degraded_reasons=state.get("batch_errors", []),
        )
        return {"report": report}

    def _to_batch_report(self, output: BatchEvaluationOutput, start_index: int) -> BatchReport:
        return BatchReport(
            overall_score=int(round(float(output.overallScore))),
            overall_feedback=output.overallFeedback,
            strengths=list(output.strengths),
            improvements=list(output.improvements),
            question_evaluations=[
                QuestionEvaluationItem(
                    question_index=start_index + i,
                    score=e.score,
                    confidence=e.confidence if e.confidence in ("high", "medium", "low") else "high",
                    needs_review=(e.confidence == "low"),
                    feedback=e.feedback,
                    reference_answer=e.referenceAnswer,
                    key_points=list(e.keyPoints),
                )
                for i, e in enumerate(output.questionEvaluations)
            ],
        )

    def _to_summary(self, output: SummaryEvaluationOutput, fallback: Summary) -> Summary:
        feedback = (
            output.overallFeedback
            if output.overallFeedback and output.overallFeedback.strip()
            else fallback.overall_feedback
        )
        strengths = self._sanitize_items(output.strengths, fallback.strengths)
        improvements = self._sanitize_items(output.improvements, fallback.improvements)
        return Summary(overall_feedback=feedback, strengths=strengths, improvements=improvements)

    @staticmethod
    def _sanitize_items(primary: list[str], fallback: list[str]) -> list[str]:
        source = primary if primary else fallback
        seen: set[str] = set()
        result: list[str] = []
        for item in source:
            if not item or not item.strip():
                continue
            cleaned = item.strip()
            if cleaned not in seen:
                seen.add(cleaned)
                result.append(cleaned)
        return result[:MAX_MERGED_LIST_ITEMS]