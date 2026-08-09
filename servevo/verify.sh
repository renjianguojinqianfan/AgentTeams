#!/usr/bin/env bash
# servevo 统一质量闸门（对应 PBH harness 的 `make verify`）。
# 一键：4 模块单测全绿 + 密钥枯死检查 + 零侵入核对。
# 用法: bash servevo/verify.sh
set -euo pipefail

# 固定用 interview-agent venv（宿主无 langgraph 等依赖）
PY="${SERVEVO_PY:-E:/code/interview-agent/interview-agent-python/backend/.venv/Scripts/python.exe}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
# 转 Windows 路径（Git-Bash 的 /e/... Python 读不了）
if command -v cygpath >/dev/null 2>&1; then
    WROOT="$(cygpath -w "$ROOT")"
else
    WROOT="$ROOT"
fi

echo "== 1/4 单测：rag =="
MSYS2_ARG_CONV_EXCL='*' PYTHONPATH="$WROOT/rag" "$PY" -m pytest "$WROOT/rag/tests" -q

echo "== 2/4 单测：eval =="
MSYS2_ARG_CONV_EXCL='*' PYTHONPATH="$WROOT/eval;$WROOT/rag" "$PY" -m pytest "$WROOT/eval/tests" -q

echo "== 3/4 单测：coach =="
MSYS2_ARG_CONV_EXCL='*' PYTHONPATH="$WROOT/coach;$WROOT/eval;$WROOT/rag" "$PY" -m pytest "$WROOT/coach/tests" -q

echo "== 4/4 单测：audit =="
MSYS2_ARG_CONV_EXCL='*' PYTHONPATH="$WROOT/audit" "$PY" -m pytest "$WROOT/audit/tests" -q

echo "== 密钥枯死检查（禁止硬编码 key）=="
if grep -rnE "sk-[A-Za-z0-9]{16,}|AGENTTEAMS_LLM_API_KEY=[A-Za-z0-9]" "$ROOT" --include="*.py" --include="*.md" --include="*.sh" 2>/dev/null | grep -v "\.venv\|/tmp/\|\.pytest_cache" ; then
    echo "!! 发现疑似硬编码密钥" >&2
    exit 1
fi
echo "无硬编码密钥 ✓"

echo "== 零侵入核对（servevo/ 外官方文件不得被改动）=="
cd "$ROOT/.."
if [ -n "$(git status --short -- . ':!servevo' 2>/dev/null)" ]; then
    echo "!! 检测到 servevo/ 外改动（违反零侵入红线）" >&2
    git status --short -- . ':!servevo'
    exit 1
fi
echo "零侵入 ✓"

echo ""
echo "✅ servevo verify 全部通过"