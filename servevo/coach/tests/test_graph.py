"""训练图级测试：回归模式（Fake invoker，无网络）端到端。

回归模式不依赖 LLM 出题（预置测试集），只靠 evaluate_answer，便于确定性验证。
"""

from __future__ import annotations

from pathlib import Path

import pytest  # type: ignore

from servevo_coach.graph import CoachGraph
from servevo_coach.tools import AnswerEvaluation
from servevo_eval.structured_output import LLMStructuredInvoker

KB = Path(__file__).parent.parent.parent / "knowledge" / "product-knowledge" / "v1" / "references"


class FakeLlm:
    pass


class FakeInvoker(LLMStructuredInvoker):
    def __init__(self, scores: list[int]) -> None:
        super().__init__(max_attempts=1)
        self.scores = scores
        self.reset()

    def reset(self) -> None:
        self.i = 0

    async def invoke(self, llm, system_prompt, user_prompt, output_model, error_code, error_prefix, log_context):
        s = self.scores[self.i % len(self.scores)]
        self.i += 1
        return AnswerEvaluation(score=s, feedback="ok")


CASES = [
    {"scenario": "K2漏水怎么处理", "category": "故障处理", "answer": "重装水箱，检查密封"},
    {"scenario": "K2不出水怎么办", "category": "故障处理", "answer": "查水位，断电重启，除垢"},
    {"scenario": "K2保修期", "category": "保修", "answer": "查知识库确认"},
]


@pytest.mark.asyncio
async def test_coach_regression_pass():
    graph = CoachGraph(kb_dir=str(KB))
    invoker = FakeInvoker([8, 9, 7])
    report = await graph.run(FakeLlm(), invoker, "reg1", mode="regression", regression_cases=CASES)
    assert report.mode == "regression"
    assert report.regression_total == 3
    assert report.regression_passed == 3
    assert report.total_scenarios == 3
    assert report.overall_score == 8


@pytest.mark.asyncio
async def test_coach_regression_partial_fail():
    graph = CoachGraph(kb_dir=str(KB))
    invoker = FakeInvoker([9, 3, 8])
    report = await graph.run(FakeLlm(), invoker, "reg2", mode="regression", regression_cases=CASES)
    assert report.regression_passed == 2
    assert report.regression_total == 3
    assert report.overall_score == 6  # (9+3+8)/3


@pytest.mark.asyncio
async def test_coach_regression_empty():
    graph = CoachGraph(kb_dir=str(KB))
    invoker = FakeInvoker([])
    report = await graph.run(FakeLlm(), invoker, "reg3", mode="regression", regression_cases=[])
    assert report.regression_total == 0
    assert report.overall_score == 0


@pytest.mark.asyncio
async def test_coach_regression_generates_knowledge_revisions():
    """陪练低分题应产出知识修订草案（进化闭环'陪练→知识修订'环节）。"""
    graph = CoachGraph(kb_dir=str(KB))
    # 一题低分（<4）→ 应产出修订草案
    invoker = FakeInvoker([3, 9, 7])
    report = await graph.run(FakeLlm(), invoker, "reg4", mode="regression", regression_cases=CASES)
    assert report.knowledge_revisions, "低分题应产出知识修订草案"
    rev = report.knowledge_revisions[0]
    assert rev.skill_id == "product-knowledge"
    assert rev.change_type == "UPDATE"
    assert rev.category == "故障处理"
    assert rev.target_section == "faq"
    assert rev.reason
    assert rev.reference and "reg4" in rev.reference


@pytest.mark.asyncio
async def test_coach_regression_all_pass_no_revisions():
    """全高分（>=4）不产出修订草案。"""
    graph = CoachGraph(kb_dir=str(KB))
    invoker = FakeInvoker([8, 9, 7])
    report = await graph.run(FakeLlm(), invoker, "reg5", mode="regression", regression_cases=CASES)
    assert report.knowledge_revisions == []