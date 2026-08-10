"""Registry 持久化：把版本/label/审批状态落盘，重启可恢复。

纯内存 Demo 版在重启后丢失发布/回滚/审批状态（MED6 审查发现）。
此处提供确定性序列化：把 KnowledgeRegistry 的 versions/labels/approvals
存为一个 JSON 文件，经 storage 接口读写。

storage 接口与 servevo_audit.storage 同契约（upload/download/exists），
默认用本地文件（LocalStorage 等价物），可替换为 MinIO 等。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .registry import APPROVED, PENDING, REJECTED, Approval, KnowledgeRegistry, KnowledgeVersion


class FileStorage:
    """最小本地文件存储（与 servevo_audit.storage 同契约的等价物，零依赖）。"""

    def __init__(self, root: str | Path = "tmp/servevo-registry") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, key: str) -> Path:
        safe = key.lstrip("/").replace("\\", "/")
        p = (self.root / safe).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise ValueError(f"非法存储 key: {key}")
        return p

    def upload(self, data: bytes, key: str) -> dict[str, Any]:
        p = self._safe_path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return {"key": key, "size": len(data)}

    def download(self, key: str) -> bytes:
        return self._safe_path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._safe_path(key).exists()


def save_registry(reg: KnowledgeRegistry, storage: Any, key: str = "registry/state.json") -> dict[str, Any]:
    """把 Registry 状态序列化并落盘（幂等，覆盖写）。"""
    versions = {
        v: {
            "version": v,
            "name": ver.name,
            "uri": ver.uri,
            "section_root": ver.section_root,
            "approved": ver.approved,
            "label": ver.label,
        }
        for v, ver in reg.versions.items()
    }
    approvals = [
        {
            "change_id": a.change_id,
            "version": a.version,
            "change_type": a.change_type,
            "proposed_label": a.proposed_label,
            "reason": a.reason,
            "status": a.status,
            "reviewer": a.reviewer,
        }
        for a in reg.approvals
    ]
    payload = json.dumps(
        {"versions": versions, "labels": reg.labels, "approvals": approvals},
        ensure_ascii=False,
    ).encode("utf-8")
    return storage.upload(payload, key)


def load_registry(storage: Any, key: str = "registry/state.json") -> KnowledgeRegistry:
    """从 storage 读回 Registry 状态；文件不存在返回空 Registry。"""
    reg = KnowledgeRegistry()
    if not storage.exists(key):
        return reg
    data = json.loads(storage.download(key).decode("utf-8"))
    for v, ver in data.get("versions", {}).items():
        reg.versions[v] = KnowledgeVersion(
            version=ver.get("version", v),
            name=ver.get("name", ""),
            uri=ver.get("uri", ""),
            section_root=ver.get("section_root", "references"),
            approved=bool(ver.get("approved", False)),
            label=ver.get("label"),
        )
    reg.labels.update(data.get("labels", {}))
    for a in data.get("approvals", []):
        reg.approvals.append(
            Approval(
                change_id=a.get("change_id", ""),
                version=a.get("version", ""),
                change_type=a.get("change_type", "UPDATE"),
                proposed_label=a.get("proposed_label", ""),
                reason=a.get("reason", ""),
                status=a.get("status", PENDING),
                reviewer=a.get("reviewer"),
            )
        )
    return reg
