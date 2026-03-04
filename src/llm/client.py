"""统一LLM客户端 - 基于OpenAI兼容接口"""
import time
import os
import ssl
import urllib3
import requests
from typing import List, Optional
from urllib3.exceptions import InsecureRequestWarning

from openai import OpenAI

from .base import LLMConfig, LLMMessage, LLMResponse, LLMError

# 修复网络问题
def fix_llm_network():
    """修复LLM网络连接问题"""
    # 禁用代理
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
    for var in proxy_vars:
        if var in os.environ:
            del os.environ[var]
    os.environ['NO_PROXY'] = '*'
    
    # 禁用SSL警告
    urllib3.disable_warnings(InsecureRequestWarning)
    
    # 设置SSL上下文
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

# 应用网络修复
fix_llm_network()


class LLMClient:
    """统一LLM客户端，支持所有OpenAI兼容的API和Gemini"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client: Optional[OpenAI] = None
        self._is_gemini = config.provider == "gemini"

    def _get_client(self) -> OpenAI:
        """获取OpenAI客户端"""
        if self._client is None and not self._is_gemini:
            # 创建带有网络修复的客户端
            import httpx
            
            # 创建自定义的httpx客户端，禁用SSL验证
            http_client = httpx.Client(
                verify=False,
                timeout=self.config.timeout,
            )
            
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                http_client=http_client,
            )
        return self._client

    def _call_gemini(self, messages: List[LLMMessage]) -> LLMResponse:
        """调用Gemini API"""
        # 转换消息格式
        contents = []
        system_instruction = None
        
        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            else:
                contents.append({
                    "role": "user" if msg.role == "user" else "model",
                    "parts": [{"text": msg.content}]
                })
        
        # 构建请求
        url = f"{self.config.base_url}/models/{self.config.model}:generateContent?key={self.config.api_key}"
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.config.temperature,
            }
        }
        
        # 只有在明确设置了max_tokens时才添加限制
        if self.config.max_tokens and self.config.max_tokens > 0:
            payload["generationConfig"]["maxOutputTokens"] = self.config.max_tokens
        
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }
        
        # 发送请求
        response = requests.post(
            url,
            json=payload,
            timeout=self.config.timeout,
            verify=False
        )
        
        if response.status_code != 200:
            raise Exception(f"Gemini API错误: {response.status_code} - {response.text}")
        
        result = response.json()
        
        # 解析响应
        if "candidates" not in result or len(result["candidates"]) == 0:
            raise Exception(f"Gemini返回空响应: {result}")
        
        content = result["candidates"][0]["content"]["parts"][0]["text"]
        
        # 获取token使用情况
        usage_metadata = result.get("usageMetadata", {})
        
        return LLMResponse(
            content=content,
            usage={
                "prompt_tokens": usage_metadata.get("promptTokenCount", 0),
                "completion_tokens": usage_metadata.get("candidatesTokenCount", 0),
                "total_tokens": usage_metadata.get("totalTokenCount", 0),
            },
            model=self.config.model,
            raw_response=result
        )

    def _call_gemini_stream(self, messages: List[LLMMessage], callback=None) -> LLMResponse:
        """调用Gemini API（流式）"""
        # 转换消息格式
        contents = []
        system_instruction = None
        
        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            else:
                contents.append({
                    "role": "user" if msg.role == "user" else "model",
                    "parts": [{"text": msg.content}]
                })
        
        # 构建请求
        url = f"{self.config.base_url}/models/{self.config.model}:streamGenerateContent?key={self.config.api_key}&alt=sse"
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.config.temperature,
            }
        }
        
        # 只有在明确设置了max_tokens时才添加限制
        if self.config.max_tokens and self.config.max_tokens > 0:
            payload["generationConfig"]["maxOutputTokens"] = self.config.max_tokens
        
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }
        
        # 发送流式请求
        response = requests.post(
            url,
            json=payload,
            timeout=self.config.timeout,
            stream=True,
            verify=False
        )
        
        if response.status_code != 200:
            raise Exception(f"Gemini API错误: {response.status_code} - {response.text}")
        
        # 处理流式响应
        full_content = ""
        import json
        
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])
                        if "candidates" in data and len(data["candidates"]) > 0:
                            parts = data["candidates"][0]["content"]["parts"]
                            if parts and "text" in parts[0]:
                                text = parts[0]["text"]
                                full_content += text
                                if callback:
                                    callback(text)
                                else:
                                    print(text, end="", flush=True)
                    except json.JSONDecodeError:
                        continue
        
        # 流式输出完成后换行
        if callback is None:
            print()
        
        return LLMResponse(
            content=full_content,
            usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            model=self.config.model,
            raw_response=None
        )

    def chat(self, messages: List[LLMMessage]) -> LLMResponse:
        """发送消息并获取响应，带重试机制"""
        if self._is_gemini:
            return self._call_gemini(messages)
        
        client = self._get_client()
        formatted_messages = [msg.to_dict() for msg in messages]
        
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=self.config.model,
                    messages=formatted_messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    **self.config.extra_params
                )
                
                return LLMResponse(
                    content=response.choices[0].message.content or "",
                    usage={
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                        "total_tokens": response.usage.total_tokens if response.usage else 0,
                    },
                    model=response.model,
                    raw_response=response
                )
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries and self._is_retryable(e):
                    # 指数退避
                    wait_time = (2 ** attempt) * 0.5
                    time.sleep(wait_time)
                    continue
                break
        
        raise LLMError(
            error_code="LLM_API_ERROR",
            error_message=str(last_error),
            retryable=self._is_retryable(last_error),
            raw_error=last_error
        )

    def chat_stream(self, messages: List[LLMMessage], callback=None):
        """发送消息并流式获取响应
        
        Args:
            messages: 消息列表
            callback: 回调函数，接收每个chunk的内容，如果为None则直接打印
            
        Returns:
            LLMResponse对象，包含完整的响应内容
        """
        if self._is_gemini:
            return self._call_gemini_stream(messages, callback)
        
        client = self._get_client()
        formatted_messages = [msg.to_dict() for msg in messages]
        
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                stream = client.chat.completions.create(
                    model=self.config.model,
                    messages=formatted_messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    stream=True,
                    **self.config.extra_params
                )
                
                full_content = ""
                for chunk in stream:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            full_content += delta.content
                            # 调用回调函数或直接打印
                            if callback:
                                callback(delta.content)
                            else:
                                print(delta.content, end="", flush=True)
                
                # 流式输出完成后换行
                if callback is None:
                    print()
                
                return LLMResponse(
                    content=full_content,
                    usage={
                        "prompt_tokens": 0,  # 流式响应通常不返回token统计
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                    model=self.config.model,
                    raw_response=None
                )
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries and self._is_retryable(e):
                    # 指数退避
                    wait_time = (2 ** attempt) * 0.5
                    time.sleep(wait_time)
                    continue
                break
        
        raise LLMError(
            error_code="LLM_API_ERROR",
            error_message=str(last_error),
            retryable=self._is_retryable(last_error),
            raw_error=last_error
        )

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """验证配置"""
        return self.config.validate()

    def _is_retryable(self, error: Exception) -> bool:
        """判断是否可重试"""
        error_str = str(error).lower()
        retryable_keywords = ["timeout", "rate limit", "429", "500", "502", "503", "504"]
        return any(kw in error_str for kw in retryable_keywords)


def create_client(
    api_key: str,
    model: str = "glm-4",
    provider: str = "zhipu",
    base_url: Optional[str] = None,
    **kwargs
) -> LLMClient:
    """快速创建LLM客户端
    
    Args:
        api_key: API密钥
        model: 模型名称
        provider: 提供商（zhipu/openai/deepseek/qwen）
        base_url: 自定义API地址（可选）
        **kwargs: 其他配置参数
    
    Examples:
        # 智谱GLM-4（默认）
        client = create_client("your-api-key")
        
        # OpenAI GPT-4
        client = create_client("your-api-key", model="gpt-4", provider="openai")
        
        # DeepSeek
        client = create_client("your-api-key", model="deepseek-chat", provider="deepseek")
        
        # 自定义API地址
        client = create_client("your-api-key", model="xxx", base_url="https://your-api.com/v1")
    """
    config = LLMConfig(
        api_key=api_key,
        model=model,
        provider=provider,
        base_url=base_url,
        **kwargs
    )
    return LLMClient(config)
