"""
Abstract Base Classes for Trading Engines

Defines the common interface that all trading engines must implement.
This allows different trading frameworks (backtesting.py, Zipline, etc.) 
to be used interchangeably in the live trading system.
"""

import pandas as pd
from abc import ABC, abstractmethod
from typing import Type, Optional, Dict, Any
from dataclasses import dataclass

from ..core.signal_extractor import TradingSignal


@dataclass
class EngineInfo:
    """Information about a trading engine"""
    name: str
    version: str
    supported_features: Dict[str, bool]
    description: str


class EngineStrategy(ABC):
    """
    Abstract wrapper for strategy objects from different engines.
    Each engine implementation will provide a concrete subclass.
    """
    
    def __init__(self, strategy_class: Type, strategy_params: Dict[str, Any] = None):
        self.strategy_class = strategy_class
        self.strategy_params = strategy_params or {}
        self.strategy_instance = None
    
    @abstractmethod
    def get_lookback_period(self) -> int:
        """Get the minimum number of bars required by this strategy"""
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        """Get a human-readable name for this strategy"""
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Get strategy parameters"""
        pass


class EngineSignalExtractor(ABC):
    """
    Abstract base class for signal extractors.
    Each engine will implement this to convert strategy logic into TradingSignal objects.
    """
    
    def __init__(self, engine_strategy: EngineStrategy):
        self.engine_strategy = engine_strategy
        self.last_signal = None
    
    @abstractmethod
    def extract_signal(self, historical_data: pd.DataFrame) -> TradingSignal:
        """
        Extract trading signal from historical data using the strategy
        
        Args:
            historical_data: DataFrame with OHLCV data indexed by timestamp
            
        Returns:
            TradingSignal object with current signal
        """
        pass
    
    @abstractmethod
    def get_minimum_bars_required(self) -> int:
        """Get minimum number of bars needed for signal extraction"""
        pass


class TradingEngine(ABC):
    """
    Abstract base class for trading engines.
    Each trading framework (backtesting.py, Zipline, etc.) will implement this interface.
    """
    
    @abstractmethod
    def get_engine_info(self) -> EngineInfo:
        """Get information about this engine"""
        pass
    
    @abstractmethod
    def load_strategy_from_file(self, strategy_path: str) -> EngineStrategy:
        """
        Load a strategy from a file
        
        Args:
            strategy_path: Path to the strategy file
            
        Returns:
            EngineStrategy wrapper for the loaded strategy
        """
        pass
    
    @abstractmethod
    def create_signal_extractor(self, engine_strategy: EngineStrategy, 
                              **kwargs) -> EngineSignalExtractor:
        """
        Create a signal extractor for the given strategy
        
        Args:
            engine_strategy: The strategy to create an extractor for
            **kwargs: Additional parameters for the signal extractor
            
        Returns:
            EngineSignalExtractor instance
        """
        pass
    
    @abstractmethod
    def validate_strategy_file(self, strategy_path: str) -> bool:
        """
        Check if a strategy file is compatible with this engine
        
        Args:
            strategy_path: Path to the strategy file
            
        Returns:
            True if the file is compatible with this engine
        """
        pass
    
    @abstractmethod
    def calculate_lookback_period(self, strategy_path: str, 
                                default_lookback: int = 50) -> int:
        """
        Calculate the required lookback period for a strategy
        
        Args:
            strategy_path: Path to the strategy file
            default_lookback: Default lookback to use if calculation fails
            
        Returns:
            Required lookback period in bars
        """
        pass 