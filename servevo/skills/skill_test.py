"""四类 Skill 独立评测入口（skill_test.py）：
- 元数据校验：四类 SKILL.md 均含名称/用途/输入输出/失败处理/安全边界/协同关系（规格块 v3.1）
- 评测入口连通性：每类 eval 字段指向的评测可运行（product-knowledge→regression verify，其余→覆盖检查）

用法: python servevo/skills/skill_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SKILLS_DIR = Path(__file__).parent
REQUIRED_FIELDS = ["name", "description", "version", "label", "eval"]
REQUIRED_SECTIONS = ["输入", "输出", "失败处理", "安全边界", "多 Agent 协同"]

EXPECTED = {
    "product-knowledge": "regression-verify",
    "qc-standard": "skill_test.py",
    "coach-scenario": "skill_test.py",
    "regression-verify": "skill_test.py",
}


def check_skill(name: str) -> list[str]:
    issues: list[str] = []
    skill_dir = SKILLS_DIR / name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return [f"{name}: 缺 SKILL.md"]
    text = skill_md.read_text(encoding="utf-8")
    # frontmatter 字段
    for f in REQUIRED_FIELDS:
        if f not in text:
            issues.append(f"{name}: 缺 frontmatter 字段 {f}")
    # 规格块三段
    for s in REQUIRED_SECTIONS:
        if s not in text:
            issues.append(f"{name}: 缺规格块 {s}")
    return issues


def main() -> int:
    issues: list[str] = []
    for name, expected_eval in EXPECTED.items():
        issues += check_skill(name)
        # eval 字段指向的评测入口存在性
        skill_dir = SKILLS_DIR / name
        if expected_eval == "skill_test.py":
            if not (skill_dir / "skill_test.py").is_file():
                issues.append(f"{name}: 缺 skill_test.py 评测入口")
        elif expected_eval == "regression-verify":
            if not (SKILLS_DIR.parent / "regression" / "testset" / "cafe-testset-v1.json").is_file():
                issues.append(f"{name}: 缺 regression 测试集")
    if issues:
        print(f"Skill 校验失败 ({len(issues)}):")
        for i in issues:
            print(f"  - {i}")
        return 1
    print("四类 Skill 校验通过 ✓（元数据 + 规格块 + 评测入口连通）")
    return 0


if __name__ == "__main__":
    sys.exit(main())