"""大盘分析Agent

实现完整的分析流程：数据加载 → 时间过滤 → 上下文构建 → LLM分析 → 结果解析。

Requirements: 5.1-5.7, 6.1-6.4, 7.1-7.5, 8.1-8.5
"""

import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional

from src.analysis.calculator import PriceCalculator
from src.analysis.context_builder import ContextBuilder, MarketContext
from src.analysis.prompt_engine import PromptEngine
from src.data.time_filter import TimeIsolationFilter, FilterResult, FilterWarning
from src.llm.base import LLMConfig, LLMMessage, LLMError
from src.llm.client import LLMClient
from src.models.analysis_result import (
    AnalysisReport,
    IntradayAnalysis,
    LLMResponseParser,
    LongTermExpectation,
    PositionAnalysis,
    ShortTermExpectation,
    SupportResistanceResult,
)
from src.models.market_data import AnalysisInput, MarketData


@dataclass
class AgentConfig:
    """Agent配置"""
    llm_config: LLMConfig
    template_dir: str = "prompts/"
    max_context_tokens: int = 8000
    daily_limit: int = 60      # 日线保留最近65个交易日（约三个月）
    m15_limit: int = 80     # 15分钟线保留最近80根（约5天）
    m5_limit: int = 48 * 2    # 5分钟线保留最近48根（约1天）
    verbose: bool = True  # 是否输出进度信息


@dataclass
class AnalysisError:
    """分析错误"""
    stage: str  # 错误发生的阶段
    message: str
    details: Optional[str] = None


@dataclass
class AnalysisResult:
    """分析结果（包含成功/失败状态）"""
    success: bool
    report: Optional[AnalysisReport] = None
    errors: Optional[List[AnalysisError]] = None
    warnings: Optional[List[FilterWarning]] = None
    
    @classmethod
    def ok(
        cls, 
        report: AnalysisReport, 
        warnings: Optional[List[FilterWarning]] = None
    ) -> "AnalysisResult":
        """创建成功结果"""
        return cls(success=True, report=report, warnings=warnings)
    
    @classmethod
    def fail(cls, errors: List[AnalysisError]) -> "AnalysisResult":
        """创建失败结果"""
        return cls(success=False, errors=errors)


