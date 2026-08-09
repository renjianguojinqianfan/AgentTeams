"""图级测试：质检 e2e（LLM 用 Fake invoker 注入，无网络）。

覆盖：正常批评估 + 汇总、批失败降级（零分兜底 + 缺失证据段）、低置信需人工复核。
"""

from __future__ import annotations

import pytest  # type: ignore

from servevo_eval.entities import QaRecord
from servevo_eval.graph import (
    BatchEvaluationOutput,
    EvaluationGraph,
    QuestionEvaluationOutput,
    SummaryEvaluationOutput,
)
from servevo_eval.structured_output import LLMStructuredInvoker


class FakeLlm:
    """占位 chat_client（图内不直接调用，invoker 已 mock）。"""

    pass


class FakeInvoker(LLMStructuredInvoker):
    """按 prompt 上下文返回固定结构化输出，无网络。"""

    def __init__(self, scores: list[int], confidence: str = "high", fail_batch: bool = False) -> None:
        super().__init__(max_attempts=1)
        self.scores = scores
        self.confidence = confidence
        self.fail_batch = fail_batch
        self.calls: list[str] = []

    async def invoke(self, llm, system_prompt, user_prompt, output_model, error_code, error_prefix, log_context):
        self.calls.append(log_context)
        if "总结" in log_context:
            return SummaryEvaluationOutput(
                overallFeedback="综合：整体服务良好。",
                strengths=["准确性好"],
                improvements=["注意转人工时机"],
            )
        if self.fail_batch:
            raise RuntimeError("LLM 调不通")
        return BatchEvaluationOutput(
            overallScore=sum(self.scores) // len(self.scores) if self.scores else 0,
            overallFeedback="批次良好",
            strengths=["批次优势"],
            improvements=["批次改进"],
            questionEvaluations=[
                QuestionEvaluationOutput(
                    questionIndex=i,
                    score=s,
                    confidence=self.confidence,
                    feedback=f"反馈{i}",
                    referenceAnswer=f"参考{i}",
                    keyPoints=[f"要点{i}"],
                )
                for i, s in enumerate(self.scores)
            ],
        )


def _qa(n: int = 3) -> list[QaRecord]:
    return [
        QaRecord(i, f"客户问题{i}", "保修", f"坐席回答{i}")
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_graph_batch_eval_and_summary():
    graph = EvaluationGraph(invoker=FakeInvoker(scores=[90, 80, 70]))
    report = await graph.evaluate(FakeLlm(), "s1", _qa())
    assert report.total_questions == 3
    assert report.overall_score == 80  # (90+80+70)/3
    assert report.overall_feedback  # 二次汇总
    assert report.strengths and report.improvements
    assert report.missing_evidence == []  # 全部成功且无低置信
    assert report.needs_review_count == 0
    assert report.degraded_reasons == []


@pytest.mark.asyncio
async def test_graph_batch_failure_degrades_to_zero_fill():
    graph = EvaluationGraph(invoker=FakeInvoker(scores=[90], fail_batch=True))
    report = await graph.evaluate(FakeLlm(), "s1", _qa(2))
    # 批次失败 → 逐题补零 + 缺失证据段说明
    assert all(d.score == 0 for d in report.question_details)
    assert report.overall_score == 0
    assert any("批次评分失败" in m for m in report.missing_evidence)
    assert report.degraded_reasons
    assert report.needs_review_count == 2  # 补零标记需人工复核


@pytest.mark.asyncio
async def test_graph_low_confidence_requires_review():
    graph = EvaluationGraph(invoker=FakeInvoker(scores=[70, 60], confidence="low"))
    report = await graph.evaluate(FakeLlm(), "s1", _qa(2))
    assert report.needs_review_count == 2
    assert all(d.needs_review for d in report.question_details)
    # 低置信仍评分（score 保留），但标记需人工复核
    assert report.overall_score == 65


@pytest.mark.asyncio
async def test_graph_empty_records():
    graph = EvaluationGraph(invoker=FakeInvoker(scores=[]))
    report = await graph.evaluate(FakeLlm(), "s1", [])
    assert report.total_questions == 0
    assert report.overall_score == 0