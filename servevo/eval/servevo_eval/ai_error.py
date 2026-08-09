"""AI 服务异常分类：将 LLM SDK 异常映射到细分错误码（裁剪自 interview-agent ai_error.py）。

仅在识别到明确的 AI SDK 异常类型时返回对应错误码；无法识别返回 None。
"""

from __future__ import annotations

import openai

from .errors import ErrorCode


def classify_ai_error(exc: BaseException):
    """将 AI SDK 异常映射到 ErrorCode；无法识别返回 None（调用方兜底）。"""
    if isinstance(exc, (TimeoutError, openai.APITimeoutError)):
        return ErrorCode.AI_SERVICE_TIMEOUT
    if isinstance(exc, openai.RateLimitError):
        return ErrorCode.AI_RATE_LIMIT_EXCEEDED
    if isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return ErrorCode.AI_API_KEY_INVALID
    if isinstance(exc, openai.APIConnectionError):
        return ErrorCode.AI_SERVICE_UNAVAILABLE
    if isinstance(exc, openai.OpenAIError):
        return ErrorCode.AI_SERVICE_ERROR
    return None