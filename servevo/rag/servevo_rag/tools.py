"""RAG 工具：search / refine / decompose（原 rag_tools 适配版）。

search_knowledge_base_impl 已替换为文件型 keyword 检索（绕 pgvector 红线）。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from langchain_core.messages import HumanMessage

from .knowledge import KnowledgeChunk, load_knowledge
from .llm import LlmClient
from .retrieval import search as keyword_search


@dataclass
class RagToolContext:
    llm: LlmClient
    kb_dir: str
    _cache: list[KnowledgeChunk] | None = None

    def chunks(self) -> list[KnowledgeChunk]:
        if self._cache is None:
            self._cache = load_knowledge(self.kb_dir)
        return self._cache


async def search_knowledge_base_impl(
    query: str,
    kb_ids: list[int],
    top_k: int,
    ctx: RagToolContext,
) -> list[dict[str, object]]:
    """文件型检索：返回 {content, source, score, section} 列表。"""
    results = keyword_search(ctx.chunks(), query, top_k=top_k)
    return [c.to_dict() for c in results]


async def refine_query_impl(
    original_query: str,
    feedback: str,
    ctx: RagToolContext,
) -> str:
    """LLM 改写查询以提升召回（与原实现一致）。"""
    llm = await ctx.llm.get_chat_client()
    prompt = f"""你是搜索查询优化专家。原始问题检索效果不好，请改写为更贴合关键词检索的查询。

原始问题：{original_query}
检索反馈：{feedback}

直接返回改写后的查询（一句话，不要解释）："""
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    content = response.content if isinstance(response.content, str) else str(response.content)
    return content.strip() or original_query


async def decompose_question_impl(
    complex_query: str,
    ctx: RagToolContext,
) -> list[str]:
    """复杂问题拆解为 2-3 个子问题。"""
    llm = await ctx.llm.get_chat_client()
    prompt = f"""你是一个问题分解专家。请将以下复杂问题拆解为 2-3 个独立的子问题，每个子问题适合关键词检索。

复杂问题：{complex_query}

直接返回子问题列表，每行一个，不要其他内容："""
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    content = response.content if isinstance(response.content, str) else str(response.content)
    lines = [ln.strip("- • ") for ln in content.splitlines() if ln.strip()]
    return [ln for ln in lines if ln] or [complex_query]