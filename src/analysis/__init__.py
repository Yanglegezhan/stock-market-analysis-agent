"""分析层模块

包含上下文构建、提示词引擎和价格计算功能。
"""

from src.analysis.calculator import (
    PriceCalculator,
    DistanceResult,
    calculate_price_distance,
    analyze_price_position,
)
from src.analysis.context_builder import (
    ContextBuilder,
    MarketContext,
    build_market_context,
)
from src.analysis.prompt_engine import (
    PromptEngine,
    PromptTemplate,
    FewShotExample,
    create_prompt_engine,
)

__all__ = [
    # calculator
    "PriceCalculator",
    "DistanceResult",
    "calculate_price_distance",
    "analyze_price_position",
    # context_builder
    "ContextBuilder",
    "MarketContext",
    "build_market_context",
    # prompt_engine
    "PromptEngine",
    "PromptTemplate",
    "FewShotExample",
    "create_prompt_engine",
]
