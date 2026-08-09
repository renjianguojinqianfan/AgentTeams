"""进化台账（Metrics jsonl）：v1/v2 指标时序，供量化对照与 AgentLoop 增强。

指标：
- 解决率 resolution_rate
- 转人工率 escalation_rate
- 质检平均分 qc_avg_score
- 回归通过率 regression_pass_rate
- 人机回环效率：每轮进化人工干预次数 / 审批平均响应时长
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from .storage import LocalStorage, MinioStorage


class MetricsLedger:
    """追加式指标台账（jsonl），按知识包版本分目录。"""

    def __init__(self, storage: LocalStorage | MinioStorage, prefix: str = "ledger") -> None:
        self._storage = storage
        self._prefix = prefix

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def append(self, knowledge_version: str, metrics: dict[str, Any]) -> dict[str, Any]:
        """记一条指标快照（含 knowledge_version 便于 v1/v2 对比）。"""
        record = {
            "ts": self._now(),
            "knowledge_version": knowledge_version,
            **metrics,
        }
        key = f"{self._prefix}/{knowledge_version}.jsonl"
        line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
        existing = b""
        if self._storage.exists(key):
            existing = self._storage.download(key)
        self._storage.upload(existing + line, key)
        return record


def resolution_metrics(
    solved: int,
    escalated: int,
    total: int,
    qc_avg_score: float,
    regression_pass: int,
    regression_total: int,
) -> dict[str, Any]:
    """由一组数字聚合标准指标（确定性，便于 v1/v2 对照）。"""
    if total <= 0:
        return {
            "resolution_rate": 0.0,
            "escalation_rate": 0.0,
            "qc_avg_score": round(qc_avg_score, 2),
            "regression_pass_rate": 0.0,
        }
    return {
        "resolution_rate": round(solved / total, 4),
        "escalation_rate": round(escalated / total, 4),
        "qc_avg_score": round(qc_avg_score, 2),
        "regression_pass_rate": round(regression_pass / regression_total, 4) if regression_total else 0.0,
    }