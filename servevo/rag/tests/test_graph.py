"""图级测试：质量循环 e2e（LLM 用 fake 注入）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest  # type: ignore

from servevo_rag.graph import RagAgentGraph

KB = Path(__file__).parent.parent.parent / "knowledge" / "product-knowledge" / "v1" / "references"


class _FakeAIMessage:
    content: str = ""


class FakeLlm:
    """无网络 fake：记录调用，返回固定文本（对齐 LlmClient 接口）。"""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_chat_client(self) -> "FakeLlm":
        return self

    async def ainvoke(self, messages: list[Any]) -> _FakeAIMessage:
        human = [m for m in messages if m.type == "human"][0].content
        self.calls.append(human)
        msg = _FakeAIMessage()
        if "检索效果不好" in human:
            # 改写失败 → 返回无意义查询，模拟检索仍无命中（确定性降级路径）
            msg.content = "xyzabc"
            return msg
        msg.content = f"（fake 回答）针对: {human[:60]}"
        return msg


@pytest.mark.asyncio
async def test_graph_simple_answer():
    graph = RagAgentGraph(kb_dir=str(KB), llm=FakeLlm())
    result = await graph.query("K2 的保修期是多久？")
    assert result["answer"]
    assert result["sources"]
    assert result["retrieval_trace"]


@pytest.mark.asyncio
async def test_graph_unknown_returns_honest_refusal():
    graph = RagAgentGraph(kb_dir=str(KB), llm=FakeLlm())
    result = await graph.query("请帮我写一首诗")
    assert "未找到" in result["answer"] or "转人工" in result["answer"]
    assert result["sources"] == []


@pytest.mark.asyncio
async def test_graph_unknown_exposes_missing_evidence():
    """P3.1 齐全缺口（SP1）：未命中必须显式声明缺失证据段。"""
    graph = RagAgentGraph(kb_dir=str(KB), llm=FakeLlm())
    result = await graph.query("量子力学与相对论的统一理论是什么")
    assert result["missing_evidence"], "未命中应产生缺失证据段"


@pytest.mark.asyncio
async def test_graph_low_overlap_returns_no_sources_on_exhaustion():
    """P3.1 质量门（SP3/SP2）：弱命中反复改写后仍不足 → 转人工兜底，不给来源。"""
    graph = RagAgentGraph(kb_dir=str(KB), llm=FakeLlm())
    # 与知识库关键词重叠极低的问题，稳定触发低质量 + 重试耗尽
    result = await graph.query("我的K2咖啡机会不会影响我的风水")
    # 要么有命中且作答，要么转人工且无来源；不得基于弱结果硬答出未知信息
    if not result["sources"]:
        assert "转人工" in result["answer"] or "确证" in result["answer"]
    assert "missing_evidence" in result