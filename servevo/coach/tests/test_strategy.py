"""陪练策略纯函数单测。"""

from __future__ import annotations

from servevo_coach.strategy import build_knowledge_revisions, compute_strategy_update, should_end_session


def test_strategy_no_data_keeps():
    u = compute_strategy_update({}, "mid", 0, 6)
    assert u.suggested_difficulty == "mid"
    assert u.suggested_category == "通用"


def test_strategy_raises_difficulty_when_high():
    u = compute_strategy_update({"保修": [8, 9]}, "junior", 2, 6)
    assert u.suggested_difficulty == "mid"


def test_strategy_lowers_difficulty_when_low():
    u = compute_strategy_update({"保修": [2, 3]}, "senior", 2, 6)
    assert u.suggested_difficulty == "mid"


def test_strategy_weak_category_picked():
    u = compute_strategy_update({"保修": [9], "退换货": [3]}, "mid", 2, 6)
    assert u.suggested_category == "退换货"


def test_strategy_keeps_difficulty_in_middle():
    u = compute_strategy_update({"保修": [5, 6]}, "mid", 2, 6)
    assert u.suggested_difficulty == "mid"


def test_should_end_session():
    assert should_end_session(6, 6, {})
    assert not should_end_session(2, 6, {})
    assert should_end_session(5, 6, {"保修": [7, 8], "价格": [6, 7]})


def test_revisions_from_low_scores():
    history = [
        {"category": "保修", "scenario": "K2 现在保修多久", "score": 3, "feedback": "答错保修期"},
        {"category": "故障", "scenario": "K2 不出水", "score": 8, "feedback": "答对"},
        {"category": "价格", "scenario": "K2 价格", "score": 2, "feedback": "报错价格"},
    ]
    revs = build_knowledge_revisions(history)
    # 低分（<4）才产草案；8 分不产
    assert len(revs) == 2
    # category -> references 文件映射正确
    by_cat = {r.category: r for r in revs}
    assert by_cat["保修"].target_section == "warranty-policy"
    assert by_cat["价格"].target_section == "products"
    # change_type 与 skill_id 固定
    assert all(r.change_type == "UPDATE" for r in revs)
    assert all(r.skill_id == "product-knowledge" for r in revs)
    # reason 含 bad case
    assert "答错保修期" in by_cat["保修"].reason


def test_revisions_skip_unanswered():
    # 无分数（未应答）不产草案
    history = [{"category": "保修", "scenario": "K2 保修", "score": None}]
    assert build_knowledge_revisions(history) == []


def test_revisions_dedup_same_section_category():
    history = [
        {"category": "保修", "scenario": "q1", "score": 2},
        {"category": "保修", "scenario": "q2", "score": 3},
    ]
    revs = build_knowledge_revisions(history)
    assert len(revs) == 1  # 同 target+category 去重