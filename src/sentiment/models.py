"""情绪分析数据模型

定义情绪分析所需的所有数据模型，包括市场数据、情绪指标、周期节点、
LLM分析结果、配置和结果模型。使用Pydantic进行数据验证。

Requirements: 1.1, 1.2, 7.1, 7.2, 7.3, 7.4
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, List, Optional

import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator


# ============ 市场数据模型 ============


class MarketDayData(BaseModel):
    """单日市场数据（从API获取的原始数据）
    
    包含情绪分析所需的所有市场指标，用于计算三条情绪指标线。
    
    Validates: Requirements 1.1, 1.2
    """
    trading_date: date = Field(..., description="交易日期（非自然日）")
    index_change: float = Field(..., description="指数涨幅 (%)")
    all_a_change: float = Field(..., description="全A涨幅 (%)")
    up_count: int = Field(..., ge=0, description="上涨家数")
    down_count: int = Field(..., ge=0, description="下跌家数")
    limit_up_count: int = Field(..., ge=0, description="涨停数")
    consecutive_limit_up: Dict[int, int] = Field(
        default_factory=dict, description="连板家数分布 {连板数: 家数}"
    )
    max_consecutive: int = Field(..., ge=0, description="最高板")
    yesterday_limit_up_performance: float = Field(
        ..., description="昨日涨停今日表现 (%)"
    )
    new_100day_high_count: int = Field(..., ge=0, description="新增百日新高个股家数")
    limit_down_count: int = Field(..., ge=0, description="跌停数")
    blown_limit_up_count: int = Field(..., ge=0, description="炸板家数")
    blown_limit_up_rate: float = Field(..., ge=0, le=1, description="炸板率")
    large_pullback_count: int = Field(..., ge=0, description="大幅回撤家数")
    yesterday_blown_performance: float = Field(
        ..., description="昨日断板今日表现 (%)"
    )

    @field_validator('consecutive_limit_up')
    @classmethod
    def validate_consecutive_limit_up(cls, v: Dict[int, int]) -> Dict[int, int]:
        """验证连板家数分布的键和值都是非负整数"""
        for k, count in v.items():
            if k < 0:
                raise ValueError(f"连板数不能为负数: {k}")
            if count < 0:
                raise ValueError(f"连板家数不能为负数: {count}")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "trading_date": "2024-01-15",
                    "index_change": 1.25,
                    "all_a_change": 1.18,
                    "up_count": 3316,
                    "down_count": 1684,
                    "limit_up_count": 52,
                    "consecutive_limit_up": {2: 15, 3: 8, 4: 3, 5: 1},
                    "max_consecutive": 5,
                    "yesterday_limit_up_performance": 2.3,
                    "new_100day_high_count": 28,
                    "limit_down_count": 8,
                    "blown_limit_up_count": 10,
                    "blown_limit_up_rate": 0.152,
                    "large_pullback_count": 45,
                    "yesterday_blown_performance": -1.2
                }
            ]
        }
    }


# ============ 情绪指标模型 ============


class DailySentiment(BaseModel):
    """单日情绪指标
    
    包含三条核心情绪指标线的计算结果。
    
    Validates: Requirements 1.3, 1.4, 1.5
    """
    trading_date: date = Field(..., description="交易日期")
    market_coefficient: float = Field(..., description="大盘系数")
    ultra_short_sentiment: float = Field(..., description="超短情绪")
    loss_effect: float = Field(..., description="亏钱效应")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "trading_date": "2024-01-15",
                    "market_coefficient": 165.8,
                    "ultra_short_sentiment": 95.2,
                    "loss_effect": 38.5
                }
            ]
        }
    }


class SentimentIndicators(BaseModel):
    """情绪指标数据（15个交易日）
    
    包含15个交易日的三条情绪指标线数据，提供获取最新值、
    计算环比变化等功能。
    
    Validates: Requirements 1.3, 1.4, 1.5, 1.6
    """
    daily_sentiments: List[DailySentiment] = Field(
        ..., min_length=1, description="每日情绪指标列表"
    )

    @field_validator('daily_sentiments')
    @classmethod
    def validate_sorted(cls, v: List[DailySentiment]) -> List[DailySentiment]:
        """验证情绪指标按日期升序排列"""
        if len(v) > 1:
            for i in range(1, len(v)):
                if v[i].trading_date <= v[i-1].trading_date:
                    raise ValueError("情绪指标必须按交易日期升序排列")
        return v

    def get_latest(self) -> DailySentiment:
        """获取最新一日的情绪指标"""
        return self.daily_sentiments[-1]

    def get_previous(self) -> Optional[DailySentiment]:
        """获取昨日（前一个交易日）的情绪指标"""
        if len(self.daily_sentiments) >= 2:
            return self.daily_sentiments[-2]
        return None

    def calculate_change_pct(self) -> Dict[str, float]:
        """计算最新一日与昨日的环比变化百分比
        
        Returns:
            包含三条指标线环比变化的字典
        """
        latest = self.get_latest()
        previous = self.get_previous()
        
        if previous is None:
            return {
                "market_coefficient_change": 0.0,
                "ultra_short_sentiment_change": 0.0,
                "loss_effect_change": 0.0,
            }
        
        def calc_pct(current: float, prev: float) -> float:
            if prev == 0:
                return 0.0
            return (current - prev) / prev * 100
        
        return {
            "market_coefficient_change": calc_pct(
                latest.market_coefficient, previous.market_coefficient
            ),
            "ultra_short_sentiment_change": calc_pct(
                latest.ultra_short_sentiment, previous.ultra_short_sentiment
            ),
            "loss_effect_change": calc_pct(
                latest.loss_effect, previous.loss_effect
            ),
        }

    def to_dataframe(self) -> pd.DataFrame:
        """转换为DataFrame便于分析"""
        data = []
        for sentiment in self.daily_sentiments:
            data.append({
                "trading_date": sentiment.trading_date,
                "market_coefficient": sentiment.market_coefficient,
                "ultra_short_sentiment": sentiment.ultra_short_sentiment,
                "loss_effect": sentiment.loss_effect,
            })
        return pd.DataFrame(data)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "daily_sentiments": [
                        {
                            "trading_date": "2024-01-15",
                            "market_coefficient": 165.8,
                            "ultra_short_sentiment": 95.2,
                            "loss_effect": 38.5
                        },
                        {
                            "trading_date": "2024-01-16",
                            "market_coefficient": 168.3,
                            "ultra_short_sentiment": 98.1,
                            "loss_effect": 35.2
                        }
                    ]
                }
            ]
        }
    }


# ============ 周期节点模型 ============


class NodeType(str, Enum):
    """周期节点类型
    
    定义市场周期中的各种关键节点类型。
    """
    ICE_POINT = "冰冰点"  # 周期之始
    RECOVERY = "冰冰点次日修复"
    DIVERGENCE_AFTER_RECOVERY = "修复后分歧"  # 第二买点
    RESONANCE_HIGH = "共振高潮"
    RETREAT = "退潮阶段"
    ICE_POINT_NEW = "冰点"  # 新周期
    TOP_DIVERGENCE = "顶背离"  # 大盘在上情绪在下
    BOTTOM_DIVERGENCE = "底背离"  # 大盘在下情绪在上
    THREE_LINE_COUPLING = "三线耦合"


class CycleNode(BaseModel):
    """周期节点
    
    LLM识别的市场周期节点，包含节点类型、描述、关键指标等信息。
    
    Validates: Requirements 2.4
    """
    trading_date: date = Field(..., description="交易日期")
    node_type: NodeType = Field(..., description="节点类型")
    description: str = Field(..., min_length=1, description="节点描述")
    key_indicators: Dict[str, float] = Field(
        default_factory=dict, description="关键指标数值"
    )
    confidence: str = Field(..., description="置信度 (高/中/低)")

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: str) -> str:
        """验证置信度只能是高、中、低"""
        if v not in ["高", "中", "低"]:
            raise ValueError(f"置信度必须是'高'、'中'或'低'，当前为: {v}")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "trading_date": "2024-01-10",
                    "node_type": "冰冰点",
                    "description": "亏钱效应达到85.2，显著高于大盘系数和超短情绪",
                    "key_indicators": {
                        "market_coefficient": 142.3,
                        "ultra_short_sentiment": 78.5,
                        "loss_effect": 85.2
                    },
                    "confidence": "高"
                }
            ]
        }
    }


# ============ LLM分析结果模型 ============


class SentimentAnalysisResult(BaseModel):
    """情绪分析结果
    
    LLM分析的完整结果，包含周期节点识别、当前阶段判断、
    情绪分析、策略建议等。
    
    Validates: Requirements 2.3, 2.4, 2.5, 2.6, 2.7, 2.8
    """
    cycle_nodes: List[CycleNode] = Field(
        default_factory=list, description="识别的周期节点"
    )
    current_stage: str = Field(..., min_length=1, description="当前所处阶段")
    stage_position: str = Field(..., min_length=1, description="在演绎顺序中的位置")
    money_making_score: int = Field(..., ge=0, le=100, description="赚钱效应评分 (0-100)")
    divergence_analysis: str = Field(..., min_length=1, description="背离分析")
    detail_analysis: str = Field(..., min_length=1, description="细节盘点")
    strategy_suggestion: str = Field(..., min_length=1, description="操作策略建议")
    position_advice: str = Field(..., description="仓位建议")
    risk_warning: str = Field(..., min_length=1, description="风险提示")
    next_node_prediction: str = Field(..., min_length=1, description="下一节点预判")

    @field_validator('position_advice')
    @classmethod
    def validate_position_advice(cls, v: str) -> str:
        """验证仓位建议只能是轻仓、半仓、重仓、空仓"""
        valid_positions = ["轻仓", "半仓", "重仓", "空仓"]
        if v not in valid_positions:
            raise ValueError(
                f"仓位建议必须是{valid_positions}之一，当前为: {v}"
            )
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "cycle_nodes": [
                        {
                            "trading_date": "2024-01-10",
                            "node_type": "冰冰点",
                            "description": "市场恐慌情绪浓厚",
                            "key_indicators": {
                                "market_coefficient": 142.3,
                                "ultra_short_sentiment": 78.5,
                                "loss_effect": 85.2
                            },
                            "confidence": "高"
                        }
                    ],
                    "current_stage": "共振高潮前期",
                    "stage_position": "周期演绎顺序第4阶段",
                    "money_making_score": 85,
                    "divergence_analysis": "当前大盘系数与超短情绪保持同步上涨",
                    "detail_analysis": "最高板为6连板，连板梯队完整",
                    "strategy_suggestion": "建议重仓参与，重点关注连板股和新高股",
                    "position_advice": "重仓",
                    "risk_warning": "共振高潮后可能快速进入退潮阶段",
                    "next_node_prediction": "如果大盘系数与超短情绪继续同步上涨，将进入共振高潮阶段"
                }
            ]
        }
    }


# ============ 配置模型 ============


class DataSourceConfig(BaseModel):
    """数据源配置
    
    Validates: Requirements 7.2
    """
    provider: str = Field(default="akshare", description="数据源提供商 (akshare/tushare)")
    api_key: Optional[str] = Field(None, description="API密钥（TuShare需要）")
    timeout: int = Field(default=30, gt=0, description="超时时间（秒）")
    max_retries: int = Field(default=3, ge=0, description="最大重试次数")

    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """验证数据源提供商"""
        valid_providers = ["akshare", "tushare"]
        if v.lower() not in valid_providers:
            raise ValueError(
                f"数据源提供商必须是{valid_providers}之一，当前为: {v}"
            )
        return v.lower()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "provider": "akshare",
                    "timeout": 30,
                    "max_retries": 3
                }
            ]
        }
    }


class AgentConfig(BaseModel):
    """Agent配置
    
    Validates: Requirements 7.1, 7.2, 7.3, 7.4
    """
    data_source_config: DataSourceConfig = Field(..., description="数据源配置")
    template_dir: str = Field(
        default="prompts/sentiment/", description="提示词模板目录"
    )
    output_dir: str = Field(
        default="output/sentiment/", description="输出目录"
    )
    num_trading_days: int = Field(
        default=15, ge=1, description="分析的交易日数量"
    )
    verbose: bool = Field(default=True, description="是否显示详细信息")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "data_source_config": {
                        "provider": "akshare",
                        "timeout": 30,
                        "max_retries": 3
                    },
                    "template_dir": "prompts/sentiment/",
                    "output_dir": "output/sentiment/",
                    "num_trading_days": 15,
                    "verbose": True
                }
            ]
        }
    }


# ============ 结果模型 ============


class AnalysisResult(BaseModel):
    """分析结果
    
    完整的分析流程结果，包含成功状态、报告路径、图表路径、
    分析结果、错误和警告信息。
    
    Validates: Requirements 4.10, 5.8
    """
    success: bool = Field(..., description="分析是否成功")
    report_path: Optional[str] = Field(None, description="报告文件路径")
    chart_path: Optional[str] = Field(None, description="图表文件路径")
    analysis_result: Optional[SentimentAnalysisResult] = Field(
        None, description="情绪分析结果"
    )
    errors: Optional[List[str]] = Field(None, description="错误信息列表")
    warnings: Optional[List[str]] = Field(None, description="警告信息列表")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "report_path": "output/sentiment/reports/sentiment_20240115.md",
                    "chart_path": "output/sentiment/charts/sentiment_20240115.png",
                    "analysis_result": {
                        "cycle_nodes": [],
                        "current_stage": "共振高潮前期",
                        "stage_position": "周期演绎顺序第4阶段",
                        "money_making_score": 85,
                        "divergence_analysis": "当前大盘系数与超短情绪保持同步上涨",
                        "detail_analysis": "最高板为6连板",
                        "strategy_suggestion": "建议重仓参与",
                        "position_advice": "重仓",
                        "risk_warning": "共振高潮后可能快速进入退潮阶段",
                        "next_node_prediction": "将进入共振高潮阶段"
                    },
                    "errors": None,
                    "warnings": None
                }
            ]
        }
    }
