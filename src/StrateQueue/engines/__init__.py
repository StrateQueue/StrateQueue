"""
Trading Engine Abstraction Layer

This package provides a unified interface for different trading engines (backtesting.py, Zipline, etc.)
allowing strategies from different frameworks to be used with the same live trading infrastructure.

Main Components:
- TradingEngine: Abstract base class for trading engines
- EngineStrategy: Generic strategy wrapper interface
- EngineSignalExtractor: Abstract signal extractor interface
- EngineFactory: Factory for creating engines and detecting engine types
"""

from .engine_base import EngineSignalExtractor, EngineStrategy, TradingEngine
from .engine_factory import (
    EngineFactory,
    auto_create_engine,
    detect_engine_type,
    get_supported_engines,
    get_all_known_engines,
    get_unavailable_engines,
    validate_strategy_compatibility,
)

# Conditional imports for optional engines
__all__ = [
    "TradingEngine",
    "EngineStrategy", 
    "EngineSignalExtractor",
    "EngineFactory",
    "detect_engine_type",
    "get_supported_engines",
    "get_all_known_engines",
    "get_unavailable_engines",
    "auto_create_engine",
    "validate_strategy_compatibility",
]

# Try to import backtesting engine if available
try:
    from .backtesting_engine import BacktestingEngine
    __all__.append("BacktestingEngine")
except ImportError:
    # backtesting.py not available - will be handled by factory
    pass

# Try to import VectorBT engine if available  
try:
    from .vectorbt_engine import VectorBTEngine
    __all__.append("VectorBTEngine")
except ImportError:
    # VectorBT not available - will be handled by factory
    pass
