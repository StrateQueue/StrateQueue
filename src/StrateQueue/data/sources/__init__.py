"""
Data Sources Package

Contains modular data ingestion classes for different data providers.
"""

from .coinmarketcap import CoinMarketCapDataIngestion
from .data_source_base import BaseDataIngestion, MarketData
from .demo import TestDataIngestion
from .polygon import PolygonDataIngestion

__all__ = [
    "BaseDataIngestion",
    "MarketData",
    "PolygonDataIngestion",
    "CoinMarketCapDataIngestion",
    "TestDataIngestion",
]
