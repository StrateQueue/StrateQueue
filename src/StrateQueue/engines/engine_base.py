"""
Abstract Base Classes for Trading Engines

Defines the common interface that all trading engines must implement.
This allows different trading frameworks (backtesting.py, Zipline, etc.)
to be used interchangeably in the live trading system.
"""

import inspect
import importlib.util
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Callable
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

    def __getattr__(self, item: str):
        """Fallback to supported_features for feature flags (e.g. vectorized_backtesting)"""
        if item in self.supported_features:
            return self.supported_features[item]
        raise AttributeError(f"{item} not found in EngineInfo")


def load_module_from_path(path: str, name: str = "strategy_module") -> ModuleType:
    """
    Load a Python module from an arbitrary file path.
    
    Args:
        path: Path to the Python file
        name: Name to give the loaded module
        
    Returns:
        Loaded module object
        
    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Strategy file not found: {path}")
        
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def granularity_to_pandas_freq(granularity: str) -> str:
    """
    Convert StrateQueue granularity format to pandas/VectorBT frequency string.
    
    This is used by engines and data providers for consistent frequency mapping.
    
    Args:
        granularity: Granularity string like '1m', '5m', '1h', '1d'
        
    Returns:
        Pandas frequency string like '1T', '5T', '1H', '1D'
    """
    # Map common granularities to pandas frequency strings
    granularity_map = {
        '1s': '1S',      # 1 second
        '5s': '5S',      # 5 seconds
        '10s': '10S',    # 10 seconds
        '30s': '30S',    # 30 seconds
        '1m': '1T',      # 1 minute (T for minute to avoid confusion with month)
        '1min': '1T',    # 1 minute
        '5m': '5T',      # 5 minutes
        '5min': '5T',    # 5 minutes
        '15m': '15T',    # 15 minutes
        '15min': '15T',  # 15 minutes
        '30m': '30T',    # 30 minutes
        '30min': '30T',  # 30 minutes
        '1h': '1H',      # 1 hour
        '1hour': '1H',   # 1 hour
        '4h': '4H',      # 4 hours
        '4hour': '4H',   # 4 hours
        '1d': '1D',      # 1 day
        '1day': '1D',    # 1 day
        '1w': '1W',      # 1 week
        '1week': '1W',   # 1 week
    }
    
    # Return mapped frequency or default to the granularity as-is
    return granularity_map.get(granularity.lower(), granularity)


def find_strategy_candidates(module: ModuleType, is_valid_strategy: Callable[[str, Any], bool]) -> Dict[str, Any]:
    """
    Find strategy candidates in a loaded module using a validation function.
    
    This removes the boilerplate of walking inspect.getmembers() in every engine.
    
    Args:
        module: Loaded Python module
        is_valid_strategy: Function that takes (name, obj) and returns True if it's a valid strategy
        
    Returns:
        Dictionary mapping strategy names to strategy objects
    """
    candidates = {}
    for name, obj in inspect.getmembers(module):
        if is_valid_strategy(name, obj):
            candidates[name] = obj
    return candidates


def select_single_strategy(candidates: Dict[str, Any], strategy_path: str, 
                         explicit_marker: str = None) -> tuple[str, Any]:
    """
    Select a single strategy from candidates, handling multiple strategies gracefully.
    
    Args:
        candidates: Dictionary of strategy name -> strategy object
        strategy_path: Path to strategy file (for error messages)
        explicit_marker: Optional attribute name that marks the preferred strategy
        
    Returns:
        Tuple of (strategy_name, strategy_object)
        
    Raises:
        ValueError: If no strategies found or ambiguous selection
    """
    if not candidates:
        raise ValueError(f"No valid strategy found in {strategy_path}")
    
    # Check for explicit marker first (e.g., __vbt_strategy__ = True)
    if explicit_marker:
        marked_strategies = {
            name: obj for name, obj in candidates.items()
            if hasattr(obj, explicit_marker) and getattr(obj, explicit_marker, False)
        }
        
        if marked_strategies:
            if len(marked_strategies) == 1:
                # Exactly one explicitly marked strategy
                strategy_name, strategy_obj = next(iter(marked_strategies.items()))
                logger.info(f"Using explicitly marked strategy: {strategy_name}")
                return strategy_name, strategy_obj
            else:
                # Multiple marked strategies - this is an error
                marked_names = list(marked_strategies.keys())
                raise ValueError(
                    f"Multiple strategies marked with {explicit_marker} = True in {strategy_path}: {marked_names}.\n"
                    "Only one strategy should be marked per file."
                )
    
    # No explicit markers - check for single implicit candidate
    if len(candidates) == 1:
        # Exactly one candidate - use it
        strategy_name, strategy_obj = next(iter(candidates.items()))
        logger.info(f"Using single strategy found: {strategy_name}")
        return strategy_name, strategy_obj
    else:
        # Multiple candidates without explicit selection - fail fast
        candidate_names = list(candidates.keys())
        marker_hint = f"  • Add  {explicit_marker} = True  to exactly one of them." if explicit_marker else ""
        raise ValueError(
            f"Multiple strategies detected in {strategy_path}: {candidate_names}.\n"
            "Either:\n"
            f"  • Keep only one strategy per file, or\n"
            f"{marker_hint}"
        )


def build_engine_info(name: str, lib_version: str, description: str = None, **feature_flags) -> EngineInfo:
    """
    Build EngineInfo with default features and custom overrides.
    
    Args:
        name: Engine name
        lib_version: Library version string
        description: Optional description (defaults to generic message)
        **feature_flags: Feature overrides (e.g., vectorized_backtesting=True)
        
    Returns:
        EngineInfo instance
    """
    # Default features that most engines support
    default_features = {
        "signal_extraction": True,
        "live_trading": True,
        "multi_strategy": True,
        "limit_orders": True,
        "stop_orders": True,
    }
    
    # Update with engine-specific features
    default_features.update(feature_flags)
    
    # Default description if none provided
    if description is None:
        description = f"Trading engine implementation for {name}"
    
    return EngineInfo(
        name=name,
        version=lib_version,
        supported_features=default_features,
        description=description
    )


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

    def get_minimum_bars_required(self) -> int:
        """
        Get minimum number of bars needed for signal extraction.
        
        Default implementation combines min_bars_required and engine strategy lookback.
        """
        min_bars = getattr(self, 'min_bars_required', 2)
        return max(min_bars, self.engine_strategy.get_lookback_period())


class TradingEngine(ABC):
    """
    Abstract base class for trading engines.
    Each trading framework (backtesting.py, Zipline, etc.) will implement this interface.
    """
    
    # Subclasses should set these for automatic dependency management
    _dependency_available_flag: bool = True
    _dependency_help: str = ""

    def __init__(self):
        """Initialize engine with dependency checking"""
        if not self._dependency_available_flag:
            raise ImportError(self._dependency_help)

    @classmethod
    def dependencies_available(cls) -> bool:
        """
        Check if this engine's dependencies are available.
        
        Returns:
            True if all required dependencies are installed
        """
        # Access the flag from the specific class
        return getattr(cls, '_dependency_available_flag', True)

    @abstractmethod
    def get_engine_info(self) -> EngineInfo:
        """Get information about this engine"""
        pass

    @abstractmethod
    def is_valid_strategy(self, name: str, obj: Any) -> bool:
        """
        Check if a given object is a valid strategy for this engine.
        
        Args:
            name: Name of the object
            obj: The object to check
            
        Returns:
            True if the object is a valid strategy for this engine
        """
        pass

    @abstractmethod
    def create_engine_strategy(self, strategy_obj: Any) -> EngineStrategy:
        """
        Create an engine-specific strategy wrapper.
        
        Args:
            strategy_obj: The raw strategy object from the loaded module
            
        Returns:
            EngineStrategy wrapper for this engine
        """
        pass

    def get_explicit_marker(self) -> str:
        """
        Get the explicit marker attribute name for this engine (optional).
        
        Returns:
            Attribute name like '__vbt_strategy__' or None if no explicit marker
        """
        return None

    def load_strategy_from_file(self, strategy_path: str) -> EngineStrategy:
        """
        Load a strategy from a file using the generic template.
        
        This provides the common flow:
        1. Load module from path
        2. Find strategy candidates 
        3. Select single strategy
        4. Create engine strategy wrapper
        
        Args:
            strategy_path: Path to the strategy file

        Returns:
            EngineStrategy wrapper for the loaded strategy
        """
        try:
            # Load the module using shared helper (includes file existence check)
            module = load_module_from_path(strategy_path, f"{self.__class__.__name__.lower()}_strategy")
            
            # Find strategy candidates using engine-specific validation
            strategy_candidates = find_strategy_candidates(module, self.is_valid_strategy)
            
            # Select single strategy using shared utility
            strategy_name, strategy_obj = select_single_strategy(
                strategy_candidates, strategy_path, self.get_explicit_marker()
            )
            
            logger.info(f"Loaded {self.__class__.__name__} strategy: {strategy_name} from {strategy_path}")
            
            # Create engine-specific wrapper
            engine_strategy = self.create_engine_strategy(strategy_obj)
            
            return engine_strategy
            
        except Exception as e:
            logger.error(f"Error loading {self.__class__.__name__} strategy from {strategy_path}: {e}")
            raise

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
