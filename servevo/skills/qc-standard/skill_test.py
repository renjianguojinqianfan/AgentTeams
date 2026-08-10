"""qc-standard 评测入口：真实跑 eval 评分链路（确定性假数据，无 LLM/网络）。

证明 qc-standard Skill 声明的评分能力真实可运行——不是只查文档关键词。
用 eval 模块的确定性纯函数 build_report，对按 qc-standard rubric 五维构造的
问答跑一次，断言产出完整报告（总体分/分类分/逐题分/缺失证据段）。
"""

import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# 复用 eval 模块（评分实现）
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "eval"))
from servevo_eval.entities import (  # noqa: E402
    QaRecord,
    QuestionEvaluationItem,
    Summary,
)
from servevo_eval.service import build_report  # noqa: E402


def main() -> int:
    issues = []

    # 1. SKILL.md 必须声明 rubric 五维（文档契约）
    text = (Path(__file__).parent / "SKILL.md").read_text(encoding="utf-8")
    for d in ["准确性", "完整性", "合规安全", "服务态度", "效率"]:
        if d not in text:
            issues.append(f"SKILL.md 缺 rubric 维度 {d}")

    # 2. 真实跑 eval 评分链路：按 rubric 五维造 3 题（1 题未应答），跑 build_report
    qa = [
        QaRecord(0, "K2 保修多久", "保修", "整机保修 1 年，自签收起算"),
        QaRecord(1, "K2 功率参数", "产品", "功率 1450W，水箱 2.0L"),
        QaRecord(2, "价格优惠", "价格", None),  # 未应答
    ]
    evals = [
        QuestionEvaluationItem(0, 90, "准确", ["保修1年"], "high", False),
        QuestionEvaluationItem(1, 80, "完整", ["1450W"], "high", False),
        QuestionEvaluationItem(2, 0, "", [], "low", True),  # 未应答补零
    ]
    report = build_report("qc-standard-selfcheck", qa, evals, Summary("", [], []))

    # 评分链路真实产出：总体分 / 分类分 / 逐题分 / 缺失证据
    if report.total_questions != 3:
        issues.append(f"评分链路题数异常: {report.total_questions}")
    if report.overall_score <= 0:
        issues.append(f"评分链路未产出有效总体分: {report.overall_score}")
    if not report.category_scores:
        issues.append("评分链路未产出分类分")
    if len(report.question_details) != 3:
        issues.append("评分链路未产出逐题分")
    if not report.missing_evidence:
        issues.append("评分链路未产出缺失证据段（未应答题应触发）")

    if issues:
        print("qc-standard 真实评测失败:")
        for i in issues:
            print(f"  - {i}")
        return 1
    print(
        f"qc-standard 真实评测通过 ✓（rubric 五维 + 评分链路产出总体分 {report.overall_score} / "
        f"分类 {len(report.category_scores)} / 逐题 {len(report.question_details)} / 缺失证据 {len(report.missing_evidence)}）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
