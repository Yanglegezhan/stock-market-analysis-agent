"""AKShare数据源

从AKShare获取上证指数多周期数据，包括日线、15分钟线、5分钟线。
支持均线计算（MA5/10/20/60/120）。

AKShare是免费开源的金融数据接口，无需API Token，无频率限制。

数据周期：日线（3个月）、15分钟线（1周）、5分钟线（1日）

Requirements: 2.1, 2.2, 2.3, 2.5
"""

from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional, List, Tuple
from pathlib import Path

import yaml
import akshare as ak
import pandas as pd
import os
import requests
import urllib3
import ssl
import socket
from urllib3.exceptions import InsecureRequestWarning
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 全面的网络修复
def fix_network_issues():
    """修复所有网络问题"""
    # 禁用代理
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
    for var in proxy_vars:
        if var in os.environ:
            del os.environ[var]
    os.environ['NO_PROXY'] = '*'
    
    # 禁用SSL警告和验证
    urllib3.disable_warnings(InsecureRequestWarning)
    
    # 设置socket超时
    socket.setdefaulttimeout(30)
    
    # 修补requests
    try:
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.proxies = {}
        session.verify = False
        session.timeout = 30
        
        # 替换akshare的requests
        if hasattr(ak, 'requests'):
            ak.requests = session
    except:
        pass

# 应用网络修复
fix_network_issues()

from src.models.market_data import (
    TimeFrame,
    OHLCV,
    MovingAverage,
    MarketData,
    AnalysisInput,
)


