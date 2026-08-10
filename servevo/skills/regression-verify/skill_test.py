"""regression-verify 评测入口：自测（对已知答案集）。

确定性验证：
1. 测试集存在且结构完整（50 题、5 缺口题、id 唯一）
2. 实际跑 compare()：构造 v1（缺口未解决）→ v2（缺口解决）指标，断言进化判定正确
   证明"各 Skill 独立评测入口"可运行，非仅元数据检查。
"""

import sys
import json
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "regression"))
from servevo_regression.compare import RunMetrics, compare  # noqa: E402

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

    # 真实跑 compare()：确定性验证进化判定
    v1 = RunMetrics("v1", 0.7, 0.3, 65.0, 0.7, gap_detected=5)
    v2 = RunMetrics("v2", 0.95, 0.05, 85.0, 0.95, gap_detected=0)
    verdict = compare(v1, v2).verdict
    if verdict != "进化达标":
        issues.append(f"compare() 进化判定错误: {verdict}")

    if issues:
        print("regression-verify 自测失败:")
        for i in issues:
            print(f"  - {i}")
        return 1
    print("regression-verify 校验通过 ✓（50 题 / 5 缺口 / compare 进化判定正确）")
    return 0


if __name__ == "__main__":
    sys.exit(main())