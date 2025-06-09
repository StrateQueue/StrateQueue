"""
Data Sources Package

Contains modular data ingestion classes for different data providers.
"""

from .base import BaseDataIngestion, MarketData
from .polygon import PolygonDataIngestion  
from .coinmarketcap import CoinMarketCapDataIngestion
from .demo import TestDataIngestion

__all__ = [
    "BaseDataIngestion",
    "MarketData", 
    "PolygonDataIngestion",
    "CoinMarketCapDataIngestion", 
    "TestDataIngestion"
] 