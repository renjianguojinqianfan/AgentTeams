"""陪练策略纯函数：根据主岗各维度得分计算陪练策略调整建议。

迁移自 interview-agent `domain/services/adaptive_strategy.py`（AGPL-3.0），
维度改为客服考察面，难度语义改为"客户刁钻程度"。
"""

from __future__ import annotations

from dataclasses import dataclass

_DIFFICULTY_LEVELS = ["junior", "mid", "senior"]

# 阈值（0-10 分制）
_HIGH_SCORE_THRESHOLD = 7
_LOW_SCORE_THRESHOLD = 4
_WEAK_CATEGORY_THRESHOLD = 5


@dataclass(frozen=True)
class StrategyUpdate:
    """策略调整建议（纯计算，无 LLM）。"""

    suggested_difficulty: str
    suggested_category: str
    reason: str


def compute_strategy_update(
    category_scores: dict[str, list[int]],
    current_difficulty: str,
    turn_count: int,
    max_turns: int,
) -> StrategyUpdate:
    """根据主岗各维度得分历史，计算下一轮陪练策略。

    规则：
    1. 全局平均分 >= HIGH 且非 senior -> 提升刁钻程度
    2. 全局平均分 <= LOW 且非 junior -> 降低
    3. 否则保持
    4. 下一题方向：优先薄弱维度（追问）
    5. 接近 max_turns 优先未覆盖维度
    """
    if not category_scores:
        return StrategyUpdate(current_difficulty, "通用", "尚无足够数据判断，保持当前策略")

    all_scores = [s for scores in category_scores.values() for s in scores]
    global_avg = sum(all_scores) / len(all_scores) if all_scores else 5

    safe = current_difficulty if current_difficulty in _DIFFICULTY_LEVELS else "mid"
    suggested_difficulty = safe
    difficulty_reason = ""
    if global_avg >= _HIGH_SCORE_THRESHOLD and safe != "senior":
        idx = _DIFFICULTY_LEVELS.index(safe)
        suggested_difficulty = _DIFFICULTY_LEVELS[min(idx + 1, len(_DIFFICULTY_LEVELS) - 1)]
        difficulty_reason = f"全局平均分 {global_avg:.1f} >= {_HIGH_SCORE_THRESHOLD}，提升刁钻程度"
    elif global_avg <= _LOW_SCORE_THRESHOLD and safe != "junior":
        idx = _DIFFICULTY_LEVELS.index(safe)
        suggested_difficulty = _DIFFICULTY_LEVELS[max(idx - 1, 0)]
        difficulty_reason = f"全局平均分 {global_avg:.1f} <= {_LOW_SCORE_THRESHOLD}，降低刁钻程度"
    else:
        difficulty_reason = f"全局平均分 {global_avg:.1f}，保持当前"

    suggested_category = _pick_next_category(category_scores, turn_count, max_turns)
    return StrategyUpdate(
        suggested_difficulty=suggested_difficulty,
        suggested_category=suggested_category,
        reason=f"{difficulty_reason}；下一题方向：{suggested_category}",
    )


def _pick_next_category(
    category_scores: dict[str, list[int]],
    turn_count: int,
    max_turns: int,
) -> str:
    if not category_scores:
        return "通用"
    category_avgs = {cat: sum(s) / len(s) for cat, s in category_scores.items() if s}
    if not category_avgs:
        return "通用"

    remaining = max_turns - turn_count
    if remaining <= 2:
        return min(category_scores.items(), key=lambda x: len(x[1]))[0]

    weakest = min(category_avgs.items(), key=lambda x: x[1])
    if weakest[1] < _WEAK_CATEGORY_THRESHOLD:
        return weakest[0]
    return min(category_scores.items(), key=lambda x: len(x[1]))[0]


def should_end_session(
    turn_count: int,
    max_turns: int,
    category_scores: dict[str, list[int]],
) -> bool:
    """判断是否应结束陪练。

    结束条件：达到最大题数，或接近且所有维度至少 2 题。
    """
    if turn_count >= max_turns:
        return True
    return turn_count >= max_turns - 1 and all(len(s) >= 2 for s in category_scores.values())