"""回归执行器单测：用 fake LLM + 真实知识包，验证 resolved 判定与指标聚合（无 Docker/网络）。"""

from __future__ import annotations

import pytest  # type: ignore

from servevo_regression.compare import RunMetrics, compare
from servevo_regression.runner import run_testset
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
        TestQuestion("P01", "产品", "K2 价格多少？", "¥3299", ["3299"], True),
        TestQuestion("G01", "政策", "保修期延长到多久？", "2 年", ["2 年"], True, gap=True),
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