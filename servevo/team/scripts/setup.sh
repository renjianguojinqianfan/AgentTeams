#!/usr/bin/env bash
# servevo 一键建队：应用 team.yaml + 4 份 worker YAML（servevo-qc/cs/coach/leader）
# 前置：AgentTeams 已部署（agt 可用，Docker 运行中）
# 用法: bash servevo/team/scripts/setup.sh
set -euo pipefail

TEAM_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "== 检查 agt =="
if ! command -v agt >/dev/null 2>&1; then
    echo "!! 未找到 agt（需在 agentteams-controller 容器或已配置 PATH）" >&2
    echo "   可先进入容器：docker exec -it agentteams-controller bash 后重试" >&2
    exit 1
fi

echo "== 应用 Worker CR（4 角色）=="
for w in servevo-leader servevo-cs servevo-qc servevo-coach; do
    echo "  - $w"
    agt apply -f "$TEAM_DIR/yamls/$w.yaml" || echo "  !! $w 应用失败（可手动 agt apply）"
done

echo "== 应用 Team CR =="
agt apply -f "$TEAM_DIR/yamls/team.yaml" || echo "  !! team 应用失败"

echo ""
echo "✅ servevo Team 建队完成（4 Worker + 1 Coordinator）"
echo "   下一步：向 servevo 房间发一句话启动全流程，如："
echo "   '客户咨询 K2 保修期，请 servevo-cs 应答；若需进化请触发闭环并汇报指标。'"