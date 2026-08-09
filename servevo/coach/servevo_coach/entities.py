"""陪练领域实体：纯 dataclass，零框架依赖。

迁移自 interview-agent `domain/entities/evaluation.py` + `adaptive`（AGPL-3.0），
语义改为客服陪练：主岗应答 vs 刁钻客户剧本，产出知识修订草案 + 回归测试执行。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScenarioRecord:
    """一轮陪练问答记录（刁钻客户剧本 + 主岗应答 + 评分）。"""

    scenario_index: int
    scenario: str          # 刁钻客户剧本/问题
    category: str          # 考察维度（产品/保修/退换/价格/故障/政策）
    difficulty: str        # junior/mid/senior（客户刁钻程度）
    agent_answer: str | None
    score: int | None = None
    feedback: str | None = None
    key_points: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class KnowledgeRevision:
    """知识修订草案（陪练暴露的知识缺口 -> 待审批的知识包变更）。"""

    skill_id: str
    category: str
    change_type: str            # ADD / UPDATE / DELETE
    target_section: str         # 目标 references 小节
    proposed_content: str       # 修订后的内容
    reason: str                 # 依据（陪练 bad case）
    reference: str | None = None  # 来源会话/报告定位


@dataclass(frozen=True)
class CoachReport:
    """陪练闭环输出报告。

    overall_score = 已答平均分（0-10 或 0-100 视 rubric）。
    knowledge_revisions: 本轮暴露的知识修订草案清单。
    decision_trace: ReAct 决策轨迹（可审计）。
    regression: 回归模式时逐题通过情况。
    """

    session_id: str
    mode: str                   # "coach" | "regression"
    total_scenarios: int
    overall_score: int
    scenarios: list[ScenarioRecord]
    strengths: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    knowledge_revisions: list[KnowledgeRevision] = field(default_factory=list)
    decision_trace: list[dict[str, Any]] = field(default_factory=list)
    regression_passed: int = 0
    regression_total: int = 0
    degraded_reasons: list[str] = field(default_factory=list)