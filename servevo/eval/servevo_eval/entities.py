"""质检评估领域实体：纯 dataclass，零框架依赖。

迁移自 interview-agent `domain/entities/evaluation.py`（AGPL-3.0），
语义改为客服质检：QaRecord = 客户提问 / 会话分类 / 坐席应答。
新增：单题 confidence + needs_review（低置信降级），报告 missing_evidence 段。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class QaRecord:
    """通用质检问答记录。

    user_answer 为 None 表示坐席未应答（评估时按 0 分处理）。
    record_id 可选，用于跨会话定位（缺省时按批次位置对齐）。
    """

    question_index: int
    question: str
    category: str
    user_answer: str | None
    record_id: str | None = None


@dataclass(frozen=True)
class QuestionEvaluationItem:
    """单题 LLM 质检评估输出（批次内）。

    confidence: 评分自信程度（high/medium/low）。low 时下游"只标注不评分"。
    needs_review: 低置信或解析失败时置 True，提示需人工复核。
    """

    question_index: int
    score: int
    feedback: str
    reference_answer: str
    key_points: list[str] = field(default_factory=list)
    confidence: str = "high"
    needs_review: bool = False


@dataclass(frozen=True)
class BatchReport:
    """单批 LLM 质检评估输出。失败批次以 None 表示，由合并逻辑零分兜底。"""

    overall_score: int
    overall_feedback: str
    strengths: list[str]
    improvements: list[str]
    question_evaluations: list[QuestionEvaluationItem]


@dataclass(frozen=True)
class QaBatch:
    """输入分批：记录批次在原 qa_records 中的起止下标与该批问答记录。"""

    start_index: int
    end_index: int
    records: list[QaRecord]


@dataclass(frozen=True)
class BatchResult:
    """批次质检结果定位：记录批次在原 qa_records 中的起止下标，用于缺失补零。

    report 为 None 表示该批 LLM 调用失败，合并时按零分兜底。
    """

    start_index: int
    end_index: int
    report: BatchReport | None


@dataclass(frozen=True)
class Summary:
    """二次汇总 LLM 输出。"""

    overall_feedback: str
    strengths: list[str]
    improvements: list[str]

    @classmethod
    def empty(cls) -> "Summary":
        return cls(overall_feedback="", strengths=[], improvements=[])


@dataclass(frozen=True)
class CategoryScore:
    """分类得分：某 category 的平均分与题数。"""

    category: str
    score: int
    question_count: int


@dataclass(frozen=True)
class QuestionEvaluation:
    """最终报告中的逐题评估（含原始问题与回答）。"""

    question_index: int
    question: str
    category: str
    user_answer: str | None
    score: int
    feedback: str
    confidence: str = "high"
    needs_review: bool = False


@dataclass(frozen=True)
class ReferenceAnswer:
    """最终报告中的参考答案与核心要点。"""

    question_index: int
    question: str
    reference_answer: str
    key_points: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvaluationReport:
    """统一质检报告。

    overall_score = 已答（有 user_answer）项平均分；全未答时为 0。
    missing_evidence（准则 3）：确定性聚合（批失败降级 + 未应答 + 低置信需人工复核），
    兼容 LLM 逐条补充（见 service.aggregate_missing_evidence），段内写明"本次因缺什么数据未能验证什么"。
    needs_review_count: 低置信/解析失败题目数。
    degraded_reasons: 批次 LLM 失败零分兜底原因清单。
    """

    session_id: str
    total_questions: int
    overall_score: int
    category_scores: list[CategoryScore]
    question_details: list[QuestionEvaluation]
    overall_feedback: str
    strengths: list[str]
    improvements: list[str]
    reference_answers: list[ReferenceAnswer]
    missing_evidence: list[str] = field(default_factory=list)
    needs_review_count: int = 0
    degraded_reasons: list[str] = field(default_factory=list)