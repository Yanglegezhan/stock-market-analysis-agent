"""统一错误响应格式"""
from dataclasses import dataclass
from typing import Optional, List, Any
from enum import Enum


class ErrorCode(str, Enum):
    """错误代码"""
    # 配置错误
    CONFIG_INVALID = "CONFIG_INVALID"
    API_KEY_MISSING = "API_KEY_MISSING"
    MODEL_NOT_SUPPORTED = "MODEL_NOT_SUPPORTED"
    
    # API错误
    LLM_API_ERROR = "LLM_API_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    TIMEOUT = "TIMEOUT"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    
    # 响应错误
    RESPONSE_PARSE_ERROR = "RESPONSE_PARSE_ERROR"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    
    # 通用错误
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


@dataclass
class ErrorResponse:
    """统一错误响应格式"""
    success: bool
    error_code: str
    error_message: str
    suggestions: List[str]
    retryable: bool = False
    raw_error: Optional[Any] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "suggestions": self.suggestions,
            "retryable": self.retryable,
        }

    @classmethod
    def from_exception(cls, e: Exception) -> "ErrorResponse":
        """从异常创建错误响应"""
        error_str = str(e).lower()
        
        # 识别错误类型
        if "api_key" in error_str or "authentication" in error_str or "401" in error_str:
            return cls(
                success=False,
                error_code=ErrorCode.API_KEY_MISSING.value,
                error_message="API密钥无效或缺失",
                suggestions=["请检查API密钥是否正确", "确认API密钥是否已过期"],
                retryable=False,
                raw_error=e
            )
        elif "rate limit" in error_str or "429" in error_str:
            return cls(
                success=False,
                error_code=ErrorCode.RATE_LIMIT_EXCEEDED.value,
                error_message="API调用频率超限",
                suggestions=["请稍后重试", "考虑降低调用频率"],
                retryable=True,
                raw_error=e
            )
        elif "timeout" in error_str:
            return cls(
                success=False,
                error_code=ErrorCode.TIMEOUT.value,
                error_message="API调用超时",
                suggestions=["请检查网络连接", "尝试增加timeout配置"],
                retryable=True,
                raw_error=e
            )
        elif "connection" in error_str:
            return cls(
                success=False,
                error_code=ErrorCode.CONNECTION_ERROR.value,
                error_message="网络连接错误",
                suggestions=["请检查网络连接", "确认API地址是否正确"],
                retryable=True,
                raw_error=e
            )
        else:
            return cls(
                success=False,
                error_code=ErrorCode.UNKNOWN_ERROR.value,
                error_message=str(e),
                suggestions=["请查看详细错误信息"],
                retryable=False,
                raw_error=e
            )
