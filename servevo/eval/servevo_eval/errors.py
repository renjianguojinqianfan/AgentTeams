"""Servevo 最小错误码：仅质检评估所需子集（裁剪自 interview-agent domain/errors.py）。"""

from __future__ import annotations


class ErrorCode:
    INTERNAL_ERROR = "INTERNAL_ERROR"

    AI_SERVICE_UNAVAILABLE = "AI_SERVICE_UNAVAILABLE"
    AI_SERVICE_TIMEOUT = "AI_SERVICE_TIMEOUT"
    AI_SERVICE_ERROR = "AI_SERVICE_ERROR"
    AI_API_KEY_INVALID = "AI_API_KEY_INVALID"
    AI_RATE_LIMIT_EXCEEDED = "AI_RATE_LIMIT_EXCEEDED"

    QC_EVALUATION_FAILED = "QC_EVALUATION_FAILED"


class BusinessException(Exception):
    """带错误码的业务异常（供降级路径透传原因）。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message