@dataclass
class AKShareConfig:
    """AKShare配置"""
    index_code: str = "000001"  # 上证指数（AKShare使用纯数字代码）
    index_name: str = "sh000001"  # 用于日线数据
    daily_days: int = 65    # 日线数据交易日数（约三个月）
    m15_days: int = 5       # 15分钟线交易日数（约一周）
    m5_days: int = 1        # 5分钟线交易日数（当日）

    def validate(self) -> Tuple[bool, Optional[str]]:
        """验证配置"""
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
    def from_yaml(cls, config_path: str = "config.yaml") -> "AKShareConfig":
        """从YAML配置文件加载配置"""
        path = Path(config_path)
        if not path.exists():
            # 如果配置文件不存在，使用默认配置
            return cls()
        
        with open(path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        
        akshare_config = config_data.get("akshare", {})
        
        return cls(
            index_code=akshare_config.get("index_code", "000001"),
            index_name=akshare_config.get("index_name", "sh000001"),
            daily_days=akshare_config.get("daily_days", 65),
            m15_days=akshare_config.get("m15_days", 5),
            m5_days=akshare_config.get("m5_days", 1),
        )


class AKShareDataSource:
    """AKShare数据源 - 获取上证指数多周期数据
    
    AKShare是免费开源的金融数据接口，无需API Token，无频率限制。
    
    数据周期：日线（3个月）、15分钟线（1周）、5分钟线（1日）
    
    Requirements: 2.1, 2.2, 2.3, 2.5
    """
    
    def __init__(self, config: AKShareConfig):
        self.config = config
        
        # 验证配置
        is_valid, error_msg = config.validate()
        if not is_valid:
            raise ValueError(f"AKShare配置无效: {error_msg}")
    
    def _get_trade_days_range(
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
        return start_date, end_date
    
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
                # 日线数据
                if "日期" in df.columns:
                    ts_val = row["日期"]
                elif "date" in df.columns:
                    ts_val = row["date"]
                else:
                    ts_val = row.name
                
                if isinstance(ts_val, str):
                    timestamp = pd.to_datetime(ts_val)
                else:
                    timestamp = pd.to_datetime(ts_val)
            else:
                # 分钟线数据
                if "时间" in df.columns:
                    ts_val = row["时间"]
                elif "datetime" in df.columns:
                    ts_val = row["datetime"]
                else:
                    ts_val = row.name
                timestamp = pd.to_datetime(ts_val)
            
            # 获取OHLCV数据，兼容中英文列名
            open_price = float(row.get("开盘", row.get("open", 0)))
            high_price = float(row.get("最高", row.get("high", 0)))
            low_price = float(row.get("最低", row.get("low", 0)))
            close_price = float(row.get("收盘", row.get("close", 0)))
            volume = float(row.get("成交量", row.get("volume", row.get("vol", 0))))
            
            # 跳过无效数据（价格为0或负数）
            if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
                continue
            
            ohlcv = OHLCV(
                timestamp=timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
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
        start_date, _ = self._get_trade_days_range(
            end_date, self.config.daily_days
        )
        
        try:
            # 使用AKShare获取指数日线数据
            df = ak.stock_zh_index_daily(symbol=self.config.index_name)
            
            if df.empty:
                raise ValueError(
                    f"无法获取日线数据: {self.config.index_name}"
                )
            
            # 过滤日期范围
            df["date"] = pd.to_datetime(df["date"])
            df = df[(df["date"].dt.date >= start_date) & 
                    (df["date"].dt.date <= end_date)]
            
            if df.empty:
                raise ValueError(
                    f"指定日期范围内无日线数据: {start_date} - {end_date}"
                )
            
        except Exception as e:
            raise ValueError(
                f"获取日线数据失败: {self.config.index_name}, "
                f"{start_date} - {end_date}, 错误: {e}"
            )
        
        # 转换为OHLCV列表
        ohlcv_list = self._df_to_ohlcv_list(df, TimeFrame.DAILY)
        
        # 限制返回的数据量（只保留最近N个交易日）
        if len(ohlcv_list) > self.config.daily_days:
            ohlcv_list = ohlcv_list[-self.config.daily_days:]
        
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
            period="15",
            timeframe=TimeFrame.M15,
        )
    
    def get_m5_data(
        self, end_date: date, end_time: Optional[str] = None
    ) -> MarketData:
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
            period="5",
            timeframe=TimeFrame.M5,
            end_time=end_time,
        )

    def _get_minute_data(
        self,
        end_date: date,
        num_days: int,
        period: str,
        timeframe: TimeFrame,
        end_time: Optional[str] = None,
    ) -> MarketData:
        """获取分钟线数据的通用方法
        
        Args:
            end_date: 截止日期
            num_days: 交易日数量
            period: 周期（1, 5, 15）
            timeframe: 时间周期
            end_time: 截止时间（格式HH:MM:SS），用于盘中模式
            
        Returns:
            MarketData
        """
        start_date, _ = self._get_trade_days_range(end_date, num_days)

        # 只使用真实数据，不使用模拟数据
        df = None
        try:
            print(f"  获取真实{period}分钟数据...")
            df = self._try_em_minute_data(start_date, end_date, period)
            if df is not None and not df.empty:
                print(f"  成功获取 {len(df)} 条真实数据")
            else:
                print(f"  返回空数据")
        except Exception as e:
            print(f"  获取真实数据失败: {str(e)}")

        # 如果分钟数据不可用，返回空的MarketData（仅使用日线数据进行分析）
        if df is None or df.empty:
            print(f"  警告: {period}分钟数据不可用，将仅使用日线数据")
            return MarketData(
                timeframe=timeframe,
                data=[],
                moving_averages=[],
            )
        
        # 重命名列以统一格式
        column_mapping = {
            "时间": "datetime",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "date": "datetime",  # 模拟数据的列名
        }
        df = df.rename(columns=column_mapping)
        
        # 转换为OHLCV列表
        ohlcv_list = self._df_to_ohlcv_list(df, timeframe)
        
        # 过滤日期范围
        ohlcv_list = [
            o for o in ohlcv_list 
            if o.timestamp.date() >= start_date and o.timestamp.date() <= end_date
        ]
        
        # 如果指定了截止时间，过滤数据
        if end_time:
            cutoff = datetime.strptime(
                f"{end_date.strftime('%Y-%m-%d')} {end_time}",
                "%Y-%m-%d %H:%M:%S"
            )
            ohlcv_list = [o for o in ohlcv_list if o.timestamp <= cutoff]
        
        if not ohlcv_list:
            raise ValueError(
                f"过滤后无{period}分钟数据: {self.config.index_code}, "
                f"截止时间: {end_time}"
            )
        
        # 计算每个交易日的K线数量，然后限制返回的数据量
        # 15分钟线：每天16根（9:30-11:30=8根, 13:00-15:00=8根）
        # 5分钟线：每天48根（9:30-11:30=24根, 13:00-15:00=24根）
        bars_per_day = 16 if period == "15" else 48
        max_bars = num_days * bars_per_day
        
        if len(ohlcv_list) > max_bars:
            ohlcv_list = ohlcv_list[-max_bars:]
        
        # 分钟线数据也计算均线
        ma_list = self.calculate_moving_averages(ohlcv_list)
        
        return MarketData(
            timeframe=timeframe,
            data=ohlcv_list,
            moving_averages=ma_list,
        )
    
    def _try_em_minute_data(self, start_date: date, end_date: date, period: str) -> pd.DataFrame:
        """尝试使用东方财富接口获取分钟数据"""
        
        # 方法1: 直接调用东方财富API
        try:
            print("    尝试直接调用东方财富API...")
            df = self._call_eastmoney_api_directly(start_date, end_date, period)
            if df is not None and not df.empty:
                print(f"    [OK] 东方财富API成功，获取 {len(df)} 条数据")
                return df
        except Exception as e:
            print(f"    [FAIL] 东方财富API失败: {str(e)[:100]}")
        
        # 方法2: 使用AkShare的原始接口（可能有连接问题）
        try:
            print("    尝试AkShare原始接口...")
            df = ak.index_zh_a_hist_min_em(
                symbol=self.config.index_code,
                period=period,
                start_date=start_date.strftime("%Y-%m-%d") + " 09:30:00",
                end_date=end_date.strftime("%Y-%m-%d") + " 15:00:00",
            )
            if df is not None and not df.empty:
                print(f"    [OK] AkShare原始接口成功，获取 {len(df)} 条数据")
                return df
        except Exception as e:
            print(f"    [FAIL] AkShare原始接口失败: {str(e)[:100]}")
        
        # 如果都失败，尝试新浪接口
        try:
            print("    尝试新浪分钟数据接口...")
            df = self._call_sina_minute_api(period)
            if df is not None and not df.empty:
                print(f"    [OK] 新浪接口成功，获取 {len(df)} 条数据")
                return df
        except Exception as e:
            print(f"    [FAIL] 新浪接口失败: {str(e)[:100]}")

        # 如果都失败，返回空DataFrame而不是抛出异常
        print(f"    警告: 分钟数据源不可用，将仅使用日线数据")
        return pd.DataFrame()

    def _call_sina_minute_api(self, period: str) -> pd.DataFrame:
        """调用新浪分钟数据API"""
        import requests

        # 新浪接口参数：scale 为分钟周期，datalen 为数据条数
        # 15分钟最多获取约 500 条，5分钟最多获取约 500 条
        url = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"
        params = {
            "symbol": self.config.index_name,  # sh000001
            "scale": period,  # 5, 15
            "ma": "no",
            "datalen": "500"
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        # 解析JSON响应
        data = response.json()
        if not data or not isinstance(data, list):
            raise Exception("API返回无效数据")

        # 转换为DataFrame格式
        records = []
        for item in data:
            try:
                records.append({
                    "时间": item["day"],
                    "开盘": float(item["open"]),
                    "收盘": float(item["close"]),
                    "最高": float(item["high"]),
                    "最低": float(item["low"]),
                    "成交量": float(item["volume"]),
                })
            except (KeyError, ValueError):
                continue

        if not records:
            raise Exception("解析后无有效数据")

        df = pd.DataFrame(records)
        df["时间"] = pd.to_datetime(df["时间"])

        return df
    
    def _call_eastmoney_api_directly(self, start_date: date, end_date: date, period: str) -> pd.DataFrame:
        """直接调用东方财富API获取分钟数据"""
        import requests
        import json
        
        # 构造API请求
        url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": "1.000001",  # 上证指数
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": period,  # 分钟周期
            "fqt": "1",
            "beg": start_date.strftime("%Y%m%d"),
            "end": end_date.strftime("%Y%m%d"),
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        if data.get("rc") != 0 or not data.get("data", {}).get("klines"):
            raise Exception("API返回无效数据")
        
        # 解析K线数据
        klines = data["data"]["klines"]
        records = []
        
        for kline in klines:
            parts = kline.split(",")
            if len(parts) >= 6:
                records.append({
                    "时间": parts[0],
                    "开盘": float(parts[1]),
                    "收盘": float(parts[2]),
                    "最高": float(parts[3]),
                    "最低": float(parts[4]),
                    "成交量": float(parts[5]) if len(parts) > 5 else 0,
                })
        
        if not records:
            raise Exception("解析后无有效数据")
        
        df = pd.DataFrame(records)
        df["时间"] = pd.to_datetime(df["时间"])
        
        return df
    
    def _simulate_minute_from_daily(self, start_date: date, end_date: date, period: str) -> pd.DataFrame:
        """从日线数据模拟分钟数据（备用方案）"""
        print("    使用日线数据模拟分钟数据...")
        
        # 获取日线数据
        daily_df = ak.stock_zh_index_daily(symbol=self.config.index_name)
        daily_df["date"] = pd.to_datetime(daily_df["date"])
        daily_df = daily_df[
            (daily_df["date"].dt.date >= start_date) & 
            (daily_df["date"].dt.date <= end_date)
        ]
        
        if daily_df.empty:
            return pd.DataFrame()
        
        # 模拟分钟数据
        minute_data = []
        period_int = int(period)
        
        for _, row in daily_df.iterrows():
            trade_date = row["date"].date()
            open_price = row["open"]
            high_price = row["high"]
            low_price = row["low"]
            close_price = row["close"]
            volume = row["volume"]
            
            # 生成交易时间段
            morning_times = pd.date_range(
                start=f"{trade_date} 09:30:00",
                end=f"{trade_date} 11:30:00",
                freq=f"{period_int}min"
            )[:-1]  # 排除11:30
            
            afternoon_times = pd.date_range(
                start=f"{trade_date} 13:00:00",
                end=f"{trade_date} 15:00:00",
                freq=f"{period_int}min"
            )
            
            all_times = list(morning_times) + list(afternoon_times)
            
            # 为每个时间点生成OHLCV数据（简单模拟）
            for i, time_point in enumerate(all_times):
                # 简单的价格模拟：在日线范围内随机分布
                ratio = i / len(all_times)
                
                # 模拟价格走势
                if i == 0:
                    sim_open = open_price
                else:
                    sim_open = minute_data[-1]["close"]
                
                if i == len(all_times) - 1:
                    sim_close = close_price
                else:
                    # 简单线性插值
                    sim_close = open_price + (close_price - open_price) * ratio
                
                # 模拟高低价
                sim_high = max(sim_open, sim_close) + (high_price - max(open_price, close_price)) * 0.1
                sim_low = min(sim_open, sim_close) - (min(open_price, close_price) - low_price) * 0.1
                
                # 确保价格合理性
                sim_high = min(sim_high, high_price)
                sim_low = max(sim_low, low_price)
                
                minute_data.append({
                    "datetime": time_point,
                    "open": sim_open,
                    "high": sim_high,
                    "low": sim_low,
                    "close": sim_close,
                    "volume": volume / len(all_times),  # 平均分配成交量
                })
        
        return pd.DataFrame(minute_data)

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

        Requirements: 2.1, 2.2, 2.3, 2.5
        """
        # 获取各周期数据
        daily_data = self.get_daily_data(analysis_date)
        m15_data = self.get_m15_data(analysis_date)
        m5_data = self.get_m5_data(analysis_date, analysis_time)

        # 获取当前价格：优先使用5分钟线，否则使用日线最新收盘价
        if m5_data.ohlcv_list:
            current_price = m5_data.get_latest_ohlcv().close
        else:
            current_price = daily_data.get_latest_ohlcv().close
            print(f"  注意: 分钟数据不可用，使用日线收盘价: {current_price:.2f}")

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


def load_akshare_config(config_path: str = "config.yaml") -> AKShareConfig:
    """从配置文件加载AKShare配置的便捷函数
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        AKShareConfig对象
    """
    return AKShareConfig.from_yaml(config_path)


def create_akshare_source(config_path: str = "config.yaml") -> AKShareDataSource:
    """创建AKShare数据源的便捷函数
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        AKShareDataSource对象
    """
    config = load_akshare_config(config_path)
    return AKShareDataSource(config)
