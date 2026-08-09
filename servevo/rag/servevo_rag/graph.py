"""Agentic RAG LangGraph 子图：自主检索 + 质量评估循环 + 查询改写。

迁移自 interview-agent `backend/app/graphs/rag_agent.py`（AGPL-3.0），
检索实现替换为文件型 keyword 检索（见 tools.search_knowledge_base_impl）。

流程：
START -> analyze_query -> [simple: direct_search / complex: decompose]
decompose -> multi_search -> evaluate_quality
direct_search -> evaluate_quality
evaluate_quality -> [quality_ok: generate_answer / quality_low: refine_query]
refine_query -> direct_search (循环，max 2 次)
generate_answer -> END
"""

from __future__ import annotations

import asyncio
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from .tools import (
    RagToolContext,
    decompose_question_impl,
    refine_query_impl,
    search_knowledge_base_impl,
)

import logging

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2
_MIN_CHUNKS_THRESHOLD = 2
_MIN_SCORE_THRESHOLD = 0.5
# 真实质量门：query 词在检索结果中的最低覆盖率（弥补归一化 score 恒最高为 1.0 的失真）
_MIN_OVERLAP_THRESHOLD = 0.3
_SEARCH_TIMEOUT = 30


class RagAgentState(TypedDict, total=False):
    """Agentic RAG 状态（与源一致）。"""

    question: str
    kb_ids: list[int]
    top_k: int

    sub_questions: list[str]
    chunks: list[dict[str, object]]
    retry_count: int
    quality_ok: bool
    is_complex: bool
    sustained_low_quality: bool  # 重试耗尽后质量仍不足 → 转人工兜底

    answer: str
    sources: list[dict[str, object]]
    retrieval_trace: list[str]
    missing_evidence: list[str]  # 缺失证据段（准则 3）：未命中/质量不足的显式声明


_CONF_CTX = "ctx"


