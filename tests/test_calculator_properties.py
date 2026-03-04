"""价格距离计算属性测试

使用hypothesis进行属性测试，验证价格距离计算和位置判断的正确性。

Property 5: 价格距离计算正确性
Property 6: 价格位置判断一致性

Validates: Requirements 5.1, 5.2, 5.3
"""

import pytest
from hypothesis import given, strategies as st, settings, assume

from src.analysis.calculator import (
    PriceCalculator,
    DistanceResult,
    calculate_price_distance,
)
from src.models.analysis_result import (
    PriceLevel,
    LevelType,
    LevelImportance,
    LevelStrength,
    SupportResistanceResult,
)


# ========== 策略定义 ==========

# 有效价格策略：正数，合理范围（股票指数通常在100-100000之间）
valid_price = st.floats(min_value=100.0, max_value=100000.0, allow_nan=False, allow_infinity=False)

# 小正数价格策略（用于边界测试）
small_positive_price = st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False)


def price_level_strategy(level_type: LevelType):
    """生成PriceLevel的策略"""
    return st.builds(
        PriceLevel,
        price=valid_price,
        level_type=st.just(level_type),
        importance=st.sampled_from(list(LevelImportance)),
        description=st.text(min_size=1, max_size=50),
        strength=st.sampled_from(list(LevelStrength)),
    )


support_level_strategy = price_level_strategy(LevelType.SUPPORT)
resistance_level_strategy = price_level_strategy(LevelType.RESISTANCE)


# ========== Property 5: 价格距离计算正确性 ==========

class TestPriceDistanceCalculation:
    """
    Property 5: 价格距离计算正确性
    
    *For any* 当前价格和支撑压力位列表，计算的距离（点数和百分比）应该数学正确。
    
    **Validates: Requirements 5.1, 5.2**
    
    测试方法：
    - 生成随机的当前价格和支撑压力位
    - 调用距离计算函数
    - 验证：距离点数 = |当前价格 - 目标价位|
    - 验证：距离百分比 = 距离点数 / 当前价格 * 100
    """
    
    @given(
        current_price=valid_price,
        target_price=valid_price,
    )
    @settings(max_examples=100)
    def test_distance_points_mathematically_correct(
        self, current_price: float, target_price: float
    ):
        """
        Feature: market-analysis-agent, Property 5: 价格距离计算正确性
        
        验证距离点数计算的数学正确性：
        距离点数 = |当前价格 - 目标价位|
        """
        result = calculate_price_distance(current_price, target_price)
        
        expected_points = abs(current_price - target_price)
        
        # 允许浮点数精度误差（四舍五入到2位小数）
        assert abs(result.points - round(expected_points, 2)) < 0.01, (
            f"距离点数计算错误: "
            f"当前价格={current_price}, 目标价格={target_price}, "
            f"期望={round(expected_points, 2)}, 实际={result.points}"
        )
    
    @given(
        current_price=valid_price,
        target_price=valid_price,
    )
    @settings(max_examples=100)
    def test_distance_percentage_mathematically_correct(
        self, current_price: float, target_price: float
    ):
        """
        Feature: market-analysis-agent, Property 5: 价格距离计算正确性
        
        验证距离百分比计算的数学正确性：
        距离百分比 = 距离点数 / 当前价格 * 100
        """
        result = calculate_price_distance(current_price, target_price)
        
        expected_points = abs(current_price - target_price)
        expected_percentage = (expected_points / current_price) * 100
        
        # 允许浮点数精度误差（四舍五入到2位小数）
        assert abs(result.percentage - round(expected_percentage, 2)) < 0.01, (
            f"距离百分比计算错误: "
            f"当前价格={current_price}, 目标价格={target_price}, "
            f"期望={round(expected_percentage, 2)}%, 实际={result.percentage}%"
        )
    
    @given(current_price=valid_price)
    @settings(max_examples=100)
    def test_distance_to_same_price_is_zero(self, current_price: float):
        """
        Feature: market-analysis-agent, Property 5: 价格距离计算正确性
        
        验证当前价格与自身的距离为零
        """
        result = calculate_price_distance(current_price, current_price)
        
        assert result.points == 0.0, f"相同价格的距离应为0，实际={result.points}"
        assert result.percentage == 0.0, f"相同价格的百分比应为0，实际={result.percentage}"
    
    @given(
        current_price=valid_price,
        target_price=valid_price,
    )
    @settings(max_examples=100)
    def test_distance_is_symmetric(self, current_price: float, target_price: float):
        """
        Feature: market-analysis-agent, Property 5: 价格距离计算正确性
        
        验证距离计算的对称性（点数部分）：
        |A - B| = |B - A|
        """
        result1 = calculate_price_distance(current_price, target_price)
        result2 = calculate_price_distance(target_price, current_price)
        
        # 点数应该相同（对称性）
        assert abs(result1.points - result2.points) < 0.01, (
            f"距离点数应该对称: "
            f"distance({current_price}, {target_price})={result1.points}, "
            f"distance({target_price}, {current_price})={result2.points}"
        )
    
    @given(
        current_price=valid_price,
        target_price=valid_price,
    )
    @settings(max_examples=100)
    def test_distance_is_non_negative(self, current_price: float, target_price: float):
        """
        Feature: market-analysis-agent, Property 5: 价格距离计算正确性
        
        验证距离始终为非负数
        """
        result = calculate_price_distance(current_price, target_price)
        
        assert result.points >= 0, f"距离点数应为非负数，实际={result.points}"
        assert result.percentage >= 0, f"距离百分比应为非负数，实际={result.percentage}"


