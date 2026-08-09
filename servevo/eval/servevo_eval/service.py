"""质检领域服务：纯函数算法，零框架依赖。

迁移自 interview-agent `domain/services/evaluation.py`（AGPL-3.0），
去掉 InterviewQuestion 依赖（overlay_answers/build_qa_records），
新增 missing_evidence 聚合与 needs_review 统计。
"""

from __future__ import annotations

from .entities import (
    BatchResult,
    CategoryScore,
    EvaluationReport,
    QaBatch,
    QaRecord,
    QuestionEvaluation,
    QuestionEvaluationItem,
    ReferenceAnswer,
    Summary,
)

MAX_RESUME_CHARS = 3000
MAX_REFERENCE_CONTEXT_CHARS = 6000
EVALUATION_BATCH_SIZE = 8
MAX_MERGED_LIST_ITEMS = 8
MAX_QUESTION_HIGHLIGHTS = 20

_QUESTION_TRUNCATE = 50
_FEEDBACK_TRUNCATE = 80

_NO_EVAL_FEEDBACK = "该题未成功生成质检结果，系统按 0 分处理。"
_NO_FEEDBACK = "该题未成功生成质检反馈。"
_DEFAULT_OVERALL_FEEDBACK = "本次质检已完成分批评估，但未生成有效综合评语。"

# 标记"需人工复核"的置信度取值
NEEDS_REVIEW_CONFIDENCE = "low"


def truncate_context(text: str | None, limit: int = MAX_RESUME_CHARS) -> str:
    """会话上下文超长截断，保留前 limit 字符并追加截断标记。"""
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...(内容过长，已截断)"


def truncate_reference(text: str | None, limit: int = MAX_REFERENCE_CONTEXT_CHARS) -> str:
    """知识基线超长截断；None 返回空串。"""
    if not text:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...(知识基线过长，已截断)"


def build_qa_records_text(batch: list[QaRecord]) -> str:
    """构建 prompt 用的问答记录文本。"""
    parts: list[str] = []
    for q in batch:
        answer = q.user_answer if q.user_answer else "(坐席未应答)"
        parts.append(f"问题{q.question_index + 1} [{q.category}]: {q.question}\n坐席应答: {answer}\n")
    return "\n".join(parts)


def split_batches(qa_records: list[QaRecord], batch_size: int = EVALUATION_BATCH_SIZE) -> list[QaBatch]:
    """将问答记录按 batch_size 分批，记录每批在原列表中的起止下标。"""
    if not qa_records:
        return []
    size = max(1, batch_size)
    batches: list[QaBatch] = []
    for start in range(0, len(qa_records), size):
        end = min(start + size, len(qa_records))
        batches.append(QaBatch(start_index=start, end_index=end, records=list(qa_records[start:end])))
    return batches


def merge_question_evaluations(batch_results: list[BatchResult]) -> list[QuestionEvaluationItem]:
    """合并各批次逐题评估，缺失项补零分。"""
    merged: list[QuestionEvaluationItem] = []
    for result in batch_results:
        expected = result.end_index - result.start_index
        current = result.report.question_evaluations if result.report else []
        for i in range(expected):
            if i < len(current):
                merged.append(current[i])
            else:
                merged.append(
                    QuestionEvaluationItem(
                        question_index=result.start_index + i,
                        score=0,
                        feedback=_NO_EVAL_FEEDBACK,
                        reference_answer="",
                        key_points=[],
                        confidence="low",
                        needs_review=True,
                    )
                )
    return merged


def merge_overall_feedback(batch_results: list[BatchResult]) -> str:
    """拼接各批次非空评语；全空时返回默认提示。"""
    feedback = "\n\n".join(
        r.report.overall_feedback
        for r in batch_results
        if r.report and r.report.overall_feedback and r.report.overall_feedback.strip()
    )
    return feedback if feedback else _DEFAULT_OVERALL_FEEDBACK


def merge_list_items(batch_results: list[BatchResult], strengths_mode: bool) -> list[str]:
    """合并 strengths/improvements：去重保序、限 MAX_MERGED_LIST_ITEMS 条。"""
    seen: set[str] = set()
    merged: list[str] = []
    for result in batch_results:
        report = result.report
        if report is None:
            continue
        items = report.strengths if strengths_mode else report.improvements
        if not items:
            continue
        for item in items:
            if not item or not item.strip():
                continue
            cleaned = item.strip()
            if cleaned not in seen:
                seen.add(cleaned)
                merged.append(cleaned)
                if len(merged) >= MAX_MERGED_LIST_ITEMS:
                    return merged
    return merged


def build_category_summary(
    qa_records: list[QaRecord],
    evaluations: list[QuestionEvaluationItem],
) -> str:
    """构建二次汇总 prompt 用的分类得分概览（仅已答计入平均分）。"""
    scores_by_category: dict[str, list[int]] = {}
    for i, q in enumerate(qa_records):
        if not q.user_answer:
            continue
        score = evaluations[i].score if i < len(evaluations) else 0
        scores_by_category.setdefault(q.category, []).append(score)
    lines = [
        f"- {cat}: 平均分 {int(sum(scores) / len(scores))}, 题数 {len(scores)}"
        for cat, scores in sorted(scores_by_category.items())
    ]
    return "\n".join(lines)


