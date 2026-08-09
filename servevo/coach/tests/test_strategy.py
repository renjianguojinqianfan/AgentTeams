"""陪练策略纯函数单测。"""

from __future__ import annotations

from servevo_coach.strategy import compute_strategy_update, should_end_session


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