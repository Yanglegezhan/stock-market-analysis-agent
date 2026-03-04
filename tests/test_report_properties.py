"""报告结构完整性属性测试

使用hypothesis进行属性测试，验证报告结构完整性和输出格式一致性。

Property 8: 报告结构完整性
Property 9: JSON/文本格式输出一致性

Validates: Requirements 9.1, 9.3, 9.4, 9.5
"""

import json
import pytest
from datetime import datetime
from hypothesis import given, strategies as st, settings, assume

from src.models.analysis_result import (
    AnalysisReport,
    Confidence,
    KeyLevel,
    LevelImportance,
    LevelStrength,
    LevelType,
    LongTermExpectation,
    MonthlyExpectation,
    OpeningScenario,
    PositionAnalysis,
    PriceLevel,
    ShortTermExpectation,
    SupportResistanceResult,
    TrendDirection,
    TrendReversalSignal,
    WatchLevel,
    WeeklyExpectation,
)
from src.output.report_generator import ReportGenerator


# ========== 策略定义 ==========

# 有效价格策略
valid_price = st.floats(
    min_value=100.0, max_value=100000.0, 
    allow_nan=False, allow_infinity=False
)

# 有效百分比策略
valid_percentage = st.floats(
    min_value=0.0, max_value=100.0,
    allow_nan=False, allow_infinity=False
)

# 非空文本策略
non_empty_text = st.text(min_size=1, max_size=100).filter(lambda x: x.strip())

# 日期时间策略
valid_datetime = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31)
)

# 数据截止时间字符串策略
data_cutoff_strategy = st.from_regex(
    r"20[2-3][0-9]-[0-1][0-9]-[0-3][0-9]( [0-2][0-9]:[0-5][0-9]:[0-5][0-9])?",
    fullmatch=True
)


def price_level_strategy(level_type: LevelType):
    """生成PriceLevel的策略"""
    return st.builds(
        PriceLevel,
        price=valid_price,
        level_type=st.just(level_type),
        importance=st.sampled_from(list(LevelImportance)),
        description=non_empty_text,
        strength=st.sampled_from(list(LevelStrength)),
    )


support_level_strategy = price_level_strategy(LevelType.SUPPORT)
resistance_level_strategy = price_level_strategy(LevelType.RESISTANCE)


# 关键位策略
key_level_strategy = st.builds(
    KeyLevel,
    price=valid_price,
    reason=non_empty_text,
)

# 支撑压力位结果策略
support_resistance_strategy = st.builds(
    SupportResistanceResult,
    support_levels=st.lists(support_level_strategy, min_size=1, max_size=3),
    resistance_levels=st.lists(resistance_level_strategy, min_size=1, max_size=3),
    key_support_today=st.one_of(st.none(), key_level_strategy),
    key_resistance_today=st.one_of(st.none(), key_level_strategy),
    analysis_notes=st.text(max_size=200),
)

# 位置分析策略
position_analysis_strategy = st.builds(
    PositionAnalysis,
    current_price=valid_price,
    nearest_support=st.one_of(st.none(), support_level_strategy),
    nearest_resistance=st.one_of(st.none(), resistance_level_strategy),
    support_distance_points=valid_price,
    support_distance_pct=valid_percentage,
    resistance_distance_points=valid_price,
    resistance_distance_pct=valid_percentage,
    position_description=non_empty_text,
)

# 开盘场景策略
opening_scenario_strategy = st.builds(
    OpeningScenario,
    scenario=non_empty_text,
    probability=non_empty_text,
    expectation=non_empty_text,
    target_levels=st.lists(valid_price, max_size=3),
    stop_levels=st.lists(valid_price, max_size=3),
)

# 观察点位策略
watch_level_strategy = st.builds(
    WatchLevel,
    price=valid_price,
    significance=non_empty_text,
)

# 短期预期策略
short_term_strategy = st.builds(
    ShortTermExpectation,
    opening_scenarios=st.lists(opening_scenario_strategy, min_size=1, max_size=3),
    key_levels_to_watch=st.lists(watch_level_strategy, max_size=5),
    operation_suggestion=non_empty_text,
    confidence=st.sampled_from(list(Confidence)),
    risk_warning=st.text(max_size=100),
)

