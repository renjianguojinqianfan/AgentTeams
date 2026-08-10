"""Team 配置校验：team.yaml + 4 份 worker YAML 可解析、结构完整。

规则：
- team.yaml：恰一个 team_leader，其余 worker；可含人类 coordinator
- 每 worker：name 对应 SOUL 文件存在；identity/soul/agents 齐全
"""

import sys
import yaml
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

TEAM_DIR = Path(__file__).parent.parent
YAMLS = TEAM_DIR / "yamls"
SOULS = TEAM_DIR / "souls"

EXPECTED_WORKERS = ["servevo-leader", "servevo-cs", "servevo-qc", "servevo-coach"]


def main() -> int:
    issues = []
    # team.yaml
    team = yaml.safe_load((YAMLS / "team.yaml").read_text(encoding="utf-8"))
    members = team.get("spec", {}).get("workerMembers", [])
    leaders = [m for m in members if m.get("role") == "team_leader"]
    if len(leaders) != 1:
        issues.append(f"team.yaml 需恰一个 team_leader，实际 {len(leaders)}")
    names = [m.get("name") for m in members]
    if sorted(names) != sorted(EXPECTED_WORKERS):
        issues.append(f"team workerMembers 缺/多: {names}")

    # worker YAML
    for name in EXPECTED_WORKERS:
        wf = YAMLS / f"{name}.yaml"
        if not wf.is_file():
            issues.append(f"缺 {name}.yaml")
            continue
        w = yaml.safe_load(wf.read_text(encoding="utf-8"))
        spec = w.get("spec", {})
        for field in ["runtime", "model", "identity", "soul", "agents"]:
            if field not in spec:
                issues.append(f"{name}: 缺 spec.{field}")
        # 官方 CRD：identity/soul/agents 均为 string（内联内容），须防止嵌套对象回归
        for field in ["identity", "soul", "agents"]:
            val = spec.get(field)
            if not isinstance(val, str):
                issues.append(f"{name}: spec.{field} 应为 string（官方 CRD 类型），当前是 {type(val).__name__}")
        soul = spec.get("soul")
        if soul and "# SOUL.md" not in soul:
            issues.append(f"{name}: spec.soul 应内联 SOUL.md 内容（含 '# SOUL.md' 头）而非文件名")

    if issues:
        print("Team 配置校验失败:")
        for i in issues:
            print(f"  - {i}")
        return 1
    print("Team 配置校验通过 ✓（team + 4 worker + SOUL 齐全）")
    return 0


if __name__ == "__main__":
    sys.exit(main())