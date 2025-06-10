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
    setup_data_ingestion, create_data_source, BaseDataIngestion,
    PolygonDataIngestion, CoinMarketCapDataIngestion, TestDataIngestion, MarketData
)

# Engine Factory imports - standardized engine interface
from .engines import (
    TradingEngine, EngineFactory, detect_engine_type, auto_create_engine,
    get_supported_engines, validate_strategy_compatibility
)

from .core.signal_extractor import LiveSignalExtractor, SignalExtractorStrategy, TradingSignal, SignalType
from .utils.config import load_config, DataConfig, TradingConfig

# Statistics tracking
from .statistics import StatisticsManager, PnLTracker, WinLossTracker, BaseTracker

# Broker Factory imports - unified broker interface
try:
    from .brokers import (
        BaseBroker, BrokerConfig, BrokerInfo, AccountInfo, Position, OrderResult,
        BrokerFactory, detect_broker_type, get_supported_brokers, auto_create_broker,
        validate_broker_credentials, AlpacaBroker
    )
except ImportError:
    # Create dummy classes if broker dependencies are not available
    class BaseBroker:
        def __init__(self, *args, **kwargs):
            raise ImportError("Broker dependencies not installed. Install with: pip install stratequeue[trading]")
    
    class BrokerConfig:
        def __init__(self, *args, **kwargs):
            raise ImportError("Broker dependencies not installed. Install with: pip install stratequeue[trading]")
    
    class BrokerInfo:
        def __init__(self, *args, **kwargs):
            raise ImportError("Broker dependencies not installed. Install with: pip install stratequeue[trading]")
    
    class AccountInfo:
        def __init__(self, *args, **kwargs):
            raise ImportError("Broker dependencies not installed. Install with: pip install stratequeue[trading]")
    
    class Position:
        def __init__(self, *args, **kwargs):
            raise ImportError("Broker dependencies not installed. Install with: pip install stratequeue[trading]")
    
    class OrderResult:
        def __init__(self, *args, **kwargs):
            raise ImportError("Broker dependencies not installed. Install with: pip install stratequeue[trading]")
    
    class BrokerFactory:
        @staticmethod
        def create_broker(*args, **kwargs):
            raise ImportError("Broker dependencies not installed. Install with: pip install stratequeue[trading]")
        
        @staticmethod 
        def get_supported_brokers(*args, **kwargs):
            raise ImportError("Broker dependencies not installed. Install with: pip install stratequeue[trading]")
    
    class AlpacaBroker:
        def __init__(self, *args, **kwargs):
            raise ImportError("Broker dependencies not installed. Install with: pip install stratequeue[trading]")
    
    def detect_broker_type(*args, **kwargs):
        raise ImportError("Broker dependencies not installed. Install with: pip install stratequeue[trading]")
    
    def get_supported_brokers(*args, **kwargs):
        raise ImportError("Broker dependencies not installed. Install with: pip install stratequeue[trading]")
    
    def auto_create_broker(*args, **kwargs):
        raise ImportError("Broker dependencies not installed. Install with: pip install stratequeue[trading]")
    
    def validate_broker_credentials(*args, **kwargs):
        raise ImportError("Broker dependencies not installed. Install with: pip install stratequeue[trading]")

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
    
    # Backward compatibility data functions
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
    
    # Statistics tracking
    "StatisticsManager",
    "WinLossTracker",
    "PnLTracker",
    "BaseTracker",
    
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