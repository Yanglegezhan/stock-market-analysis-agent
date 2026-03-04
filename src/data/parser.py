"""数据解析器

支持CSV和JSON格式的离线数据解析，用于加载本地市场数据文件。
实现格式错误检测和错误信息返回。

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
"""

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.models.market_data import (
    AnalysisInput,
    MarketData,
    MovingAverage,
    OHLCV,
    TimeFrame,
)


@dataclass
class ParseError:
    """解析错误信息"""
    field: str
    message: str
    row_index: Optional[int] = None
    
    def __str__(self) -> str:
        if self.row_index is not None:
            return f"行 {self.row_index}: 字段 '{self.field}' - {self.message}"
        return f"字段 '{self.field}' - {self.message}"


@dataclass
class ParseResult:
    """解析结果"""
    success: bool
    data: Optional[Any] = None
    errors: Optional[List[ParseError]] = None
    
    @classmethod
    def ok(cls, data: Any) -> "ParseResult":
        """创建成功结果"""
        return cls(success=True, data=data, errors=None)
    
    @classmethod
    def fail(cls, errors: List[ParseError]) -> "ParseResult":
        """创建失败结果"""
        return cls(success=False, data=None, errors=errors)
    
    def get_error_messages(self) -> List[str]:
        """获取所有错误信息"""
        if self.errors:
            return [str(e) for e in self.errors]
        return []