class MarketAnalysisAgent:
    """大盘分析Agent
    
    实现完整的分析流程：
    1. 数据加载
    2. 时间过滤（防止未来数据泄露）
    3. 上下文构建
    4. LLM分析（支撑压力位识别、短期预期、中长期预期）
    5. 结果解析和报告生成
    
    Requirements: 5.1-5.7, 6.1-6.4, 7.1-7.5, 8.1-8.5
    """
    
    def __init__(self, config: AgentConfig):
        """初始化Agent
        
        Args:
            config: Agent配置
        """
        self.config = config
        self.llm_client = LLMClient(config.llm_config)
        self.prompt_engine = PromptEngine(config.template_dir)
        self.context_builder = ContextBuilder(
            max_tokens=config.max_context_tokens,
            daily_limit=config.daily_limit,
            m15_limit=config.m15_limit,
            m5_limit=config.m5_limit,
        )
        self.verbose = config.verbose
    
    def _log(self, message: str, end: str = "\n", flush: bool = True):
        """输出日志信息
        
        Args:
            message: 日志消息
            end: 结束符
            flush: 是否立即刷新
        """
        if self.verbose:
            print(message, end=end, flush=flush)
    
    def _log_step(self, step: int, total: int, description: str):
        """输出步骤信息
        
        Args:
            step: 当前步骤
            total: 总步骤数
            description: 步骤描述
        """
        self._log(f"[{step}/{total}] {description}...")
    
    def _log_done(self, duration: float = None):
        """输出完成信息
        
        Args:
            duration: 耗时（秒）
        """
        if duration is not None:
            self._log(f"  ✓ 完成 ({duration:.1f}s)")
        else:
            self._log(f"  ✓ 完成")
    
    def _log_error(self, message: str):
        """输出错误信息
        
        Args:
            message: 错误消息
        """
        self._log(f"  ✗ 错误: {message}")
    
    def analyze(self, input_data: AnalysisInput) -> AnalysisResult:
        """执行完整分析流程
        
        Args:
            input_data: 分析输入数据
            
        Returns:
            AnalysisResult对象
        """
        errors: List[AnalysisError] = []
        all_warnings: List[FilterWarning] = []
        total_steps = 8
        
        self._log("=" * 50)
        self._log("开始大盘分析...")
        self._log(f"分析日期: {input_data.analysis_date}")
        self._log(f"当前价格: {input_data.current_price:.2f}")
        self._log("=" * 50)
        
        analysis_start = time.time()
        
        # 1. 时间过滤
        self._log_step(1, total_steps, "时间过滤（防止未来数据泄露）")
        step_start = time.time()
        try:
            filtered_input, filter_warnings = self._filter_data(input_data)
            all_warnings.extend(filter_warnings)
            self._log_done(time.time() - step_start)
            if filter_warnings:
                self._log(f"  ⚠ 警告: 过滤了 {len(filter_warnings)} 条未来数据")
        except Exception as e:
            self._log_error(str(e))
            errors.append(AnalysisError(
                stage="time_filter",
                message="时间过滤失败",
                details=str(e)
            ))
            return AnalysisResult.fail(errors)
        
        # 2. 构建上下文
        self._log_step(2, total_steps, "构建LLM上下文")
        step_start = time.time()
        try:
            context = self.context_builder.build_context(filtered_input)
            self._log_done(time.time() - step_start)
            self._log(f"  日线数据: {len(filtered_input.daily_data.data)} 条")
            self._log(f"  15分钟数据: {len(filtered_input.m15_data.data)} 条")
            self._log(f"  5分钟数据: {len(filtered_input.m5_data.data)} 条")
        except Exception as e:
            self._log_error(str(e))
            errors.append(AnalysisError(
                stage="context_build",
                message="上下文构建失败",
                details=str(e)
            ))
            return AnalysisResult.fail(errors)
        
        # 3. LLM分析 - 支撑压力位识别
        self._log_step(3, total_steps, "LLM分析 - 支撑压力位识别")
        step_start = time.time()
        sr_result = self._analyze_support_resistance(context)
        if sr_result is None:
            self._log_error("LLM响应解析失败")
            errors.append(AnalysisError(
                stage="support_resistance",
                message="支撑压力位识别失败",
                details="LLM响应解析失败"
            ))
            return AnalysisResult.fail(errors)
        self._log_done(time.time() - step_start)
        self._log(f"  识别支撑位: {len(sr_result.support_levels)} 个")
        self._log(f"  识别压力位: {len(sr_result.resistance_levels)} 个")
        
        # 4. 价格位置分析
        self._log_step(4, total_steps, "价格位置分析")
        step_start = time.time()
        position_analysis = PriceCalculator.analyze_position(
            input_data.current_price, sr_result
        )
        self._log_done(time.time() - step_start)
        self._log(f"  位置判断: {position_analysis.position_description}")
        
        # 5. LLM分析 - 当日走势分析
        self._log_step(5, total_steps, "LLM分析 - 当日走势分析（多周期复盘）")
        step_start = time.time()
        intraday_analysis = self._analyze_intraday(context)
        if intraday_analysis is None:
            self._log_error("LLM响应解析失败")
            errors.append(AnalysisError(
                stage="intraday_analysis",
                message="当日走势分析失败",
                details="LLM响应解析失败"
            ))
            return AnalysisResult.fail(errors)
        self._log_done(time.time() - step_start)
        self._log(f"  走势类型: {intraday_analysis.pattern_type}")
        self._log(f"  多周期趋势: {intraday_analysis.trend_alignment}")
        self._log(f"  日K形态: {intraday_analysis.daily_candle}")
        
        # 6. LLM分析 - 短期预期
        self._log_step(6, total_steps, "LLM分析 - 短期预期（次日）")
        step_start = time.time()
        short_term = self._analyze_short_term(context, sr_result, position_analysis)
        if short_term is None:
            self._log_error("LLM响应解析失败")
            errors.append(AnalysisError(
                stage="short_term",
                message="短期预期分析失败",
                details="LLM响应解析失败"
            ))
            return AnalysisResult.fail(errors)
        self._log_done(time.time() - step_start)
        self._log(f"  开盘场景: {len(short_term.opening_scenarios)} 个")
        self._log(f"  置信度: {short_term.confidence.value}")
        
        # 7. LLM分析 - 中长期预期
        self._log_step(7, total_steps, "LLM分析 - 中长期预期")
        step_start = time.time()
        long_term = self._analyze_long_term(context, sr_result)
        if long_term is None:
            self._log_error("LLM响应解析失败")
            errors.append(AnalysisError(
                stage="long_term",
                message="中长期预期分析失败",
                details="LLM响应解析失败"
            ))
            return AnalysisResult.fail(errors)
        self._log_done(time.time() - step_start)
        self._log(f"  当前趋势: {long_term.current_trend}")
        self._log(f"  置信度: {long_term.confidence.value}")
        
        # 8. 生成报告
        self._log_step(8, total_steps, "生成分析报告")
        step_start = time.time()
        report = AnalysisReport(
            analysis_time=datetime.now(),
            data_cutoff=context.data_cutoff,
            current_price=input_data.current_price,
            support_resistance=sr_result,
            position_analysis=position_analysis,
            intraday_analysis=intraday_analysis,
            short_term=short_term,
            long_term=long_term,
        )
        self._log_done(time.time() - step_start)
        
        total_time = time.time() - analysis_start
        self._log("=" * 50)
        self._log(f"分析完成！总耗时: {total_time:.1f}s")
        self._log("=" * 50)
        
        return AnalysisResult.ok(report, all_warnings if all_warnings else None)
    
    def _filter_data(
        self, 
        input_data: AnalysisInput
    ) -> tuple[AnalysisInput, List[FilterWarning]]:
        """过滤数据，防止未来数据泄露
        
        Args:
            input_data: 原始输入数据
            
        Returns:
            (过滤后的输入数据, 警告列表)
        """
        time_filter = TimeIsolationFilter(
            cutoff_date=input_data.analysis_date,
            cutoff_time=input_data.analysis_time
        )
        
        all_warnings: List[FilterWarning] = []
        
        # 过滤各周期数据
        daily_result = time_filter.filter_data(input_data.daily_data)
        all_warnings.extend(daily_result.warnings)
        
        m15_result = time_filter.filter_data(input_data.m15_data)
        all_warnings.extend(m15_result.warnings)
        
        m5_result = time_filter.filter_data(input_data.m5_data)
        all_warnings.extend(m5_result.warnings)
        
        # 创建过滤后的输入数据
        filtered_input = AnalysisInput(
            analysis_date=input_data.analysis_date,
            analysis_time=input_data.analysis_time,
            daily_data=daily_result.data,
            m15_data=m15_result.data,
            m5_data=m5_result.data,
            current_price=input_data.current_price,
        )
        
        return filtered_input, all_warnings
    
    def _analyze_support_resistance(
        self, 
        context: MarketContext
    ) -> Optional[SupportResistanceResult]:
        """分析支撑压力位
        
        Args:
            context: 市场上下文
            
        Returns:
            SupportResistanceResult对象，失败返回None
        """
        try:
            # 构建提示词
            system_prompt = self.prompt_engine.get_system_prompt()
            user_prompt = self.prompt_engine.build_support_resistance_prompt(context)
            
            # 调用LLM
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ]
            
            self._log("  正在调用LLM（流式输出）...")
            self._log("  " + "=" * 60)
            response = self.llm_client.chat_stream(messages)
            self._log("  " + "=" * 60)
            self._log("  ✓ LLM响应完成")
            
            # 解析响应
            result = LLMResponseParser.parse_support_resistance(response.content)
            if result is None:
                self._log(f"  ⚠ LLM响应解析失败，原始响应:")
                self._log(f"  {response.content[:500]}..." if len(response.content) > 500 else f"  {response.content}")
            return result
            
        except LLMError as e:
            self._log(f"  ⚠ LLM调用错误: {e}")
            return None
        except Exception as e:
            self._log(f"  ⚠ 未知错误: {e}")
            return None
    
    def _analyze_short_term(
        self,
        context: MarketContext,
        sr_result: SupportResistanceResult,
        position_analysis: PositionAnalysis
    ) -> Optional[ShortTermExpectation]:
        """分析短期预期
        
        Args:
            context: 市场上下文
            sr_result: 支撑压力位结果
            position_analysis: 位置分析结果
            
        Returns:
            ShortTermExpectation对象，失败返回None
        """
        try:
            # 构建提示词
            system_prompt = self.prompt_engine.get_system_prompt()
            user_prompt = self.prompt_engine.build_short_term_prompt(
                context,
                sr_result.to_dict(),
                position_analysis.to_dict()
            )
            
            # 调用LLM
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ]
            
            self._log("  正在调用LLM（流式输出）...")
            self._log("  " + "=" * 60)
            response = self.llm_client.chat_stream(messages)
            self._log("  " + "=" * 60)
            self._log("  ✓ LLM响应完成")
            
            # 解析响应
            result = LLMResponseParser.parse_short_term(response.content)
            if result is None:
                self._log(f"  ⚠ LLM响应解析失败，原始响应:")
                self._log(f"  {response.content[:500]}..." if len(response.content) > 500 else f"  {response.content}")
            return result
            
        except LLMError as e:
            self._log(f"  ⚠ LLM调用错误: {e}")
            return None
        except Exception as e:
            self._log(f"  ⚠ 未知错误: {e}")
            return None
    
    def _analyze_long_term(
        self,
        context: MarketContext,
        sr_result: SupportResistanceResult
    ) -> Optional[LongTermExpectation]:
        """分析中长期预期
        
        Args:
            context: 市场上下文
            sr_result: 支撑压力位结果
            
        Returns:
            LongTermExpectation对象，失败返回None
        """
        try:
            # 构建提示词
            system_prompt = self.prompt_engine.get_system_prompt()
            user_prompt = self.prompt_engine.build_long_term_prompt(
                context,
                sr_result.to_dict()
            )
            
            # 调用LLM
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ]
            
            self._log("  正在调用LLM（流式输出）...")
            self._log("  " + "=" * 60)
            response = self.llm_client.chat_stream(messages)
            self._log("  " + "=" * 60)
            self._log("  ✓ LLM响应完成")
            
            # 解析响应
            result = LLMResponseParser.parse_long_term(response.content)
            if result is None:
                self._log(f"  ⚠ LLM响应解析失败，原始响应:")
                self._log(f"  {response.content[:500]}..." if len(response.content) > 500 else f"  {response.content}")
            return result
            
        except LLMError as e:
            self._log(f"  ⚠ LLM调用错误: {e}")
            return None
        except Exception as e:
            self._log(f"  ⚠ 未知错误: {e}")
            return None
    
    def _analyze_intraday(
        self,
        context: MarketContext
    ) -> Optional[IntradayAnalysis]:
        """分析当日走势
        
        基于5分钟K线数据分析当日走势。
        
        Args:
            context: 市场上下文
            
        Returns:
            IntradayAnalysis对象，失败返回None
        """
        try:
            # 构建提示词
            system_prompt = self.prompt_engine.get_system_prompt()
            user_prompt = self.prompt_engine.build_intraday_analysis_prompt(context)
            
            # 调用LLM
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ]
            
            self._log("  正在调用LLM（流式输出）...")
            self._log("  " + "=" * 60)
            response = self.llm_client.chat_stream(messages)
            self._log("  " + "=" * 60)
            self._log("  ✓ LLM响应完成")
            
            # 解析响应
            result = LLMResponseParser.parse_intraday_analysis(response.content)
            if result is None:
                self._log(f"  ⚠ LLM响应解析失败，原始响应:")
                self._log(f"  {response.content[:500]}..." if len(response.content) > 500 else f"  {response.content}")
            return result
            
        except LLMError as e:
            self._log(f"  ⚠ LLM调用错误: {e}")
            return None
        except Exception as e:
            self._log(f"  ⚠ 未知错误: {e}")
            return None


def create_agent(
    api_key: str,
    model: str = "glm-4",
    provider: str = "zhipu",
    base_url: Optional[str] = None,
    template_dir: str = "prompts/",
    verbose: bool = True,
    **kwargs
) -> MarketAnalysisAgent:
    """创建分析Agent的便捷函数
    
    Args:
        api_key: API密钥
        model: 模型名称
        provider: 提供商
        base_url: 自定义API地址
        template_dir: 提示词模板目录
        verbose: 是否输出进度信息
        **kwargs: 其他LLM配置参数
        
    Returns:
        MarketAnalysisAgent实例
    """
    llm_config = LLMConfig(
        api_key=api_key,
        model=model,
        provider=provider,
        base_url=base_url,
        **kwargs
    )
    
    agent_config = AgentConfig(
        llm_config=llm_config,
        template_dir=template_dir,
        verbose=verbose,
    )
    
    return MarketAnalysisAgent(agent_config)
