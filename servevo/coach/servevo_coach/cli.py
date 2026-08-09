"""CLI：servevo-coach run --mode coach|regression [--kb <references>] [--json]。

coach 模式：LLM 驱动出刁钻客户端剧本 + 评估主岗应答（需 LLM env）。
regression 模式：跑预置测试集（--cases json），按 score>=7 判通过。
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

from servevo_eval.llm import create_chat_client, is_configured
from servevo_eval.structured_output import LLMStructuredInvoker

from .graph import CoachGraph


def _load_cases(path: str) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("cases", [])


async def _run(
    kb_dir: str,
    session_id: str,
    mode: str,
    context: str,
    difficulty: str,
    max_turns: int,
    cases_path: str | None,
    approval_mode: bool,
) -> dict:
    graph = CoachGraph(kb_dir=kb_dir, approval_mode=approval_mode)
    chat_client = create_chat_client() if is_configured() else None
    invoker = LLMStructuredInvoker()
    cases = _load_cases(cases_path) if cases_path else None
    report = await graph.run(
        chat_client=chat_client,
        invoker=invoker,
        session_id=session_id,
        mode=mode,
        session_context=context,
        difficulty=difficulty,
        max_turns=max_turns,
        regression_cases=cases,
    )
    return _to_dict(report)


def _to_dict(report) -> dict:
    return {
        "session_id": report.session_id,
        "mode": report.mode,
        "total_scenarios": report.total_scenarios,
        "overall_score": report.overall_score,
        "scenarios": [
            {
                "scenario_index": s.scenario_index,
                "scenario": s.scenario,
                "category": s.category,
                "difficulty": s.difficulty,
                "agent_answer": s.agent_answer,
                "score": s.score,
                "feedback": s.feedback,
            }
            for s in report.scenarios
        ],
        "strengths": list(report.strengths),
        "improvements": list(report.improvements),
        "knowledge_revisions": [
            {
                "skill_id": r.skill_id,
                "category": r.category,
                "change_type": r.change_type,
                "target_section": r.target_section,
                "proposed_content": r.proposed_content,
                "reason": r.reason,
            }
            for r in report.knowledge_revisions
        ],
        "regression_passed": report.regression_passed,
        "regression_total": report.regression_total,
        "decision_trace": list(report.decision_trace),
        "degraded_reasons": list(report.degraded_reasons),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="servevo-coach")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="跑一轮陪练/回归")
    r.add_argument("--mode", choices=["coach", "regression"], default="coach")
    r.add_argument("--kb", required=True, help="references 目录")
    r.add_argument("--session", default="coach-session-001")
    r.add_argument("--context", default="")
    r.add_argument("--difficulty", default="mid", choices=["junior", "mid", "senior"])
    r.add_argument("--max-turns", type=int, default=6)
    r.add_argument("--cases", default=None, help="回归测试集 JSON（mode=regression 必填）")
    r.add_argument("--approval", action="store_true", help="开启 HITL 剧本审批 interrupt")
    r.add_argument("--json", action="store_true", help="输出 JSON 报告")

    args = p.parse_args(argv)

    result = asyncio.run(_run(
        args.kb, args.session, args.mode, args.context, args.difficulty,
        args.max_turns, args.cases, args.approval,
    ))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        m = result["mode"]
        print(f"== 陪练报告 [{result['session_id']}] mode={m} ==")
        if m == "regression":
            print(f"回归通过: {result['regression_passed']}/{result['regression_total']}")
        print(f"总分: {result['overall_score']} / 剧本数: {result['total_scenarios']}")
        for s in result["scenarios"]:
            print(f"  [{s['scenario_index']}][{s['category']}/{s['difficulty']}] score={s['score']}")
            print(f"    Q: {s['scenario'][:80]}")
            print(f"    A: {(s['agent_answer'] or '')[:80]}")
            print(f"    F: {s['feedback']}")
        if result["knowledge_revisions"]:
            print("=== 知识修订草案 ===")
            for r in result["knowledge_revisions"]:
                print(f"  [{r['change_type']}] {r['category']}::{r['target_section']} - {r['reason'][:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())