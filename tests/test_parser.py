"""数据解析器测试

测试CSV和JSON格式解析功能，以及错误检测。

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
"""

import json
import pytest
from datetime import datetime

from src.data.parser import (
    DataParser,
    ParseError,
    ParseResult,
    parse_csv_string,
    parse_json_string,
)
from src.models.market_data import TimeFrame


class TestDataParser:
    """DataParser测试类"""
    
    def setup_method(self):
        """测试前初始化"""
        self.parser = DataParser()
    
    # ========== CSV解析测试 ==========
    
    def test_parse_csv_string_success(self):
        """测试CSV字符串解析成功"""
        csv_content = """timestamp,open,high,low,close,volume
2024-01-15,3000.0,3050.0,2980.0,3020.0,100000000
2024-01-16,3020.0,3060.0,3010.0,3040.0,120000000"""
        
        result = parse_csv_string(csv_content, TimeFrame.DAILY)
        
        assert result.success is True
        assert result.data is not None
        assert len(result.data.data) == 2
        assert result.data.timeframe == TimeFrame.DAILY
        
        # 验证第一条数据
        first = result.data.data[0]
        assert first.open == 3000.0
        assert first.high == 3050.0
        assert first.low == 2980.0
        assert first.close == 3020.0
        assert first.volume == 100000000
    
    def test_parse_csv_with_ma(self):
        """测试CSV解析包含均线数据"""
        csv_content = """timestamp,open,high,low,close,volume,ma5,ma10,ma20
2024-01-15,3000.0,3050.0,2980.0,3020.0,100000000,3010.0,3000.0,2990.0"""
        
        result = parse_csv_string(csv_content, TimeFrame.DAILY, has_ma=True)
        
        assert result.success is True
        assert result.data.moving_averages is not None
        assert len(result.data.moving_averages) == 1
        
        ma = result.data.moving_averages[0]
        assert ma.ma5 == 3010.0
        assert ma.ma10 == 3000.0
        assert ma.ma20 == 2990.0
    
    def test_parse_csv_empty_content(self):
        """测试空CSV内容"""
        result = parse_csv_string("", TimeFrame.DAILY)
        
        assert result.success is False
        assert result.errors is not None
        assert len(result.errors) > 0
    
    def test_parse_csv_missing_field(self):
        """测试CSV缺少必需字段"""
        csv_content = """timestamp,open,high,low,close
2024-01-15,3000.0,3050.0,2980.0,3020.0"""
        
        result = parse_csv_string(csv_content, TimeFrame.DAILY)
        
        assert result.success is False
        assert any("volume" in str(e) for e in result.errors)
    
    def test_parse_csv_invalid_number(self):
        """测试CSV无效数字"""
        csv_content = """timestamp,open,high,low,close,volume
2024-01-15,invalid,3050.0,2980.0,3020.0,100000000"""
        
        result = parse_csv_string(csv_content, TimeFrame.DAILY)
        
        assert result.success is False
        assert any("open" in str(e) for e in result.errors)
    
    def test_parse_csv_negative_price(self):
        """测试CSV负数价格"""
        csv_content = """timestamp,open,high,low,close,volume
2024-01-15,-3000.0,3050.0,2980.0,3020.0,100000000"""
        
        result = parse_csv_string(csv_content, TimeFrame.DAILY)
        
        assert result.success is False
        assert any("open" in str(e) for e in result.errors)
    
    def test_parse_csv_invalid_timestamp(self):
        """测试CSV无效时间戳"""
        csv_content = """timestamp,open,high,low,close,volume
invalid-date,3000.0,3050.0,2980.0,3020.0,100000000"""
        
        result = parse_csv_string(csv_content, TimeFrame.DAILY)
        
        assert result.success is False
        assert any("timestamp" in str(e) for e in result.errors)
    
    # ========== JSON解析测试 ==========
    
    def test_parse_json_string_success(self):
        """测试JSON字符串解析成功"""
        json_data = {
            "analysis_date": "2024-01-15",
            "daily": {
                "data": [
                    {"timestamp": "2024-01-15", "open": 3000.0, "high": 3050.0, 
                     "low": 2980.0, "close": 3020.0, "volume": 100000000}
                ]
            },
            "m15": {
                "data": [
                    {"timestamp": "2024-01-15 09:30:00", "open": 3000.0, "high": 3010.0,
                     "low": 2995.0, "close": 3005.0, "volume": 10000000}
                ]
            },
            "m5": {
                "data": [
                    {"timestamp": "2024-01-15 09:30:00", "open": 3000.0, "high": 3005.0,
                     "low": 2998.0, "close": 3003.0, "volume": 5000000}
                ]
            }
        }
        
        result = parse_json_string(json.dumps(json_data))
        
        assert result.success is True
        assert result.data is not None
        assert result.data.current_price == 3003.0
        assert result.data.daily_data.timeframe == TimeFrame.DAILY
        assert result.data.m15_data.timeframe == TimeFrame.M15
        assert result.data.m5_data.timeframe == TimeFrame.M5
    
    def test_parse_json_with_analysis_time(self):
        """测试JSON解析包含分析时间"""
        json_data = {
            "analysis_date": "2024-01-15",
            "analysis_time": "14:30:00",
            "daily": {
                "data": [
                    {"timestamp": "2024-01-15", "open": 3000.0, "high": 3050.0,
                     "low": 2980.0, "close": 3020.0, "volume": 100000000}
                ]
            },
            "m15": {
                "data": [
                    {"timestamp": "2024-01-15 09:30:00", "open": 3000.0, "high": 3010.0,
                     "low": 2995.0, "close": 3005.0, "volume": 10000000}
                ]
            },
            "m5": {
                "data": [
                    {"timestamp": "2024-01-15 09:30:00", "open": 3000.0, "high": 3005.0,
                     "low": 2998.0, "close": 3003.0, "volume": 5000000}
                ]
            }
        }
        
        result = parse_json_string(json.dumps(json_data))
        
        assert result.success is True
        assert result.data.analysis_time is not None
        assert result.data.analysis_time.hour == 14
        assert result.data.analysis_time.minute == 30
    
    def test_parse_json_missing_required_field(self):
        """测试JSON缺少必需字段"""
        json_data = {
            "analysis_date": "2024-01-15",
            "daily": {
                "data": [
                    {"timestamp": "2024-01-15", "open": 3000.0, "high": 3050.0,
                     "low": 2980.0, "close": 3020.0, "volume": 100000000}
                ]
            }
            # 缺少 m15, m5
        }
        
        result = parse_json_string(json.dumps(json_data))
        
        assert result.success is False
        assert any("m15" in str(e) or "m5" in str(e) 
                   for e in result.errors)
    
    def test_parse_json_invalid_format(self):
        """测试无效JSON格式"""
        result = parse_json_string("not valid json")
        
        assert result.success is False
        assert any("JSON" in str(e) for e in result.errors)
    
    def test_parse_json_empty_data(self):
        """测试JSON空数据"""
        json_data = {
            "analysis_date": "2024-01-15",
            "daily": {"data": []},
            "m15": {"data": []},
            "m5": {"data": []}
        }
        
        result = parse_json_string(json.dumps(json_data))
        
        assert result.success is False
        assert any("不能为空" in str(e) for e in result.errors)
    
    # ========== 时间戳解析测试 ==========
    
    def test_parse_timestamp_formats(self):
        """测试各种时间戳格式"""
        test_cases = [
            ("2024-01-15", datetime(2024, 1, 15)),
            ("2024-01-15 09:30:00", datetime(2024, 1, 15, 9, 30, 0)),
            ("2024-01-15T09:30:00", datetime(2024, 1, 15, 9, 30, 0)),
            ("20240115", datetime(2024, 1, 15)),
            ("2024/01/15", datetime(2024, 1, 15)),
        ]
        
        for ts_str, expected in test_cases:
            result, error = self.parser.parse_timestamp(ts_str)
            assert error is None, f"Failed for {ts_str}: {error}"
            assert result == expected, f"Failed for {ts_str}"
    
    # ========== 错误信息测试 ==========
    
    def test_parse_error_str(self):
        """测试ParseError字符串表示"""
        error = ParseError(field="open", message="必须是数字", row_index=5)
        error_str = str(error)
        
        assert "行 5" in error_str
        assert "open" in error_str
        assert "必须是数字" in error_str
    
    def test_parse_result_error_messages(self):
        """测试ParseResult错误信息获取"""
        errors = [
            ParseError(field="open", message="错误1"),
            ParseError(field="close", message="错误2"),
        ]
        result = ParseResult.fail(errors)
        
        messages = result.get_error_messages()
        assert len(messages) == 2
        assert "open" in messages[0]
        assert "close" in messages[1]


