"""
Live Trading Infrastructure

A comprehensive and modular live trading system that supports:

Features:
- Multi-strategy portfolio management
- Real-time data ingestion from multiple sources
- Dynamic strategy loading and signal extraction
- Paper and live trading execution via Alpaca
- Support for various data granularities
- Extensive logging and error handling

Components:
- LiveTradingSystem: Main orchestrator
- MultiStrategyRunner: Manages multiple trading strategies
- Data Sources: Polygon, CoinMarketCap, Demo data
- AlpacaExecution: Trading execution layer
- SignalExtractor: Strategy signal processing
- CLI: Command-line interface

Usage:
    from trading_system import cli_main
    
    # Single strategy mode
    cli_main(['--strategy', 'sma.py', '--symbols', 'AAPL'])
    
    # Multi-strategy mode
    cli_main(['--strategies', 'strategies.txt', '--symbols', 'AAPL,MSFT'])
"""

__version__ = "1.0.0"
__author__ = "Trading System Contributors"

from .data_ingestion import setup_data_ingestion
from .data_sources import PolygonDataIngestion, CoinMarketCapDataIngestion, TestDataIngestion, MarketData
from .signal_extractor import LiveSignalExtractor, SignalExtractorStrategy, TradingSignal, SignalType
from .config import load_config, DataConfig, TradingConfig
from .alpaca import AlpacaExecutor, AlpacaConfig, create_alpaca_executor_from_env, normalize_crypto_symbol
from .strategy_loader import StrategyLoader
from .live_system import LiveTradingSystem
from .multi_strategy import MultiStrategyRunner
from .simple_portfolio_manager import SimplePortfolioManager
from .mocks import Order
from .cli import main as cli_main

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
    "MultiStrategyRunner",
    "SimplePortfolioManager",
    "Order",
    "cli_main"
] 