class DataParser:
    """数据解析器 - 支持CSV和JSON格式
    
    Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
    """
    
    # OHLCV必需字段
    OHLCV_REQUIRED_FIELDS = ["timestamp", "open", "high", "low", "close", "volume"]
    
    # 均线可选字段
    MA_FIELDS = ["ma5", "ma10", "ma20", "ma60", "ma120"]
    
    # 时间戳格式列表（按优先级排序）
    TIMESTAMP_FORMATS = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%Y%m%d",
        "%Y%m%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
    ]

    def parse_timestamp(self, value: str) -> Tuple[Optional[datetime], Optional[str]]:
        """解析时间戳字符串
        
        Args:
            value: 时间戳字符串
            
        Returns:
            (datetime对象, 错误信息) - 成功时错误信息为None
        """
        if not value or not isinstance(value, str):
            return None, "时间戳不能为空"
        
        value = value.strip()
        
        for fmt in self.TIMESTAMP_FORMATS:
            try:
                return datetime.strptime(value, fmt), None
            except ValueError:
                continue
        
        return None, f"无法解析时间戳格式: '{value}'"
    
    def parse_float(
        self, value: Any, field_name: str, allow_zero: bool = False
    ) -> Tuple[Optional[float], Optional[str]]:
        """解析浮点数
        
        Args:
            value: 要解析的值
            field_name: 字段名（用于错误信息）
            allow_zero: 是否允许零值
            
        Returns:
            (float值, 错误信息) - 成功时错误信息为None
        """
        if value is None or value == "":
            return None, f"{field_name}不能为空"
        
        try:
            float_val = float(value)
        except (ValueError, TypeError):
            return None, f"{field_name}必须是数字，当前值: '{value}'"
        
        if not allow_zero and float_val <= 0:
            return None, f"{field_name}必须大于0，当前值: {float_val}"
        
        if allow_zero and float_val < 0:
            return None, f"{field_name}不能为负数，当前值: {float_val}"
        
        return float_val, None
    
    def parse_ohlcv_row(
        self, row: Dict[str, Any], row_index: int
    ) -> Tuple[Optional[OHLCV], List[ParseError]]:
        """解析单行OHLCV数据
        
        Args:
            row: 数据行字典
            row_index: 行索引（用于错误信息）
            
        Returns:
            (OHLCV对象, 错误列表) - 成功时错误列表为空
        """
        errors: List[ParseError] = []
        
        # 检查必需字段
        for field in self.OHLCV_REQUIRED_FIELDS:
            if field not in row:
                errors.append(ParseError(
                    field=field,
                    message=f"缺少必需字段",
                    row_index=row_index
                ))
        
        if errors:
            return None, errors
        
        # 解析时间戳
        ts_value = row.get("timestamp", "")
        if isinstance(ts_value, datetime):
            timestamp = ts_value
        else:
            timestamp, ts_error = self.parse_timestamp(str(ts_value))
            if ts_error:
                errors.append(ParseError(
                    field="timestamp",
                    message=ts_error,
                    row_index=row_index
                ))
        
        # 解析价格字段
        open_val, open_err = self.parse_float(row.get("open"), "open")
        if open_err:
            errors.append(ParseError(field="open", message=open_err, row_index=row_index))
        
        high_val, high_err = self.parse_float(row.get("high"), "high")
        if high_err:
            errors.append(ParseError(field="high", message=high_err, row_index=row_index))
        
        low_val, low_err = self.parse_float(row.get("low"), "low")
        if low_err:
            errors.append(ParseError(field="low", message=low_err, row_index=row_index))
        
        close_val, close_err = self.parse_float(row.get("close"), "close")
        if close_err:
            errors.append(ParseError(field="close", message=close_err, row_index=row_index))
        
        volume_val, volume_err = self.parse_float(row.get("volume"), "volume", allow_zero=True)
        if volume_err:
            errors.append(ParseError(field="volume", message=volume_err, row_index=row_index))
        
        if errors:
            return None, errors
        
        # 创建OHLCV对象（Pydantic会进行额外验证）
        try:
            ohlcv = OHLCV(
                timestamp=timestamp,
                open=open_val,
                high=high_val,
                low=low_val,
                close=close_val,
                volume=volume_val,
            )
            return ohlcv, []
        except ValueError as e:
            errors.append(ParseError(
                field="ohlcv",
                message=str(e),
                row_index=row_index
            ))
            return None, errors

    def parse_ma_row(
        self, row: Dict[str, Any], row_index: int
    ) -> Tuple[Optional[MovingAverage], List[ParseError]]:
        """解析单行均线数据
        
        Args:
            row: 数据行字典
            row_index: 行索引（用于错误信息）
            
        Returns:
            (MovingAverage对象, 错误列表) - 成功时错误列表为空
        """
        errors: List[ParseError] = []
        
        # 检查时间戳字段
        if "timestamp" not in row:
            errors.append(ParseError(
                field="timestamp",
                message="缺少必需字段",
                row_index=row_index
            ))
            return None, errors
        
        # 解析时间戳
        ts_value = row.get("timestamp", "")
        if isinstance(ts_value, datetime):
            timestamp = ts_value
        else:
            timestamp, ts_error = self.parse_timestamp(str(ts_value))
            if ts_error:
                errors.append(ParseError(
                    field="timestamp",
                    message=ts_error,
                    row_index=row_index
                ))
                return None, errors
        
        # 解析均线字段（均为可选）
        ma_values = {}
        for ma_field in self.MA_FIELDS:
            value = row.get(ma_field)
            if value is not None and value != "":
                ma_val, ma_err = self.parse_float(value, ma_field)
                if ma_err:
                    errors.append(ParseError(
                        field=ma_field,
                        message=ma_err,
                        row_index=row_index
                    ))
                else:
                    ma_values[ma_field] = ma_val
            else:
                ma_values[ma_field] = None
        
        if errors:
            return None, errors
        
        try:
            ma = MovingAverage(
                timestamp=timestamp,
                ma5=ma_values.get("ma5"),
                ma10=ma_values.get("ma10"),
                ma20=ma_values.get("ma20"),
                ma60=ma_values.get("ma60"),
                ma120=ma_values.get("ma120"),
            )
            return ma, []
        except ValueError as e:
            errors.append(ParseError(
                field="moving_average",
                message=str(e),
                row_index=row_index
            ))
            return None, errors
    
    def parse_ohlcv_list(
        self, rows: List[Dict[str, Any]]
    ) -> ParseResult:
        """解析OHLCV数据列表
        
        Args:
            rows: 数据行列表
            
        Returns:
            ParseResult对象
        """
        if not rows:
            return ParseResult.fail([ParseError(
                field="data",
                message="数据列表不能为空"
            )])
        
        ohlcv_list: List[OHLCV] = []
        all_errors: List[ParseError] = []
        
        for i, row in enumerate(rows):
            ohlcv, errors = self.parse_ohlcv_row(row, i)
            if errors:
                all_errors.extend(errors)
            elif ohlcv:
                ohlcv_list.append(ohlcv)
        
        if all_errors:
            return ParseResult.fail(all_errors)
        
        # 按时间排序
        ohlcv_list.sort(key=lambda x: x.timestamp)
        
        return ParseResult.ok(ohlcv_list)
    
    def parse_ma_list(
        self, rows: List[Dict[str, Any]]
    ) -> ParseResult:
        """解析均线数据列表
        
        Args:
            rows: 数据行列表
            
        Returns:
            ParseResult对象
        """
        if not rows:
            return ParseResult.ok([])  # 均线数据可以为空
        
        ma_list: List[MovingAverage] = []
        all_errors: List[ParseError] = []
        
        for i, row in enumerate(rows):
            ma, errors = self.parse_ma_row(row, i)
            if errors:
                all_errors.extend(errors)
            elif ma:
                ma_list.append(ma)
        
        if all_errors:
            return ParseResult.fail(all_errors)
        
        # 按时间排序
        ma_list.sort(key=lambda x: x.timestamp)
        
        return ParseResult.ok(ma_list)

    def parse_market_data(
        self,
        timeframe: TimeFrame,
        ohlcv_rows: List[Dict[str, Any]],
        ma_rows: Optional[List[Dict[str, Any]]] = None
    ) -> ParseResult:
        """解析市场数据
        
        Args:
            timeframe: 时间周期
            ohlcv_rows: OHLCV数据行列表
            ma_rows: 均线数据行列表（可选）
            
        Returns:
            ParseResult对象，成功时data为MarketData
        """
        # 解析OHLCV数据
        ohlcv_result = self.parse_ohlcv_list(ohlcv_rows)
        if not ohlcv_result.success:
            return ohlcv_result
        
        # 解析均线数据
        ma_list = None
        if ma_rows:
            ma_result = self.parse_ma_list(ma_rows)
            if not ma_result.success:
                return ma_result
            ma_list = ma_result.data
        
        # 创建MarketData对象
        try:
            market_data = MarketData(
                timeframe=timeframe,
                data=ohlcv_result.data,
                moving_averages=ma_list if ma_list else None,
            )
            return ParseResult.ok(market_data)
        except ValueError as e:
            return ParseResult.fail([ParseError(
                field="market_data",
                message=str(e)
            )])
    
    def parse_csv_file(
        self,
        file_path: Union[str, Path],
        timeframe: TimeFrame,
        has_ma: bool = False
    ) -> ParseResult:
        """解析CSV文件
        
        Args:
            file_path: CSV文件路径
            timeframe: 时间周期
            has_ma: 是否包含均线数据（在同一文件中）
            
        Returns:
            ParseResult对象，成功时data为MarketData
            
        Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
        """
        path = Path(file_path)
        
        if not path.exists():
            return ParseResult.fail([ParseError(
                field="file_path",
                message=f"文件不存在: {file_path}"
            )])
        
        if not path.suffix.lower() == ".csv":
            return ParseResult.fail([ParseError(
                field="file_path",
                message=f"文件格式错误，期望CSV文件: {file_path}"
            )])
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except UnicodeDecodeError:
            # 尝试GBK编码
            try:
                with open(path, "r", encoding="gbk") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
            except Exception as e:
                return ParseResult.fail([ParseError(
                    field="file_path",
                    message=f"无法读取文件: {e}"
                )])
        except Exception as e:
            return ParseResult.fail([ParseError(
                field="file_path",
                message=f"无法读取文件: {e}"
            )])
        
        if not rows:
            return ParseResult.fail([ParseError(
                field="data",
                message="CSV文件为空"
            )])
        
        # 如果包含均线数据，从同一行中提取
        ma_rows = rows if has_ma else None
        
        return self.parse_market_data(timeframe, rows, ma_rows)
    
    def parse_csv_string(
        self,
        csv_content: str,
        timeframe: TimeFrame,
        has_ma: bool = False
    ) -> ParseResult:
        """解析CSV字符串
        
        Args:
            csv_content: CSV内容字符串
            timeframe: 时间周期
            has_ma: 是否包含均线数据
            
        Returns:
            ParseResult对象，成功时data为MarketData
        """
        if not csv_content or not csv_content.strip():
            return ParseResult.fail([ParseError(
                field="csv_content",
                message="CSV内容不能为空"
            )])
        
        try:
            reader = csv.DictReader(csv_content.strip().splitlines())
            rows = list(reader)
        except Exception as e:
            return ParseResult.fail([ParseError(
                field="csv_content",
                message=f"无法解析CSV内容: {e}"
            )])
        
        if not rows:
            return ParseResult.fail([ParseError(
                field="data",
                message="CSV内容为空"
            )])
        
        ma_rows = rows if has_ma else None
        
        return self.parse_market_data(timeframe, rows, ma_rows)

    def parse_json_file(
        self,
        file_path: Union[str, Path]
    ) -> ParseResult:
        """解析JSON文件（完整分析输入格式）
        
        JSON格式示例:
        {
            "analysis_date": "2024-01-15",
            "analysis_time": "14:30:00",  // 可选
            "daily": {
                "data": [...],
                "ma": [...]  // 可选
            },
            "m15": {...},
            "m5": {...}
        }
        
        Args:
            file_path: JSON文件路径
            
        Returns:
            ParseResult对象，成功时data为AnalysisInput
            
        Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
        """
        path = Path(file_path)
        
        if not path.exists():
            return ParseResult.fail([ParseError(
                field="file_path",
                message=f"文件不存在: {file_path}"
            )])
        
        if not path.suffix.lower() == ".json":
            return ParseResult.fail([ParseError(
                field="file_path",
                message=f"文件格式错误，期望JSON文件: {file_path}"
            )])
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
        except json.JSONDecodeError as e:
            return ParseResult.fail([ParseError(
                field="json",
                message=f"JSON格式错误: {e}"
            )])
        except Exception as e:
            return ParseResult.fail([ParseError(
                field="file_path",
                message=f"无法读取文件: {e}"
            )])
        
        return self.parse_json_data(json_data)
    
    def parse_json_string(self, json_content: str) -> ParseResult:
        """解析JSON字符串
        
        Args:
            json_content: JSON内容字符串
            
        Returns:
            ParseResult对象，成功时data为AnalysisInput
        """
        if not json_content or not json_content.strip():
            return ParseResult.fail([ParseError(
                field="json_content",
                message="JSON内容不能为空"
            )])
        
        try:
            json_data = json.loads(json_content)
        except json.JSONDecodeError as e:
            return ParseResult.fail([ParseError(
                field="json",
                message=f"JSON格式错误: {e}"
            )])
        
        return self.parse_json_data(json_data)
    
    def parse_json_data(self, json_data: Dict[str, Any]) -> ParseResult:
        """解析JSON数据字典
        
        Args:
            json_data: JSON数据字典
            
        Returns:
            ParseResult对象，成功时data为AnalysisInput
        """
        errors: List[ParseError] = []
        
        # 检查必需字段
        required_fields = ["analysis_date", "daily", "m15", "m5"]
        for field in required_fields:
            if field not in json_data:
                errors.append(ParseError(
                    field=field,
                    message="缺少必需字段"
                ))
        
        if errors:
            return ParseResult.fail(errors)
        
        # 解析分析日期
        analysis_date_str = json_data.get("analysis_date", "")
        analysis_date, date_err = self.parse_timestamp(str(analysis_date_str))
        if date_err:
            errors.append(ParseError(
                field="analysis_date",
                message=date_err
            ))
        
        # 解析分析时间（可选）
        analysis_time = None
        analysis_time_str = json_data.get("analysis_time")
        if analysis_time_str:
            # 如果只有时间部分，与日期组合
            if ":" in str(analysis_time_str) and len(str(analysis_time_str)) <= 8:
                full_time_str = f"{analysis_date_str} {analysis_time_str}"
                analysis_time, time_err = self.parse_timestamp(full_time_str)
            else:
                analysis_time, time_err = self.parse_timestamp(str(analysis_time_str))
            
            if time_err:
                errors.append(ParseError(
                    field="analysis_time",
                    message=time_err
                ))
        
        if errors:
            return ParseResult.fail(errors)
        
        # 解析各周期数据
        timeframe_map = {
            "daily": TimeFrame.DAILY,
            "m15": TimeFrame.M15,
            "m5": TimeFrame.M5,
        }
        
        market_data_dict: Dict[str, MarketData] = {}
        
        for key, timeframe in timeframe_map.items():
            tf_data = json_data.get(key, {})
            
            if not isinstance(tf_data, dict):
                errors.append(ParseError(
                    field=key,
                    message=f"期望字典类型，当前类型: {type(tf_data).__name__}"
                ))
                continue
            
            ohlcv_rows = tf_data.get("data", [])
            ma_rows = tf_data.get("ma")
            
            if not ohlcv_rows:
                errors.append(ParseError(
                    field=f"{key}.data",
                    message="K线数据不能为空"
                ))
                continue
            
            result = self.parse_market_data(timeframe, ohlcv_rows, ma_rows)
            if not result.success:
                for err in result.errors or []:
                    err.field = f"{key}.{err.field}"
                    errors.append(err)
            else:
                market_data_dict[key] = result.data
        
        if errors:
            return ParseResult.fail(errors)
        
        # 获取当前价格（使用最新的5分钟线收盘价）
        current_price = market_data_dict["m5"].get_latest_ohlcv().close
        
        # 如果有analysis_time，则analysis_date应该使用analysis_time
        # 因为AnalysisInput要求analysis_time <= analysis_date
        final_analysis_date = analysis_time if analysis_time else analysis_date
        
        # 创建AnalysisInput对象
        try:
            analysis_input = AnalysisInput(
                analysis_date=final_analysis_date,
                analysis_time=analysis_time,
                daily_data=market_data_dict["daily"],
                m15_data=market_data_dict["m15"],
                m5_data=market_data_dict["m5"],
                current_price=current_price,
            )
            return ParseResult.ok(analysis_input)
        except ValueError as e:
            return ParseResult.fail([ParseError(
                field="analysis_input",
                message=str(e)
            )])

    def parse_single_timeframe_json(
        self,
        json_data: Dict[str, Any],
        timeframe: TimeFrame
    ) -> ParseResult:
        """解析单个时间周期的JSON数据
        
        JSON格式示例:
        {
            "data": [...],
            "ma": [...]  // 可选
        }
        
        Args:
            json_data: JSON数据字典
            timeframe: 时间周期
            
        Returns:
            ParseResult对象，成功时data为MarketData
        """
        if not isinstance(json_data, dict):
            return ParseResult.fail([ParseError(
                field="json_data",
                message=f"期望字典类型，当前类型: {type(json_data).__name__}"
            )])
        
        ohlcv_rows = json_data.get("data", [])
        ma_rows = json_data.get("ma")
        
        if not ohlcv_rows:
            return ParseResult.fail([ParseError(
                field="data",
                message="K线数据不能为空"
            )])
        
        return self.parse_market_data(timeframe, ohlcv_rows, ma_rows)


