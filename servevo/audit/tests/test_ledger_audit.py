"""台账与审计链单测（本地后端）。"""

from __future__ import annotations

from servevo_audit.audit import AuditLog
from servevo_audit.ledger import MetricsLedger, resolution_metrics
from servevo_audit.storage import LocalStorage


def test_resolution_metrics():
    m = resolution_metrics(solved=8, escalated=2, total=10, qc_avg_score=76.5, regression_pass=10, regression_total=10)
    assert m["resolution_rate"] == 0.8
    assert m["escalation_rate"] == 0.2
    assert m["qc_avg_score"] == 76.5
    assert m["regression_pass_rate"] == 1.0


def test_resolution_metrics_zero_total():
    m = resolution_metrics(0, 0, 0, 0.0, 0, 0)
    assert m["resolution_rate"] == 0.0


def test_ledger_append_snapshot(tmp_path):
    st = LocalStorage(root=tmp_path)
    led = MetricsLedger(st, prefix="ledger")
    rec = led.append("v1", resolution_metrics(8, 2, 10, 76.5, 10, 10))
    assert rec["knowledge_version"] == "v1"
    assert rec["ts"]
    # 追加第二条，jsonl 累积
    led.append("v1", resolution_metrics(9, 1, 10, 82.0, 10, 10))


def test_audit_append(tmp_path):
    st = LocalStorage(root=tmp_path)
    log = AuditLog(st, prefix="audit")
    rec = log.append("qc.report", "approve", "servevo-qc", {"session": "s1"})
    assert rec["event"] == "qc.report"
    assert rec["actor"] == "servevo-qc"
    assert rec["hash"]
    assert len(rec["hash"]) == 64  # sha256