"""回归执行器单测：用 fake LLM + 真实知识包，验证 resolved/passed 判定与指标聚合（无 Docker/网络）。"""

from __future__ import annotations

import pytest  # type: ignore

from servevo_regression.compare import RunMetrics, compare
from servevo_regression.runner import _match_key_points, run_testset
from servevo_regression.testset import TestQuestion, TestSet

KB = r"E:\code\AgentTeams-source\AgentTeams\servevo\knowledge\product-knowledge\v1\references"


class _FakeMsg:
    content: str = ""


class _FakeLLM:
    """fake chat client：返回固定答案（对齐 RagAgentGraph 的 get_chat_client 接口）。"""

    async def get_chat_client(self):
        return self

    async def ainvoke(self, messages):
        m = _FakeMsg()
        m.content = "（测试答案）根据知识库，K2 保修期 1 年。"
        return m


def _ts(ids: list[str]) -> TestSet:
    qs = [
        TestQuestion(id="P01", category="产品", question="K2 价格多少？", answer="¥3299", key_points=["3299"]),
        TestQuestion(id="G01", category="政策", question="保修期延长到多久？", answer="2 年", key_points=["2 年"], gap=True),
    ]
    return TestSet("t", "1", "kb", qs)


@pytest.mark.asyncio
async def test_run_testset_metrics():
    res = await run_testset(_ts(["P01", "G01"]), KB, "v1", llm=_FakeLLM())
    # 有来源且非转人工 → resolved；缺口题知识未同步 → 视检索结果
    assert res.metrics.knowledge_version == "v1"
    assert 0 <= res.metrics.resolution_rate <= 1
    assert res.metrics.qc_avg_score in (40.0, 65.0, 90.0)  # 0/2→40, 1/2→65, 2/2→90


@pytest.mark.asyncio
async def test_run_testset_empty():
    res = await run_testset(TestSet("t", "1", "kb", []), KB, "v1", llm=_FakeLLM())
    assert res.metrics.resolution_rate == 0.0
    assert res.metrics.escalation_rate == 0.0


def test_match_key_points_all_hit():
    assert _match_key_points("K2 保修期 1 年", ["维修", "1 年"]) is False  # 缺"维修"
    assert _match_key_points("K2 保修期 1 年，免费维修", ["维修", "1 年"]) is True
    assert _match_key_points("", ["要点"]) is False
    assert _match_key_points("任意答案", []) is True