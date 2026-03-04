"""提示词引擎

实现提示词模板加载、变量替换和上下文压缩策略。

Requirements: 4.4, 4.7, 4.8
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.analysis.context_builder import MarketContext


@dataclass
class PromptTemplate:
    """提示词模板
    
    Requirements: 4.4
    """
    name: str
    version: str
    content: str
    variables: List[str] = field(default_factory=list)
    
    @classmethod
    def from_file(cls, file_path: Path, name: str, version: str = "1.0") -> "PromptTemplate":
        """从文件加载模板"""
        content = file_path.read_text(encoding="utf-8")
        # 提取变量名 {variable_name}
        variables = re.findall(r'\{(\w+)\}', content)
        return cls(
            name=name,
            version=version,
            content=content,
            variables=list(set(variables))
        )
    
    def render(self, **kwargs) -> str:
        """渲染模板，替换变量"""
        result = self.content
        for key, value in kwargs.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))
        return result


@dataclass
class FewShotExample:
    """Few-shot示例"""
    name: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    
    @classmethod
    def from_file(cls, file_path: Path) -> "FewShotExample":
        """从JSON文件加载示例"""
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return cls(
            name=file_path.stem,
            input_data=data.get("input", {}),
            output_data=data.get("output", {})
        )
    
    def to_prompt_text(self) -> str:
        """转换为提示词文本"""
        input_text = json.dumps(self.input_data, ensure_ascii=False, indent=2)
        output_text = json.dumps(self.output_data, ensure_ascii=False, indent=2)
        return f"""## 示例输入
{input_text}

## 示例输出
```json
{output_text}
```"""


class PromptEngine:
    """提示词引擎
    
    负责加载和管理提示词模板，构建完整的LLM提示词。
    
    Requirements: 4.4, 4.7, 4.8
    """
    
    def __init__(self, template_dir: str = "prompts/"):
        """初始化提示词引擎
        
        Args:
            template_dir: 提示词模板目录
        """
        self.template_dir = Path(template_dir)
        self.templates: Dict[str, PromptTemplate] = {}
        self.examples: Dict[str, FewShotExample] = {}
        self._load_templates()
        self._load_examples()
    
    def _load_templates(self):
        """加载所有模板文件"""
        if not self.template_dir.exists():
            return
        
        template_files = {
            "system": "system.txt",
            "support_resistance": "support_resistance.txt",
            "short_term": "short_term.txt",
            "long_term": "long_term.txt",
            "intraday_analysis": "intraday_analysis.txt",
        }
        
        for name, filename in template_files.items():
            file_path = self.template_dir / filename
            if file_path.exists():
                self.templates[name] = PromptTemplate.from_file(
                    file_path, name=name
                )
    
    def _load_examples(self):
        """加载所有Few-shot示例"""
        examples_dir = self.template_dir / "examples"
        if not examples_dir.exists():
            return
        
        for file_path in examples_dir.glob("*.json"):
            example = FewShotExample.from_file(file_path)
            self.examples[example.name] = example
    
    def get_system_prompt(self) -> str:
        """获取系统提示词
        
        Returns:
            系统提示词文本
            
        Requirements: 4.1
        """
        if "system" in self.templates:
            return self.templates["system"].content
        
        # 默认系统提示词
        return """你是一位专业的A股技术分析师，专注于上证指数的技术面分析。
你的任务是基于多周期K线数据和均线数据，识别关键支撑压力位，并给出走势预期。

