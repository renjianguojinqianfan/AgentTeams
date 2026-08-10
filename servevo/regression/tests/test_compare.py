"""测试集与对比纯函数单测（无网络 Deterministic）。"""

from __future__ import annotations

from pathlib import Path

from servevo_regression.compare import RunMetrics, compare, to_report
from servevo_regression.testset import TestQuestion, TestSet, load_testset, validate

TEST_PATH = Path(__file__).parent.parent / "testset" / "cafe-testset-v1.json"


def test_load_testset_50_questions():
    ts = load_testset(TEST_PATH)
    assert ts.total == 50
    assert len(ts.by_category()) >= 4
    assert sum(1 for q in ts.questions if q.gap) == 5


def test_validate_no_issues():
    ts = load_testset(TEST_PATH)
    assert validate(ts) == []


def test_validate_duplicate():
    q1 = TestQuestion(id="A", category="产品", question="q", answer="a", key_points=[], gap=False)
    q2 = TestQuestion(id="A", category="产品", question="q2", answer="a", key_points=[], gap=False)
    ts = TestSet("t", "1", "kb", [q1, q2])
    issues = validate(ts)
    assert any("重复" in i for i in issues)


def test_compare_evolution_ok():
    v1 = RunMetrics("v1", 0.7, 0.3, 65.0, 0.7, gap_detected=5)
    v2 = RunMetrics("v2", 0.95, 0.05, 85.0, 0.95, gap_detected=0)
    cmp = compare(v1, v2)
    assert cmp.verdict == "进化达标"
    assert cmp.deltas["resolution_rate"] > 0
    assert cmp.deltas["escalation_rate"] < 0
    assert cmp.deltas["qc_avg_score"] > 0


def test_compare_evolution_fail_no_gain():
    v1 = RunMetrics("v1", 0.9, 0.1, 80.0, 0.9)
    v2 = RunMetrics("v2", 0.85, 0.15, 75.0, 0.85)
    cmp = compare(v1, v2)
    assert cmp.verdict == "进化未达标"


def test_compare_report_has_missing_evidence():
    v1 = RunMetrics("v1", 0.7, 0.3, 65.0, 0.7, gap_detected=5)
    v2 = RunMetrics("v2", 0.95, 0.05, 85.0, 0.95, gap_detected=0)
    rep = to_report(compare(v1, v2))
    assert any("缺口题" in m for m in rep["missing_evidence"])