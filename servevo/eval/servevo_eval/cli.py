"""CLI：servevo-eval evaluate --qa <json> [--kb <references>] [--json]。

qa JSON 结构：
{
  "session_id": "…",
  "context": "可选会话上下文",
  "records": [
    {"question": "…", "category": "…", "user_answer": "…", "record_id": "…可选"}
  ]
}

零 LLM 也能跑（无 key → 报告降级，批次零分兜底 + 缺失证据段说明）。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from .entities import QaRecord
from .graph import EvaluationGraph
from .llm import create_chat_client, is_configured
from .structured_output import LLMStructuredInvoker


def _reference_text(refs_dir: str | None) -> str:
    """从 servevo_rag 知识包生成知识基线文本（DRY 复用 RAG 读取）。"""
    if not refs_dir:
        return ""
    try:
        from servevo_rag.knowledge import load_knowledge

        chunks = load_knowledge(refs_dir)
        return "\n\n".join(
            f"[{c.source}::{c.section}]\n{c.content}" for c in chunks
        )
    except Exception as e:  # 知识包缺失不应阻断质检
        return f"(知识基线加载失败: {e})"


def _load_qa(path: str) -> tuple[str, str, list[QaRecord]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    session_id = data.get("session_id", os.path.basename(path))
    context = data.get("context", "")
    records = [
        QaRecord(
            question_index=i,
            question=r.get("question", ""),
            category=r.get("category", "未知"),
            user_answer=r.get("user_answer"),
            record_id=r.get("record_id"),
        )
        for i, r in enumerate(data.get("records", []))
    ]
    return session_id, context, records


async def _run(path: str, refs_dir: str | None) -> dict:
    session_id, context, records = _load_qa(path)
    graph = EvaluationGraph(invoker=LLMStructuredInvoker())
    chat_client = create_chat_client() if is_configured() else None
    report = await graph.evaluate(
        chat_client=chat_client,
        session_id=session_id,
        qa_records=records,
        context_text=context,
        reference_context=_reference_text(refs_dir),
    )
    return _to_dict(report)


def _to_dict(report) -> dict:
    return {
        "session_id": report.session_id,
        "total_questions": report.total_questions,
        "overall_score": report.overall_score,
        "category_scores": [c.__dict__ for c in report.category_scores],
        "question_details": [
            {
                "question_index": d.question_index,
                "question": d.question,
                "category": d.category,
                "user_answer": d.user_answer,
                "score": d.score,
                "confidence": d.confidence,
                "needs_review": d.needs_review,
                "feedback": d.feedback,
            }
            for d in report.question_details
        ],
        "overall_feedback": report.overall_feedback,
        "strengths": list(report.strengths),
        "improvements": list(report.improvements),
        "reference_answers": [
            {"question_index": r.question_index, "reference_answer": r.reference_answer}
            for r in report.reference_answers
        ],
        "missing_evidence": list(report.missing_evidence),
        "needs_review_count": report.needs_review_count,
        "degraded_reasons": list(report.degraded_reasons),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="servevo-eval")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("evaluate", help="质检一个会话（qa JSON）")
    e.add_argument("--qa", required=True, help="QA JSON 文件路径")
    e.add_argument("--kb", default=None, help="references 目录（知识基线，可选）")
    e.add_argument("--json", action="store_true", help="输出 JSON 报告")

    args = p.parse_args(argv)

    result = asyncio.run(_run(args.qa, args.kb))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"== 质检报告 [{result['session_id']}] ==")
        print(f"总分: {result['overall_score']} / 题数: {result['total_questions']} / 需人工复核: {result['needs_review_count']}")
        print()
        print("=== 缺失证据段 ===")
        if result["missing_evidence"]:
            for m in result["missing_evidence"]:
                print(f"  - {m}")
        else:
            print("  （无）")
        print()
        print("=== 分类得分 ===")
        for c in result["category_scores"]:
            print(f"  {c['category']}: {c['score']} ({c['question_count']} 题)")
        print()
        print("=== 综合评语 ===")
        print(result["overall_feedback"])
        print()
        print("=== 优势 ===")
        for s in result["strengths"]:
            print(f"  + {s}")
        print("=== 待改进 ===")
        for i in result["improvements"]:
            print(f"  - {i}")
    return 0


if __name__ == "__main__":
    sys.exit(main())