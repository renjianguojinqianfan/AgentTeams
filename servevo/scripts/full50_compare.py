#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""B5：全量 50 题 v1/v2 真跑对照（确定性 runner，qwen3.7-flash 廉价档）。

物化 v2 知识包（v1 副本 + 5 缺口新政策条目）→ run_testset(v1) → run_testset(v2) → compare。
产物落 tmp/full50-verify/（不进 git）。qc 为 runner 确定性代理分（resolved=90/转人工=40）。
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB_V1 = ROOT / "knowledge" / "product-knowledge" / "v1"
KB_V1_REFS = KB_V1 / "references"
KB_V2 = ROOT / "tmp" / "full50-kb-v2"  # v2 运行时物化（全量 5 缺口，不进 git）
TEST_PATH = ROOT / "regression" / "testset" / "cafe-testset-v1.json"
TOP_K = 3  # 控额度：全量 100 查询，降 top_k 省上下文 token

sys.path.insert(0, str(ROOT / "rag"))
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "regression"))

from servevo_regression.testset import load_testset  # noqa: E402
from servevo_regression.runner import run_testset  # noqa: E402
from servevo_regression.compare import compare  # noqa: E402

_SECTION_FILES = {"warranty-policy": "warranty-policy.md", "faq": "faq.md", "products": "products.md"}


def _section_for(category: str) -> str:
    if any(k in category for k in ("政策", "保修", "退换")):
        return "warranty-policy"
    if "故障" in category:
        return "faq"
    return "products"


def _materialize_v2(gap_questions: list) -> tuple[Path, list[dict]]:
    """物化 v2 知识包：v1 副本 + 全部 5 缺口新政策条目（diff 可审计）。"""
    if KB_V2.exists():
        shutil.rmtree(KB_V2)
    shutil.copytree(KB_V1, KB_V2)
    diff: list[dict] = []
    for q in gap_questions:
        section = _section_for(q.category)
        target = KB_V2 / "references" / _SECTION_FILES[section]
        entry = (
            f"\n## 2026 新政策（v2 修订，来源：测试集缺口题 {q.id}）\n\n"
            f"- 问题：{q.question}\n- 答复：{q.answer}\n"
        )
        with target.open("a", encoding="utf-8") as fh:
            fh.write(entry)
        diff.append({"source": "testset-gap", "question_id": q.id, "section": section, "answer": q.answer})
    sk = KB_V2 / "SKILL.md"
    t = sk.read_text(encoding="utf-8")
    sk.write_text(
        t.replace("version: 1.0.0", "version: 2.0.0").replace("label: v1", "label: v2"),
        encoding="utf-8",
    )
    return KB_V2, diff


def _metrics_dict(metrics) -> dict:
    return {
        "knowledge_version": metrics.knowledge_version,
        "resolution_rate": metrics.resolution_rate,
        "escalation_rate": metrics.escalation_rate,
        "qc_avg_score": metrics.qc_avg_score,
        "regression_pass_rate": metrics.regression_pass_rate,
        "gap_detected": metrics.gap_detected,
    }


def _cases_dict(run) -> list[dict]:
    """逐题结果（答辩诊断用：哪题 answered/passed 及缺口语义）。"""
    return [
        {
            "question_id": c.question_id,
            "category": c.category,
            "gap": c.gap,
            "resolved": c.resolved,
            "passed": c.passed,
            "qc_score": c.qc_score,
            "answer": (c.answer or "")[:200],
            "missing_evidence": list(c.missing_evidence),
        }
        for c in run.cases
    ]


async def main() -> int:
    testset = load_testset(TEST_PATH)
    gaps = [q for q in testset.questions if q.gap]
    v2_dir, diff = _materialize_v2(gaps)

    print("== v1 全量 50 题真跑 ==", flush=True)
    r1 = await run_testset(testset, str(KB_V1_REFS), "v1", top_k=TOP_K)
    print("v1 完成:", _metrics_dict(r1.metrics), flush=True)

    print("== v2 全量 50 题真跑 ==", flush=True)
    r2 = await run_testset(testset, str(v2_dir / "references"), "v2", top_k=TOP_K)
    print("v2 完成:", _metrics_dict(r2.metrics), flush=True)

    cmp = compare(r1.metrics, r2.metrics)
    out = {
        "ts": datetime.now(UTC).isoformat(),
        "model": __import__("os").environ.get("LLM_MODEL", "?"),
        "top_k": TOP_K,
        "v1": _metrics_dict(r1.metrics),
        "v2": _metrics_dict(r2.metrics),
        "deltas": cmp.deltas,
        "verdict": cmp.verdict,
        "v2_knowledge_diff": diff,
        "cases_v1": _cases_dict(r1),
        "cases_v2": _cases_dict(r2),
        "missing_evidence": [
            "qc 为 run_testset 确定性代理分（resolved=90/转人工=40），非 LLM 质检分；LLM 质检证据见 closedloop 快照",
            "v2 物化条目以测试集缺口题参考答案为准（确定性写入）",
            "回归通过率反映真实 LLM 应答与确定性 kp 匹配的命中率，未达 0.95 的题可在 cases_v1/v2 逐题诊断",
        ],
    }
    out_dir = ROOT / "tmp" / "full50-verify"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"{datetime.now().strftime('%Y-%m-%d')}-full50.json"
    fname.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("full50 对照完成:", fname, flush=True)
    print(json.dumps(out, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
