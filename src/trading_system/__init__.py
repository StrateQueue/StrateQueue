"""
Live Trading System Package

A scalable live trading infrastructure that converts backtesting.py strategies
into real-time signal generators with support for multiple data sources.
"""

from .data_ingestion import setup_data_ingestion
from .data_sources import PolygonDataIngestion, CoinMarketCapDataIngestion, TestDataIngestion, MarketData
from .signal_extractor import LiveSignalExtractor, SignalExtractorStrategy, TradingSignal, SignalType
from .config import load_config, DataConfig, TradingConfig
from .alpaca_execution import AlpacaExecutor, AlpacaConfig, create_alpaca_executor_from_env, normalize_crypto_symbol
from .strategy_loader import StrategyLoader
from .live_trading_system import LiveTradingSystem
from .mocks import Order
from .cli import main as cli_main

__version__ = "0.1.0"
__all__ = [
    "setup_data_ingestion",
    "PolygonDataIngestion", 
    "CoinMarketCapDataIngestion",
    "TestDataIngestion",
    "MarketData",
    "LiveSignalExtractor",
    "SignalExtractorStrategy",
    "TradingSignal",
    "SignalType",
    "load_config",
    "DataConfig",
    "TradingConfig",
    "AlpacaExecutor",
    "AlpacaConfig",
    "create_alpaca_executor_from_env",
    "normalize_crypto_symbol",
    "StrategyLoader",
    "LiveTradingSystem",
    "Order",
    "cli_main"
] 