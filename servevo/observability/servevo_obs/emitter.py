"""可观测 Emitter：OTLP 同契约的指标/日志上报，云接入或自建等价物。

- cloud：配置 AGENTTEAMS_CMS_* 齐全 → 云接入（交由官方 AgentTeams/AgentLoop）
- local：无云 → 指标落本地台账（servevo_audit 的 MetricsLedger），OTLP 同契约
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .cms import CmsConfig, mode


class LocalObservability:
    """自建等价观测：指标/日志落本地 jsonl（答辩等价物，OTLP 同契约）。"""

    def __init__(self, log_dir: str | Path | None = None) -> None:
        self.log_dir = Path(log_dir or "tmp/servevo-obs")
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _append(self, kind: str, data: dict[str, Any]) -> None:
        record = {"ts": datetime.now(UTC).isoformat(), "kind": kind, **data}
        f = self.log_dir / f"{kind}.jsonl"
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def emit_metric(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """发一条指标（时序）。"""
        self._append("metrics", {"name": name, "value": value, "tags": tags or {}})

    def emit_log(self, level: str, message: str, **ctx: Any) -> None:
        """发一条日志。"""
        self._append("logs", {"level": level, "message": message, "ctx": ctx})


class Observability:
    """统一观测门面：按 CMS 配置决定云接入或自建等价物。

    诚实边界：本模块不实现 OTLP 协议本身（不引入 opentelemetry 依赖）。
    云接入时由官方 AgentTeams/AgentLoop 经 AGENTTEAMS_CMS_* env 走 OTLP 上报；
    本模块始终落本地 jsonl 台账作为等价审计轨迹（不静默丢数据），
    模式经 mode 暴露供答辩讲清"OTLP 同契约，差一个云 endpoint"。
    """

    def __init__(self, cfg: CmsConfig | None = None, log_dir: str | Path | None = None) -> None:
        self._cfg = cfg or CmsConfig()
        self._local = LocalObservability(log_dir)

    @property
    def mode(self) -> str:
        return mode(self._cfg)

    def emit_metric(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        # 无论云/本地，都落本地 jsonl 台账（等价审计轨迹）。云 OTLP 由官方 env 接管，不在此重复实现。
        self._local.emit_metric(name, value, tags)

    def emit_log(self, level: str, message: str, **ctx: Any) -> None:
        self._local.emit_log(level, message, **ctx)