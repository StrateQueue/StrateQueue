"""
Data module for trading system

Handles all data ingestion, processing, and source management.
Now includes standardized factory pattern for data providers.
"""

# Import factory system - new standardized approach
from .provider_factory import (
    DataProviderFactory,
    DataProviderConfig,
    DataProviderInfo,
    detect_provider_type,
    auto_create_provider,
    get_supported_providers,
    validate_provider_credentials,
    list_provider_features
)

# Import backward compatibility functions
from .ingestion import (
    setup_data_ingestion, 
    create_data_source,
    list_supported_granularities,
    get_default_granularity,
    MinimalSignalGenerator
)

from .sources import (
    BaseDataIngestion,
    MarketData, 
    PolygonDataIngestion,
    CoinMarketCapDataIngestion,
    TestDataIngestion
)

__all__ = [
    # New factory system
    "DataProviderFactory",
    "DataProviderConfig", 
    "DataProviderInfo",
    "detect_provider_type",
    "auto_create_provider",
    "get_supported_providers",
    "validate_provider_credentials",
    "list_provider_features",
    
    # Backward compatibility functions
    "setup_data_ingestion",
    "create_data_source", 
    "list_supported_granularities",
    "get_default_granularity",
    "MinimalSignalGenerator",
    
    # Base classes and data structures
    "BaseDataIngestion",
    "MarketData",
    "PolygonDataIngestion", 
    "CoinMarketCapDataIngestion",
    "TestDataIngestion"
] 