# 便捷函数

def parse_csv(
    file_path: Union[str, Path],
    timeframe: TimeFrame,
    has_ma: bool = False
) -> ParseResult:
    """解析CSV文件的便捷函数
    
    Args:
        file_path: CSV文件路径
        timeframe: 时间周期
        has_ma: 是否包含均线数据
        
    Returns:
        ParseResult对象
    """
    parser = DataParser()
    return parser.parse_csv_file(file_path, timeframe, has_ma)


def parse_json(file_path: Union[str, Path]) -> ParseResult:
    """解析JSON文件的便捷函数
    
    Args:
        file_path: JSON文件路径
        
    Returns:
        ParseResult对象
    """
    parser = DataParser()
    return parser.parse_json_file(file_path)


def parse_csv_string(
    csv_content: str,
    timeframe: TimeFrame,
    has_ma: bool = False
) -> ParseResult:
    """解析CSV字符串的便捷函数
    
    Args:
        csv_content: CSV内容字符串
        timeframe: 时间周期
        has_ma: 是否包含均线数据
        
    Returns:
        ParseResult对象
    """
    parser = DataParser()
    return parser.parse_csv_string(csv_content, timeframe, has_ma)


def parse_json_string(json_content: str) -> ParseResult:
    """解析JSON字符串的便捷函数
    
    Args:
        json_content: JSON内容字符串
        
    Returns:
        ParseResult对象
    """
    parser = DataParser()
    return parser.parse_json_string(json_content)
