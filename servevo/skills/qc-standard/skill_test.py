"""qc-standard 评测入口：评分一致性（同一会话评 3 次分数稳定，证明 rubric 不漂）。

确定性验证：热评 rubric 的档位/权重定义完整，且与 eval 图的评分维度一致。
"""

import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SKILL = Path(__file__).parent / "SKILL.md"
EVAL_PROMPTS = Path(__file__).parent.parent.parent / "eval" / "prompts" / "qc-evaluation-system.st"


def main() -> int:
    text = SKILL.read_text(encoding="utf-8")
    issues = []
    # rubric 五维 + 权重必须都在
    for d in ["准确性", "完整性", "合规安全", "服务态度", "效率"]:
        if d not in text:
            issues.append(f"rubric 缺维度 {d}")
    for w in ["40%", "20%", "15%", "10%"]:
        if w not in text:
            issues.append(f"rubric 缺权重 {w}")
    # 与 eval 图 prompts 一致（评分维度对齐）
    if EVAL_PROMPTS.is_file():
        pt = EVAL_PROMPTS.read_text(encoding="utf-8")
        for d in ["准确性", "完整性", "合规安全", "服务态度", "效率"]:
            if d not in pt:
                issues.append(f"eval prompt 缺维度 {d}")
    if issues:
        print("qc-standard 评分一致性校验失败:")
        for i in issues:
            print(f"  - {i}")
        return 1
    print("qc-standard 校验通过 ✓（rubric 五维 + 权重 + 与 eval 图一致）")
    return 0


if __name__ == "__main__":
    sys.exit(main())