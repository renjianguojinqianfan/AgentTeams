"""keyword 检索：中英混合分词 + BM25 简化计分 + 标题/路由加权。

零依赖（纯标准库）；分数归一化到 [0,1] 供 RAG 图质量阈值使用。
"""

from __future__ import annotations

import math
import re
from collections import Counter

from .knowledge import KnowledgeChunk

_STOPWORDS = {
    "了", "的", "是", "我", "你", "啊", "呢", "吗", "请问", "什么", "怎么", "一个",
    "一下", "多久", "多少", "这个", "那个", "我们", "你们", "一下",
}
_ROUTE_TERMS: dict[str, str] = {
    "保修": "warranty-policy",
    "质保": "warranty-policy",
    "退货": "warranty-policy",
    "退款": "warranty-policy",
    "换货": "warranty-policy",
    "故障": "faq",
    "维修": "faq",
    "参数": "products",
    "型号": "products",
    "规格": "products",
    "咖啡机": "products",
}
_MODEL_RE = re.compile(r"\bK[12]\b")


def tokenize(text: str) -> list[str]:
    """中文 2-gram + 英文小写单词。"""
    tokens: list[str] = []
    for eng in re.findall(r"[a-zA-Z0-9_]+", text.lower()):
        tokens.append(eng)
    han = re.sub(r"[^\u4e00-\u9fff]", "", text)
    if han:
        tokens.extend(han[i : i + 2] for i in range(len(han) - 1))
    return [t for t in tokens if t not in _STOPWORDS and len(t) >= 2]


def search(chunks: list[KnowledgeChunk], query: str, top_k: int = 5) -> list[KnowledgeChunk]:
    """BM25 简化：tf 饱和 + 文档频率 idf + 标题/路由/型号加权。"""
    q_tokens = Counter(tokenize(query))
    if not q_tokens:
        return []

    n_docs = max(len(chunks), 1)
    df: Counter[str] = Counter()
    for c in chunks:
        for t in set(tokenize(c.content)):
            df[t] += 1

    scores: list[tuple[float, int]] = []
    for idx, c in enumerate(chunks):
        tfs = Counter(tokenize(c.content))
        score = 0.0
        for tok, qtf in q_tokens.items():
            if tok not in df:
                continue
            idf = math.log(1.0 + (n_docs - df[tok] + 0.5) / (df[tok] + 0.5))
            tf = tfs[tok] / (tfs[tok] + 2.0)  # 饱和
            score += qtf * tf * idf
        if score <= 0:
            continue
        # 标题/小节名命中加权
        header = f"{c.source} {c.section}"
        if any(t in header for t in q_tokens):
            score *= 1.5
        # 路由词：query 关键词 → 对应文件加权
        for term, fname in _ROUTE_TERMS.items():
            if term in query and fname in c.source:
                score += 2.0
        # 型号出现
        if _MODEL_RE.search(query) and _MODEL_RE.search(c.content):
            score += 1.0
        scores.append((score, idx))

    scores.sort(key=lambda kv: kv[0], reverse=True)
    ranked = scores[:top_k]
    if not ranked:
        return []
    max_s = ranked[0][0]
    out: list[KnowledgeChunk] = []
    for s, idx in ranked:
        c = chunks[idx]
        c.score = round(s / max_s, 3)
        # 真实质量信号：query 词在 chunk 中的覆盖率（去停用词后），弥补归一化后最高分恒为 1.0 的失真
        content_tokens = set(t for t in tokenize(c.content))
        query_tokens = set(q_tokens.keys())
        overlap = (len(content_tokens & query_tokens) / len(query_tokens)) if query_tokens else 0.0
        c.overlap = round(overlap, 3)
        out.append(c)
    return out