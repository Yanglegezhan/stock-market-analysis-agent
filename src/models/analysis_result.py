"""分析结果模型

定义LLM分析结果的数据结构，包括支撑压力位、位置分析、
短期预期、中长期预期和完整分析报告。

Requirements: 5.1-5.7, 6.1-6.4, 7.1-7.5, 8.1-8.5
"""

import json
import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator


class LevelType(str, Enum):
    """支撑压力位类型"""
    SUPPORT = "support"
    RESISTANCE = "resistance"


class LevelImportance(str, Enum):
    """支撑压力位级别重要性"""
    DAILY = "daily"
    M15 = "m15"
    M5 = "m5"
    MA = "ma"


class LevelStrength(str, Enum):
    """支撑压力位强度"""
    STRONG = "强"
    MEDIUM = "中"
    WEAK = "弱"


class Confidence(str, Enum):
    """置信度"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TrendDirection(str, Enum):
    """趋势方向"""
    BULLISH = "看涨"
    BEARISH = "看跌"
    SIDEWAYS = "震荡"


class PriceLevel(BaseModel):
    """价格支撑压力位
    
    Requirements: 5.1-5.6
    """
    price: float = Field(..., description="价格")
    level_type: LevelType = Field(..., description="类型（支撑/压力）")
    importance: LevelImportance = Field(..., description="级别重要性")
    description: str = Field(..., description="描述")
    strength: LevelStrength = Field(LevelStrength.MEDIUM, description="强度")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], level_type: LevelType) -> "PriceLevel":
        """从字典创建PriceLevel"""
        importance_map = {
            "daily": LevelImportance.DAILY,
            "m15": LevelImportance.M15,
            "m5": LevelImportance.M5,
            "ma": LevelImportance.MA,
        }
        strength_map = {
            "强": LevelStrength.STRONG,
            "中": LevelStrength.MEDIUM,
            "弱": LevelStrength.WEAK,
        }
        
        return cls(
            price=float(data.get("price", 0)),
            level_type=level_type,
            importance=importance_map.get(
                data.get("importance", "daily"), 
                LevelImportance.DAILY
            ),
            description=data.get("description", ""),
            strength=strength_map.get(
                data.get("strength", "中"), 
                LevelStrength.MEDIUM
            ),
        )


class KeyLevel(BaseModel):
    """当日关键支撑压力位
    
    Requirements: 5.7
    """
    price: float = Field(..., description="价格")
    reason: str = Field(..., description="原因")


class PositionAnalysis(BaseModel):
    """当前价格位置分析
    
    Requirements: 6.1-6.4
    """
    current_price: float = Field(..., description="当前价格")
    nearest_support: Optional[PriceLevel] = Field(None, description="最近支撑位")
    nearest_resistance: Optional[PriceLevel] = Field(None, description="最近压力位")
    support_distance_points: float = Field(0, description="距支撑位点数")
    support_distance_pct: float = Field(0, description="距支撑位百分比")
    resistance_distance_points: float = Field(0, description="距压力位点数")
    resistance_distance_pct: float = Field(0, description="距压力位百分比")
    position_description: str = Field("", description="位置描述")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "current_price": self.current_price,
            "support_distance": self.support_distance_points,
            "support_distance_pct": self.support_distance_pct,
            "resistance_distance": self.resistance_distance_points,
            "resistance_distance_pct": self.resistance_distance_pct,
            "position_description": self.position_description,
        }


class OpeningScenario(BaseModel):
    """开盘场景预期
    
    Requirements: 7.1-7.4
    """
    scenario: str = Field(..., description="场景名称")
    probability: str = Field(..., description="概率评估")
    expectation: str = Field(..., description="预期走势")
    target_levels: List[float] = Field(default_factory=list, description="目标位")
    stop_levels: List[float] = Field(default_factory=list, description="止损位")


class WatchLevel(BaseModel):
    """关键观察点位
    
    Requirements: 7.5
    """
    price: float = Field(..., description="价格")
    significance: str = Field(..., description="意义说明")


class ShortTermExpectation(BaseModel):
    """短期走势预期（次日）
    
    Requirements: 7.1-7.5
    """
    opening_scenarios: List[OpeningScenario] = Field(
        default_factory=list, 
        description="开盘场景列表"
    )
    key_levels_to_watch: List[WatchLevel] = Field(
        default_factory=list,
        description="关键观察点位"
    )
    operation_suggestion: str = Field("", description="操作建议")
    confidence: Confidence = Field(Confidence.MEDIUM, description="置信度")
    risk_warning: str = Field("", description="风险提示")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShortTermExpectation":
        """从字典创建ShortTermExpectation"""
        scenarios = []
        for s in data.get("opening_scenarios", []):
            scenarios.append(OpeningScenario(
                scenario=s.get("scenario", ""),
                probability=s.get("probability", ""),
                expectation=s.get("expectation", ""),
                target_levels=s.get("target_levels", []),
                stop_levels=s.get("stop_levels", []),
            ))
        
        watch_levels = []
        for w in data.get("key_levels_to_watch", []):
            watch_levels.append(WatchLevel(
                price=float(w.get("price", 0)),
                significance=w.get("significance", ""),
            ))
        
        confidence_map = {
            "high": Confidence.HIGH,
            "medium": Confidence.MEDIUM,
            "low": Confidence.LOW,
        }
        
        return cls(
            opening_scenarios=scenarios,
            key_levels_to_watch=watch_levels,
            operation_suggestion=data.get("operation_suggestion", ""),
            confidence=confidence_map.get(
                data.get("confidence", "medium"),
                Confidence.MEDIUM
            ),
            risk_warning=data.get("risk_warning", ""),
        )


class WeeklyExpectation(BaseModel):
    """周线级别预期
    
    Requirements: 8.2
    """
    direction: TrendDirection = Field(..., description="方向")
    target_range: List[float] = Field(default_factory=list, description="目标区间")
    key_events: List[str] = Field(default_factory=list, description="关键观察点")


class MonthlyExpectation(BaseModel):
    """月线级别预期
    
    Requirements: 8.3
    """
    direction: TrendDirection = Field(..., description="方向")
    target_range: List[float] = Field(default_factory=list, description="目标区间")
    key_levels: List[str] = Field(default_factory=list, description="关键位置")


class TrendReversalSignal(BaseModel):
    """趋势转折信号
    
    Requirements: 8.5
    """
    signal: str = Field(..., description="信号描述")
    trigger_level: float = Field(..., description="触发价位")


class LongTermExpectation(BaseModel):
    """中长期走势预期
    
    Requirements: 8.1-8.5
    """
    current_trend: str = Field(..., description="当前趋势")
    trend_strength: str = Field("中", description="趋势强度")
    weekly_expectation: Optional[WeeklyExpectation] = Field(
        None, description="周线预期"
    )
    monthly_expectation: Optional[MonthlyExpectation] = Field(
        None, description="月线预期"
    )
    trend_reversal_signals: List[TrendReversalSignal] = Field(
        default_factory=list,
        description="趋势转折信号"
    )
    confidence: Confidence = Field(Confidence.MEDIUM, description="置信度")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LongTermExpectation":
        """从字典创建LongTermExpectation"""
        direction_map = {
            "看涨": TrendDirection.BULLISH,
            "看跌": TrendDirection.BEARISH,
            "震荡": TrendDirection.SIDEWAYS,
            "震荡偏多": TrendDirection.BULLISH,
            "震荡偏空": TrendDirection.BEARISH,
        }
        
        weekly = None
        weekly_data = data.get("weekly_expectation")
        if weekly_data:
            weekly = WeeklyExpectation(
                direction=direction_map.get(
                    weekly_data.get("direction", "震荡"),
                    TrendDirection.SIDEWAYS
                ),
                target_range=weekly_data.get("target_range", []),
                key_events=weekly_data.get("key_events", []),
            )
        
        monthly = None
        monthly_data = data.get("monthly_expectation")
        if monthly_data:
            monthly = MonthlyExpectation(
                direction=direction_map.get(
                    monthly_data.get("direction", "震荡"),
                    TrendDirection.SIDEWAYS
                ),
                target_range=monthly_data.get("target_range", []),
                key_levels=monthly_data.get("key_levels", []),
            )
        
        signals = []
        for s in data.get("trend_reversal_signals", []):
            signals.append(TrendReversalSignal(
                signal=s.get("signal", ""),
                trigger_level=float(s.get("trigger_level", 0)),
            ))
        
        confidence_map = {
            "high": Confidence.HIGH,
            "medium": Confidence.MEDIUM,
            "low": Confidence.LOW,
        }
        
        return cls(
            current_trend=data.get("current_trend", "震荡趋势"),
            trend_strength=data.get("trend_strength", "中"),
            weekly_expectation=weekly,
            monthly_expectation=monthly,
            trend_reversal_signals=signals,
            confidence=confidence_map.get(
                data.get("confidence", "medium"),
                Confidence.MEDIUM
            ),
        )


class SupportResistanceResult(BaseModel):
    """支撑压力位识别结果
    
    Requirements: 5.1-5.7
    """
    support_levels: List[PriceLevel] = Field(
        default_factory=list,
        description="支撑位列表"
    )
    resistance_levels: List[PriceLevel] = Field(
        default_factory=list,
        description="压力位列表"
    )
    key_support_today: Optional[KeyLevel] = Field(
        None, description="当日关键支撑位"
    )
    key_resistance_today: Optional[KeyLevel] = Field(
        None, description="当日关键压力位"
    )
    analysis_notes: str = Field("", description="分析说明")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SupportResistanceResult":
        """从字典创建SupportResistanceResult
        
        支持两种格式：
        1. 旧格式：support_levels/resistance_levels 直接列表
        2. 新格式：daily_levels/m15_levels/m5_levels/ma_levels 分周期
        """
        support_levels = []
        resistance_levels = []
        
        # 检查是否为新格式（分周期）
        if "daily_levels" in data or "m15_levels" in data or "m5_levels" in data:
            # 新格式：分周期解析
            level_configs = [
                ("daily_levels", LevelImportance.DAILY),
                ("m15_levels", LevelImportance.M15),
                ("m5_levels", LevelImportance.M5),
                ("ma_levels", LevelImportance.MA),
            ]
            
            for level_key, importance in level_configs:
                level_data = data.get(level_key, {})
                
                # 解析支撑位
                for s in level_data.get("support", []):
                    s["importance"] = importance.value
                    # 均线支撑位使用ma_name作为描述
                    if importance == LevelImportance.MA and "ma_name" in s:
                        s["description"] = f"{s['ma_name']}均线支撑"
                    support_levels.append(
                        PriceLevel.from_dict(s, LevelType.SUPPORT)
                    )
                
                # 解析压力位
                for r in level_data.get("resistance", []):
                    r["importance"] = importance.value
                    # 均线压力位使用ma_name作为描述
                    if importance == LevelImportance.MA and "ma_name" in r:
                        r["description"] = f"{r['ma_name']}均线压力"
                    resistance_levels.append(
                        PriceLevel.from_dict(r, LevelType.RESISTANCE)
                    )
        else:
            # 旧格式：直接列表
            support_levels = [
                PriceLevel.from_dict(s, LevelType.SUPPORT)
                for s in data.get("support_levels", [])
            ]
            resistance_levels = [
                PriceLevel.from_dict(r, LevelType.RESISTANCE)
                for r in data.get("resistance_levels", [])
            ]
        
        # 获取当前价格用于验证关键位
        current_price = data.get("current_price", 0)
        
        # 解析关键支撑位（新格式使用key_support，旧格式使用key_support_today）
        key_support = None
        ks_data = data.get("key_support") or data.get("key_support_today")
        if ks_data and ks_data.get("price") is not None:
            ks_price = float(ks_data.get("price", 0))
            # 验证关键支撑位必须小于当前价格
            if ks_price > 0 and (current_price == 0 or ks_price < current_price):
                reason = ks_data.get("reason", "")
                source = ks_data.get("source", "")
                if source:
                    reason = f"[{source}] {reason}"
                key_support = KeyLevel(price=ks_price, reason=reason)
        
        # 解析关键压力位（新格式使用key_resistance，旧格式使用key_resistance_today）
        key_resistance = None
        kr_data = data.get("key_resistance") or data.get("key_resistance_today")
        if kr_data and kr_data.get("price") is not None:
            kr_price = float(kr_data.get("price", 0))
            # 验证关键压力位必须大于当前价格
            if kr_price > 0 and (current_price == 0 or kr_price > current_price):
                reason = kr_data.get("reason", "")
                source = kr_data.get("source", "")
                if source:
                    reason = f"[{source}] {reason}"
                key_resistance = KeyLevel(price=kr_price, reason=reason)
        
        # 按价格排序：支撑位从高到低，压力位从低到高
        support_levels.sort(key=lambda x: x.price, reverse=True)
        resistance_levels.sort(key=lambda x: x.price)
        
        return cls(
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            key_support_today=key_support,
            key_resistance_today=key_resistance,
            analysis_notes=data.get("analysis_notes", ""),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "support_levels": [
                {
                    "price": s.price,
                    "importance": s.importance.value,
                    "description": s.description,
                    "strength": s.strength.value,
                }
                for s in self.support_levels
            ],
            "resistance_levels": [
                {
                    "price": r.price,
                    "importance": r.importance.value,
                    "description": r.description,
                    "strength": r.strength.value,
                }
                for r in self.resistance_levels
            ],
            "key_support_today": {
                "price": self.key_support_today.price,
                "reason": self.key_support_today.reason,
            } if self.key_support_today else None,
            "key_resistance_today": {
                "price": self.key_resistance_today.price,
                "reason": self.key_resistance_today.reason,
            } if self.key_resistance_today else None,
            "analysis_notes": self.analysis_notes,
        }


class IntradayAnalysis(BaseModel):
    """当日走势分析结果（多周期复盘）"""
    
    # 开盘分析
    opening_type: str = Field("平开", description="开盘类型")
    opening_gap: float = Field(0, description="跳空点数")
    opening_description: str = Field("", description="开盘描述")
    
    # 盘中走势（5分钟级别）
    pattern_type: str = Field("震荡", description="走势类型")
    pattern_description: str = Field("", description="走势描述")
    key_time_points: List[Dict[str, Any]] = Field(default_factory=list, description="关键时间点")
    
    # 关键点位
    high_point: Dict[str, Any] = Field(default_factory=dict, description="最高点")
    low_point: Dict[str, Any] = Field(default_factory=dict, description="最低点")
    
    # 尾盘分析
    closing_trend: str = Field("震荡", description="尾盘走势")
    close_position: str = Field("", description="收盘位置")
    volume_trend: str = Field("", description="量能变化")
    
    # 量能分析
    opening_volume: str = Field("", description="开盘量能特征")
    intraday_volume: str = Field("", description="盘中量能变化")
    closing_volume: str = Field("", description="尾盘量能特征")
    volume_analysis: str = Field("", description="量能综合分析")
    
    # 15分钟级别分析
    m15_pattern: str = Field("", description="15分钟级别走势形态")
    m15_key_points: str = Field("", description="15分钟关键转折点")
    m15_resonance: str = Field("", description="与5分钟走势的共振/背离")
    m15_volume_feature: str = Field("", description="15分钟量能特征")
    
    # 日线级别分析
    daily_position: str = Field("", description="当日K线在日线趋势中的位置")
    daily_combination: str = Field("", description="与前几日K线形成的组合形态")
    ma_status: str = Field("", description="均线系统状态")
    daily_volume_trend: str = Field("", description="日线量能趋势")
    
    # 多周期共振分析
    trend_alignment: str = Field("", description="三周期趋势一致性")
    resonance_levels: str = Field("", description="各周期共振的关键点位")
    divergence_signals: str = Field("", description="多周期背离信号")
    volume_resonance: str = Field("", description="多周期量能共振")
    
    # 技术形态
    daily_candle: str = Field("", description="日K线形态")
    candle_meaning: str = Field("", description="形态含义")
    short_term_trend: str = Field("震荡", description="短期趋势")
    volume_confirmation: str = Field("", description="量能确认信号")
    
    # 总结
    summary: str = Field("", description="当日总结")
    next_day_hint: str = Field("", description="次日启示")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntradayAnalysis":
        """从字典创建IntradayAnalysis"""
        opening = data.get("opening_analysis", {})
        pattern = data.get("intraday_pattern", {})
        key_levels = data.get("key_levels_test", {})
        closing = data.get("closing_analysis", {})
        m15 = data.get("m15_analysis", {})
        daily = data.get("daily_analysis", {})
        multi_tf = data.get("multi_timeframe", {})
        technical = data.get("technical_pattern", {})
        volume = data.get("volume_analysis", {})
        
        # 构建量能综合分析文本
        volume_summary_parts = []
        if volume.get("daily_comparison"):
            volume_summary_parts.append(volume["daily_comparison"])
        if volume.get("volume_price_divergence"):
            volume_summary_parts.append(f"量价背离：{volume['volume_price_divergence']}")
        volume_summary = "；".join(volume_summary_parts) if volume_summary_parts else ""
        
        return cls(
            opening_type=opening.get("type", "平开"),
            opening_gap=float(opening.get("gap_points", 0)),
            opening_description=opening.get("description", ""),
            pattern_type=pattern.get("pattern_type", "震荡"),
            pattern_description=pattern.get("description", ""),
            key_time_points=pattern.get("key_time_points", []),
            high_point=key_levels.get("high_point", {}),
            low_point=key_levels.get("low_point", {}),
            closing_trend=closing.get("last_30min_trend", "震荡"),
            close_position=closing.get("close_position", ""),
            volume_trend=closing.get("volume_trend", ""),
            # 量能分析
            opening_volume=volume.get("opening_volume", ""),
            intraday_volume=volume.get("intraday_volume", ""),
            closing_volume=volume.get("closing_volume", ""),
            volume_analysis=volume_summary,
            # 15分钟级别
            m15_pattern=m15.get("pattern", ""),
            m15_key_points=m15.get("key_points", ""),
            m15_resonance=m15.get("resonance_with_m5", ""),
            m15_volume_feature=m15.get("volume_feature", ""),
            # 日线级别
            daily_position=daily.get("position_in_trend", ""),
            daily_combination=daily.get("candle_combination", ""),
            ma_status=daily.get("ma_status", ""),
            daily_volume_trend=daily.get("volume_trend", ""),
            # 多周期共振
            trend_alignment=multi_tf.get("trend_alignment", ""),
            resonance_levels=multi_tf.get("resonance_levels", ""),
            divergence_signals=multi_tf.get("divergence_signals", ""),
            volume_resonance=multi_tf.get("volume_resonance", ""),
            # 技术形态
            daily_candle=technical.get("daily_candle", ""),
            candle_meaning=technical.get("candle_meaning", ""),
            short_term_trend=technical.get("short_term_trend", "震荡"),
            volume_confirmation=technical.get("volume_confirmation", ""),
            summary=data.get("summary", ""),
            next_day_hint=data.get("next_day_hint", ""),
        )


class AnalysisReport(BaseModel):
    """完整分析报告
    
    Requirements: 9.1-9.5
    """
    analysis_time: datetime = Field(..., description="分析时间")
    data_cutoff: str = Field(..., description="数据截止时间")
    current_price: float = Field(..., description="当前价格")
    support_resistance: SupportResistanceResult = Field(
        ..., description="支撑压力位结果"
    )
    position_analysis: PositionAnalysis = Field(..., description="位置分析")
    intraday_analysis: Optional[IntradayAnalysis] = Field(None, description="当日走势分析")
    short_term: ShortTermExpectation = Field(..., description="短期预期")
    long_term: LongTermExpectation = Field(..., description="中长期预期")
    
    def to_json(self, indent: int = 2) -> str:
        """输出JSON格式报告
        
        Requirements: 9.5
        """
        return self.model_dump_json(indent=indent)
    
    def to_text(self) -> str:
        """输出文本格式报告
        
        Requirements: 9.5
        """
        lines = [
            "=" * 60,
            "大盘分析报告",
            "=" * 60,
            f"分析时间：{self.analysis_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"数据截止：{self.data_cutoff}",
            f"当前价格：{self.current_price:.2f}",
            "",
            "-" * 40,
            "【支撑压力位】",
            "-" * 40,
        ]
        
        # 压力位
        lines.append("压力位：")
        for r in self.support_resistance.resistance_levels:
            lines.append(f"  {r.price:.2f} - {r.description}（{r.strength.value}）")
        
        # 支撑位
        lines.append("支撑位：")
        for s in self.support_resistance.support_levels:
            lines.append(f"  {s.price:.2f} - {s.description}（{s.strength.value}）")
        
        # 当日关键位
        if self.support_resistance.key_resistance_today:
            kr = self.support_resistance.key_resistance_today
            lines.append(f"当日关键压力：{kr.price:.2f}（{kr.reason}）")
        if self.support_resistance.key_support_today:
            ks = self.support_resistance.key_support_today
            lines.append(f"当日关键支撑：{ks.price:.2f}（{ks.reason}）")
        
        # 位置分析
        lines.extend([
            "",
            "-" * 40,
            "【当前位置分析】",
            "-" * 40,
            f"位置判断：{self.position_analysis.position_description}",
            f"距最近支撑：{self.position_analysis.support_distance_points:.2f}点"
            f"（{self.position_analysis.support_distance_pct:.2f}%）",
            f"距最近压力：{self.position_analysis.resistance_distance_points:.2f}点"
            f"（{self.position_analysis.resistance_distance_pct:.2f}%）",
        ])
        
        # 短期预期
        lines.extend([
            "",
            "-" * 40,
            "【短期预期（次日）】",
            "-" * 40,
        ])
        for scenario in self.short_term.opening_scenarios:
            lines.append(f"场景：{scenario.scenario}（概率：{scenario.probability}）")
            lines.append(f"  预期：{scenario.expectation}")
            if scenario.target_levels:
                lines.append(f"  目标：{scenario.target_levels}")
            if scenario.stop_levels:
                lines.append(f"  止损：{scenario.stop_levels}")
        
        lines.append(f"操作建议：{self.short_term.operation_suggestion}")
        lines.append(f"置信度：{self.short_term.confidence.value}")
        lines.append(f"风险提示：{self.short_term.risk_warning}")
        
        # 中长期预期
        lines.extend([
            "",
            "-" * 40,
            "【中长期预期】",
            "-" * 40,
            f"当前趋势：{self.long_term.current_trend}（强度：{self.long_term.trend_strength}）",
        ])
        
        if self.long_term.weekly_expectation:
            we = self.long_term.weekly_expectation
            lines.append(f"周线预期：{we.direction.value}，目标区间{we.target_range}")
        
        if self.long_term.monthly_expectation:
            me = self.long_term.monthly_expectation
            lines.append(f"月线预期：{me.direction.value}，目标区间{me.target_range}")
        
        if self.long_term.trend_reversal_signals:
            lines.append("趋势转折信号：")
            for sig in self.long_term.trend_reversal_signals:
                lines.append(f"  - {sig.signal}（触发位：{sig.trigger_level:.2f}）")
        
        lines.append(f"置信度：{self.long_term.confidence.value}")
        
        lines.extend([
            "",
            "=" * 60,
            self.support_resistance.analysis_notes,
            "=" * 60,
        ])
        
        return "\n".join(lines)


class LLMResponseParser:
    """LLM响应解析器
    
    解析LLM返回的JSON格式响应。
    """
    
    @staticmethod
    def extract_json(text: str) -> Optional[Dict[str, Any]]:
        """从文本中提取JSON
        
        Args:
            text: LLM响应文本
            
        Returns:
            解析后的字典，如果解析失败返回None
        """
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 尝试从markdown代码块中提取
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        matches = re.findall(json_pattern, text)
        
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        # 尝试查找JSON对象（改进版：查找第一个{和最后一个}）
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            json_str = text[start_idx:end_idx + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        
        # 如果上面都失败了，尝试使用正则表达式（保留原有逻辑作为后备）
        brace_pattern = r'\{[\s\S]*\}'
        matches = re.findall(brace_pattern, text)
        
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        return None
    
    @classmethod
    def parse_support_resistance(cls, text: str) -> Optional[SupportResistanceResult]:
        """解析支撑压力位响应
        
        Args:
            text: LLM响应文本
            
        Returns:
            SupportResistanceResult对象，解析失败返回None
        """
        data = cls.extract_json(text)
        if data is None:
            return None
        
        try:
            return SupportResistanceResult.from_dict(data)
        except Exception:
            return None
    
    @classmethod
    def parse_short_term(cls, text: str) -> Optional[ShortTermExpectation]:
        """解析短期预期响应
        
        Args:
            text: LLM响应文本
            
        Returns:
            ShortTermExpectation对象，解析失败返回None
        """
        data = cls.extract_json(text)
        if data is None:
            return None
        
        try:
            return ShortTermExpectation.from_dict(data)
        except Exception:
            return None
    
    @classmethod
    def parse_long_term(cls, text: str) -> Optional[LongTermExpectation]:
        """解析中长期预期响应
        
        Args:
            text: LLM响应文本
            
        Returns:
            LongTermExpectation对象，解析失败返回None
        """
        data = cls.extract_json(text)
        if data is None:
            return None
        
        try:
            return LongTermExpectation.from_dict(data)
        except Exception:
            return None
    
    @classmethod
    def parse_intraday_analysis(cls, text: str) -> Optional[IntradayAnalysis]:
        """解析当日走势分析响应
        
        Args:
            text: LLM响应文本
            
        Returns:
            IntradayAnalysis对象，解析失败返回None
        """
        data = cls.extract_json(text)
        if data is None:
            return None
        
        try:
            return IntradayAnalysis.from_dict(data)
        except Exception:
            return None
