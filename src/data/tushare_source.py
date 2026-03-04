"""Tushare数据源

从Tushare获取上证指数多周期数据，包括日线、15分钟线、5分钟线。
支持均线计算（MA5/10/20/60/120）。

注意：此数据源已被AKShare替代，保留仅供参考。

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional, List, Tuple
from pathlib import Path

import yaml
import tushare as ts
import pandas as pd

from src.models.market_data import (
    TimeFrame,
    OHLCV,
    MovingAverage,
    MarketData,
    AnalysisInput,
)


@dataclass
class TushareConfig:
    """Tushare配置"""
    api_token: str
    index_code: str = "000001.SH"  # 上证指数
    daily_days: int = 65    # 日线数据交易日数（约三个月）
    m15_days: int = 5       # 15分钟线交易日数（约一周）
    m5_days: int = 1        # 5分钟线交易日数（当日）

    def validate(self) -> Tuple[bool, Optional[str]]:
        """验证配置"""
        if not self.api_token:
            return False, "api_token不能为空"
        if not self.index_code:
            return False, "index_code不能为空"
        if self.daily_days <= 0:
            return False, "daily_days必须大于0"
        if self.m15_days <= 0:
            return False, "m15_days必须大于0"
        if self.m5_days <= 0:
            return False, "m5_days必须大于0"
        return True, None

    @classmethod
    def from_yaml(cls, config_path: str = "config.yaml") -> "TushareConfig":
        """从YAML配置文件加载配置"""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        
        tushare_config = config_data.get("tushare", {})
        
        return cls(
            api_token=tushare_config.get("api_token", ""),
            index_code=tushare_config.get("index_code", "000001.SH"),
            daily_days=tushare_config.get("daily_days", 252),
            m15_days=tushare_config.get("m15_days", 20),
            m5_days=tushare_config.get("m5_days", 5),
        )


class TushareDataSource:
    """Tushare数据源 - 获取上证指数多周期数据
    
    Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
    """
    
    def __init__(self, config: TushareConfig):
        self.config = config
        self._pro: Optional[ts.pro_api] = None
        
        # 验证配置
        is_valid, error_msg = config.validate()
        if not is_valid:
            raise ValueError(f"Tushare配置无效: {error_msg}")
    
    def _get_api(self) -> ts.pro_api:
        """获取Tushare Pro API"""
        if self._pro is None:
            ts.set_token(self.config.api_token)
            self._pro = ts.pro_api()
        return self._pro

    def get_trade_calendar(
        self, start_date: date, end_date: date
    ) -> List[date]:
        """获取交易日历
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            交易日列表
        """
        pro = self._get_api()
        
        df = pro.trade_cal(
            exchange="SSE",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            is_open="1"
        )
        
        if df.empty:
            return []
        
        trade_dates = [
            datetime.strptime(d, "%Y%m%d").date()
            for d in df["cal_date"].tolist()
        ]
        return sorted(trade_dates)
    
    def _get_trade_days_before(
        self, end_date: date, num_days: int
    ) -> Tuple[date, date]:
        """获取指定日期之前N个交易日的起止日期
        
        Args:
            end_date: 结束日期
            num_days: 需要的交易日数量
            
        Returns:
            (start_date, end_date) 元组
        """
        # 预估需要的自然日数量（考虑周末和节假日，约1.5倍）
        estimated_days = int(num_days * 1.5) + 30
        start_date = end_date - timedelta(days=estimated_days)
        
        trade_dates = self.get_trade_calendar(start_date, end_date)
        
        if len(trade_dates) < num_days:
            # 如果交易日不够，扩大范围重新获取
            start_date = end_date - timedelta(days=estimated_days * 2)
            trade_dates = self.get_trade_calendar(start_date, end_date)
        
        # 取最近的num_days个交易日
        if len(trade_dates) >= num_days:
            actual_start = trade_dates[-num_days]
        else:
            actual_start = trade_dates[0] if trade_dates else start_date
        
        return actual_start, end_date
    
    def _df_to_ohlcv_list(
        self, df: pd.DataFrame, timeframe: TimeFrame
    ) -> List[OHLCV]:
        """将DataFrame转换为OHLCV列表
        
        Args:
            df: 包含K线数据的DataFrame
            timeframe: 时间周期
            
        Returns:
            OHLCV列表
        """
        if df.empty:
            return []
        
        ohlcv_list = []
        
        for _, row in df.iterrows():
            # 解析时间戳
            if timeframe == TimeFrame.DAILY:
                # 日线数据的trade_date格式为YYYYMMDD
                ts_str = str(row.get("trade_date", row.get("datetime", "")))
                if len(ts_str) == 8:
                    timestamp = datetime.strptime(ts_str, "%Y%m%d")
                else:
                    timestamp = pd.to_datetime(ts_str)
            else:
                # 分钟线数据的datetime格式为YYYY-MM-DD HH:MM:SS
                ts_str = str(row.get("datetime", row.get("trade_time", "")))
                timestamp = pd.to_datetime(ts_str)
            
            ohlcv = OHLCV(
                timestamp=timestamp,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("vol", row.get("volume", 0))),
            )
            ohlcv_list.append(ohlcv)
        
        # 按时间升序排序
        ohlcv_list.sort(key=lambda x: x.timestamp)
        return ohlcv_list

    def get_daily_data(self, end_date: date) -> MarketData:
        """获取日线数据（按交易日计算）
        
        Args:
            end_date: 截止日期
            
        Returns:
            日线MarketData
            
        Requirements: 2.1
        """
        pro = self._get_api()
        
        start_date, _ = self._get_trade_days_before(
            end_date, self.config.daily_days
        )
        
        # 获取指数日线数据
        df = pro.index_daily(
            ts_code=self.config.index_code,
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )
        
        if df.empty:
            raise ValueError(
                f"无法获取日线数据: {self.config.index_code}, "
                f"{start_date} - {end_date}"
            )
        
        # 转换为OHLCV列表
        ohlcv_list = self._df_to_ohlcv_list(df, TimeFrame.DAILY)
        
        # 计算均线
        ma_list = self.calculate_moving_averages(ohlcv_list)
        
        return MarketData(
            timeframe=TimeFrame.DAILY,
            data=ohlcv_list,
            moving_averages=ma_list,
        )
    
    def get_m15_data(self, end_date: date) -> MarketData:
        """获取15分钟线数据（按交易日计算）
        
        Args:
            end_date: 截止日期
            
        Returns:
            15分钟线MarketData
            
        Requirements: 2.2
        """
        return self._get_minute_data(
            end_date=end_date,
            num_days=self.config.m15_days,
            freq="15min",
            timeframe=TimeFrame.M15,
        )
    
    def get_m5_data(self, end_date: date, end_time: Optional[str] = None) -> MarketData:
        """获取5分钟线数据（按交易日计算）
        
        Args:
            end_date: 截止日期
            end_time: 截止时间（格式HH:MM:SS），用于盘中模式
            
        Returns:
            5分钟线MarketData
            
        Requirements: 2.3
        """
        return self._get_minute_data(
            end_date=end_date,
            num_days=self.config.m5_days,
            freq="5min",
            timeframe=TimeFrame.M5,
            end_time=end_time,
        )

    def _get_minute_data(
        self,
        end_date: date,
        num_days: int,
        freq: str,
        timeframe: TimeFrame,
        end_time: Optional[str] = None,
    ) -> MarketData:
        """获取分钟线数据的通用方法
        
        Args:
            end_date: 截止日期
            num_days: 交易日数量
            freq: 频率（1min, 5min, 15min）
            timeframe: 时间周期
            end_time: 截止时间（格式HH:MM:SS），用于盘中模式
            
        Returns:
            MarketData
        """
        pro = self._get_api()
        
        start_date, _ = self._get_trade_days_before(end_date, num_days)
        
        # 构建时间范围
        start_datetime = f"{start_date.strftime('%Y-%m-%d')} 09:30:00"
        if end_time:
            end_datetime = f"{end_date.strftime('%Y-%m-%d')} {end_time}"
        else:
            end_datetime = f"{end_date.strftime('%Y-%m-%d')} 15:00:00"
        
        # 获取分钟线数据
        # 注意：tushare的stk_mins接口需要较高积分
        # 这里使用ts.pro_bar作为替代方案
        try:
            df = ts.pro_bar(
                ts_code=self.config.index_code,
                asset="I",  # 指数
                freq=freq,
                start_date=start_datetime,
                end_date=end_datetime,
            )
        except Exception as e:
            raise ValueError(
                f"无法获取{freq}数据: {self.config.index_code}, "
                f"{start_datetime} - {end_datetime}, 错误: {e}"
            )
        
        if df is None or df.empty:
            raise ValueError(
                f"无法获取{freq}数据: {self.config.index_code}, "
                f"{start_datetime} - {end_datetime}"
            )
        
        # 转换为OHLCV列表
        ohlcv_list = self._df_to_ohlcv_list(df, timeframe)
        
        # 如果指定了截止时间，过滤数据
        if end_time:
            cutoff = datetime.strptime(
                f"{end_date.strftime('%Y-%m-%d')} {end_time}",
                "%Y-%m-%d %H:%M:%S"
            )
            ohlcv_list = [o for o in ohlcv_list if o.timestamp <= cutoff]
        
        if not ohlcv_list:
            raise ValueError(
                f"过滤后无{freq}数据: {self.config.index_code}, "
                f"截止时间: {end_time}"
            )
        
        # 分钟线数据也计算均线
        ma_list = self.calculate_moving_averages(ohlcv_list)
        
        return MarketData(
            timeframe=timeframe,
            data=ohlcv_list,
            moving_averages=ma_list,
        )

    def calculate_moving_averages(
        self, data: List[OHLCV]
    ) -> List[MovingAverage]:
        """计算均线数据（MA5/10/20/60/120）
        
        Args:
            data: OHLCV数据列表（必须按时间升序排列）
            
        Returns:
            均线数据列表
            
        Requirements: 2.5
        """
        if not data:
            return []
        
        # 提取收盘价序列
        closes = [o.close for o in data]
        timestamps = [o.timestamp for o in data]
        
        ma_periods = [5, 10, 20, 60, 120]
        ma_values = {period: [] for period in ma_periods}
        
        # 计算各周期均线
        for i in range(len(closes)):
            for period in ma_periods:
                if i + 1 >= period:
                    # 有足够数据计算均线
                    ma_value = sum(closes[i - period + 1:i + 1]) / period
                    ma_values[period].append(ma_value)
                else:
                    # 数据不足，设为None
                    ma_values[period].append(None)
        
        # 构建MovingAverage列表
        ma_list = []
        for i, ts in enumerate(timestamps):
            ma = MovingAverage(
                timestamp=ts,
                ma5=ma_values[5][i],
                ma10=ma_values[10][i],
                ma20=ma_values[20][i],
                ma60=ma_values[60][i],
                ma120=ma_values[120][i],
            )
            ma_list.append(ma)
        
        return ma_list
    
    def get_all_data(
        self,
        analysis_date: date,
        analysis_time: Optional[str] = None
    ) -> AnalysisInput:
        """获取所有周期数据
        
        Args:
            analysis_date: 分析日期
            analysis_time: 盘中截止时间（格式HH:MM:SS）
            
        Returns:
            AnalysisInput对象
            
        Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
        """
        # 获取各周期数据
        daily_data = self.get_daily_data(analysis_date)
        m15_data = self.get_m15_data(analysis_date)
        m5_data = self.get_m5_data(analysis_date, analysis_time)
        
        # 获取当前价格（使用最新的5分钟线收盘价）
        current_price = m5_data.get_latest_ohlcv().close
        
        # 构建分析截止时间
        if analysis_time:
            analysis_datetime = datetime.strptime(
                f"{analysis_date.strftime('%Y-%m-%d')} {analysis_time}",
                "%Y-%m-%d %H:%M:%S"
            )
        else:
            analysis_datetime = datetime.combine(
                analysis_date, datetime.strptime("15:00:00", "%H:%M:%S").time()
            )
        
        return AnalysisInput(
            analysis_date=analysis_datetime,
            analysis_time=analysis_datetime if analysis_time else None,
            daily_data=daily_data,
            m15_data=m15_data,
            m5_data=m5_data,
            current_price=current_price,
        )


def load_tushare_config(config_path: str = "config.yaml") -> TushareConfig:
    """从配置文件加载Tushare配置的便捷函数
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        TushareConfig对象
    """
    return TushareConfig.from_yaml(config_path)


def create_tushare_source(config_path: str = "config.yaml") -> TushareDataSource:
    """创建Tushare数据源的便捷函数
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        TushareDataSource对象
    """
    config = load_tushare_config(config_path)
    return TushareDataSource(config)
