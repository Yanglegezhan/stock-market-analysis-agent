"""上下文构建器

将原始市场数据转换为LLM易于理解的上下文格式。
保留完整的CSV格式数据，同时提供关键点位提取和均线位置格式化。

数据周期：日线、15分钟线、5分钟线（无1分钟线）

Requirements: 4.2, 4.3, 4.7
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from src.models.market_data import (
    AnalysisInput,
    MarketData,
    MovingAverage,
    OHLCV,
    TimeFrame,
)


@dataclass
class MarketContext:
    """LLM分析所需的市场上下文
    
    保留完整的CSV格式数据，让LLM能够看到所有细节。
    使用日线、15分钟线、5分钟线三个周期。
    
    Requirements: 4.2, 4.3
    """
    # 日线数据（CSV格式，包含均线）
    daily_csv: str
    daily_count: int
    
    # 15分钟线数据（CSV格式）
    m15_csv: str
    m15_count: int
    
    # 5分钟线数据（CSV格式）
    m5_csv: str
    m5_count: int
    
    # 均线位置
    ma_positions: str
    
    # 当前价格信息
    current_price: float
    price_change_pct: float
    
    # 数据截止信息
    data_cutoff: str
    
    def to_full_context(self) -> str:
        """生成完整的上下文文本"""
        return f"""## 市场数据

### 当前价格
当前价格：{self.current_price:.2f}
今日涨跌幅：{self.price_change_pct:+.2f}%

### 日线数据（最近{self.daily_count}个交易日）
```csv
{self.daily_csv}
```

### 15分钟线数据（共{self.m15_count}根K线）
```csv
{self.m15_csv}
```

### 5分钟线数据（共{self.m5_count}根K线）
```csv
{self.m5_csv}
```

### 均线位置
{self.ma_positions}

