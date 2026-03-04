"""LLM接口抽象层 - 基于OpenAI兼容接口"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class LLMProviderType(str, Enum):
    """LLM提供商类型 - 所有提供商使用OpenAI兼容接口"""
    ZHIPU = "zhipu"          # 智谱GLM
    OPENAI = "openai"        # OpenAI
    CLAUDE = "claude"        # Anthropic Claude (通过兼容接口)
    QWEN = "qwen"            # 阿里通义千问
    DEEPSEEK = "deepseek"    # DeepSeek
    GEMINI = "gemini"        # Google Gemini
    KIMI = "kimi"            # Moonshot Kimi
    MINIMAX = "minimax"      # MiniMax
    SILICONFLOW = "siliconflow"  # SiliconFlow
    ZHIPU_OPEN = "zhipu_open"  # 智谱开放平台 (与zhipu相同)
    CUSTOM = "custom"        # 自定义OpenAI兼容接口


# 预设的base_url配置 - 所有提供商使用OpenAI兼容接口
PROVIDER_BASE_URLS = {
    # 国内主流
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "kimi": "https://api.moonshot.cn/v1",
    "minimax": "https://api.minimax.chat/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "siliconflow": "https://api.siliconflow.cn/v1",

    # 国际主流
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",

    # 别名
    "moonshot": "https://api.moonshot.cn/v1",  # Kimi别名
    "zhipu_open": "https://open.bigmodel.cn/api/paas/v4",  # 智谱别名
}


# 预设的推荐模型配置
PROVIDER_MODELS = {
    "zhipu": ["glm-4", "glm-4-flash", "glm-4-plus", "glm-4-air"],
    "kimi": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
    "minimax": ["abab6.5-chat", "abab6.5s-chat", "abab5.5-chat"],
    "qwen": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long"],
    "deepseek": ["deepseek-chat", "deepseek-coder"],
    "siliconflow": ["deepseek-ai/DeepSeek-V3", "Qwen/Qwen2.5-72B-Instruct"],
    "openai": ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"],
    "gemini": ["gemini-pro", "gemini-1.5-pro", "gemini-1.5-flash"],
}


@dataclass
class LLMConfig:
    """LLM配置 - 所有提供商使用OpenAI兼容接口"""
    api_key: str
    model: str  # "glm-4", "gpt-4", "deepseek-chat", "qwen-max"等
    provider: str = "zhipu"  # 用于自动选择base_url
    base_url: Optional[str] = None  # 可自定义，覆盖provider默认值
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 60
    max_retries: int = 3
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """自动设置base_url"""
        if self.base_url is None:
            self.base_url = PROVIDER_BASE_URLS.get(self.provider)

    def validate(self) -> tuple[bool, Optional[str]]:
        """验证配置是否有效"""
        if not self.api_key:
            return False, "api_key不能为空"
        if not self.model:
            return False, "model不能为空"
        if not self.base_url:
            return False, "base_url不能为空，请指定provider或直接设置base_url"
        if self.temperature < 0 or self.temperature > 2:
            return False, "temperature必须在0-2之间"
        if self.max_tokens <= 0:
            return False, "max_tokens必须大于0"
        if self.timeout <= 0:
            return False, "timeout必须大于0"
        if self.max_retries < 0:
            return False, "max_retries不能为负数"
        return True, None


@dataclass
class LLMMessage:
    """LLM消息"""
    role: str  # "system", "user", "assistant"
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    usage: Dict[str, int]
    model: str
    raw_response: Optional[Any] = None

    @property
    def prompt_tokens(self) -> int:
        return self.usage.get("prompt_tokens", 0)

    @property
    def completion_tokens(self) -> int:
        return self.usage.get("completion_tokens", 0)

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", self.prompt_tokens + self.completion_tokens)


@dataclass
class LLMError(Exception):
    """LLM错误"""
    error_code: str
    error_message: str
    retryable: bool = True
    raw_error: Optional[Any] = None

    def __str__(self):
        return f"[{self.error_code}] {self.error_message}"
