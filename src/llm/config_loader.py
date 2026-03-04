"""配置加载器 - 支持yaml文件和环境变量"""
import os
from pathlib import Path
from typing import Optional

from .base import LLMConfig


def load_config(
    config_path: Optional[str] = None,
    env_prefix: str = "LLM_"
) -> LLMConfig:
    """加载LLM配置
    
    优先级: 环境变量 > config.yaml > config.example.yaml
    
    环境变量:
        LLM_API_KEY: API密钥
        LLM_MODEL: 模型名称
        LLM_PROVIDER: 提供商
        LLM_BASE_URL: 自定义API地址
    
    Args:
        config_path: 配置文件路径，默认查找 config.yaml
        env_prefix: 环境变量前缀
    
    Returns:
        LLMConfig: 配置对象
    """
    config_data = {}
    
    # 1. 尝试从yaml文件加载
    if config_path is None:
        # 查找配置文件
        for name in ["config.yaml", "config.yml", "config.example.yaml"]:
            if Path(name).exists():
                config_path = name
                break
    
    if config_path and Path(config_path).exists():
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config and "llm" in yaml_config:
                    config_data = yaml_config["llm"]
        except ImportError:
            # 没有yaml库，跳过
            pass
    
    # 2. 环境变量覆盖
    env_mapping = {
        "api_key": f"{env_prefix}API_KEY",
        "model": f"{env_prefix}MODEL",
        "provider": f"{env_prefix}PROVIDER",
        "base_url": f"{env_prefix}BASE_URL",
        "temperature": f"{env_prefix}TEMPERATURE",
        "max_tokens": f"{env_prefix}MAX_TOKENS",
        "timeout": f"{env_prefix}TIMEOUT",
        "max_retries": f"{env_prefix}MAX_RETRIES",
    }
    
    for key, env_var in env_mapping.items():
        env_value = os.environ.get(env_var)
        if env_value:
            # 类型转换
            if key in ["temperature"]:
                config_data[key] = float(env_value)
            elif key in ["max_tokens", "timeout", "max_retries"]:
                config_data[key] = int(env_value)
            else:
                config_data[key] = env_value
    
    # 3. 设置默认值
    config_data.setdefault("provider", "zhipu")
    config_data.setdefault("model", "glm-4")
    config_data.setdefault("temperature", 0.3)
    config_data.setdefault("max_tokens", 4096)
    config_data.setdefault("timeout", 60)
    config_data.setdefault("max_retries", 3)
    
    # 验证必填项
    if not config_data.get("api_key"):
        raise ValueError(
            "API密钥未配置！请通过以下方式之一配置:\n"
            "1. 创建 config.yaml 文件并填入 api_key\n"
            "2. 设置环境变量 LLM_API_KEY\n"
            "3. 调用时直接传入 api_key 参数"
        )
    
    return LLMConfig(**config_data)
