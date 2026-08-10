"""CLI：servevo-regression。

- validate <testset.json>             校验测试集
- compare --v1 <json> --v2 <json>     对比 v1/v2 指标（纯函数，无 LLM）
"""
from __future__ import annotations

import argparse
import json
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from .compare import RunMetrics, compare, to_report
from .testset import load_testset, validate


def _metrics_from_dict(d: dict) -> RunMetrics:
    return RunMetrics(
        knowledge_version=d.get("knowledge_version", ""),
        resolution_rate=d.get("resolution_rate", 0.0),
        escalation_rate=d.get("escalation_rate", 0.0),
        qc_avg_score=d.get("qc_avg_score", 0.0),
        regression_pass_rate=d.get("regression_pass_rate", 0.0),
        gap_detected=d.get("gap_detected", 0),
        degraded_reasons=list(d.get("degraded_reasons", [])),
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="servevo-regression")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="校验测试集")
    v.add_argument("testset")

    c = sub.add_parser("compare", help="对比 v1/v2 指标")
    c.add_argument("--v1", required=True, help="v1 指标 JSON")
    c.add_argument("--v2", required=True, help="v2 指标 JSON")
    c.add_argument("--json", action="store_true")

    args = p.parse_args(argv)

    if args.cmd == "validate":
        ts = load_testset(args.testset)
        issues = validate(ts)
        print(f"测试集 {ts.name} v{ts.version}: {ts.total} 题, {len(ts.by_category())} 类")
        if issues:
            for i in issues:
                print(f"  !! {i}")
            return 1
        print("校验通过 ✓")
        return 0

    v1 = _metrics_from_dict(json.load(open(args.v1, encoding="utf-8")))
    v2 = _metrics_from_dict(json.load(open(args.v2, encoding="utf-8")))
    cmp = compare(v1, v2)
    rep = to_report(cmp)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(f"== v1/v2 量化对照: {cmp.verdict} ==")
        print(f"  解决率: {v1.resolution_rate:.2f} -> {v2.resolution_rate:.2f} (Δ{cmp.deltas['resolution_rate']:+.2f})")
        print(f"  转人工率: {v1.escalation_rate:.2f} -> {v2.escalation_rate:.2f} (Δ{cmp.deltas['escalation_rate']:+.2f})")
        print(f"  质检分: {v1.qc_avg_score:.1f} -> {v2.qc_avg_score:.1f} (Δ{cmp.deltas['qc_avg_score']:+.1f})")
        print(f"  回归通过率: {v1.regression_pass_rate:.2f} -> {v2.regression_pass_rate:.2f}")
        print(f"  缺口题: v1={v1.gap_detected} v2={v2.gap_detected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())