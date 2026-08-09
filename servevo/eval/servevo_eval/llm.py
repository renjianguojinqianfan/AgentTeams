"""LLM 通道：Higress OpenAI 兼容（同 servevo_rag.llm，供质检评估复用）。

只用环境变量配置（红线：代码/文档禁止硬编码 key）。
"""

from __future__ import annotations

import os

from langchain_openai import ChatOpenAI

_CONNECT_TIMEOUT = 10
_READ_TIMEOUT = 300
_TEMPERATURE = 0.2


def create_chat_client() -> ChatOpenAI:
    """按环境变量创建 OpenAI 兼容客户端。"""
    return ChatOpenAI(
        model=os.environ.get("LLM_MODEL", "qwen3.7-flash"),
        base_url=os.environ.get("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        api_key=os.environ.get("LLM_API_KEY", ""),
        temperature=_TEMPERATURE,
        timeout=_READ_TIMEOUT,
        max_retries=2,
        request_timeout=_CONNECT_TIMEOUT,
        stream=False,
    )


def is_configured() -> bool:
    """LLM 是否配置（无 key 时图可降级为确定性报告）。"""
    return bool(os.environ.get("LLM_API_KEY") or os.environ.get("LLM_BASE_URL", "").startswith("http"))