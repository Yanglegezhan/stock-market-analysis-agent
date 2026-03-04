"""支撑压力位数量约束属性测试

使用hypothesis进行属性测试，验证支撑压力位的数量约束和价格关系。

Property 7: 支撑压力位数量约束

Validates: Requirements 5.4
"""

import pytest
from hypothesis import given, strategies as st, settings, assume

from src.models.analysis_result import (
    PriceLevel,
    LevelType,
    LevelImportance,
    LevelStrength,
    SupportResistanceResult,
    KeyLevel,
)
from src.analysis.calculator import PriceCalculator


# ========== 策略定义 ==========

# 有效价格策略：正数，合理范围（股票指数通常在100-100000之间）
valid_price = st.floats(
    min_value=1000.0, 
    max_value=10000.0, 
    allow_nan=False, 
    allow_infinity=False
)


def support_level_strategy(max_price: float):
    """生成支撑位的策略（价格低于max_price）"""
    return st.builds(
        PriceLevel,
        price=st.floats(
            min_value=100.0, 
            max_value=max_price - 1.0, 
            allow_nan=False, 
            allow_infinity=False
        ),
        level_type=st.just(LevelType.SUPPORT),
        importance=st.sampled_from(list(LevelImportance)),
        description=st.text(min_size=1, max_size=50),
        strength=st.sampled_from(list(LevelStrength)),
    )


def resistance_level_strategy(min_price: float):
    """生成压力位的策略（价格高于min_price）"""
    return st.builds(
        PriceLevel,
        price=st.floats(
            min_value=min_price + 1.0, 
            max_value=20000.0, 
            allow_nan=False, 
            allow_infinity=False
        ),
        level_type=st.just(LevelType.RESISTANCE),
        importance=st.sampled_from(list(LevelImportance)),
        description=st.text(min_size=1, max_size=50),
        strength=st.sampled_from(list(LevelStrength)),
    )


# ========== Property 7: 支撑压力位数量约束 ==========

