"""LLM基础设施测试 - 验证LLM接口抽象层功能"""
import pytest
from src.llm import (
    LLMConfig,
    LLMMessage,
    LLMResponse,
    LLMError,
    LLMClient,
    create_client,
    PROVIDER_BASE_URLS,
    ErrorCode,
    ErrorResponse,
)


class TestLLMConfig:
    """LLMConfig配置测试"""

    def test_valid_config_with_provider(self):
        """测试使用provider的有效配置"""
        config = LLMConfig(
            api_key="test-api-key",
            model="glm-4",
            provider="zhipu"
        )
        is_valid, error = config.validate()
        assert is_valid is True
        assert error is None
        assert config.base_url == PROVIDER_BASE_URLS["zhipu"]

    def test_valid_config_with_custom_base_url(self):
        """测试使用自定义base_url的有效配置"""
        custom_url = "https://custom-api.example.com/v1"
        config = LLMConfig(
            api_key="test-api-key",
            model="custom-model",
            base_url=custom_url
        )
        is_valid, error = config.validate()
        assert is_valid is True
        assert error is None
        assert config.base_url == custom_url

    def test_invalid_config_missing_api_key(self):
        """测试缺少api_key的无效配置"""
        config = LLMConfig(
            api_key="",
            model="glm-4",
            provider="zhipu"
        )
        is_valid, error = config.validate()
        assert is_valid is False
        assert "api_key" in error

    def test_invalid_config_missing_model(self):
        """测试缺少model的无效配置"""
        config = LLMConfig(
            api_key="test-api-key",
            model="",
            provider="zhipu"
        )
        is_valid, error = config.validate()
        assert is_valid is False
        assert "model" in error

    def test_invalid_config_missing_base_url(self):
        """测试缺少base_url的无效配置（未知provider）"""
        config = LLMConfig(
            api_key="test-api-key",
            model="test-model",
            provider="unknown_provider"
        )
        is_valid, error = config.validate()
        assert is_valid is False
        assert "base_url" in error

    def test_invalid_temperature_too_low(self):
        """测试temperature过低"""
        config = LLMConfig(
            api_key="test-api-key",
            model="glm-4",
            provider="zhipu",
            temperature=-0.1
        )
        is_valid, error = config.validate()
        assert is_valid is False
        assert "temperature" in error

    def test_invalid_temperature_too_high(self):
        """测试temperature过高"""
        config = LLMConfig(
            api_key="test-api-key",
            model="glm-4",
            provider="zhipu",
            temperature=2.5
        )
        is_valid, error = config.validate()
        assert is_valid is False
        assert "temperature" in error

    def test_invalid_max_tokens(self):
        """测试max_tokens无效"""
        config = LLMConfig(
            api_key="test-api-key",
            model="glm-4",
            provider="zhipu",
            max_tokens=0
        )
        is_valid, error = config.validate()
        assert is_valid is False
        assert "max_tokens" in error

    def test_invalid_timeout(self):
        """测试timeout无效"""
        config = LLMConfig(
            api_key="test-api-key",
            model="glm-4",
            provider="zhipu",
            timeout=0
        )
        is_valid, error = config.validate()
        assert is_valid is False
        assert "timeout" in error

    def test_invalid_max_retries(self):
        """测试max_retries无效"""
        config = LLMConfig(
            api_key="test-api-key",
            model="glm-4",
            provider="zhipu",
            max_retries=-1
        )
        is_valid, error = config.validate()
        assert is_valid is False
        assert "max_retries" in error

    def test_all_providers_have_base_urls(self):
        """测试所有预设provider都有base_url"""
        expected_providers = ["zhipu", "openai", "deepseek", "qwen"]
        for provider in expected_providers:
            assert provider in PROVIDER_BASE_URLS
            assert PROVIDER_BASE_URLS[provider].startswith("https://")


class TestLLMMessage:
    """LLMMessage消息测试"""

    def test_message_to_dict(self):
        """测试消息转换为字典"""
        msg = LLMMessage(role="user", content="Hello")
        result = msg.to_dict()
        assert result == {"role": "user", "content": "Hello"}

    def test_system_message(self):
        """测试系统消息"""
        msg = LLMMessage(role="system", content="You are a helpful assistant")
        result = msg.to_dict()
        assert result["role"] == "system"

    def test_assistant_message(self):
        """测试助手消息"""
        msg = LLMMessage(role="assistant", content="I can help you")
        result = msg.to_dict()
        assert result["role"] == "assistant"


