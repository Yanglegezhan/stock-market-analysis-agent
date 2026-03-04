"""时间隔离过滤器

实现数据时间隔离，防止未来数据泄露。
支持日期过滤和盘中时间过滤。

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""

from dataclasses import dataclass, field
from datetime import datetime, date, time
from typing import List, Optional, Tuple

from src.models.market_data import (
    MarketData,
    OHLCV,
    MovingAverage,
    TimeFrame,
)


@dataclass
class FilterWarning:
    """过滤警告信息"""
    message: str
    filtered_count: int
    timeframe: Optional[TimeFrame] = None
    
    def __str__(self) -> str:
        if self.timeframe:
            return f"[{self.timeframe.value}] {self.message} (过滤了{self.filtered_count}条数据)"
        return f"{self.message} (过滤了{self.filtered_count}条数据)"


@dataclass
class FilterResult:
    """过滤结果"""
    data: MarketData
    warnings: List[FilterWarning] = field(default_factory=list)
    original_count: int = 0
    filtered_count: int = 0
    
    @property
    def has_warnings(self) -> bool:
        """是否有警告"""
        return len(self.warnings) > 0
    
    def get_warning_messages(self) -> List[str]:
        """获取所有警告信息"""
        return [str(w) for w in self.warnings]


class TimeIsolationFilter:
    """时间隔离过滤器
    
    用于过滤掉截止时间之后的数据，防止未来数据泄露。
    支持日期级别过滤和盘中时间级别过滤。
    
    Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
    """
    
    def __init__(
        self,
        cutoff_date: datetime,
        cutoff_time: Optional[datetime] = None
    ):
        """初始化时间隔离过滤器
        
        Args:
            cutoff_date: 截止日期（包含该日期的数据）
            cutoff_time: 盘中截止时间（可选，用于分钟线数据过滤）
        
        Requirements: 3.1, 3.5
        """
        self.cutoff_date = cutoff_date
        self.cutoff_time = cutoff_time
        
        # 验证盘中时间在截止日期当天
        if cutoff_time is not None:
            if cutoff_time.date() != cutoff_date.date():
                raise ValueError(
                    f"盘中截止时间({cutoff_time})必须在截止日期({cutoff_date.date()})当天"
                )
    
    def filter_data(self, data: MarketData) -> FilterResult:
        """过滤掉截止时间之后的数据
        
        Args:
            data: 市场数据
            
        Returns:
            FilterResult对象，包含过滤后的数据和警告信息
            
        Requirements: 3.1, 3.2, 3.4, 3.5, 3.6
        """
        original_count = len(data.data)
        warnings: List[FilterWarning] = []
        
        # 根据时间周期选择过滤策略
        if data.timeframe == TimeFrame.DAILY:
            filtered_ohlcv = self._filter_daily_data(data.data)
        else:
            # 分钟线数据使用更精确的时间过滤
            filtered_ohlcv = self._filter_intraday_data(data.data, data.timeframe)
        
        filtered_count = original_count - len(filtered_ohlcv)
        
        # 生成警告信息
        if filtered_count > 0:
            warnings.append(FilterWarning(
                message=f"检测到未来数据，已自动过滤",
                filtered_count=filtered_count,
                timeframe=data.timeframe
            ))
        
        # 过滤均线数据
        filtered_ma = None
        if data.moving_averages:
            original_ma_count = len(data.moving_averages)
            filtered_ma = self._filter_moving_averages(
                data.moving_averages, 
                data.timeframe
            )
            ma_filtered_count = original_ma_count - len(filtered_ma)
            
            if ma_filtered_count > 0:
                warnings.append(FilterWarning(
                    message=f"均线数据包含未来数据，已自动过滤",
                    filtered_count=ma_filtered_count,
                    timeframe=data.timeframe
                ))
        
        # 如果过滤后没有数据，对于分钟线数据返回空数据（允许仅使用日线分析）
        if not filtered_ohlcv:
            if data.timeframe != TimeFrame.DAILY:
                # 分钟数据为空，返回空的MarketData
                return FilterResult(
                    data=MarketData(
                        timeframe=data.timeframe,
                        data=[],
                        moving_averages=None
                    ),
                    warnings=[FilterWarning(
                        message=f"分钟数据不可用，将仅使用日线数据进行分析",
                        filtered_count=original_count,
                        timeframe=data.timeframe
                    )],
                    original_count=original_count,
                    filtered_count=original_count
                )
            else:
                # 日线数据为空，这是错误
                raise ValueError(
                    f"过滤后{data.timeframe.value}数据为空，"
                    f"请检查截止时间({self.cutoff_date})是否正确"
                )
        
        # 创建新的MarketData对象
        filtered_data = MarketData(
            timeframe=data.timeframe,
            data=filtered_ohlcv,
            moving_averages=filtered_ma if filtered_ma else None
        )
        
        return FilterResult(
            data=filtered_data,
            warnings=warnings,
            original_count=original_count,
            filtered_count=filtered_count
        )
    
    def _filter_daily_data(self, ohlcv_list: List[OHLCV]) -> List[OHLCV]:
        """过滤日线数据
        
        日线数据按日期过滤，只保留截止日期及之前的数据。
        
        Args:
            ohlcv_list: K线数据列表
            
        Returns:
            过滤后的K线数据列表
            
        Requirements: 3.1, 3.2
        """
        cutoff = self.cutoff_date.date()
        return [
            ohlcv for ohlcv in ohlcv_list
            if ohlcv.timestamp.date() <= cutoff
        ]
    
    def _filter_intraday_data(
        self, 
        ohlcv_list: List[OHLCV],
        timeframe: TimeFrame
    ) -> List[OHLCV]:
        """过滤分钟线数据
        
        分钟线数据需要考虑盘中截止时间。
        - 截止日期之前的数据全部保留
        - 截止日期当天的数据，如果有盘中截止时间，则只保留该时间之前的数据
        
        Args:
            ohlcv_list: K线数据列表
            timeframe: 时间周期
            
        Returns:
            过滤后的K线数据列表
            
        Requirements: 3.4, 3.5
        """
        cutoff_date = self.cutoff_date.date()
        filtered: List[OHLCV] = []
        
        for ohlcv in ohlcv_list:
            ohlcv_date = ohlcv.timestamp.date()
            
            # 截止日期之后的数据直接过滤
            if ohlcv_date > cutoff_date:
                continue
            
            # 截止日期之前的数据全部保留
            if ohlcv_date < cutoff_date:
                filtered.append(ohlcv)
                continue
            
            # 截止日期当天的数据
            if self.cutoff_time is not None:
                # 有盘中截止时间，只保留该时间及之前的数据
                if ohlcv.timestamp <= self.cutoff_time:
                    filtered.append(ohlcv)
            else:
                # 没有盘中截止时间，保留当天所有数据
                filtered.append(ohlcv)
        
        return filtered
    
    def _filter_moving_averages(
        self,
        ma_list: List[MovingAverage],
        timeframe: TimeFrame
    ) -> List[MovingAverage]:
        """过滤均线数据
        
        均线数据的过滤逻辑与K线数据相同。
        
        Args:
            ma_list: 均线数据列表
            timeframe: 时间周期
            
        Returns:
            过滤后的均线数据列表
            
        Requirements: 3.6
        """
        cutoff_date = self.cutoff_date.date()
        filtered: List[MovingAverage] = []
        
        for ma in ma_list:
            ma_date = ma.timestamp.date()
            
            # 截止日期之后的数据直接过滤
            if ma_date > cutoff_date:
                continue
            
            # 截止日期之前的数据全部保留
            if ma_date < cutoff_date:
                filtered.append(ma)
                continue
            
            # 截止日期当天的数据
            if timeframe == TimeFrame.DAILY:
                # 日线均线，保留当天数据
                filtered.append(ma)
            elif self.cutoff_time is not None:
                # 分钟线均线，有盘中截止时间
                if ma.timestamp <= self.cutoff_time:
                    filtered.append(ma)
            else:
                # 分钟线均线，没有盘中截止时间，保留当天所有数据
                filtered.append(ma)
        
        return filtered
    
    def validate_no_future_data(
        self, 
        data: MarketData
    ) -> Tuple[bool, List[FilterWarning]]:
        """验证数据中是否包含未来数据
        
        Args:
            data: 市场数据
            
        Returns:
            (是否通过验证, 警告列表)
            - 如果没有未来数据，返回(True, [])
            - 如果有未来数据，返回(False, [警告列表])
            
        Requirements: 3.2, 3.4
        """
        warnings: List[FilterWarning] = []
        cutoff_date = self.cutoff_date.date()
        
        # 检查K线数据
        future_ohlcv_count = 0
        for ohlcv in data.data:
            ohlcv_date = ohlcv.timestamp.date()
            
            if ohlcv_date > cutoff_date:
                future_ohlcv_count += 1
            elif ohlcv_date == cutoff_date and self.cutoff_time is not None:
                if data.timeframe != TimeFrame.DAILY:
                    if ohlcv.timestamp > self.cutoff_time:
                        future_ohlcv_count += 1
        
        if future_ohlcv_count > 0:
            warnings.append(FilterWarning(
                message=f"K线数据包含未来数据",
                filtered_count=future_ohlcv_count,
                timeframe=data.timeframe
            ))
        
        # 检查均线数据
        if data.moving_averages:
            future_ma_count = 0
            for ma in data.moving_averages:
                ma_date = ma.timestamp.date()
                
                if ma_date > cutoff_date:
                    future_ma_count += 1
                elif ma_date == cutoff_date and self.cutoff_time is not None:
                    if data.timeframe != TimeFrame.DAILY:
                        if ma.timestamp > self.cutoff_time:
                            future_ma_count += 1
            
            if future_ma_count > 0:
                warnings.append(FilterWarning(
                    message=f"均线数据包含未来数据",
                    filtered_count=future_ma_count,
                    timeframe=data.timeframe
                ))
        
        return (len(warnings) == 0, warnings)
    
    def get_cutoff_info(self) -> str:
        """返回数据截止时间信息，用于报告
        
        Returns:
            截止时间信息字符串
            
        Requirements: 3.3
        """
        if self.cutoff_time is not None:
            return f"数据截止时间: {self.cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            return f"数据截止日期: {self.cutoff_date.strftime('%Y-%m-%d')}"


def filter_market_data(
    data: MarketData,
    cutoff_date: datetime,
    cutoff_time: Optional[datetime] = None
) -> FilterResult:
    """过滤市场数据的便捷函数
    
    Args:
        data: 市场数据
        cutoff_date: 截止日期
        cutoff_time: 盘中截止时间（可选）
        
    Returns:
        FilterResult对象
    """
    filter_instance = TimeIsolationFilter(cutoff_date, cutoff_time)
    return filter_instance.filter_data(data)


def validate_data_time(
    data: MarketData,
    cutoff_date: datetime,
    cutoff_time: Optional[datetime] = None
) -> Tuple[bool, List[FilterWarning]]:
    """验证数据时间的便捷函数
    
    Args:
        data: 市场数据
        cutoff_date: 截止日期
        cutoff_time: 盘中截止时间（可选）
        
    Returns:
        (是否通过验证, 警告列表)
    """
    filter_instance = TimeIsolationFilter(cutoff_date, cutoff_time)
    return filter_instance.validate_no_future_data(data)
