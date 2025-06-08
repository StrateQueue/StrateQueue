"""
Data module for trading system

Handles all data ingestion, processing, and source management.
Now includes standardized factory pattern for data providers.
"""

# Import factory system - standardized approach
from .ingestion import IngestionInit, MinimalSignalGenerator, setup_data_ingestion
from .provider_factory import (
    DataProviderConfig,
    DataProviderFactory,
    DataProviderInfo,
    auto_create_provider,
    detect_provider_type,
    get_supported_providers,
    list_provider_features,
    validate_provider_credentials,
)
from .sources import (
    BaseDataIngestion,
    CoinMarketCapDataIngestion,
    MarketData,
    PolygonDataIngestion,
    TestDataIngestion,
)

__all__ = [
    # Factory system
    "DataProviderFactory",
    "DataProviderConfig",
    "DataProviderInfo",
    "detect_provider_type",
    "auto_create_provider",
    "get_supported_providers",
    "validate_provider_credentials",
    "list_provider_features",
    # Legacy functions (maintained for compatibility)
    "setup_data_ingestion",
    "IngestionInit",
    "MinimalSignalGenerator",
    # Base classes and data structures
    "BaseDataIngestion",
    "MarketData",
    "PolygonDataIngestion",
    "CoinMarketCapDataIngestion",
    "TestDataIngestion",
]