class TestParserEdgeCases:
    """边界情况测试"""
    
    def test_high_low_validation(self):
        """测试高低价验证"""
        csv_content = """timestamp,open,high,low,close,volume
2024-01-15,3000.0,2980.0,3050.0,3020.0,100000000"""
        
        result = parse_csv_string(csv_content, TimeFrame.DAILY)
        
        # high < low 应该失败
        assert result.success is False
    
    def test_zero_volume_allowed(self):
        """测试零成交量允许"""
        csv_content = """timestamp,open,high,low,close,volume
2024-01-15,3000.0,3050.0,2980.0,3020.0,0"""
        
        result = parse_csv_string(csv_content, TimeFrame.DAILY)
        
        assert result.success is True
        assert result.data.data[0].volume == 0
    
    def test_data_sorted_by_timestamp(self):
        """测试数据按时间排序"""
        csv_content = """timestamp,open,high,low,close,volume
2024-01-16,3020.0,3060.0,3010.0,3040.0,120000000
2024-01-15,3000.0,3050.0,2980.0,3020.0,100000000"""
        
        result = parse_csv_string(csv_content, TimeFrame.DAILY)
        
        assert result.success is True
        # 应该按时间升序排列
        assert result.data.data[0].timestamp < result.data.data[1].timestamp