def build_question_highlights(
    qa_records: list[QaRecord],
    evaluations: list[QuestionEvaluationItem],
) -> str:
    """构建二次汇总 prompt 用的题目高亮（截断长问题/反馈，限 MAX_QUESTION_HIGHLIGHTS 条）。"""
    highlights: list[str] = []
    for i, q in enumerate(qa_records):
        if len(highlights) >= MAX_QUESTION_HIGHLIGHTS:
            break
        eval_item = evaluations[i] if i < len(evaluations) else None
        score = eval_item.score if eval_item else 0
        feedback = eval_item.feedback if eval_item and eval_item.feedback else ""
        short_q = q.question[:_QUESTION_TRUNCATE] + "..." if len(q.question) > _QUESTION_TRUNCATE else q.question
        short_f = feedback[:_FEEDBACK_TRUNCATE] + "..." if len(feedback) > _FEEDBACK_TRUNCATE else feedback
        highlights.append(f"- Q{q.question_index + 1} | {short_q} | 分数:{score} | 反馈:{short_f}")
    return "\n".join(highlights)


def compute_category_scores(details: list[QuestionEvaluation]) -> list[CategoryScore]:
    """计算分类平均分（仅已答计入分母）。空 category 统一为 '未知'。"""
    scores_by_category: dict[str, list[int]] = {}
    for d in details:
        if not d.user_answer:
            continue
        cat = d.category or "未知"
        scores_by_category.setdefault(cat, []).append(d.score)
    return [
        CategoryScore(
            category=cat,
            score=int(sum(scores) / len(scores)),
            question_count=len(scores),
        )
        for cat, scores in scores_by_category.items()
    ]


def aggregate_missing_evidence(
    qa_records: list[QaRecord],
    evaluations: list[QuestionEvaluationItem],
    degraded_reasons: list[str],
) -> list[str]:
    """聚合缺失证据段（准则 3）：确定性部分 + LLM 逐题缺失证据。

    确定性来源：
    - 批次 LLM 失败（degraded_reasons）→ 该批题目未成功评分
    - 单题置信度 low（needs_review）→ 该题评分自信不足，需人工复核
    - 坐席未应答（user_answer 为空）→ 该题无坐席应答可评
    LLM 逐题缺失证据存于 reference_answer 空白时由 feedback 兜底，此处不作拼接，
    保持"缺失证据"为确定性可审计信号（避免放空话）。
    """
    evidence: list[str] = []
    for reason in degraded_reasons:
        evidence.append(f"批次评分失败，未能逐题验证：{reason}")
    for i, q in enumerate(qa_records):
        eval_item = evaluations[i] if i < len(evaluations) else None
        if not q.user_answer:
            evidence.append(f"题 {q.question_index + 1} 无坐席应答，无法评分验证。")
        elif eval_item and eval_item.needs_review:
            evidence.append(f"题 {q.question_index + 1} 评分置信度不足，需人工复核。")
    # 去重保序
    seen: set[str] = set()
    result: list[str] = []
    for item in evidence:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def build_report(
    session_id: str,
    qa_records: list[QaRecord],
    evaluations: list[QuestionEvaluationItem],
    summary: Summary,
    degraded_reasons: list[str] | None = None,
) -> EvaluationReport:
    """组装最终质检报告。

    overall_score = 已答平均分（未答不计入分母）；全未答时为 0。
    """
    question_details: list[QuestionEvaluation] = []
    reference_answers: list[ReferenceAnswer] = []
    degraded = list(degraded_reasons or [])

    for i, q in enumerate(qa_records):
        eval_item = evaluations[i] if i < len(evaluations) else None
        has_answer = bool(q.user_answer)
        score = eval_item.score if (has_answer and eval_item) else 0
        feedback = eval_item.feedback if (eval_item and eval_item.feedback) else _NO_FEEDBACK
        ref_answer = eval_item.reference_answer if (eval_item and eval_item.reference_answer) else ""
        key_points = eval_item.key_points if eval_item else []
        confidence = eval_item.confidence if eval_item else "high"
        needs_review = bool(eval_item and eval_item.needs_review)

        question_details.append(
            QuestionEvaluation(
                question_index=q.question_index,
                question=q.question,
                category=q.category,
                user_answer=q.user_answer,
                score=score,
                feedback=feedback,
                confidence=confidence,
                needs_review=needs_review,
            )
        )
        reference_answers.append(
            ReferenceAnswer(
                question_index=q.question_index,
                question=q.question,
                reference_answer=ref_answer,
                key_points=list(key_points),
            )
        )

    category_scores = compute_category_scores(question_details)

    answered_count = sum(1 for q in qa_records if q.user_answer)
    overall_score = int(sum(d.score for d in question_details) / answered_count) if answered_count else 0

    missing_evidence = aggregate_missing_evidence(qa_records, evaluations, degraded)
    needs_review_count = sum(1 for i, q in enumerate(qa_records)
                             if (evaluations[i] if i < len(evaluations) else None)
                             and evaluations[i].needs_review)

    return EvaluationReport(
        session_id=session_id,
        total_questions=len(qa_records),
        overall_score=overall_score,
        category_scores=category_scores,
        question_details=question_details,
        overall_feedback=summary.overall_feedback,
        strengths=list(summary.strengths),
        improvements=list(summary.improvements),
        reference_answers=reference_answers,
        missing_evidence=missing_evidence,
        needs_review_count=needs_review_count,
        degraded_reasons=degraded,
    )