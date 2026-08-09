"""审计链：记录进化/服务闭环中的关键动作，形成可回放、可回滚的审计证据。

审计条目 = 事件 + 动作 + 主体 + 关联产物 + 哈希 + 时间戳。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from .storage import LocalStorage, MinioStorage, compute_hash


class AuditLog:
    """追加式审计日志（jsonl）。"""

    def __init__(self, storage: LocalStorage | MinioStorage, prefix: str = "audit") -> None:
        self._storage = storage
        self._prefix = prefix

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def append(
        self,
        event: str,
        action: str,
        actor: str,
        payload: dict[str, Any] | None = None,
        artifact_ref: str | None = None,
    ) -> dict[str, Any]:
        """追加一条审计记录，返回该记录（含 hash）。"""
        record = {
            "ts": self._now(),
            "event": event,
            "action": action,
            "actor": actor,
            "payload": payload or {},
            "artifact_ref": artifact_ref,
        }
        record["hash"] = compute_hash(json.dumps(record, ensure_ascii=False).encode("utf-8"))
        key = f"{self._prefix}/{self._now()[:10]}.jsonl"
        line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
        # 追加：读已有 + 写回
        existing = b""
        if self._storage.exists(key):
            existing = self._storage.download(key)
        self._storage.upload(existing + line, key)
        return record

    def read(self, prefix: str | None = None) -> list[dict[str, Any]]:
        """读取审计链（按前缀，返回全部记录）。"""
        raise NotImplementedError("读审计链通过 ledger/归档遍历实现，见 ledger.EventLog")