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

from .base import TradingEngine, EngineStrategy, EngineSignalExtractor
from .engine_factory import EngineFactory, detect_engine_type, get_supported_engines, auto_create_engine, validate_strategy_compatibility
from .backtesting_engine import BacktestingEngine

__all__ = [
    'TradingEngine',
    'EngineStrategy', 
    'EngineSignalExtractor',
    'EngineFactory',
    'detect_engine_type',
    'get_supported_engines',
    'auto_create_engine',
    'validate_strategy_compatibility',
    'BacktestingEngine'
] 