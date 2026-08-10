"""coach-scenario 评测入口：真实跑 coach 陪练逻辑（确定性，无 LLM/网络）。

证明 coach-scenario Skill 声明的能力真实可运行——不是只查文档关键词。
用 coach 的确定性纯函数 build_knowledge_revisions 跑一遍：构造含低分题的
陪练历史，断言产出知识修订草案（验证"剧本暴露缺口 → 产出修订草案"真实生效）。
"""

import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# 复用 coach 模块（陪练实现）
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "coach"))
from servevo_coach.strategy import build_knowledge_revisions  # noqa: E402


def main() -> int:
    issues = []

    # 1. SKILL.md 必须声明 6 考察维度 + 4 剧本类型（文档契约）
    text = (Path(__file__).parent / "SKILL.md").read_text(encoding="utf-8")
    for cat in ["产品", "保修", "退换货", "价格", "政策", "故障"]:
        if cat not in text:
            issues.append(f"SKILL.md 缺剧本考察维度 {cat}")
    for t in ["知识缺口陷阱", "合规陷阱", "多要点误导", "转人工判断"]:
        if t not in text:
            issues.append(f"SKILL.md 缺剧本类型 {t}")

    # 2. 真实跑 coach 陪练逻辑：低分题 → 知识修订草案
    history = [
        {"category": "保修", "scenario": "K2 现在保修多久？", "score": 3, "feedback": "答错保修期"},
        {"category": "故障", "scenario": "K2 不出水怎么排查？", "score": 9, "feedback": "答对"},
        {"category": "价格", "scenario": "K2 现在价格多少？", "score": 2, "feedback": "报错价格"},
    ]
    revisions = build_knowledge_revisions(history)
    if len(revisions) != 2:
        issues.append(f"陪练历史应产出 2 条修订草案（2 低分题），实际 {len(revisions)}")
    if not any(r.target_section == "warranty-policy" for r in revisions):
        issues.append("保修类草案未映射到 warranty-policy 文件")
    if not any(r.target_section == "products" for r in revisions):
        issues.append("价格类草案未映射到 products 文件")

    if issues:
        print("coach-scenario 真实评测失败:")
        for i in issues:
            print(f"  - {i}")
        return 1
    print(
        f"coach-scenario 真实评测通过 ✓（6 维度 + 4 剧本类型 + 陪练产出修订草案 {len(revisions)} 条）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
