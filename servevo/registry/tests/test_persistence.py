"""Registry 持久化单测：save/load roundtrip，重启恢复发布/回滚/审批状态。"""

from __future__ import annotations

from servevo_registry.persistence import FileStorage, load_registry, save_registry
from servevo_registry.registry import (
    APPROVED,
    Approval,
    KnowledgeRegistry,
    KnowledgeVersion,
    LABEL_CANARY,
    LABEL_STABLE,
    file_uri,
)


def _reg() -> KnowledgeRegistry:
    r = KnowledgeRegistry()
    r.register(KnowledgeVersion("v1", "product-knowledge", file_uri("kb", "product-knowledge", "v1"), approved=True))
    r.register(KnowledgeVersion("v2", "product-knowledge", file_uri("kb", "product-knowledge", "v2"), approved=True))
    r.promote("v1", LABEL_STABLE)
    r.promote("v2", LABEL_CANARY)
    return r


def test_save_load_roundtrip(tmp_path):
    r = _reg()
    a = Approval("c1", "v2", "UPDATE", LABEL_STABLE, "政策更新")
    r.submit_approval(a)
    r.decide_approval("c1", APPROVED, "servevo-qc")

    st = FileStorage(root=tmp_path)
    save_registry(r, st)
    # 全新 Registry 模拟"重启"
    loaded = load_registry(st)

    assert loaded.current(LABEL_STABLE) == "v1"
    assert loaded.current(LABEL_CANARY) == "v2"
    assert loaded.resolve(LABEL_STABLE).version == "v1"
    # 审批状态恢复
    assert len(loaded.approvals) == 1
    assert loaded.approvals[0].status == APPROVED
    assert loaded.approvals[0].reviewer == "servevo-qc"
    # 发布仍可用（审批已批准）
    assert loaded.promote("v2", LABEL_STABLE, approval=loaded.approvals[0]) is True


def test_load_missing_returns_empty(tmp_path):
    st = FileStorage(root=tmp_path)
    loaded = load_registry(st)
    assert loaded.versions == {}
    assert loaded.labels == {}


def test_file_storage_path_traversal_blocked(tmp_path):
    st = FileStorage(root=tmp_path)
    try:
        st.upload(b"x", "../../evil.txt")
        assert False, "应拒绝路径穿越"
    except ValueError:
        pass


def test_rollback_persisted(tmp_path):
    r = _reg()
    r.promote("v2", LABEL_STABLE)  # v2 提升稳定
    assert r.current(LABEL_STABLE) == "v2"
    r.rollback(LABEL_STABLE, "v1")  # 回滚 v1

    st = FileStorage(root=tmp_path)
    save_registry(r, st)
    loaded = load_registry(st)
    assert loaded.current(LABEL_STABLE) == "v1"  # 回滚状态重启后保留