## 输出要求
- 所有价格精确到小数点后2位
- 距离百分比精确到小数点后2位
- 给出置信度评级（高、中、低）
- 分析结论要具体、可操作
- 必须严格按照指定的JSON格式输出"""
    
    def build_support_resistance_prompt(self, context: MarketContext) -> str:
        """构建支撑压力位识别提示词
        
        Args:
            context: 市场上下文
            
        Returns:
            完整的提示词文本
            
        Requirements: 4.4, 4.5
        """
        if "support_resistance" not in self.templates:
            raise ValueError("未找到support_resistance模板")
        
        template = self.templates["support_resistance"]
        market_context = context.to_full_context()
        
        prompt = template.render(market_context=market_context)
        
        # 添加Few-shot示例
        if "support_resistance_example" in self.examples:
            example = self.examples["support_resistance_example"]
            prompt = f"{prompt}\n\n{example.to_prompt_text()}"
        
        return prompt
    
    def build_short_term_prompt(
        self,
        context: MarketContext,
        sr_result: Dict[str, Any],
        position_analysis: Dict[str, Any]
    ) -> str:
        """构建短期预期分析提示词
        
        Args:
            context: 市场上下文
            sr_result: 支撑压力位识别结果
            position_analysis: 价格位置分析结果
            
        Returns:
            完整的提示词文本
            
        Requirements: 4.4, 4.6
        """
        if "short_term" not in self.templates:
            raise ValueError("未找到short_term模板")
        
        template = self.templates["short_term"]
        
        # 格式化支撑压力位结果
        sr_text = json.dumps(sr_result, ensure_ascii=False, indent=2)
        
        # 构建今日走势摘要
        today_summary = f"""当日开盘：{context.current_price:.2f}
当日涨跌：{context.price_change_pct:+.2f}%"""
        
        prompt = template.render(
            support_resistance_result=sr_text,
            current_price=f"{context.current_price:.2f}",
            support_distance=f"{position_analysis.get('support_distance', 0):.2f}",
            support_distance_pct=f"{position_analysis.get('support_distance_pct', 0):.2f}",
            resistance_distance=f"{position_analysis.get('resistance_distance', 0):.2f}",
            resistance_distance_pct=f"{position_analysis.get('resistance_distance_pct', 0):.2f}",
            position_description=position_analysis.get('position_description', ''),
            today_summary=today_summary
        )
        
        # 添加Few-shot示例
        if "short_term_example" in self.examples:
            example = self.examples["short_term_example"]
            prompt = f"{prompt}\n\n{example.to_prompt_text()}"
        
        return prompt
    
    def build_long_term_prompt(
        self,
        context: MarketContext,
        sr_result: Dict[str, Any]
    ) -> str:
        """构建中长期预期分析提示词
        
        Args:
            context: 市场上下文
            sr_result: 支撑压力位识别结果
            
        Returns:
            完整的提示词文本
            
        Requirements: 4.4, 4.6
        """
        if "long_term" not in self.templates:
            raise ValueError("未找到long_term模板")
        
        template = self.templates["long_term"]
        
        # 格式化关键点位
        key_levels = {
            "support": [l["price"] for l in sr_result.get("support_levels", [])],
            "resistance": [l["price"] for l in sr_result.get("resistance_levels", [])]
        }
        key_levels_text = json.dumps(key_levels, ensure_ascii=False, indent=2)
        
        prompt = template.render(
            daily_data=context.daily_csv,
            ma_system_status=context.ma_positions,
            key_levels=key_levels_text
        )
        
        # 添加Few-shot示例
        if "long_term_example" in self.examples:
            example = self.examples["long_term_example"]
            prompt = f"{prompt}\n\n{example.to_prompt_text()}"
        
        return prompt
    
    def build_intraday_analysis_prompt(self, context: MarketContext) -> str:
        """构建当日走势分析提示词
        
        基于多周期K线数据（5分钟、15分钟、日线）分析当日走势。
        
        Args:
            context: 市场上下文
            
        Returns:
            完整的提示词文本
        """
        if "intraday_analysis" not in self.templates:
            raise ValueError("未找到intraday_analysis模板")
        
        template = self.templates["intraday_analysis"]
        
        # 构建多周期数据的上下文
        multi_tf_context = f"""## 多周期K线数据