### 数据截止时间
{self.data_cutoff}"""


class ContextBuilder:
    """上下文构建器
    
    将原始市场数据转换为CSV格式的上下文，保留完整数据细节。
    使用日线、15分钟线、5分钟线三个周期（无1分钟线）。
    
    Requirements: 4.2, 4.3, 4.7
    """
    
    def __init__(
        self, 
        max_tokens: int = 8000,
        daily_limit: int = 60,      # 日线保留最近60个交易日
        m15_limit: int = 200,       # 15分钟线保留最近200根
        m5_limit: int = 300,        # 5分钟线保留最近300根（约3-4天）
    ):
        """初始化上下文构建器
        
        Args:
            max_tokens: 上下文最大token数（用于压缩策略）
            daily_limit: 日线数据保留条数
            m15_limit: 15分钟线数据保留条数
            m5_limit: 5分钟线数据保留条数
        """
        self.max_tokens = max_tokens
        self.daily_limit = daily_limit
        self.m15_limit = m15_limit
        self.m5_limit = m5_limit
    
    def build_context(self, input_data: AnalysisInput) -> MarketContext:
        """将原始数据转换为LLM易于理解的上下文
        
        Args:
            input_data: 分析输入数据
            
        Returns:
            MarketContext对象
            
        Requirements: 4.2, 4.3, 4.7
        """
        # 计算涨跌幅
        if len(input_data.daily_data.data) > 1:
            prev_close = input_data.daily_data.data[-2].close
            price_change_pct = (input_data.current_price - prev_close) / prev_close * 100
        else:
            price_change_pct = 0.0
        
        # 转换各周期数据为CSV格式
        daily_csv, daily_count = self._to_csv_with_ma(
            input_data.daily_data, 
            self.daily_limit,
            include_ma=True
        )
        
        m15_csv, m15_count = self._to_csv(
            input_data.m15_data, 
            self.m15_limit
        )
        
        m5_csv, m5_count = self._to_csv(
            input_data.m5_data, 
            self.m5_limit
        )
        
        # 格式化均线位置
        ma_positions = self.format_ma_positions(
            input_data.daily_data.moving_averages,
            input_data.current_price
        )
        
        # 数据截止信息
        if input_data.analysis_time:
            data_cutoff = input_data.analysis_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            data_cutoff = input_data.analysis_date.strftime("%Y-%m-%d")
        
        return MarketContext(
            daily_csv=daily_csv,
            daily_count=daily_count,
            m15_csv=m15_csv,
            m15_count=m15_count,
            m5_csv=m5_csv,
            m5_count=m5_count,
            ma_positions=ma_positions,
            current_price=input_data.current_price,
            price_change_pct=price_change_pct,
            data_cutoff=data_cutoff,
        )
    
    def _to_csv(self, data: MarketData, limit: int) -> Tuple[str, int]:
        """将市场数据转换为CSV格式
        
        Args:
            data: 市场数据
            limit: 最大行数限制
            
        Returns:
            (CSV字符串, 实际行数)
        """
        ohlcv_list = data.data[-limit:] if len(data.data) > limit else data.data
        
        if not ohlcv_list:
            return "无数据", 0
        
        # CSV头
        lines = ["timestamp,open,high,low,close,volume"]
        
        # 数据行
        for ohlcv in ohlcv_list:
            ts = ohlcv.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            line = f"{ts},{ohlcv.open:.2f},{ohlcv.high:.2f},{ohlcv.low:.2f},{ohlcv.close:.2f},{ohlcv.volume:.0f}"
            lines.append(line)
        
        return "\n".join(lines), len(ohlcv_list)
    
    def _to_csv_with_ma(
        self, 
        data: MarketData, 
        limit: int,
        include_ma: bool = True
    ) -> Tuple[str, int]:
        """将市场数据转换为CSV格式（包含均线）
        
        Args:
            data: 市场数据
            limit: 最大行数限制
            include_ma: 是否包含均线数据
            
        Returns:
            (CSV字符串, 实际行数)
        """
        ohlcv_list = data.data[-limit:] if len(data.data) > limit else data.data
        
        if not ohlcv_list:
            return "无数据", 0
        
        # 构建均线数据映射
        ma_map = {}
        if include_ma and data.moving_averages:
            for ma in data.moving_averages:
                ma_map[ma.timestamp] = ma
        
        # CSV头
        if include_ma and ma_map:
            lines = ["timestamp,open,high,low,close,volume,ma5,ma10,ma20,ma60,ma120"]
        else:
            lines = ["timestamp,open,high,low,close,volume"]
        
        # 数据行
        for ohlcv in ohlcv_list:
            ts = ohlcv.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            base_line = f"{ts},{ohlcv.open:.2f},{ohlcv.high:.2f},{ohlcv.low:.2f},{ohlcv.close:.2f},{ohlcv.volume:.0f}"
            
            if include_ma and ma_map:
                ma = ma_map.get(ohlcv.timestamp)
                if ma:
                    ma5 = f"{ma.ma5:.2f}" if ma.ma5 else ""
                    ma10 = f"{ma.ma10:.2f}" if ma.ma10 else ""
                    ma20 = f"{ma.ma20:.2f}" if ma.ma20 else ""
                    ma60 = f"{ma.ma60:.2f}" if ma.ma60 else ""
                    ma120 = f"{ma.ma120:.2f}" if ma.ma120 else ""
                    line = f"{base_line},{ma5},{ma10},{ma20},{ma60},{ma120}"
                else:
                    line = f"{base_line},,,,,"
                lines.append(line)
            else:
                lines.append(base_line)
        
        return "\n".join(lines), len(ohlcv_list)
    
    def format_ma_positions(
        self, 
        ma_data: Optional[List[MovingAverage]], 
        current_price: float
    ) -> str:
        """格式化均线位置信息
        
        Args:
            ma_data: 均线数据列表
            current_price: 当前价格
            
        Returns:
            均线位置格式化文本
            
        Requirements: 4.3
        """
        if not ma_data:
            return "无均线数据"
        
        latest_ma = ma_data[-1]
        
        lines = []
        ma_values = [
            ("MA5", latest_ma.ma5),
            ("MA10", latest_ma.ma10),
            ("MA20", latest_ma.ma20),
            ("MA60", latest_ma.ma60),
            ("MA120", latest_ma.ma120),
        ]
        
        for name, value in ma_values:
            if value is not None:
                diff = current_price - value
                diff_pct = diff / value * 100
                position = "上方" if diff > 0 else "下方"
                lines.append(
                    f"- {name}：{value:.2f}（当前价在其{position}，"
                    f"距离{abs(diff):.2f}点，{abs(diff_pct):.2f}%）"
                )
        
        if not lines:
            return "无有效均线数据"
        
        # 添加均线排列状态
        valid_mas = [(name, value) for name, value in ma_values if value is not None]
        if len(valid_mas) >= 3:
            arrangement = self._analyze_ma_arrangement(valid_mas)
            lines.append(f"\n均线排列：{arrangement}")
        
        return "\n".join(lines)
    
    def _analyze_ma_arrangement(
        self, 
        ma_values: List[Tuple[str, float]]
    ) -> str:
        """分析均线排列状态
        
        Args:
            ma_values: 均线值列表 [(名称, 值), ...]
            
        Returns:
            均线排列描述
        """
        # 按周期排序（短周期在前）
        sorted_mas = sorted(ma_values, key=lambda x: int(x[0][2:]))
        values = [v for _, v in sorted_mas]
        
        # 检查是否多头排列（短期均线在上）
        is_bullish = all(values[i] >= values[i+1] for i in range(len(values)-1))
        
        # 检查是否空头排列（短期均线在下）
        is_bearish = all(values[i] <= values[i+1] for i in range(len(values)-1))
        
        if is_bullish:
            return "多头排列（短期均线在上，长期均线在下）"
        elif is_bearish:
            return "空头排列（短期均线在下，长期均线在上）"
        else:
            return "交叉排列（均线缠绕）"


def build_market_context(
    input_data: AnalysisInput, 
    max_tokens: int = 8000,
    daily_limit: int = 65,
    m15_limit: int = 80,
    m5_limit: int = 48,
) -> MarketContext:
    """构建市场上下文的便捷函数
    
    Args:
        input_data: 分析输入数据
        max_tokens: 最大token数
        daily_limit: 日线数据保留条数
        m15_limit: 15分钟线数据保留条数
        m5_limit: 5分钟线数据保留条数
        
    Returns:
        MarketContext对象
    """
    builder = ContextBuilder(
        max_tokens=max_tokens,
        daily_limit=daily_limit,
        m15_limit=m15_limit,
        m5_limit=m5_limit,
    )
    return builder.build_context(input_data)
