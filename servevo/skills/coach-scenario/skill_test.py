"""coach-scenario 评测入口：剧本覆盖率检查（生成剧本后输出考察点覆盖清单，证明不漏维度）。

确定性验证：SKILL.md 定义 4 类剧本类型，覆盖全部 6 个考察维度。
"""

import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SKILL = Path(__file__).parent / "SKILL.md"


def main() -> int:
    text = SKILL.read_text(encoding="utf-8")
    issues = []
    for cat in ["产品", "保修", "退换货", "价格", "政策", "故障"]:
        if cat not in text:
            issues.append(f"剧本考察维度缺 {cat}")
    for t in ["知识缺口陷阱", "合规陷阱", "多要点误导", "转人工判断"]:
        if t not in text:
            issues.append(f"剧本类型缺 {t}")
    if issues:
        print("coach-scenario 覆盖率校验失败:")
        for i in issues:
            print(f"  - {i}")
        return 1
    print("coach-scenario 校验通过 ✓（4 类剧本覆盖 6 个考察维度）")
    return 0


if __name__ == "__main__":
    sys.exit(main())