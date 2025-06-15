"""
Live Trading Infrastructure

A comprehensive and modular live trading system that supports:

Features:
- Multi-strategy portfolio management
- Real-time data ingestion from multiple sources
- Dynamic strategy loading and signal extraction
- Paper and live trading execution via extensible broker factory
- Support for various data granularities
- Extensive logging and error handling

Components:
- LiveTradingSystem: Main orchestrator
- MultiStrategyRunner: Manages multiple trading strategies
- Data Sources: Polygon, CoinMarketCap, Demo data (with factory pattern)
- Broker Factory: Unified broker interface supporting multiple platforms
- Engine Factory: Unified engine interface supporting multiple trading frameworks
- Data Provider Factory: Standardized data provider interface
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

# Data Provider Factory imports - new standardized interface
from .data import (
    DataProviderFactory, DataProviderConfig, DataProviderInfo,
    detect_provider_type, auto_create_provider, get_supported_providers,
    validate_provider_credentials, list_provider_features,
    setup_data_ingestion, BaseDataIngestion,
    PolygonDataIngestion, CoinMarketCapDataIngestion, TestDataIngestion, MarketData
)

# Import create_data_source from provider factory for backward compatibility
from .data.provider_factory import create_data_source

# Engine Factory imports - standardized engine interface
from .engines import (
    TradingEngine, EngineFactory, detect_engine_type, auto_create_engine,
    get_supported_engines, validate_strategy_compatibility
)

from .core.signal_extractor import LiveSignalExtractor, SignalExtractorStrategy, TradingSignal, SignalType
from .utils.config import load_config, DataConfig, TradingConfig

# Broker Factory imports - unified broker interface
try:
    from .brokers import (
        BaseBroker, BrokerConfig, BrokerInfo, AccountInfo, Position, OrderResult,
        BrokerFactory, detect_broker_type, get_supported_brokers, auto_create_broker,
        validate_broker_credentials, AlpacaBroker
    )
except ImportError as e:
    raise ImportError(
        "Broker dependencies are required but could not be imported. "
        "Please reinstall the package: pip install stratequeue"
    ) from e

from .core.strategy_loader import StrategyLoader
from .live_system import LiveTradingSystem
from .multi_strategy import MultiStrategyRunner
from .core.portfolio_manager import SimplePortfolioManager
from .utils.mocks import Order
from .cli.cli import main as cli_main

__all__ = [
    # Data Provider Factory - new standardized interface
    "DataProviderFactory",
    "DataProviderConfig", 
    "DataProviderInfo",
    "detect_provider_type",
    "auto_create_provider",
    "get_supported_providers",
    "validate_provider_credentials",
    "list_provider_features",
    
    # Data functions
    "setup_data_ingestion",
    "create_data_source",
    "BaseDataIngestion",
    "PolygonDataIngestion", 
    "CoinMarketCapDataIngestion",
    "TestDataIngestion",
    "MarketData",
    
    # Engine Factory interface
    "TradingEngine",
    "EngineFactory",
    "detect_engine_type",
    "auto_create_engine",
    "get_supported_engines",
    "validate_strategy_compatibility",
    
    # Signal processing
    "LiveSignalExtractor",
    "SignalExtractorStrategy",
    "TradingSignal",
    "SignalType",
    
    # Configuration
    "load_config",
    "DataConfig",
    "TradingConfig",
    
    # Broker factory interface
    "BaseBroker",
    "BrokerConfig", 
    "BrokerInfo",
    "AccountInfo",
    "Position",
    "OrderResult",
    "BrokerFactory",
    "detect_broker_type",
    "get_supported_brokers", 
    "auto_create_broker",
    "validate_broker_credentials",
    "AlpacaBroker",
    
    # Core components
    "StrategyLoader",
    "LiveTradingSystem",
    "MultiStrategyRunner",
    "SimplePortfolioManager",
    "Order",
    "cli_main"
] 