class TestSupportResistanceLevelConstraints:
    """
    Property 7: 支撑压力位数量约束
    
    *For any* LLM分析结果，输出的支撑位和压力位各应该有3个（或在数据不足时尽可能多）。
    
    **Validates: Requirements 5.4**
    
    测试方法：
    - 调用分析函数
    - 验证支撑位列表长度 <= 3
    - 验证压力位列表长度 <= 3
    - 验证支撑位价格都 < 当前价格
    - 验证压力位价格都 > 当前价格
    """
    
    @given(
        current_price=st.floats(
            min_value=3000.0, 
            max_value=5000.0, 
            allow_nan=False, 
            allow_infinity=False
        ),
        num_supports=st.integers(min_value=0, max_value=10),
        num_resistances=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=100)
    def test_nearby_levels_count_constraint(
        self, 
        current_price: float, 
        num_supports: int,
        num_resistances: int
    ):
        """
        Feature: market-analysis-agent, Property 7: 支撑压力位数量约束
        
        验证get_nearby_levels返回的支撑位和压力位各不超过3个
        """
        # 生成支撑位（价格低于当前价格）
        support_levels = []
        for i in range(num_supports):
            price = current_price - (i + 1) * 50  # 每个支撑位间隔50点
            if price > 100:  # 确保价格有效
                support_levels.append(PriceLevel(
                    price=price,
                    level_type=LevelType.SUPPORT,
                    importance=LevelImportance.DAILY,
                    description=f"支撑位{i+1}",
                    strength=LevelStrength.MEDIUM,
                ))
        
        # 生成压力位（价格高于当前价格）
        resistance_levels = []
        for i in range(num_resistances):
            price = current_price + (i + 1) * 50  # 每个压力位间隔50点
            resistance_levels.append(PriceLevel(
                price=price,
                level_type=LevelType.RESISTANCE,
                importance=LevelImportance.DAILY,
                description=f"压力位{i+1}",
                strength=LevelStrength.MEDIUM,
            ))
        
        sr_result = SupportResistanceResult(
            support_levels=support_levels,
            resistance_levels=resistance_levels,
        )
        
        # 调用get_nearby_levels
        nearby_supports, nearby_resistances = PriceCalculator.get_nearby_levels(
            current_price, sr_result, count=3
        )
        
        # 验证数量约束
        assert len(nearby_supports) <= 3, (
            f"支撑位数量应 <= 3，实际={len(nearby_supports)}"
        )
        assert len(nearby_resistances) <= 3, (
            f"压力位数量应 <= 3，实际={len(nearby_resistances)}"
        )
        
        # 验证返回数量不超过输入数量
        expected_support_count = min(len(support_levels), 3)
        expected_resistance_count = min(len(resistance_levels), 3)
        
        assert len(nearby_supports) == expected_support_count, (
            f"支撑位数量应为{expected_support_count}，实际={len(nearby_supports)}"
        )
        assert len(nearby_resistances) == expected_resistance_count, (
            f"压力位数量应为{expected_resistance_count}，实际={len(nearby_resistances)}"
        )
    
    @given(
        current_price=st.floats(
            min_value=3000.0, 
            max_value=5000.0, 
            allow_nan=False, 
            allow_infinity=False
        ),
        num_supports=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_support_prices_below_current(
        self, 
        current_price: float, 
        num_supports: int
    ):
        """
        Feature: market-analysis-agent, Property 7: 支撑压力位数量约束
        
        验证所有返回的支撑位价格都低于当前价格
        """
        # 生成支撑位（价格低于当前价格）
        support_levels = []
        for i in range(num_supports):
            price = current_price - (i + 1) * 50
            if price > 100:
                support_levels.append(PriceLevel(
                    price=price,
                    level_type=LevelType.SUPPORT,
                    importance=LevelImportance.DAILY,
                    description=f"支撑位{i+1}",
                    strength=LevelStrength.MEDIUM,
                ))
        
        assume(len(support_levels) > 0)  # 确保至少有一个有效支撑位
        
        sr_result = SupportResistanceResult(
            support_levels=support_levels,
            resistance_levels=[],
        )
        
        nearby_supports, _ = PriceCalculator.get_nearby_levels(
            current_price, sr_result, count=3
        )
        
        # 验证所有支撑位价格 < 当前价格
        for support in nearby_supports:
            assert support.price < current_price, (
                f"支撑位价格{support.price}应 < 当前价格{current_price}"
            )
    
    @given(
        current_price=st.floats(
            min_value=3000.0, 
            max_value=5000.0, 
            allow_nan=False, 
            allow_infinity=False
        ),
        num_resistances=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_resistance_prices_above_current(
        self, 
        current_price: float, 
        num_resistances: int
    ):
        """
        Feature: market-analysis-agent, Property 7: 支撑压力位数量约束
        
        验证所有返回的压力位价格都高于当前价格
        """
        # 生成压力位（价格高于当前价格）
        resistance_levels = []
        for i in range(num_resistances):
            price = current_price + (i + 1) * 50
            resistance_levels.append(PriceLevel(
                price=price,
                level_type=LevelType.RESISTANCE,
                importance=LevelImportance.DAILY,
                description=f"压力位{i+1}",
                strength=LevelStrength.MEDIUM,
            ))
        
        sr_result = SupportResistanceResult(
            support_levels=[],
            resistance_levels=resistance_levels,
        )
        
        _, nearby_resistances = PriceCalculator.get_nearby_levels(
            current_price, sr_result, count=3
        )
        
        # 验证所有压力位价格 > 当前价格
        for resistance in nearby_resistances:
            assert resistance.price > current_price, (
                f"压力位价格{resistance.price}应 > 当前价格{current_price}"
            )
    
    @given(
        current_price=st.floats(
            min_value=3000.0, 
            max_value=5000.0, 
            allow_nan=False, 
            allow_infinity=False
        ),
    )
    @settings(max_examples=100)
    def test_nearby_levels_sorted_by_proximity(
        self, 
        current_price: float
    ):
        """
        Feature: market-analysis-agent, Property 7: 支撑压力位数量约束
        
        验证返回的支撑压力位按距离当前价格的远近排序
        - 支撑位：按价格降序（最近的在前）
        - 压力位：按价格升序（最近的在前）
        """
        # 生成多个支撑位
        support_levels = [
            PriceLevel(
                price=current_price - 100,
                level_type=LevelType.SUPPORT,
                importance=LevelImportance.DAILY,
                description="支撑位1",
                strength=LevelStrength.MEDIUM,
            ),
            PriceLevel(
                price=current_price - 200,
                level_type=LevelType.SUPPORT,
                importance=LevelImportance.M15,
                description="支撑位2",
                strength=LevelStrength.WEAK,
            ),
            PriceLevel(
                price=current_price - 50,
                level_type=LevelType.SUPPORT,
                importance=LevelImportance.M5,
                description="支撑位3",
                strength=LevelStrength.STRONG,
            ),
            PriceLevel(
                price=current_price - 300,
                level_type=LevelType.SUPPORT,
                importance=LevelImportance.MA,
                description="支撑位4",
                strength=LevelStrength.MEDIUM,
            ),
        ]
        
        # 生成多个压力位
        resistance_levels = [
            PriceLevel(
                price=current_price + 150,
                level_type=LevelType.RESISTANCE,
                importance=LevelImportance.DAILY,
                description="压力位1",
                strength=LevelStrength.MEDIUM,
            ),
            PriceLevel(
                price=current_price + 50,
                level_type=LevelType.RESISTANCE,
                importance=LevelImportance.M15,
                description="压力位2",
                strength=LevelStrength.WEAK,
            ),
            PriceLevel(
                price=current_price + 250,
                level_type=LevelType.RESISTANCE,
                importance=LevelImportance.M5,
                description="压力位3",
                strength=LevelStrength.STRONG,
            ),
            PriceLevel(
                price=current_price + 100,
                level_type=LevelType.RESISTANCE,
                importance=LevelImportance.MA,
                description="压力位4",
                strength=LevelStrength.MEDIUM,
            ),
        ]
        
        sr_result = SupportResistanceResult(
            support_levels=support_levels,
            resistance_levels=resistance_levels,
        )
        
        nearby_supports, nearby_resistances = PriceCalculator.get_nearby_levels(
            current_price, sr_result, count=3
        )
        
        # 验证支撑位按价格降序排列（最近的在前）
        for i in range(len(nearby_supports) - 1):
            assert nearby_supports[i].price >= nearby_supports[i + 1].price, (
                f"支撑位应按价格降序排列: "
                f"{nearby_supports[i].price} >= {nearby_supports[i + 1].price}"
            )
        
        # 验证压力位按价格升序排列（最近的在前）
        for i in range(len(nearby_resistances) - 1):
            assert nearby_resistances[i].price <= nearby_resistances[i + 1].price, (
                f"压力位应按价格升序排列: "
                f"{nearby_resistances[i].price} <= {nearby_resistances[i + 1].price}"
            )
    
    @given(
        current_price=st.floats(
            min_value=3000.0, 
            max_value=5000.0, 
            allow_nan=False, 
            allow_infinity=False
        ),
    )
    @settings(max_examples=100)
    def test_empty_levels_returns_empty(self, current_price: float):
        """
        Feature: market-analysis-agent, Property 7: 支撑压力位数量约束
        
        验证当没有支撑压力位时返回空列表
        """
        sr_result = SupportResistanceResult(
            support_levels=[],
            resistance_levels=[],
        )
        
        nearby_supports, nearby_resistances = PriceCalculator.get_nearby_levels(
            current_price, sr_result, count=3
        )
        
        assert len(nearby_supports) == 0, "无支撑位时应返回空列表"
        assert len(nearby_resistances) == 0, "无压力位时应返回空列表"
    
    @given(
        current_price=st.floats(
            min_value=3000.0, 
            max_value=5000.0, 
            allow_nan=False, 
            allow_infinity=False
        ),
    )
    @settings(max_examples=100)
    def test_levels_at_current_price_excluded(self, current_price: float):
        """
        Feature: market-analysis-agent, Property 7: 支撑压力位数量约束
        
        验证等于当前价格的支撑压力位被排除
        """
        # 创建一个等于当前价格的"支撑位"和"压力位"
        support_levels = [
            PriceLevel(
                price=current_price,  # 等于当前价格
                level_type=LevelType.SUPPORT,
                importance=LevelImportance.DAILY,
                description="等于当前价格的支撑位",
                strength=LevelStrength.MEDIUM,
            ),
            PriceLevel(
                price=current_price - 100,  # 有效支撑位
                level_type=LevelType.SUPPORT,
                importance=LevelImportance.DAILY,
                description="有效支撑位",
                strength=LevelStrength.MEDIUM,
            ),
        ]
        
        resistance_levels = [
            PriceLevel(
                price=current_price,  # 等于当前价格
                level_type=LevelType.RESISTANCE,
                importance=LevelImportance.DAILY,
                description="等于当前价格的压力位",
                strength=LevelStrength.MEDIUM,
            ),
            PriceLevel(
                price=current_price + 100,  # 有效压力位
                level_type=LevelType.RESISTANCE,
                importance=LevelImportance.DAILY,
                description="有效压力位",
                strength=LevelStrength.MEDIUM,
            ),
        ]
        
        sr_result = SupportResistanceResult(
            support_levels=support_levels,
            resistance_levels=resistance_levels,
        )
        
        nearby_supports, nearby_resistances = PriceCalculator.get_nearby_levels(
            current_price, sr_result, count=3
        )
        
        # 验证等于当前价格的被排除
        for support in nearby_supports:
            assert support.price < current_price, (
                f"支撑位价格{support.price}应 < 当前价格{current_price}"
            )
        
        for resistance in nearby_resistances:
            assert resistance.price > current_price, (
                f"压力位价格{resistance.price}应 > 当前价格{current_price}"
            )
        
        # 验证只返回有效的支撑压力位
        assert len(nearby_supports) == 1, "应只返回1个有效支撑位"
        assert len(nearby_resistances) == 1, "应只返回1个有效压力位"
