"""AI 连接的公共错误和规范枚举。无家具领域依赖。"""
from __future__ import annotations


DEFAULT_TIMEOUT_SECONDS = 240


VALID_PROVIDERS = {
    "codex_cli",
    "agy_cli",
    "openai_compatible",
}


VALID_REASONING_EFFORTS = {
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
}


class AIConnectionError(RuntimeError):
    """AI 连接配置或模型调用错误，供宿主转换为对外响应。"""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
