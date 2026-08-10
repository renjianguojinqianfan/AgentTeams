"""regression-verify 评测入口：自测（对已知答案集）。

确定性验证：测试集存在且结构完整（50 题、5 缺口题、id 唯一）。
"""

import sys
import json
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

TEST = Path(__file__).parent.parent.parent / "regression" / "testset" / "cafe-testset-v1.json"


def main() -> int:
    issues = []
    if not TEST.is_file():
        print("regression-verify 校验失败：缺测试集 cafe-testset-v1.json")
        return 1
    data = json.loads(TEST.read_text(encoding="utf-8"))
    qs = data.get("questions", [])
    if len(qs) != 50:
        issues.append(f"测试集题数 {len(qs)} != 50")
    if sum(1 for q in qs if q.get("gap")) != 5:
        issues.append("缺口题数 != 5")
    ids = [q["id"] for q in qs]
    if len(ids) != len(set(ids)):
        issues.append("id 重复")
    if issues:
        print("regression-verify 自测失败:")
        for i in issues:
            print(f"  - {i}")
        return 1
    print("regression-verify 校验通过 ✓（50 题 / 5 缺口 / id 唯一）")
    return 0


if __name__ == "__main__":
    sys.exit(main())