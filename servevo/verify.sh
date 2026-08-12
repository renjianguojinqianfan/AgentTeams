#!/usr/bin/env bash
# servevo 统一质量闸门（对应 PBH harness 的 `make verify`）。
# 一键：7 模块单测全绿 + Skills 评测 + Team 校验 + 密钥枯死检查 + 零侵入核对。
# 用法: bash servevo/verify.sh [--fast]
#   --fast: 仅单测（hook pre-commit / make test 用，跳过重量检查）
set -euo pipefail

FAST=0
if [ "${1:-}" = "--fast" ] || [ "${1:-}" = "-f" ]; then
    FAST=1
fi

# 固定用 interview-agent venv（宿主无 langgraph 等依赖）
PY="${SERVEVO_PY:-E:/code/interview-agent/interview-agent-python/backend/.venv/Scripts/python.exe}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
# 转 Windows 路径（Git-Bash 的 /e/... Python 读不了）
if command -v cygpath >/dev/null 2>&1; then
    WROOT="$(cygpath -w "$ROOT")"
else
    WROOT="$ROOT"
fi

echo "== 1/7 单测：rag =="
MSYS2_ARG_CONV_EXCL='*' PYTHONPATH="$WROOT/rag" "$PY" -m pytest "$WROOT/rag/tests" -q

echo "== 2/7 单测：eval =="
MSYS2_ARG_CONV_EXCL='*' PYTHONPATH="$WROOT/eval;$WROOT/rag" "$PY" -m pytest "$WROOT/eval/tests" -q

echo "== 3/7 单测：coach =="
MSYS2_ARG_CONV_EXCL='*' PYTHONPATH="$WROOT/coach;$WROOT/eval;$WROOT/rag" "$PY" -m pytest "$WROOT/coach/tests" -q

echo "== 4/7 单测：audit =="
MSYS2_ARG_CONV_EXCL='*' PYTHONPATH="$WROOT/audit" "$PY" -m pytest "$WROOT/audit/tests" -q

echo "== 5/7 单测：regression =="
MSYS2_ARG_CONV_EXCL='*' PYTHONPATH="$WROOT/regression;$WROOT/rag;$WROOT/eval" "$PY" -m pytest "$WROOT/regression/tests" -q

echo "== 6/7 单测：registry =="
MSYS2_ARG_CONV_EXCL='*' PYTHONPATH="$WROOT/registry" "$PY" -m pytest "$WROOT/registry/tests" -q

echo "== 7/7 单测：observability =="
MSYS2_ARG_CONV_EXCL='*' PYTHONPATH="$WROOT/observability" "$PY" -m pytest "$WROOT/observability/tests" -q

echo "== Skills 评测入口（四类 SKILL.md + skill_test）=="
# 避免向 venv 写 __pycache__（写保护环境用 -B + pycache 重定向）
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="${SERVEVO_PYCACHE:-$TMPDIR/servevo-pycache}"
"$PY" -B "$WROOT/skills/skill_test.py"
MSYS2_ARG_CONV_EXCL='*' PYTHONPATH="$WROOT/eval" "$PY" -B "$WROOT/skills/qc-standard/skill_test.py"
MSYS2_ARG_CONV_EXCL='*' PYTHONPATH="$WROOT/coach;$WROOT/eval;$WROOT/rag" "$PY" -B "$WROOT/skills/coach-scenario/skill_test.py"
MSYS2_ARG_CONV_EXCL='*' PYTHONPATH="$WROOT/regression;$WROOT/rag;$WROOT/eval" "$PY" -B "$WROOT/skills/regression-verify/skill_test.py"

echo "== Team 配置校验（team + 4 worker + SOUL）=="
"$PY" "$WROOT/team/yamls/validate_team.py"

# 快速绊线模式（hook pre-commit / make test 用）：跳过密钥与零侵入重量检查
if [ "$FAST" = "1" ] || [ "${SERVEVO_FAST:-0}" = "1" ]; then
    echo ""
    echo "✅ servevo 单测通过（快速模式）"
    exit 0
fi

echo "== 闭环脚本诚实性检查（v1/v2 指标必须由真实应答推导，见 code-review HARD-1）=="
if grep -nE "resolution_metrics\([^)]*=[0-9]+" "$ROOT/scripts/closedloop_e2e.py" 2>/dev/null; then
    echo "!! closedloop_e2e.py 存在硬编码指标数字（违反'可验证的数据不是叙事'）" >&2
    exit 1
fi
if ! grep -q '"missing_evidence"' "$ROOT/scripts/closedloop_e2e.py" 2>/dev/null; then
    echo "!! closedloop_e2e.py 缺顶层缺失证据段（违反四准则③）" >&2
    exit 1
fi
echo "闭环脚本诚实性检查通过 ✓"

echo "== 密钥枯死检查（禁止硬编码 key）=="
if grep -rnE "sk-[A-Za-z0-9]{16,}|qwen-[A-Za-z0-9]{16,}|lk_live_[A-Za-z0-9]{16,}|AGENTTEAMS_LLM_API_KEY=[A-Za-z0-9]" "$ROOT" --include="*.py" --include="*.md" --include="*.sh" 2>/dev/null | grep -v "\.venv\|/tmp/\|\.pytest_cache" ; then
    echo "!! 发现疑似硬编码密钥" >&2
    exit 1
fi
echo "无硬编码密钥 ✓"

echo "== 零侵入核对（servevo/ 外改动须登记于 .intrusion-record.md，见 ADR-003）=="
cd "$ROOT/.."
OUTSIDE="$(git status --short -- . ':!servevo' 2>/dev/null)"
if [ -n "$OUTSIDE" ]; then
    # 提取改动路径，检查是否已在侵入记录中登记
    RECORD="$ROOT/.intrusion-record.md"
    UNRECORDED=""
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        # 取路径字段（git status --short: "XY path"，含引号需剥离）
        path="${line:3}"
        path="${path#\"}"; path="${path%\"}"
        if ! grep -qF "$path" "$RECORD" 2>/dev/null; then
            UNRECORDED="$UNRECORDED\n  $line"
        fi
    done <<< "$OUTSIDE"
    if [ -n "$UNRECORDED" ]; then
        echo "!! 存在未登记的 servevo/ 外改动（违反 ADR-003）：" >&2
        echo -e "$UNRECORDED" >&2
        echo "!! 请先在 servevo/.intrusion-record.md 登记，或回退改动" >&2
        exit 1
    fi
fi
echo "零侵入核对通过（无未登记的 servevo/ 外改动）✓"

echo ""
echo "✅ servevo verify 全部通过"