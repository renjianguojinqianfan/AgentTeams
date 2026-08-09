#!/usr/bin/env bash
# 一键质检示例：跑一个示例会话 → 输出可读质检报告
# 用法: bash scripts/demo_eval.sh   （可选带 LLM env 走真模型，无则纯降级报告）
set -euo pipefail

PY="E:/code/interview-agent/interview-agent-python/backend/.venv/Scripts/python.exe"
EVAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
KB="${EVAL_DIR}/../knowledge/product-knowledge/v1/references"
QA="${EVAL_DIR}/scripts/sample_qa.json"

cd "$EVAL_DIR"
MSYS2_ARG_CONV_EXCL='*' PYTHONPATH="$EVAL_DIR" \
  "$PY" -m servevo_eval.cli evaluate --qa "$QA" --kb "$KB"