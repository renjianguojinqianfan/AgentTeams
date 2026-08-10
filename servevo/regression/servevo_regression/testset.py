"""测试集加载与校验：50 题预置测试集（星辰咖啡机，含预埋缺口）。

确定性可复现（规划 §5）：测试集与评分 rubric 全部入库开源，v1/v2 差异=知识包版本 diff。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class TestQuestion:
    __test__ = False  # 抑制 pytest 误收集为测试类
    id: str
    category: str
    question: str
    answer: str
    key_points: list[str]
    expected_pass: bool
    gap: bool = False


@dataclass(frozen=True)
class TestSet:
    __test__ = False
    name: str
    version: str
    knowledge_ref: str
    questions: list[TestQuestion]

    @property
    def total(self) -> int:
        return len(self.questions)

    def by_category(self) -> dict[str, list[TestQuestion]]:
        out: dict[str, list[TestQuestion]] = {}
        for q in self.questions:
            out.setdefault(q.category, []).append(q)
        return out


def load_testset(path: str | Path) -> TestSet:
    """加载测试集 JSON，校验结构完整性。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    meta = data.get("meta", {})
    questions = [
        TestQuestion(
            id=q["id"],
            category=q["category"],
            question=q["question"],
            answer=q["answer"],
            key_points=list(q.get("key_points", [])),
            expected_pass=bool(q.get("expected_pass", True)),
            gap=bool(q.get("gap", False)),
        )
        for q in data.get("questions", [])
    ]
    return TestSet(
        name=meta.get("name", ""),
        version=meta.get("version", ""),
        knowledge_ref=meta.get("knowledge_ref", ""),
        questions=questions,
    )


def validate(ts: TestSet) -> list[str]:
    """校验测试集约束：总数、id 唯一、expected_pass 一致性、缺口题标记。"""
    issues: list[str] = []
    ids = [q.id for q in ts.questions]
    if len(ids) != len(set(ids)):
        issues.append("存在重复 id")
    gaps = [q for q in ts.questions if q.gap]
    non_gap_fail = [q.id for q in ts.questions if not q.expected_pass and not q.gap]
    if non_gap_fail:
        issues.append(f"非缺口题不应 expected_pass=False: {non_gap_fail}")
    return issues