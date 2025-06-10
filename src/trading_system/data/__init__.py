"""
Data module for trading system

Handles all data ingestion, processing, and source management.
"""

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
    "setup_data_ingestion",
    "create_data_source", 
    "list_supported_granularities",
    "get_default_granularity",
    "MinimalSignalGenerator",
    "BaseDataIngestion",
    "MarketData",
    "PolygonDataIngestion", 
    "CoinMarketCapDataIngestion",
    "TestDataIngestion"
] 