### 当前价格
当前价格：{context.current_price:.2f}
今日涨跌幅：{context.price_change_pct:+.2f}%

### 5分钟线数据（共{context.m5_count}根K线）
```csv
{context.m5_csv}
```

### 15分钟线数据（共{context.m15_count}根K线）
```csv
{context.m15_csv}
```

### 日线数据（共{context.daily_count}根K线）
```csv
{context.daily_csv}
```

### 均线系统状态
{context.ma_positions}

### 数据截止时间
{context.data_cutoff}"""
        
        prompt = template.render(market_context=multi_tf_context)
        
        # 添加Few-shot示例
        if "intraday_analysis_example" in self.examples:
            example = self.examples["intraday_analysis_example"]
            prompt = f"{prompt}\n\n{example.to_prompt_text()}"
        
        return prompt
    
    def compress_context(
        self, 
        context: MarketContext, 
        max_tokens: int = 4000
    ) -> MarketContext:
        """压缩上下文以适应token限制
        
        当上下文过长时，减少数据量以适应LLM的token限制。
        
        Args:
            context: 原始市场上下文
            max_tokens: 最大token数
            
        Returns:
            压缩后的MarketContext
            
        Requirements: 4.7
        """
        # 估算当前token数（粗略估计：1个中文字符约2个token）
        full_text = context.to_full_context()
        estimated_tokens = len(full_text) * 0.5  # 粗略估计
        
        if estimated_tokens <= max_tokens:
            return context
        
        # 需要压缩，减少数据行数
        compression_ratio = max_tokens / estimated_tokens
        
        # 压缩CSV数据
        compressed_daily = self._compress_csv(
            context.daily_csv, 
            int(context.daily_count * compression_ratio)
        )
        compressed_m15 = self._compress_csv(
            context.m15_csv,
            int(context.m15_count * compression_ratio)
        )
        compressed_m5 = self._compress_csv(
            context.m5_csv,
            int(context.m5_count * compression_ratio)
        )
        
        return MarketContext(
            daily_csv=compressed_daily[0],
            daily_count=compressed_daily[1],
            m15_csv=compressed_m15[0],
            m15_count=compressed_m15[1],
            m5_csv=compressed_m5[0],
            m5_count=compressed_m5[1],
            ma_positions=context.ma_positions,
            current_price=context.current_price,
            price_change_pct=context.price_change_pct,
            data_cutoff=context.data_cutoff,
        )
    
    def _compress_csv(self, csv_text: str, target_rows: int) -> tuple:
        """压缩CSV数据
        
        Args:
            csv_text: CSV文本
            target_rows: 目标行数
            
        Returns:
            (压缩后的CSV文本, 实际行数)
        """
        if csv_text == "无数据":
            return csv_text, 0
        
        lines = csv_text.strip().split("\n")
        if len(lines) <= 1:
            return csv_text, 0
        
        header = lines[0]
        data_lines = lines[1:]
        
        if len(data_lines) <= target_rows:
            return csv_text, len(data_lines)
        
        # 保留最近的数据
        kept_lines = data_lines[-target_rows:]
        result = "\n".join([header] + kept_lines)
        
        return result, len(kept_lines)
    
    def reload_templates(self):
        """重新加载所有模板（用于A/B测试）
        
        Requirements: 4.8
        """
        self.templates.clear()
        self.examples.clear()
        self._load_templates()
        self._load_examples()
    
    def get_template_version(self, template_name: str) -> Optional[str]:
        """获取模板版本
        
        Args:
            template_name: 模板名称
            
        Returns:
            版本号，如果模板不存在则返回None
        """
        if template_name in self.templates:
            return self.templates[template_name].version
        return None


def create_prompt_engine(template_dir: str = "prompts/") -> PromptEngine:
    """创建提示词引擎的便捷函数
    
    Args:
        template_dir: 模板目录
        
    Returns:
        PromptEngine实例
    """
    return PromptEngine(template_dir=template_dir)
