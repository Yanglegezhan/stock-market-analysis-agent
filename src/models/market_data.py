"""市场数据模型

定义多周期K线数据、均线数据和分析输入的数据结构。
使用Pydantic进行数据验证。

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class TimeFrame(str, Enum):
    """时间周期枚举"""
    DAILY = "daily"   # 日线
    M15 = "m15"       # 15分钟
    M5 = "m5"         # 5分钟


class OHLCV(BaseModel):
    """K线数据模型 (Open, High, Low, Close, Volume)
    
    Validates: Requirements 2.1, 2.2, 2.3, 2.4
    """
    timestamp: datetime = Field(..., description="K线时间戳")
    open: float = Field(..., gt=0, description="开盘价")
    high: float = Field(..., gt=0, description="最高价")
    low: float = Field(..., gt=0, description="最低价")
    close: float = Field(..., gt=0, description="收盘价")
    volume: float = Field(..., ge=0, description="成交量")

    @model_validator(mode='after')
    def validate_price_relationships(self) -> 'OHLCV':
        """验证价格关系：high >= low, high >= open/close, low <= open/close"""
        if self.high < self.low:
            raise ValueError(f"最高价({self.high})不能小于最低价({self.low})")
        if self.high < self.open:
            raise ValueError(f"最高价({self.high})不能小于开盘价({self.open})")
        if self.high < self.close:
            raise ValueError(f"最高价({self.high})不能小于收盘价({self.close})")
        if self.low > self.open:
            raise ValueError(f"最低价({self.low})不能大于开盘价({self.open})")
        if self.low > self.close:
            raise ValueError(f"最低价({self.low})不能大于收盘价({self.close})")
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "timestamp": "2024-01-15T00:00:00",
                    "open": 3000.0,
                    "high": 3050.0,
                    "low": 2980.0,
                    "close": 3020.0,
                    "volume": 100000000
                }
            ]
        }
    }


class MovingAverage(BaseModel):
    """均线数据模型
    
    Validates: Requirements 2.5
    """
    timestamp: datetime = Field(..., description="时间戳")
    ma5: Optional[float] = Field(None, gt=0, description="5日均线")
    ma10: Optional[float] = Field(None, gt=0, description="10日均线")
    ma20: Optional[float] = Field(None, gt=0, description="20日均线")
    ma60: Optional[float] = Field(None, gt=0, description="60日均线")
    ma120: Optional[float] = Field(None, gt=0, description="120日均线")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "timestamp": "2024-01-15T00:00:00",
                    "ma5": 3010.0,
                    "ma10": 3000.0,
                    "ma20": 2990.0,
                    "ma60": 2950.0,
                    "ma120": 2900.0
                }
            ]
        }
    }


class MarketData(BaseModel):
    """市场数据模型 - 包含特定时间周期的K线数据和均线数据
    
    Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5
    """
    timeframe: TimeFrame = Field(..., description="时间周期")
    data: List[OHLCV] = Field(..., min_length=1, description="K线数据列表")
    moving_averages: Optional[List[MovingAverage]] = Field(
        None, description="均线数据列表"
    )

    @field_validator('data')
    @classmethod
    def validate_data_sorted(cls, v: List[OHLCV]) -> List[OHLCV]:
        """验证K线数据按时间排序"""
        if len(v) > 1:
            for i in range(1, len(v)):
                if v[i].timestamp < v[i-1].timestamp:
                    raise ValueError("K线数据必须按时间升序排列")
        return v

    @model_validator(mode='after')
    def validate_ma_alignment(self) -> 'MarketData':
        """验证均线数据与K线数据的时间对齐"""
        if self.moving_averages is not None and len(self.moving_averages) > 0:
            ohlcv_timestamps = {d.timestamp for d in self.data}
            for ma in self.moving_averages:
                if ma.timestamp not in ohlcv_timestamps:
                    raise ValueError(
                        f"均线时间戳 {ma.timestamp} 在K线数据中不存在"
                    )
        return self

    def get_latest_ohlcv(self) -> OHLCV:
        """获取最新的K线数据"""
        return self.data[-1]

    def get_latest_ma(self) -> Optional[MovingAverage]:
        """获取最新的均线数据"""
        if self.moving_averages and len(self.moving_averages) > 0:
            return self.moving_averages[-1]
        return None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "timeframe": "daily",
                    "data": [
                        {
                            "timestamp": "2024-01-15T00:00:00",
                            "open": 3000.0,
                            "high": 3050.0,
                            "low": 2980.0,
                            "close": 3020.0,
                            "volume": 100000000
                        }
                    ],
                    "moving_averages": [
                        {
                            "timestamp": "2024-01-15T00:00:00",
                            "ma5": 3010.0,
                            "ma10": 3000.0,
                            "ma20": 2990.0,
                            "ma60": 2950.0,
                            "ma120": 2900.0
                        }
                    ]
                }
            ]
        }
    }


class AnalysisInput(BaseModel):
    """分析输入模型 - 包含所有周期的市场数据
    
    数据周期：日线（3个月）、15分钟线（1周）、5分钟线（1日）
    
    Validates: Requirements 2.1, 2.2, 2.3, 2.5
    """
    analysis_date: datetime = Field(..., description="分析截止日期")
    analysis_time: Optional[datetime] = Field(
        None, description="盘中模式的截止时间"
    )
    daily_data: MarketData = Field(..., description="日线数据（三个月）")
    m15_data: MarketData = Field(..., description="15分钟线数据（一周）")
    m5_data: MarketData = Field(..., description="5分钟线数据（当日）")
    current_price: float = Field(..., gt=0, description="当前价格")

    @model_validator(mode='after')
    def validate_timeframes(self) -> 'AnalysisInput':
        """验证各数据的时间周期正确"""
        if self.daily_data.timeframe != TimeFrame.DAILY:
            raise ValueError(
                f"daily_data的timeframe必须是DAILY，当前为{self.daily_data.timeframe}"
            )
        if self.m15_data.timeframe != TimeFrame.M15:
            raise ValueError(
                f"m15_data的timeframe必须是M15，当前为{self.m15_data.timeframe}"
            )
        if self.m5_data.timeframe != TimeFrame.M5:
            raise ValueError(
                f"m5_data的timeframe必须是M5，当前为{self.m5_data.timeframe}"
            )
        return self

    @model_validator(mode='after')
    def validate_analysis_time(self) -> 'AnalysisInput':
        """验证盘中时间在分析日期当天"""
        if self.analysis_time is not None:
            if self.analysis_time.date() != self.analysis_date.date():
                raise ValueError(
                    f"盘中时间({self.analysis_time})必须在分析日期({self.analysis_date.date()})当天"
                )
            if self.analysis_time > self.analysis_date:
                raise ValueError(
                    f"盘中时间({self.analysis_time})不能晚于分析截止日期({self.analysis_date})"
                )
        return self

    def get_all_market_data(self) -> List[MarketData]:
        """获取所有周期的市场数据"""
        return [self.daily_data, self.m15_data, self.m5_data]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "analysis_date": "2024-01-15T15:00:00",
                    "analysis_time": "2024-01-15T14:30:00",
                    "current_price": 3020.0,
                    "daily_data": {
                        "timeframe": "daily",
                        "data": [{"timestamp": "2024-01-15T00:00:00", "open": 3000.0, "high": 3050.0, "low": 2980.0, "close": 3020.0, "volume": 100000000}]
                    },
                    "m15_data": {
                        "timeframe": "m15",
                        "data": [{"timestamp": "2024-01-15T09:30:00", "open": 3000.0, "high": 3010.0, "low": 2995.0, "close": 3005.0, "volume": 10000000}]
                    },
                    "m5_data": {
                        "timeframe": "m5",
                        "data": [{"timestamp": "2024-01-15T09:30:00", "open": 3000.0, "high": 3005.0, "low": 2998.0, "close": 3003.0, "volume": 5000000}]
                    }
                }
            ]
        }
    }