# ========== Property 6: 价格位置判断一致性 ==========

class TestPricePositionConsistency:
    """
    Property 6: 价格位置判断一致性
    
    *For any* 当前价格和最近的支撑位、压力位，位置判断应该与距离比例一致：
    - 如果距离支撑位 < 距离压力位的30%，则判断为"接近支撑位"
    - 如果距离压力位 < 距离支撑位的30%，则判断为"接近压力位"
    - 否则判断为"中间区域"
    
    **Validates: Requirements 5.3**
    """
    
    @given(
        current_price=st.floats(min_value=1000.0, max_value=5000.0, allow_nan=False, allow_infinity=False),
        # 使用较小的support_offset和较大的resistance_offset来确保接近支撑位
        support_offset=st.floats(min_value=5.0, max_value=50.0, allow_nan=False, allow_infinity=False),
        resistance_offset=st.floats(min_value=100.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_position_near_support_when_close_to_support(
        self, 
        current_price: float, 
        support_offset: float,
        resistance_offset: float,
    ):
        """
        Feature: market-analysis-agent, Property 6: 价格位置判断一致性
        
        验证当距离支撑位 < 总距离的30%时，判断为"接近支撑位"
        """
        # 构造场景：当前价格接近支撑位
        # 支撑位在下方，压力位在上方
        support_price = current_price - support_offset
        resistance_price = current_price + resistance_offset
        
        total_range = support_offset + resistance_offset
        support_ratio = support_offset / total_range
        
        # 只测试接近支撑位的情况（support_ratio < 0.3）
        # 由于策略已调整，大部分情况应满足条件
        assume(support_ratio < PriceCalculator.NEAR_THRESHOLD)
        
        support_level = PriceLevel(
            price=support_price,
            level_type=LevelType.SUPPORT,
            importance=LevelImportance.DAILY,
            description="测试支撑位",
            strength=LevelStrength.MEDIUM,
        )
        resistance_level = PriceLevel(
            price=resistance_price,
            level_type=LevelType.RESISTANCE,
            importance=LevelImportance.DAILY,
            description="测试压力位",
            strength=LevelStrength.MEDIUM,
        )
        
        position = PriceCalculator.determine_position(
            current_price, support_level, resistance_level
        )
        
        assert position == "接近支撑位", (
            f"当support_ratio={support_ratio:.2f} < 0.3时，应判断为'接近支撑位'，"
            f"实际判断为'{position}'"
        )
    
    @given(
        current_price=st.floats(min_value=1000.0, max_value=5000.0, allow_nan=False, allow_infinity=False),
        # 使用较大的support_offset和较小的resistance_offset来确保接近压力位
        support_offset=st.floats(min_value=100.0, max_value=500.0, allow_nan=False, allow_infinity=False),
        resistance_offset=st.floats(min_value=5.0, max_value=50.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_position_near_resistance_when_close_to_resistance(
        self, 
        current_price: float, 
        support_offset: float,
        resistance_offset: float,
    ):
        """
        Feature: market-analysis-agent, Property 6: 价格位置判断一致性
        
        验证当距离压力位 < 总距离的30%时，判断为"接近压力位"
        """
        support_price = current_price - support_offset
        resistance_price = current_price + resistance_offset
        
        total_range = support_offset + resistance_offset
        resistance_ratio = resistance_offset / total_range
        
        # 只测试接近压力位的情况（resistance_ratio < 0.3）
        # 由于策略已调整，大部分情况应满足条件
        assume(resistance_ratio < PriceCalculator.NEAR_THRESHOLD)
        
        support_level = PriceLevel(
            price=support_price,
            level_type=LevelType.SUPPORT,
            importance=LevelImportance.DAILY,
            description="测试支撑位",
            strength=LevelStrength.MEDIUM,
        )
        resistance_level = PriceLevel(
            price=resistance_price,
            level_type=LevelType.RESISTANCE,
            importance=LevelImportance.DAILY,
            description="测试压力位",
            strength=LevelStrength.MEDIUM,
        )
        
        position = PriceCalculator.determine_position(
            current_price, support_level, resistance_level
        )
        
        assert position == "接近压力位", (
            f"当resistance_ratio={resistance_ratio:.2f} < 0.3时，应判断为'接近压力位'，"
            f"实际判断为'{position}'"
        )
    
    @given(
        current_price=st.floats(min_value=1000.0, max_value=5000.0, allow_nan=False, allow_infinity=False),
        support_offset=st.floats(min_value=10.0, max_value=500.0, allow_nan=False, allow_infinity=False),
        resistance_offset=st.floats(min_value=10.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_position_middle_when_not_close_to_either(
        self, 
        current_price: float, 
        support_offset: float,
        resistance_offset: float,
    ):
        """
        Feature: market-analysis-agent, Property 6: 价格位置判断一致性
        
        验证当两边距离比例都 >= 30%时，判断为中间区域相关
        """
        support_price = current_price - support_offset
        resistance_price = current_price + resistance_offset
        
        total_range = support_offset + resistance_offset
        support_ratio = support_offset / total_range
        resistance_ratio = resistance_offset / total_range
        
        # 只测试中间区域的情况（两边都 >= 0.3）
        assume(support_ratio >= PriceCalculator.NEAR_THRESHOLD)
        assume(resistance_ratio >= PriceCalculator.NEAR_THRESHOLD)
        
        support_level = PriceLevel(
            price=support_price,
            level_type=LevelType.SUPPORT,
            importance=LevelImportance.DAILY,
            description="测试支撑位",
            strength=LevelStrength.MEDIUM,
        )
        resistance_level = PriceLevel(
            price=resistance_price,
            level_type=LevelType.RESISTANCE,
            importance=LevelImportance.DAILY,
            description="测试压力位",
            strength=LevelStrength.MEDIUM,
        )
        
        position = PriceCalculator.determine_position(
            current_price, support_level, resistance_level
        )
        
        # 中间区域可能是"中间区域"、"中间偏支撑"或"中间偏压力"
        valid_middle_positions = ["中间区域", "中间偏支撑", "中间偏压力"]
        assert position in valid_middle_positions, (
            f"当support_ratio={support_ratio:.2f} >= 0.3 且 "
            f"resistance_ratio={resistance_ratio:.2f} >= 0.3时，"
            f"应判断为中间区域相关，实际判断为'{position}'"
        )
    
    @given(current_price=valid_price)
    @settings(max_examples=100)
    def test_position_with_only_support(self, current_price: float):
        """
        Feature: market-analysis-agent, Property 6: 价格位置判断一致性
        
        验证只有支撑位时的位置判断
        """
        support_level = PriceLevel(
            price=current_price - 100,
            level_type=LevelType.SUPPORT,
            importance=LevelImportance.DAILY,
            description="测试支撑位",
            strength=LevelStrength.MEDIUM,
        )
        
        position = PriceCalculator.determine_position(
            current_price, support_level, None
        )
        
        assert position == "接近支撑位", (
            f"只有支撑位时应判断为'接近支撑位'，实际判断为'{position}'"
        )
    
    @given(current_price=valid_price)
    @settings(max_examples=100)
    def test_position_with_only_resistance(self, current_price: float):
        """
        Feature: market-analysis-agent, Property 6: 价格位置判断一致性
        
        验证只有压力位时的位置判断
        """
        resistance_level = PriceLevel(
            price=current_price + 100,
            level_type=LevelType.RESISTANCE,
            importance=LevelImportance.DAILY,
            description="测试压力位",
            strength=LevelStrength.MEDIUM,
        )
        
        position = PriceCalculator.determine_position(
            current_price, None, resistance_level
        )
        
        assert position == "接近压力位", (
            f"只有压力位时应判断为'接近压力位'，实际判断为'{position}'"
        )
    
    @given(current_price=valid_price)
    @settings(max_examples=100)
    def test_position_with_no_levels(self, current_price: float):
        """
        Feature: market-analysis-agent, Property 6: 价格位置判断一致性
        
        验证没有支撑压力位时的位置判断
        """
        position = PriceCalculator.determine_position(current_price, None, None)
        
        assert "无法判断" in position, (
            f"没有支撑压力位时应包含'无法判断'，实际判断为'{position}'"
        )
