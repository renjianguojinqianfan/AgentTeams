"""v1/v2 量化对照：指标对比 + 报告组装（纯函数，确定性）。

对应规划 §5 量化对照：解决率↑ / 转人工率↓ / 质检平均分↑ / 回归通过率 100%。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RunMetrics:
    """一次测试集运行的聚合指标。"""

    knowledge_version: str
    resolution_rate: float
    escalation_rate: float
    qc_avg_score: float
    regression_pass_rate: float
    gap_detected: int = 0          # 缺口题被正确识别为"需更新"的数量
    degraded_reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VersionCompare:
    """v1 vs v2 对比结果。"""

    v1: RunMetrics
    v2: RunMetrics
    deltas: dict[str, float]
    verdict: str  # 进化达标 / 未达标


def _delta(a: float, b: float) -> float:
    return round(b - a, 4)


def compare(v1: RunMetrics, v2: RunMetrics, pass_threshold: float = 0.95) -> VersionCompare:
    """对比 v1/v2，判定进化是否达标。

    达标标准：v2 解决率↑ 且 转人工率↓ 且 质检分↑(或持平) 且 回归通过率>=pass_threshold。
    """
    deltas = {
        "resolution_rate": _delta(v1.resolution_rate, v2.resolution_rate),
        "escalation_rate": _delta(v1.escalation_rate, v2.escalation_rate),
        "qc_avg_score": _delta(v1.qc_avg_score, v2.qc_avg_score),
        "regression_pass_rate": _delta(v1.regression_pass_rate, v2.regression_pass_rate),
    }
    ok = (
        v2.resolution_rate >= v1.resolution_rate
        and v2.escalation_rate <= v1.escalation_rate
        and v2.qc_avg_score >= v1.qc_avg_score
        and v2.regression_pass_rate >= pass_threshold
    )
    verdict = "进化达标" if ok else "进化未达标"
    return VersionCompare(v1=v1, v2=v2, deltas=deltas, verdict=verdict)


def to_report(cmp: VersionCompare) -> dict:
    """组装对比报告（供 CLI 输出 / 答辩展示）。"""
    return {
        "verdict": cmp.verdict,
        "v1": {
            "knowledge_version": cmp.v1.knowledge_version,
            "resolution_rate": cmp.v1.resolution_rate,
            "escalation_rate": cmp.v1.escalation_rate,
            "qc_avg_score": cmp.v1.qc_avg_score,
            "regression_pass_rate": cmp.v1.regression_pass_rate,
            "gap_detected": cmp.v1.gap_detected,
        },
        "v2": {
            "knowledge_version": cmp.v2.knowledge_version,
            "resolution_rate": cmp.v2.resolution_rate,
            "escalation_rate": cmp.v2.escalation_rate,
            "qc_avg_score": cmp.v2.qc_avg_score,
            "regression_pass_rate": cmp.v2.regression_pass_rate,
            "gap_detected": cmp.v2.gap_detected,
        },
        "deltas": cmp.deltas,
        "missing_evidence": [
            f"v1 缺口题 {cmp.v1.gap_detected} 条待进化（知识未同步）"
            if cmp.v1.gap_detected
            else "v1 无缺口题待进化",
        ],
    }