# 周线预期策略
weekly_expectation_strategy = st.builds(
    WeeklyExpectation,
    direction=st.sampled_from(list(TrendDirection)),
    target_range=st.lists(valid_price, min_size=2, max_size=2),
    key_events=st.lists(non_empty_text, max_size=3),
)

# 月线预期策略
monthly_expectation_strategy = st.builds(
    MonthlyExpectation,
    direction=st.sampled_from(list(TrendDirection)),
    target_range=st.lists(valid_price, min_size=2, max_size=2),
    key_levels=st.lists(non_empty_text, max_size=3),
)

# 趋势转折信号策略
trend_reversal_signal_strategy = st.builds(
    TrendReversalSignal,
    signal=non_empty_text,
    trigger_level=valid_price,
)

# 中长期预期策略
long_term_strategy = st.builds(
    LongTermExpectation,
    current_trend=non_empty_text,
    trend_strength=st.sampled_from(["强", "中", "弱"]),
    weekly_expectation=st.one_of(st.none(), weekly_expectation_strategy),
    monthly_expectation=st.one_of(st.none(), monthly_expectation_strategy),
    trend_reversal_signals=st.lists(trend_reversal_signal_strategy, max_size=3),
    confidence=st.sampled_from(list(Confidence)),
)

# 完整分析报告策略
analysis_report_strategy = st.builds(
    AnalysisReport,
    analysis_time=valid_datetime,
    data_cutoff=data_cutoff_strategy,
    current_price=valid_price,
    support_resistance=support_resistance_strategy,
    position_analysis=position_analysis_strategy,
    short_term=short_term_strategy,
    long_term=long_term_strategy,
)


# ========== Property 8: 报告结构完整性 ==========

class TestReportStructureCompleteness:
    """
    Property 8: 报告结构完整性
    
    *For any* 分析报告输出，必须包含所有必要字段：分析时间戳、数据截止时间、
    支撑位列表、压力位列表、位置分析、短期预期、中长期预期、置信度。
    
    **Validates: Requirements 9.1, 9.3, 9.4**
    """
    
    def setup_method(self):
        """测试前初始化"""
        self.generator = ReportGenerator()
    
    @given(report=analysis_report_strategy)
    @settings(max_examples=100)
    def test_json_output_contains_all_required_fields(self, report: AnalysisReport):
        """
        Feature: market-analysis-agent, Property 8: 报告结构完整性
        
        验证JSON输出包含所有必要字段
        """
        json_output = self.generator.generate_json(report)
        data = json.loads(json_output)
        
        # 验证顶层必要字段
        required_fields = [
            "analysis_time",
            "data_cutoff", 
            "current_price",
            "support_levels",
            "resistance_levels",
            "position_analysis",
            "short_term",
            "long_term",
        ]
        
        for field in required_fields:
            assert field in data, f"JSON输出缺少必要字段: {field}"
        
        # 验证分析时间戳格式
        assert data["analysis_time"], "分析时间戳不能为空"
        
        # 验证数据截止时间
        assert data["data_cutoff"], "数据截止时间不能为空"
        
        # 验证当前价格
        assert data["current_price"] > 0, "当前价格必须为正数"
        
        # 验证支撑位列表是列表类型
        assert isinstance(data["support_levels"], list), "支撑位必须是列表"
        
        # 验证压力位列表是列表类型
        assert isinstance(data["resistance_levels"], list), "压力位必须是列表"
    
    @given(report=analysis_report_strategy)
    @settings(max_examples=100)
    def test_json_output_contains_position_analysis_fields(
        self, report: AnalysisReport
    ):
        """
        Feature: market-analysis-agent, Property 8: 报告结构完整性
        
        验证JSON输出的位置分析包含必要字段
        """
        json_output = self.generator.generate_json(report)
        data = json.loads(json_output)
        
        position = data["position_analysis"]
        required_position_fields = [
            "support_distance_pct",
            "resistance_distance_pct",
            "position",
        ]
        
        for field in required_position_fields:
            assert field in position, f"位置分析缺少必要字段: {field}"
    
    @given(report=analysis_report_strategy)
    @settings(max_examples=100)
    def test_json_output_contains_short_term_fields(self, report: AnalysisReport):
        """
        Feature: market-analysis-agent, Property 8: 报告结构完整性
        
        验证JSON输出的短期预期包含必要字段
        """
        json_output = self.generator.generate_json(report)
        data = json.loads(json_output)
        
        short_term = data["short_term"]
        required_short_term_fields = [
            "scenarios",
            "suggestion",
            "confidence",
        ]
        
        for field in required_short_term_fields:
            assert field in short_term, f"短期预期缺少必要字段: {field}"
        
        # 验证置信度值有效
        valid_confidences = ["high", "medium", "low"]
        assert short_term["confidence"] in valid_confidences, (
            f"短期预期置信度无效: {short_term['confidence']}"
        )
    
    @given(report=analysis_report_strategy)
    @settings(max_examples=100)
    def test_json_output_contains_long_term_fields(self, report: AnalysisReport):
        """
        Feature: market-analysis-agent, Property 8: 报告结构完整性
        
        验证JSON输出的中长期预期包含必要字段
        """
        json_output = self.generator.generate_json(report)
        data = json.loads(json_output)
        
        long_term = data["long_term"]
        required_long_term_fields = [
            "trend",
            "confidence",
        ]
        
        for field in required_long_term_fields:
            assert field in long_term, f"中长期预期缺少必要字段: {field}"
        
        # 验证置信度值有效
        valid_confidences = ["high", "medium", "low"]
        assert long_term["confidence"] in valid_confidences, (
            f"中长期预期置信度无效: {long_term['confidence']}"
        )
    
    @given(report=analysis_report_strategy)
    @settings(max_examples=100)
    def test_validate_report_passes_for_valid_report(self, report: AnalysisReport):
        """
        Feature: market-analysis-agent, Property 8: 报告结构完整性
        
        验证有效报告通过验证
        """
        is_valid, errors = self.generator.validate_report(report)
        
        assert is_valid, f"有效报告应通过验证，错误: {errors}"
        assert len(errors) == 0, f"有效报告不应有错误: {errors}"