class TestLLMResponse:
    """LLMResponse响应测试"""

    def test_response_properties(self):
        """测试响应属性"""
        response = LLMResponse(
            content="Test response",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            model="glm-4"
        )
        assert response.content == "Test response"
        assert response.prompt_tokens == 10
        assert response.completion_tokens == 20
        assert response.total_tokens == 30
        assert response.model == "glm-4"

    def test_response_total_tokens_fallback(self):
        """测试total_tokens回退计算"""
        response = LLMResponse(
            content="Test",
            usage={"prompt_tokens": 10, "completion_tokens": 20},
            model="glm-4"
        )
        assert response.total_tokens == 30


class TestLLMError:
    """LLMError错误测试"""

    def test_error_str(self):
        """测试错误字符串表示"""
        error = LLMError(
            error_code="TEST_ERROR",
            error_message="Test error message"
        )
        assert str(error) == "[TEST_ERROR] Test error message"

    def test_error_retryable_default(self):
        """测试错误默认可重试"""
        error = LLMError(
            error_code="TEST_ERROR",
            error_message="Test"
        )
        assert error.retryable is True


class TestLLMClient:
    """LLMClient客户端测试"""

    def test_client_creation(self):
        """测试客户端创建"""
        config = LLMConfig(
            api_key="test-api-key",
            model="glm-4",
            provider="zhipu"
        )
        client = LLMClient(config)
        assert client.config == config

    def test_client_validate_config(self):
        """测试客户端配置验证"""
        config = LLMConfig(
            api_key="test-api-key",
            model="glm-4",
            provider="zhipu"
        )
        client = LLMClient(config)
        is_valid, error = client.validate_config()
        assert is_valid is True

    def test_create_client_helper(self):
        """测试create_client辅助函数"""
        client = create_client(
            api_key="test-api-key",
            model="glm-4",
            provider="zhipu"
        )
        assert isinstance(client, LLMClient)
        assert client.config.api_key == "test-api-key"
        assert client.config.model == "glm-4"
        assert client.config.provider == "zhipu"

    def test_create_client_with_custom_params(self):
        """测试create_client自定义参数"""
        client = create_client(
            api_key="test-api-key",
            model="gpt-4",
            provider="openai",
            temperature=0.7,
            max_tokens=2048
        )
        assert client.config.temperature == 0.7
        assert client.config.max_tokens == 2048


class TestErrorResponse:
    """ErrorResponse错误响应测试"""

    def test_error_response_to_dict(self):
        """测试错误响应转换为字典"""
        response = ErrorResponse(
            success=False,
            error_code="TEST_ERROR",
            error_message="Test error",
            suggestions=["Try again"],
            retryable=True
        )
        result = response.to_dict()
        assert result["success"] is False
        assert result["error_code"] == "TEST_ERROR"
        assert result["error_message"] == "Test error"
        assert result["suggestions"] == ["Try again"]
        assert result["retryable"] is True

    def test_error_response_from_auth_exception(self):
        """测试从认证异常创建错误响应"""
        exc = Exception("401 authentication failed")
        response = ErrorResponse.from_exception(exc)
        assert response.error_code == ErrorCode.API_KEY_MISSING.value
        assert response.retryable is False

    def test_error_response_from_rate_limit_exception(self):
        """测试从频率限制异常创建错误响应"""
        exc = Exception("429 rate limit exceeded")
        response = ErrorResponse.from_exception(exc)
        assert response.error_code == ErrorCode.RATE_LIMIT_EXCEEDED.value
        assert response.retryable is True

    def test_error_response_from_timeout_exception(self):
        """测试从超时异常创建错误响应"""
        exc = Exception("Request timeout")
        response = ErrorResponse.from_exception(exc)
        assert response.error_code == ErrorCode.TIMEOUT.value
        assert response.retryable is True

    def test_error_response_from_connection_exception(self):
        """测试从连接异常创建错误响应"""
        exc = Exception("Connection refused")
        response = ErrorResponse.from_exception(exc)
        assert response.error_code == ErrorCode.CONNECTION_ERROR.value
        assert response.retryable is True

    def test_error_response_from_unknown_exception(self):
        """测试从未知异常创建错误响应"""
        exc = Exception("Some unknown error")
        response = ErrorResponse.from_exception(exc)
        assert response.error_code == ErrorCode.UNKNOWN_ERROR.value
        assert response.retryable is False


class TestErrorCode:
    """ErrorCode错误代码测试"""

    def test_all_error_codes_exist(self):
        """测试所有错误代码存在"""
        expected_codes = [
            "CONFIG_INVALID",
            "API_KEY_MISSING",
            "MODEL_NOT_SUPPORTED",
            "LLM_API_ERROR",
            "RATE_LIMIT_EXCEEDED",
            "TIMEOUT",
            "CONNECTION_ERROR",
            "RESPONSE_PARSE_ERROR",
            "EMPTY_RESPONSE",
            "UNKNOWN_ERROR",
        ]
        for code in expected_codes:
            assert hasattr(ErrorCode, code)
