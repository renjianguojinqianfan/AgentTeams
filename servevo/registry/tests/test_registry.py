"""Registry 单测：版本注册 / label 寻址 / 发布 / 灰度 / 回滚 / 审批流。"""

from __future__ import annotations

from servevo_registry.registry import (
    APPROVED,
    PENDING,
    Approval,
    KnowledgeRegistry,
    KnowledgeVersion,
    LABEL_CANARY,
    LABEL_STABLE,
    file_uri,
    http_uri,
)


def _reg() -> KnowledgeRegistry:
    r = KnowledgeRegistry()
    r.register(KnowledgeVersion("v1", "product-knowledge", file_uri("kb", "product-knowledge", "v1"), approved=True))
    r.register(KnowledgeVersion("v2", "product-knowledge", file_uri("kb", "product-knowledge", "v2"), approved=True))
    return r


def test_file_uri_double_track():
    assert file_uri("kb", "product-knowledge", "v1").startswith("file://")
    assert http_uri("http://x", "n", "v1").startswith("http://")


def test_register_and_resolve_by_version():
    r = KnowledgeRegistry()
    r.register(KnowledgeVersion("v1", "n", file_uri("kb", "n", "v1"), approved=True))
    assert r.resolve_by_version("v1") is not None
    assert r.resolve_by_version("v9") is None


def test_publish_promote_label():
    r = _reg()
    assert r.promote("v1", LABEL_STABLE)
    assert r.current(LABEL_STABLE) == "v1"
    assert r.resolve(LABEL_STABLE).version == "v1"


def test_gray_canary_then_promote_stable():
    r = _reg()
    r.promote("v1", LABEL_STABLE)
    r.promote("v2", LABEL_CANARY)  # 灰度
    assert r.resolve(LABEL_CANARY).version == "v2"
    assert r.resolve(LABEL_STABLE).version == "v1"
    r.promote("v2", LABEL_STABLE)  # 提升稳定
    assert r.resolve(LABEL_STABLE).version == "v2"


def test_rollback_switches_label():
    r = _reg()
    r.promote("v1", LABEL_STABLE)
    r.promote("v2", LABEL_CANARY)
    r.promote("v2", LABEL_STABLE)
    assert r.current(LABEL_STABLE) == "v2"
    r.rollback(LABEL_STABLE, "v1")
    assert r.current(LABEL_STABLE) == "v1"


def test_publish_requires_approval():
    r = KnowledgeRegistry()
    r.register(KnowledgeVersion("v2", "n", file_uri("kb", "n", "v2")))  # 未审批
    assert r.promote("v2", LABEL_STABLE) is False  # 无审批且未 approved → 拒绝


def test_approval_flow_pending_to_approved():
    r = KnowledgeRegistry()
    r.register(KnowledgeVersion("v2", "n", file_uri("kb", "n", "v2")))
    a = Approval("c1", "v2", "UPDATE", LABEL_STABLE, "政策更新")
    r.submit_approval(a)
    assert a.status == PENDING
    assert r.promote("v2", LABEL_STABLE, approval=a) is False  # 未审批
    r.decide_approval("c1", APPROVED, "servevo-qc")
    assert a.status == APPROVED
    assert r.promote("v2", LABEL_STABLE, approval=a) is True


def test_approval_reject():
    r = KnowledgeRegistry()
    a = Approval("c2", "v2", "UPDATE", LABEL_STABLE, "x")
    r.submit_approval(a)
    r.decide_approval("c2", "rejected", "servevo-qc")
    assert a.status == "rejected"