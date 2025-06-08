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
    from StrateQueue import cli_main

    # Single strategy mode
    cli_main(['--strategy', 'sma.py', '--symbol', 'AAPL'])

    # Multi-strategy mode
    cli_main(['--strategy', 'strategy1.py,strategy2.py', '--symbol', 'AAPL,MSFT'])
"""

__version__ = "0.0.1"
__author__ = "Trading System Contributors"

# Data Provider Factory imports - new standardized interface
from .core.signal_extractor import (
    LiveSignalExtractor,
    SignalExtractorStrategy,
    SignalType,
    TradingSignal,
)
from .data import (
    BaseDataIngestion,
    CoinMarketCapDataIngestion,
    DataProviderConfig,
    DataProviderFactory,
    DataProviderInfo,
    MarketData,
    PolygonDataIngestion,
    TestDataIngestion,
    auto_create_provider,
    detect_provider_type,
    get_supported_providers,
    list_provider_features,
    setup_data_ingestion,
    validate_provider_credentials,
)
from .data.provider_factory import create_data_source

# Engine Factory imports - standardized engine interface
from .engines import (
    EngineFactory,
    TradingEngine,
    auto_create_engine,
    detect_engine_type,
    get_supported_engines,
    validate_strategy_compatibility,
)
from .utils.system_config import DataConfig, TradingConfig, load_config

# Broker Factory imports - unified broker interface
try:
    from .brokers import (
        AccountInfo,
        AlpacaBroker,
        BaseBroker,
        BrokerConfig,
        BrokerFactory,
        BrokerInfo,
        OrderResult,
        Position,
        auto_create_broker,
        detect_broker_type,
        get_supported_brokers,
        validate_broker_credentials,
    )
except ImportError as e:
    raise ImportError(
        "Broker dependencies are required but could not be imported. "
        "Please reinstall the package: pip install stratequeue"
    ) from e

# CLI is available via console script entry point
# No need to import here - reduces import dependencies
from .core.portfolio_manager import SimplePortfolioManager
from .core.strategy_loader import StrategyLoader
from .live_system import LiveTradingSystem
from .multi_strategy import MultiStrategyRunner

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
# CLI available via console script: stratequeue
]