# ========== Property 9: JSON/文本格式输出一致性 ==========

class TestJsonTextOutputConsistency:
    """
    Property 9: JSON/文本格式输出一致性
    
    *For any* 分析结果，JSON格式和文本格式输出应该包含相同的核心信息
    （支撑压力位、预期结论）。
    
    **Validates: Requirements 9.5**
    """
    
    def setup_method(self):
        """测试前初始化"""
        self.generator = ReportGenerator()
    
    @given(report=analysis_report_strategy)
    @settings(max_examples=100)
    def test_support_levels_present_in_both_formats(self, report: AnalysisReport):
        """
        Feature: market-analysis-agent, Property 9: JSON/文本格式输出一致性
        
        验证支撑位在JSON和文本格式中都存在
        """
        json_output = self.generator.generate_json(report)
        text_output = self.generator.generate_text(report)
        
        json_data = json.loads(json_output)
        
        # 验证JSON中的支撑位价格在文本中也存在
        for level in json_data["support_levels"]:
            price = level["price"]
            # 价格应该以某种格式出现在文本中
            price_str = f"{price:.2f}"
            assert price_str in text_output, (
                f"支撑位价格 {price_str} 应出现在文本输出中"
            )
    
    @given(report=analysis_report_strategy)
    @settings(max_examples=100)
    def test_resistance_levels_present_in_both_formats(self, report: AnalysisReport):
        """
        Feature: market-analysis-agent, Property 9: JSON/文本格式输出一致性
        
        验证压力位在JSON和文本格式中都存在
        """
        json_output = self.generator.generate_json(report)
        text_output = self.generator.generate_text(report)
        
        json_data = json.loads(json_output)
        
        # 验证JSON中的压力位价格在文本中也存在
        for level in json_data["resistance_levels"]:
            price = level["price"]
            price_str = f"{price:.2f}"
            assert price_str in text_output, (
                f"压力位价格 {price_str} 应出现在文本输出中"
            )
    
    @given(report=analysis_report_strategy)
    @settings(max_examples=100)
    def test_current_price_present_in_both_formats(self, report: AnalysisReport):
        """
        Feature: market-analysis-agent, Property 9: JSON/文本格式输出一致性
        
        验证当前价格在JSON和文本格式中都存在
        """
        json_output = self.generator.generate_json(report)
        text_output = self.generator.generate_text(report)
        
        json_data = json.loads(json_output)
        
        current_price = json_data["current_price"]
        price_str = f"{current_price:.2f}"
        
        assert price_str in text_output, (
            f"当前价格 {price_str} 应出现在文本输出中"
        )
    
    @given(report=analysis_report_strategy)
    @settings(max_examples=100)
    def test_confidence_present_in_both_formats(self, report: AnalysisReport):
        """
        Feature: market-analysis-agent, Property 9: JSON/文本格式输出一致性
        
        验证置信度在JSON和文本格式中都存在
        """
        json_output = self.generator.generate_json(report)
        text_output = self.generator.generate_text(report)
        
        json_data = json.loads(json_output)
        
        # 短期预期置信度
        short_term_confidence = json_data["short_term"]["confidence"]
        # 文本中可能显示为中文或英文
        confidence_map = {"high": "高", "medium": "中", "low": "低"}
        
        # 检查置信度值（英文或中文）出现在文本中
        assert (
            short_term_confidence in text_output or 
            confidence_map.get(short_term_confidence, "") in text_output
        ), f"短期预期置信度 {short_term_confidence} 应出现在文本输出中"
        
        # 中长期预期置信度
        long_term_confidence = json_data["long_term"]["confidence"]
        assert (
            long_term_confidence in text_output or
            confidence_map.get(long_term_confidence, "") in text_output
        ), f"中长期预期置信度 {long_term_confidence} 应出现在文本输出中"
    
    @given(report=analysis_report_strategy)
    @settings(max_examples=100)
    def test_analysis_time_present_in_both_formats(self, report: AnalysisReport):
        """
        Feature: market-analysis-agent, Property 9: JSON/文本格式输出一致性
        
        验证分析时间在JSON和文本格式中都存在
        """
        json_output = self.generator.generate_json(report)
        text_output = self.generator.generate_text(report)
        
        json_data = json.loads(json_output)
        
        # 分析时间应该出现在文本中
        analysis_time = json_data["analysis_time"]
        # 时间格式可能略有不同，检查日期部分
        date_part = analysis_time.split(" ")[0]
        
        assert date_part in text_output, (
            f"分析时间日期 {date_part} 应出现在文本输出中"
        )
    
    @given(report=analysis_report_strategy)
    @settings(max_examples=100)
    def test_data_cutoff_present_in_both_formats(self, report: AnalysisReport):
        """
        Feature: market-analysis-agent, Property 9: JSON/文本格式输出一致性
        
        验证数据截止时间在JSON和文本格式中都存在
        """
        json_output = self.generator.generate_json(report)
        text_output = self.generator.generate_text(report)
        
        json_data = json.loads(json_output)
        
        data_cutoff = json_data["data_cutoff"]
        
        assert data_cutoff in text_output, (
            f"数据截止时间 {data_cutoff} 应出现在文本输出中"
        )
    
    @given(report=analysis_report_strategy)
    @settings(max_examples=100)
    def test_trend_present_in_both_formats(self, report: AnalysisReport):
        """
        Feature: market-analysis-agent, Property 9: JSON/文本格式输出一致性
        
        验证趋势判断在JSON和文本格式中都存在
        """
        json_output = self.generator.generate_json(report)
        text_output = self.generator.generate_text(report)
        
        json_data = json.loads(json_output)
        
        trend = json_data["long_term"]["trend"]
        
        assert trend in text_output, (
            f"趋势判断 '{trend}' 应出现在文本输出中"
        )
    
    @given(report=analysis_report_strategy)
    @settings(max_examples=100)
    def test_json_and_text_both_non_empty(self, report: AnalysisReport):
        """
        Feature: market-analysis-agent, Property 9: JSON/文本格式输出一致性
        
        验证JSON和文本输出都非空
        """
        json_output = self.generator.generate_json(report)
        text_output = self.generator.generate_text(report)
        
        assert len(json_output) > 0, "JSON输出不应为空"
        assert len(text_output) > 0, "文本输出不应为空"
        
        # JSON应该是有效的JSON
        try:
            json.loads(json_output)
        except json.JSONDecodeError as e:
            pytest.fail(f"JSON输出无效: {e}")
