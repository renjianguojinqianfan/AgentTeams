"""知识 Registry：version+label 寻址 + 发布/灰度/回滚 + 审批流。

对应规划 §4.3：
- 双轨 URI 抽象：`file://`/`http://` 通道发同一个知识包（Nacos 不在默认栈）
- label 寻址：`stable` 生产 / `canary` 灰度；回滚=切 label；审批=label 提升
- 纯函数/轻状态，零外依赖（确定性可复现）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

LABEL_STABLE = "stable"
LABEL_CANARY = "canary"
APPROVED = "approved"
PENDING = "pending"
REJECTED = "rejected"


@dataclass(frozen=True)
class KnowledgeVersion:
    """一个知识包版本。uri 为 file:// 或 http:// 的包定位。"""

    version: str                     # v1 / v2
    name: str                        # 如 product-knowledge
    uri: str                         # file:///path 或 http://...
    section_root: str = "references" # 包内 references 相对路径
    approved: bool = False           # 是否已通过审批可发布
    label: str | None = None         # 当前指向的 label（stable/canary）


@dataclass
class Approval:
    """一次知识变更审批记录（HITL）。"""

    change_id: str
    version: str
    change_type: str                 # ADD / UPDATE / DELETE
    proposed_label: str              # 申请提升到的 label
    reason: str
    status: str = PENDING            # pending / approved / rejected
    reviewer: str | None = None


class KnowledgeRegistry:
    """版本 + label 寻址的轻量 Registry。

    状态：versions 全部已注册版本；labels 当前 label -> 生效版本。
    纯内存（Demo 用）；持久化由 audit 台账承接（P3.4）。
    """

    def __init__(self) -> None:
        self.versions: dict[str, KnowledgeVersion] = {}
        self.labels: dict[str, str] = {}       # label -> version
        self.approvals: list[Approval] = []

    def register(self, version: KnowledgeVersion) -> None:
        """注册一个版本（file:// 双轨 URI 抽象）。"""
        self.versions[version.version] = version

    def resolve(self, label: str = LABEL_STABLE) -> KnowledgeVersion | None:
        """按 label 解析当前生效版本。"""
        ver = self.labels.get(label)
        return self.versions.get(ver) if ver else None

    def resolve_by_version(self, version: str) -> KnowledgeVersion | None:
        return self.versions.get(version)

    def promote(self, version: str, to_label: str, approval: Approval | None = None) -> bool:
        """把版本提升到某 label（发布/灰度）。返回是否成功。

        - 版本必须已注册、已审批通过（approval 提供时）
        - label 提升=发布/灰度；回滚=把 label 指回旧版本（见 rollback）
        """
        ver = self.versions.get(version)
        if ver is None:
            return False
        if approval is not None and approval.status != APPROVED:
            return False
        if ver.approved is False and approval is None:
            return False
        self.labels[to_label] = version
        return True

    def rollback(self, label: str, target_version: str) -> bool:
        """回滚：把 label 切回旧版本（回滚优先于自动化率，规划四准则）。"""
        if target_version not in self.versions:
            return False
        self.labels[label] = target_version
        return True

    def current(self, label: str = LABEL_STABLE) -> str | None:
        return self.labels.get(label)

    def submit_approval(self, approval: Approval) -> None:
        self.approvals.append(approval)

    def decide_approval(self, change_id: str, status: str, reviewer: str) -> bool:
        """审批：只允许 approved/rejected。"""
        if status not in (APPROVED, REJECTED):
            return False
        for a in self.approvals:
            if a.change_id == change_id:
                a.status = status
                a.reviewer = reviewer
                return True
        return False


def file_uri(root: str | Path, name: str, version: str) -> str:
    """构造 file:// 双轨 URI（Demo 通道）。"""
    return f"file://{Path(root).resolve()}/{name}/{version}"


def http_uri(base: str, name: str, version: str) -> str:
    """构造 http:// URI（后续 Nacos/远端通道）。"""
    return f"{base.rstrip('/')}/{name}/{version}"