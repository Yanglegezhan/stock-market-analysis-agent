"""价格距离计算器

实现价格距离计算和位置判断功能。

Requirements: 6.1, 6.2, 6.3
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

from src.models.analysis_result import (
    PriceLevel,
    PositionAnalysis,
    SupportResistanceResult,
    LevelType,
)


@dataclass
class DistanceResult:
    """距离计算结果"""
    points: float  # 距离点数
    percentage: float  # 距离百分比


class PriceCalculator:
    """价格距离计算器
    
    计算当前价格与支撑压力位的距离，判断价格位置。
    
    Requirements: 6.1, 6.2, 6.3
    """
    
    # 位置判断阈值（距离比例）
    NEAR_THRESHOLD = 0.3  # 距离小于30%认为"接近"
    
    @staticmethod
    def calculate_distance(
        current_price: float, 
        target_price: float
    ) -> DistanceResult:
        """计算价格距离
        
        Args:
            current_price: 当前价格
            target_price: 目标价格
            
        Returns:
            DistanceResult对象，包含点数和百分比
            
        Requirements: 6.1, 6.2
        """
        points = abs(current_price - target_price)
        percentage = (points / current_price) * 100 if current_price > 0 else 0
        
        return DistanceResult(
            points=round(points, 2),
            percentage=round(percentage, 2)
        )
    
    @classmethod
    def find_nearest_support(
        cls,
        current_price: float,
        support_levels: List[PriceLevel]
    ) -> Optional[PriceLevel]:
        """查找最近的支撑位
        
        Args:
            current_price: 当前价格
            support_levels: 支撑位列表
            
        Returns:
            最近的支撑位，如果没有则返回None
        """
        # 筛选出低于当前价格的支撑位
        valid_supports = [
            s for s in support_levels 
            if s.price < current_price
        ]
        
        if not valid_supports:
            return None
        
        # 按价格降序排列，取最高的（最近的）
        valid_supports.sort(key=lambda x: x.price, reverse=True)
        return valid_supports[0]
    
    @classmethod
    def find_nearest_resistance(
        cls,
        current_price: float,
        resistance_levels: List[PriceLevel]
    ) -> Optional[PriceLevel]:
        """查找最近的压力位
        
        Args:
            current_price: 当前价格
            resistance_levels: 压力位列表
            
        Returns:
            最近的压力位，如果没有则返回None
        """
        # 筛选出高于当前价格的压力位
        valid_resistances = [
            r for r in resistance_levels 
            if r.price > current_price
        ]
        
        if not valid_resistances:
            return None
        
        # 按价格升序排列，取最低的（最近的）
        valid_resistances.sort(key=lambda x: x.price)
        return valid_resistances[0]
    
    @classmethod
    def determine_position(
        cls,
        current_price: float,
        nearest_support: Optional[PriceLevel],
        nearest_resistance: Optional[PriceLevel]
    ) -> str:
        """判断当前价格位置
        
        Args:
            current_price: 当前价格
            nearest_support: 最近支撑位
            nearest_resistance: 最近压力位
            
        Returns:
            位置描述字符串
            
        Requirements: 6.3
        """
        if nearest_support is None and nearest_resistance is None:
            return "无法判断（缺少支撑压力位数据）"
        
        if nearest_support is None:
            return "接近压力位"
        
        if nearest_resistance is None:
            return "接近支撑位"
        
        # 计算距离
        support_distance = cls.calculate_distance(
            current_price, nearest_support.price
        )
        resistance_distance = cls.calculate_distance(
            current_price, nearest_resistance.price
        )
        
        total_range = support_distance.points + resistance_distance.points
        
        if total_range == 0:
            return "中间区域"
        
        # 计算距离比例
        support_ratio = support_distance.points / total_range
        resistance_ratio = resistance_distance.points / total_range
        
        if support_ratio < cls.NEAR_THRESHOLD:
            return "接近支撑位"
        elif resistance_ratio < cls.NEAR_THRESHOLD:
            return "接近压力位"
        else:
            # 判断偏向
            if support_ratio < 0.4:
                return "中间偏支撑"
            elif resistance_ratio < 0.4:
                return "中间偏压力"
            else:
                return "中间区域"
    
    @classmethod
    def analyze_position(
        cls,
        current_price: float,
        sr_result: SupportResistanceResult
    ) -> PositionAnalysis:
        """分析当前价格位置
        
        Args:
            current_price: 当前价格
            sr_result: 支撑压力位识别结果
            
        Returns:
            PositionAnalysis对象
            
        Requirements: 6.1, 6.2, 6.3, 6.4
        """
        # 查找最近的支撑位和压力位
        nearest_support = cls.find_nearest_support(
            current_price, sr_result.support_levels
        )
        nearest_resistance = cls.find_nearest_resistance(
            current_price, sr_result.resistance_levels
        )
        
        # 计算距离
        support_distance = DistanceResult(0, 0)
        resistance_distance = DistanceResult(0, 0)
        
        if nearest_support:
            support_distance = cls.calculate_distance(
                current_price, nearest_support.price
            )
        
        if nearest_resistance:
            resistance_distance = cls.calculate_distance(
                current_price, nearest_resistance.price
            )
        
        # 判断位置
        position_description = cls.determine_position(
            current_price, nearest_support, nearest_resistance
        )
        
        return PositionAnalysis(
            current_price=current_price,
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance,
            support_distance_points=support_distance.points,
            support_distance_pct=support_distance.percentage,
            resistance_distance_points=resistance_distance.points,
            resistance_distance_pct=resistance_distance.percentage,
            position_description=position_description,
        )
    
    @classmethod
    def get_nearby_levels(
        cls,
        current_price: float,
        sr_result: SupportResistanceResult,
        count: int = 3
    ) -> Tuple[List[PriceLevel], List[PriceLevel]]:
        """获取当前价格上下方各N个关键支撑压力位
        
        Args:
            current_price: 当前价格
            sr_result: 支撑压力位识别结果
            count: 每侧返回的数量
            
        Returns:
            (支撑位列表, 压力位列表)
            
        Requirements: 6.4
        """
        # 筛选并排序支撑位（低于当前价格，按价格降序）
        supports = [
            s for s in sr_result.support_levels 
            if s.price < current_price
        ]
        supports.sort(key=lambda x: x.price, reverse=True)
        
        # 筛选并排序压力位（高于当前价格，按价格升序）
        resistances = [
            r for r in sr_result.resistance_levels 
            if r.price > current_price
        ]
        resistances.sort(key=lambda x: x.price)
        
        return supports[:count], resistances[:count]


def calculate_price_distance(
    current_price: float, 
    target_price: float
) -> DistanceResult:
    """计算价格距离的便捷函数
    
    Args:
        current_price: 当前价格
        target_price: 目标价格
        
    Returns:
        DistanceResult对象
    """
    return PriceCalculator.calculate_distance(current_price, target_price)


def analyze_price_position(
    current_price: float,
    sr_result: SupportResistanceResult
) -> PositionAnalysis:
    """分析价格位置的便捷函数
    
    Args:
        current_price: 当前价格
        sr_result: 支撑压力位识别结果
        
    Returns:
        PositionAnalysis对象
    """
    return PriceCalculator.analyze_position(current_price, sr_result)
