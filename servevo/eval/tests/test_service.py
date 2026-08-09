"""质检评估纯函数单测：分批 / 合并 / 缺失证据 / 报告组装。"""

from __future__ import annotations

from servevo_eval.entities import (
    BatchReport,
    BatchResult,
    QaRecord,
    QuestionEvaluationItem,
    Summary,
)
from servevo_eval.service import (
    aggregate_missing_evidence,
    build_category_summary,
    build_report,
    compute_category_scores,
    merge_list_items,
    merge_question_evaluations,
    merge_overall_feedback,
    split_batches,
)


def _qa(n: int = 3, start: int = 0) -> list[QaRecord]:
    return [
        QaRecord(
            question_index=start + i,
            question=f"问题{i}",
            category="保修",
            user_answer=f"答案{i}",
        )
        for i in range(n)
    ]


def test_split_batches_sizes():
    batches = split_batches(_qa(10), batch_size=4)
    assert [b.end_index - b.start_index for b in batches] == [4, 4, 2]
    assert batches[0].start_index == 0 and batches[-1].end_index == 10


def test_split_batches_empty():
    assert split_batches([]) == []


def test_merge_question_evaluations_dedup_and_zero_fill():
    results = [
        BatchResult(
            start_index=0,
            end_index=2,
            report=BatchReport(
                overall_score=80,
                overall_feedback="好",
                strengths=["s1"],
                improvements=["i1"],
                question_evaluations=[
                    QuestionEvaluationItem(question_index=0, score=90, feedback="ok", reference_answer=""),
                ],
            ),
        ),
        BatchResult(start_index=2, end_index=4, report=None),
    ]
    merged = merge_question_evaluations(results)
    assert len(merged) == 4
    assert merged[0].score == 90
    assert merged[1].score == 0 and merged[1].needs_review  # 缺失补零需人工复核
    assert merged[2].score == 0 and merged[2].needs_review  # 失败批次补零


def test_merge_overall_feedback_default():
    assert merge_overall_feedback([])  # 非空默认提示


def test_merge_list_items_dedup_limit():
    items = [
        BatchResult(0, 1, BatchReport(0, "", ["a", "a", "b"], ["x"], [])),
        BatchResult(1, 2, BatchReport(0, "", ["c", "d", "e", "f", "g", "h", "i", "j"], ["y"], [])),
    ]
    strengths = merge_list_items(items, strengths_mode=True)
    assert strengths == ["a", "b", "c", "d", "e", "f", "g", "h"]  # 去重保序 + 限 8 条


def test_build_category_summary():
    qa = [QaRecord(0, "q", "保修", "a"), QaRecord(1, "q2", "保修", None), QaRecord(2, "q3", "价格", "a")]
    evals = [
        QuestionEvaluationItem(0, 80, "", ""),
        QuestionEvaluationItem(1, 0, "", ""),
        QuestionEvaluationItem(2, 60, "", ""),
    ]
    text = build_category_summary(qa, evals)
    assert "保修: 平均分 80" in text
    assert "价格: 平均分 60" in text


def test_compute_category_scores_only_answered():
    # 不走 build_report，直接用 QuestionEvaluation 构造
    from servevo_eval.entities import QuestionEvaluation

    details = [
        QuestionEvaluation(0, "q", "保修", "a", 80, ""),
        QuestionEvaluation(1, "q2", "保修", None, 0, ""),  # 未答不计入
    ]
    scores = compute_category_scores(details)
    assert scores[0].category == "保修"
    assert scores[0].score == 80 and scores[0].question_count == 1


def test_report_zero_fill_and_missing_evidence():
    qa = _qa(2)
    evals = [
        QuestionEvaluationItem(0, 60, "ok", "", confidence="low", needs_review=True),
        QuestionEvaluationItem(1, 0, "", "", confidence="low", needs_review=True),
    ]
    report = build_report(
        session_id="s1",
        qa_records=qa,
        evaluations=evals,
        summary=Summary("g", ["s"], ["i"]),
        degraded_reasons=["批次[0,2): timeout"],
    )
    assert report.overall_score == 30  # (60+0)/2
    assert report.total_questions == 2
    assert any("批次评分失败" in m for m in report.missing_evidence)
    assert report.needs_review_count == 2
    assert report.degraded_reasons == ["批次[0,2): timeout"]


def test_report_no_answer_zero_and_evidence():
    qa = [QaRecord(0, "q", "保修", None)]
    evals = [QuestionEvaluationItem(0, 0, "", "", confidence="low", needs_review=True)]
    report = build_report("s", qa, evals, Summary.empty())
    assert report.overall_score == 0
    assert any("无坐席应答" in m for m in report.missing_evidence)


def test_aggregate_missing_evidence_dedup():
    qa = [QaRecord(0, "q", "保修", None)]
    evals = [QuestionEvaluationItem(0, 0, "", "", needs_review=True)]
    out = aggregate_missing_evidence(qa, evals, [])
    assert len(out) == 1  # 无应答，不重复计 needs_review
    assert "无坐席应答" in out[0]