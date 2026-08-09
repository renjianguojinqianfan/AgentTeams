"""检索单测：keyword 引擎对 6 类问题的命中验证。"""

from __future__ import annotations

from pathlib import Path

from servevo_rag.knowledge import load_knowledge
from servevo_rag.retrieval import search

KB = Path(__file__).parent.parent.parent / "knowledge" / "product-knowledge" / "v1" / "references"


def _top_source(query: str) -> str:
    chunks = load_knowledge(KB)
    hits = search(chunks, query, top_k=3)
    assert hits, f"无命中: {query}"
    return hits[0].source


def test_warranty_routes_to_warranty_policy():
    assert "warranty" in _top_source("K2 的保修期是多久？")


def test_refund_routes_to_warranty_policy():
    assert "warranty" in _top_source("买错了可以退货吗？")


def test_faq_routes_to_faq():
    assert "faq" in _top_source("机器不出水怎么办？")


def test_products_routes_to_products():
    assert "products" in _top_source("K1 的功率参数是多少？")


def test_model_mention_boosts():
    q = "K2 全自动咖啡机价格"
    chunks = load_knowledge(KB)
    hits = search(chunks, q, top_k=3)
    assert hits and any("K2" in c.content for c in hits)


def test_unknown_question_still_scores_zero():
    chunks = load_knowledge(KB)
    hits = search(chunks, "请帮我写一首诗", top_k=3)
    assert hits == []