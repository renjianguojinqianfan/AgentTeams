"""CLI：servevo-rag query "问题" --kb <references 目录>。

零 LLM 也能跑（无 key → 检索汇报模式，用于检索侧验证）。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from .graph import RagAgentGraph
from .knowledge import load_knowledge
from .llm import LlmClient
from .retrieval import search


def _print_chunks(query: str, refs_dir: str, top_k: int) -> None:
    chunks = load_knowledge(refs_dir)
    hits = search(chunks, query, top_k=top_k)
    print(f"== 检索命中 {len(hits)}/{top_k} (共 {len(chunks)} 块)")
    for c in hits:
        print(f"  [{c.source}::{c.section}] score={c.score:.2f}")
        print(f"    {c.content[:120].replace(chr(10), ' ')}")
    print()


async def _run_query(question: str, refs_dir: str, top_k: int, use_llm: bool) -> dict:
    llm = LlmClient()  # 惰性：无 key 时仅检索路径可用
    graph = RagAgentGraph(kb_dir=refs_dir, llm=llm)
    result = await graph.query(question, top_k=top_k)
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="servevo-rag")
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("query", help="问答（含 LLM 生成）")
    q.add_argument("question")
    q.add_argument("--kb", required=True, help="references 目录")
    q.add_argument("--top-k", type=int, default=5)
    q.add_argument("--json", action="store_true", help="输出 JSON（含 trace）")

    r = sub.add_parser("retrieve", help="仅检索，不出 LLM（验证用）")
    r.add_argument("query")
    r.add_argument("--kb", required=True)
    r.add_argument("--top-k", type=int, default=5)

    args = p.parse_args(argv)

    if args.cmd == "retrieve":
        _print_chunks(args.query, args.kb, args.top_k)
        return 0

    result = asyncio.run(_run_query(args.question, args.kb, args.top_k, use_llm=True))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("== 回答 ==")
        print(result["answer"])
        print()
        if result.get("missing_evidence"):
            print("== 缺失证据 ==")
            for m in result["missing_evidence"]:
                print(f"  - {m}")
            print()
        print("== 来源 ==")
        for s in result["sources"]:
            print(f"  {s.get('score')} {s.get('content', '')[:100]}")
        print()
        print("== 轨迹 ==")
        for t in result["retrieval_trace"]:
            print(f"  {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())