class RagAgentGraph:
    """带质量循环的自主检索图（检索=keyword，生成=LLM）。"""

    def __init__(self, kb_dir: str, llm: Any) -> None:
        self._kb_dir = kb_dir
        self._llm = llm
        self._compiled = self._build()

    async def query(self, question: str, top_k: int = 5) -> dict[str, Any]:
        config: RunnableConfig = {
            "configurable": {
                _CONF_CTX: RagToolContext(llm=self._llm, kb_dir=self._kb_dir),
            }
        }
        initial: RagAgentState = {
            "question": question,
            "kb_ids": [],
            "top_k": top_k,
            "sub_questions": [],
            "chunks": [],
            "retry_count": 0,
            "quality_ok": False,
            "is_complex": False,
            "answer": "",
            "sources": [],
            "retrieval_trace": [],
            "sustained_low_quality": False,
            "missing_evidence": [],
        }
        result = await self._compiled.ainvoke(initial, config=config)
        return {
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "retrieval_trace": result.get("retrieval_trace", []),
            "missing_evidence": result.get("missing_evidence", []),
        }

    def _build(self) -> Any:
        builder: StateGraph[RagAgentState] = StateGraph(RagAgentState)
        builder.add_node("analyze_query", self._analyze_query)
        builder.add_node("direct_search", self._direct_search)
        builder.add_node("decompose", self._decompose)
        builder.add_node("multi_search", self._multi_search)
        builder.add_node("evaluate_quality", self._evaluate_quality)
        builder.add_node("refine_query", self._refine_query)
        builder.add_node("generate_answer", self._generate_answer)

        builder.add_edge(START, "analyze_query")
        builder.add_conditional_edges("analyze_query", self._route_complexity)
        builder.add_edge("direct_search", "evaluate_quality")
        builder.add_edge("decompose", "multi_search")
        builder.add_edge("multi_search", "evaluate_quality")
        builder.add_conditional_edges("evaluate_quality", self._route_quality)
        builder.add_edge("refine_query", "direct_search")
        builder.add_edge("generate_answer", END)
        return builder.compile()

    # ==================== 节点 ====================

    async def _analyze_query(self, state: RagAgentState, config: RunnableConfig) -> dict[str, Any]:
        question = state.get("question", "")
        trace = list(state.get("retrieval_trace", []))
        is_complex = len(question) > 50 or any(kw in question for kw in ["和", "以及", "对比", "区别", "比较"])
        trace.append(f"[分析] 问题复杂度: {'复杂' if is_complex else '简单'}")
        return {"is_complex": is_complex, "retrieval_trace": trace}

    async def _direct_search(self, state: RagAgentState, config: RunnableConfig) -> dict[str, Any]:
        ctx = config["configurable"][_CONF_CTX]
        question = state.get("question", "")
        kb_ids = state.get("kb_ids", [])
        top_k = state.get("top_k", 5)
        trace = list(state.get("retrieval_trace", []))
        try:
            chunks = await asyncio.wait_for(
                search_knowledge_base_impl(question, kb_ids, top_k, ctx),
                timeout=_SEARCH_TIMEOUT,
            )
            trace.append(f"[检索] 直接搜索返回 {len(chunks)} 个结果")
        except TimeoutError:
            chunks = []
            trace.append("[检索] 搜索超时")
        except Exception as e:
            chunks = []
            trace.append(f"[检索] 搜索失败: {e}")
        return {"chunks": chunks, "retrieval_trace": trace}

    async def _decompose(self, state: RagAgentState, config: RunnableConfig) -> dict[str, Any]:
        ctx = config["configurable"][_CONF_CTX]
        question = state.get("question", "")
        trace = list(state.get("retrieval_trace", []))
        try:
            sub_questions = await decompose_question_impl(question, ctx)
            trace.append(f"[拆解] 拆为 {len(sub_questions)} 个子问题: {sub_questions[:3]}")
        except Exception as e:
            sub_questions = [question]
            trace.append(f"[拆解] 失败，使用原问题: {e}")
        return {"sub_questions": sub_questions, "retrieval_trace": trace}

    async def _multi_search(self, state: RagAgentState, config: RunnableConfig) -> dict[str, Any]:
        ctx = config["configurable"][_CONF_CTX]
        sub_questions = state.get("sub_questions", [])
        kb_ids = state.get("kb_ids", [])
        top_k = state.get("top_k", 5)
        trace = list(state.get("retrieval_trace", []))
        all_chunks: list[dict[str, object]] = []
        for sq in sub_questions:
            try:
                chunks = await asyncio.wait_for(
                    search_knowledge_base_impl(sq, kb_ids, top_k, ctx),
                    timeout=_SEARCH_TIMEOUT,
                )
                all_chunks.extend(chunks)
            except Exception as e:
                trace.append(f"[多路检索] 子问题 '{sq[:30]}...' 失败: {e}")
        seen: set[str] = set()
        deduped: list[dict[str, object]] = []
        for chunk in all_chunks:
            content = str(chunk.get("content", ""))
            if content not in seen:
                seen.add(content)
                deduped.append(chunk)
        trace.append(f"[多路检索] 合并去重后 {len(deduped)} 个结果")
        return {"chunks": deduped, "retrieval_trace": trace}

    async def _evaluate_quality(self, state: RagAgentState, config: RunnableConfig) -> dict[str, Any]:
        chunks = state.get("chunks", [])
        trace = list(state.get("retrieval_trace", []))
        if len(chunks) < _MIN_CHUNKS_THRESHOLD:
            quality_ok = False
            trace.append(f"[质量评估] 结果不足 ({len(chunks)} < {_MIN_CHUNKS_THRESHOLD})")
        else:
            # 用真实质量信号 overlap（query 词覆盖率），而非归一化 score（其最高分恒为 1.0）
            max_overlap = max((float(str(c.get("overlap", 0)) or 0) for c in chunks), default=0.0)
            quality_ok = max_overlap >= _MIN_OVERLAP_THRESHOLD
            trace.append(f"[质量评估] 通过={quality_ok} (最高覆盖率 {max_overlap:.2f} >= {_MIN_OVERLAP_THRESHOLD})")
        return {"quality_ok": quality_ok, "retrieval_trace": trace}

    async def _refine_query(self, state: RagAgentState, config: RunnableConfig) -> dict[str, Any]:
        ctx = config["configurable"][_CONF_CTX]
        question = state.get("question", "")
        retry_count = state.get("retry_count", 0)
        trace = list(state.get("retrieval_trace", []))
        feedback = f"第 {retry_count + 1} 次检索结果不够好，请换一种表述"
        try:
            refined = await refine_query_impl(question, feedback, ctx)
            trace.append(f"[改写] 原→新: '{question[:40]}...' -> '{refined[:40]}...'")
        except Exception as e:
            refined = question
            trace.append(f"[改写] 失败，使用原问题: {e}")
        return {"question": refined, "retry_count": retry_count + 1, "retrieval_trace": trace}

    async def _generate_answer(self, state: RagAgentState, config: RunnableConfig) -> dict[str, Any]:
        ctx = config["configurable"][_CONF_CTX]
        chunks = state.get("chunks", [])
        question = state.get("question", "")
        trace = list(state.get("retrieval_trace", []))
        quality_ok = state.get("quality_ok", False)

        # 缺失证据段（准则 3）：收集未命中/质量不足的显式声明
        missing_evidence = list(state.get("missing_evidence", []))
        if not chunks:
            trace.append("[生成] 无检索结果，显式声明缺失证据")
            missing_evidence.append("知识库未检索到与问题相关的信息，无法验证答案。")
            return {
                "answer": "抱歉，知识库中未找到与您问题相关的信息。请转人工核实。",
                "sources": [],
                "retrieval_trace": trace,
                "missing_evidence": missing_evidence,
            }
        # 重试耗尽仍质量不足 → 不基于弱结果作答，转人工兜底（SP2）
        if not quality_ok and state.get("retry_count", 0) >= _MAX_RETRIES:
            trace.append("[生成] 多次改写后质量仍不足，转人工兜底")
            missing_evidence.append("多次检索后仍无法确证答案，为避免幻觉转人工核实。")
            return {
                "answer": "抱歉，未能从知识库确证您的问题，为避免误导已转人工为您核实。",
                "sources": [],
                "retrieval_trace": trace,
                "missing_evidence": missing_evidence,
            }

        context_parts = [f"[来源:{c.get('source','?')}::{c.get('section','')}]\n{str(c.get('content', ''))}" for c in chunks[:5]]
        context = "\n\n---\n\n".join(context_parts)

        llm = await ctx.llm.get_chat_client()
        messages = [
            SystemMessage(
                content=(
                    "你是星辰客服助手。仅根据提供的上下文（knowledge references）回答问题。"
                    "上下文中没有的信息必须明确说明'未收录，请转人工核实'，禁止编造。"
                    "回答末尾附加所用来源文件名列表。"
                )
            ),
            HumanMessage(content=f"上下文：\n{context}\n\n问题：{question}"),
        ]
        try:
            response = await llm.ainvoke(messages)
            answer = response.content if isinstance(response.content, str) else str(response.content)
            trace.append(f"[生成] 成功，答案长度 {len(answer)}")
        except Exception as e:
            answer = f"回答生成失败: {e}"
            trace.append(f"[生成] 失败: {e}")

        sources = [{"content": str(c.get("content", ""))[:200], "score": c.get("score")} for c in chunks[:5]]
        return {"answer": answer, "sources": sources, "retrieval_trace": trace, "missing_evidence": missing_evidence}

    # ==================== 路由 ====================

    def _route_complexity(self, state: RagAgentState) -> str:
        return "decompose" if state.get("is_complex") else "direct_search"

    def _route_quality(self, state: RagAgentState) -> str:
        if state.get("quality_ok"):
            return "generate_answer"
        if state.get("retry_count", 0) >= _MAX_RETRIES:
            # 重试耗尽仍质量不足 → 标记持续低质量，转人工兜底（SP2）
            return "generate_answer"
        return "refine_query"

    # ==================== 辅助 ====================

    def _get_ctx(self, config: RunnableConfig) -> RagToolContext:
        return config["configurable"][_CONF_CTX]