"""
Abstract Base Classes for Trading Engines

Defines the common interface that all trading engines must implement.
This allows different trading frameworks (backtesting.py, Zipline, etc.)
to be used interchangeably in the live trading system.
"""

import inspect
import importlib.util
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from types import ModuleType

import pandas as pd

from ..core.signal_extractor import TradingSignal

logger = logging.getLogger(__name__)


@dataclass
class EngineInfo:
    """Information about a trading engine"""

    name: str
    version: str
    supported_features: dict[str, bool]
    description: str


def load_module_from_path(path: str, name: str = "strategy_module") -> ModuleType:
    """
    Load a Python module from an arbitrary file path.
    
    Args:
        path: Path to the Python file
        name: Name to give the loaded module
        
    Returns:
        Loaded module object
    """
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EngineStrategy(ABC):
    """
    Abstract wrapper for strategy objects from different engines.
    Each engine implementation will provide a concrete subclass.
    """

    # Subclasses can override this to skip specific attributes during parameter collection
    _skip_attrs: set[str] = set()

    def __init__(self, strategy_class: type, strategy_params: dict[str, Any] = None):
        self.strategy_class = strategy_class
        self.strategy_params = strategy_params or {}
        self.strategy_instance = None

    @abstractmethod
    def get_lookback_period(self) -> int:
        """Get the minimum number of bars required by this strategy"""
        pass

    def get_strategy_name(self) -> str:
        """Get a human-readable name for this strategy"""
        return self.strategy_class.__name__

    def get_parameters(self) -> dict[str, Any]:
        """Get strategy parameters"""
        params = {}

        # Extract class-level parameters for class-based strategies
        if inspect.isclass(self.strategy_class):
            for attr_name in dir(self.strategy_class):
                if (
                    not attr_name.startswith("_")
                    and not callable(getattr(self.strategy_class, attr_name, None))
                    and attr_name not in self._skip_attrs
                ):
                    try:
                        params[attr_name] = getattr(self.strategy_class, attr_name)
                    except (AttributeError, TypeError):
                        # Skip attributes that can't be retrieved
                        pass

        # Add strategy_params passed to constructor (these override class-level params)
        params.update(self.strategy_params)

        return params


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
    def create_signal_extractor(
        self, engine_strategy: EngineStrategy, **kwargs
    ) -> EngineSignalExtractor:
        """
        Create a signal extractor for the given strategy

        Args:
            engine_strategy: The strategy to create an extractor for
            **kwargs: Additional parameters for the signal extractor

        Returns:
            EngineSignalExtractor instance
        """
        pass

    def validate_strategy_file(self, strategy_path: str) -> bool:
        """
        Check if a strategy file is compatible with this engine

        Args:
            strategy_path: Path to the strategy file

        Returns:
            True if the file is compatible with this engine
        """
        try:
            self.load_strategy_from_file(strategy_path)
            return True
        except Exception as e:
            logger.debug(f"Strategy validation failed for {self.__class__.__name__}: {e}")
            return False

    @staticmethod
    def dependencies_available() -> bool:
        """
        Check if this engine's dependencies are available.
        
        Returns:
            True if all required dependencies are installed
        """
        return True  # Default implementation - engines can override
