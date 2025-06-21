"""
VectorBT Engine Implementation

Implements the trading engine interface for VectorBT strategies.
This module contains all the VectorBT-specific logic for loading strategies
and extracting signals.
"""

import inspect
import logging
from typing import Any, Dict, Type, Tuple

import pandas as pd

# Conditional import for VectorBT with conflict resolution
try:
    # Handle telegram conflict by temporarily removing from sys.modules
    import sys
    telegram_modules = [m for m in sys.modules.keys() if m.startswith('telegram')]
    for module in telegram_modules:
        if module in sys.modules:
            del sys.modules[module]
    
    import vectorbt as vbt
    VECTORBT_AVAILABLE = True
except ImportError as e:
    VECTORBT_AVAILABLE = False
    vbt = None
    logger = logging.getLogger(__name__)
    logger.warning(f"VectorBT not available: {e}")

from ..core.signal_extractor import SignalType, TradingSignal
from ..core.base_signal_extractor import BaseSignalExtractor
from .engine_base import (
    EngineInfo, EngineSignalExtractor, EngineStrategy, TradingEngine,
    build_engine_info, granularity_to_pandas_freq
)

logger = logging.getLogger(__name__)


def call_vectorbt_strategy(strategy_class: Type, data: pd.DataFrame, **strategy_params) -> Tuple[pd.Series, pd.Series, pd.Series | None]:
    """
    Call a VectorBT strategy function/class and return entries, exits, and optional size.
    
    This shared function removes duplication between single and multi-ticker extractors.
    
    Args:
        strategy_class: Strategy function or class to call
        data: Price data DataFrame
        **strategy_params: Parameters to pass to the strategy
        
    Returns:
        Tuple of (entries, exits, size) where size may be None
    """
    if inspect.isfunction(strategy_class):
        # Function-based strategy
        result = strategy_class(data, **strategy_params)
        
        if isinstance(result, tuple):
            if len(result) == 2:
                entries, exits = result
                size = None
            elif len(result) == 3:
                entries, exits, size = result
            else:
                raise ValueError(f"VectorBT strategy function must return (entries, exits) or (entries, exits, size), got {len(result)} values")
        else:
            raise ValueError("VectorBT strategy function must return a tuple")
            
    elif inspect.isclass(strategy_class):
        # Class-based strategy
        strategy_instance = strategy_class(**strategy_params)
        
        if hasattr(strategy_instance, 'run'):
            result = strategy_instance.run(data)
        else:
            raise ValueError("VectorBT strategy class must have a 'run' method")
            
        if isinstance(result, tuple):
            if len(result) == 2:
                entries, exits = result
                size = None
            elif len(result) == 3:
                entries, exits, size = result
            else:
                raise ValueError(f"VectorBT strategy class run() must return (entries, exits) or (entries, exits, size), got {len(result)} values")
        else:
            raise ValueError("VectorBT strategy class run() must return a tuple")
    else:
        raise ValueError("VectorBT strategy must be a function or class")
    
    # Ensure entries and exits are boolean Series
    if not isinstance(entries, pd.Series):
        entries = pd.Series(entries, index=data.index)
    if not isinstance(exits, pd.Series):
        exits = pd.Series(exits, index=data.index)
    
    entries = entries.astype(bool)
    exits = exits.astype(bool)
    
    # Handle size if provided
    if size is not None:
        if not isinstance(size, pd.Series):
            size = pd.Series(size, index=data.index)
    
    return entries, exits, size


class VectorBTEngineStrategy(EngineStrategy):
    """Wrapper for VectorBT strategies"""

    def __init__(self, strategy_class: Type, strategy_params: Dict[str, Any] = None):
        super().__init__(strategy_class, strategy_params)

    def get_lookback_period(self) -> int:
        """Get the minimum number of bars required by this strategy"""
        # VectorBT strategies typically need at least 10 bars for meaningful signals
        return 10


class VectorBTSignalExtractor(BaseSignalExtractor, EngineSignalExtractor):
    """Signal extractor for VectorBT strategies"""

    def __init__(self, engine_strategy: VectorBTEngineStrategy, min_bars_required: int = 2, granularity: str = '1min', **strategy_params):
        super().__init__(engine_strategy)
        self.strategy_class = engine_strategy.strategy_class
        self.strategy_params = strategy_params
        self.min_bars_required = min_bars_required
        self.granularity = granularity

    def _validate_and_normalize_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Validate and normalize data for VectorBT processing.
        
        VectorBT strategies typically expect OHLCV data, but can work with just Close.
        This method handles both cases and normalizes column names.
        """
        # Check if we have the basic required data
        if data.empty:
            raise ValueError("Empty data provided")
        
        # Normalize column names to title case (VectorBT convention)
        data = data.copy()
        column_mapping = {}
        
        # Map common column name variations
        for col in data.columns:
            col_lower = col.lower()
            if col_lower in ['open', 'o']:
                column_mapping[col] = 'Open'
            elif col_lower in ['high', 'h']:
                column_mapping[col] = 'High'
            elif col_lower in ['low', 'l']:
                column_mapping[col] = 'Low'
            elif col_lower in ['close', 'c', 'price']:
                column_mapping[col] = 'Close'
            elif col_lower in ['volume', 'vol', 'v']:
                column_mapping[col] = 'Volume'
        
        # Rename columns
        data = data.rename(columns=column_mapping)
        
        # If we only have Close data, create OHLC from Close
        if 'Close' in data.columns and len([c for c in ['Open', 'High', 'Low'] if c in data.columns]) == 0:
            logger.debug("Only Close data available, creating OHLC from Close prices")
            data['Open'] = data['Close']
            data['High'] = data['Close']
            data['Low'] = data['Close']
        
        # Add Volume if missing (some strategies might need it)
        if 'Volume' not in data.columns:
            data['Volume'] = 1.0  # Default volume
        
        # Ensure we have at least Close data
        if 'Close' not in data.columns:
            raise ValueError("Data must contain at least 'Close' price information")
        
        # Ensure numeric data types
        numeric_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        # Check for NaN values
        if data.isnull().any().any():
            logger.warning("Data contains NaN values, forward filling...")
            data = data.fillna(method='ffill').fillna(method='bfill')
        
        return data

    def extract_signal(self, historical_data: pd.DataFrame) -> TradingSignal:
        """Extract trading signal from historical data using VectorBT strategy"""
        try:
            # Check for insufficient data first
            if (hold_signal := self._abort_insufficient_bars(historical_data)):
                return hold_signal
            
            # Validate and normalize the data
            data = self._validate_and_normalize_data(historical_data)
            
            # Call strategy using shared function
            entries, exits, size = call_vectorbt_strategy(self.strategy_class, data, **self.strategy_params)
            
            # Extract signal from the last timestep
            return self._extract_signal_from_last_bar(data, entries, exits, size)
            
        except Exception as e:
            logger.error(f"Error extracting VectorBT signal: {e}")
            # Return safe default signal
            price = self._safe_get_last_value(historical_data['Close']) if len(historical_data) > 0 and 'Close' in historical_data.columns else 0.0
            return self._safe_hold(price=price, error=e)

    def _extract_signal_from_last_bar(self, data: pd.DataFrame, entries: pd.Series, exits: pd.Series, size: pd.Series = None) -> TradingSignal:
        """Extract trading signal from the last bar of entries/exits"""
        try:
            current_price = self._safe_get_last_value(data['Close'])
            
            # Check what happened on the last bar
            last_entry = bool(self._safe_get_last_value(entries, False))
            last_exit = bool(self._safe_get_last_value(exits, False))
            
            # Extract size if provided
            signal_size = None
            if size is not None:
                signal_size = self._safe_get_last_value(size, None)
                if signal_size is not None:
                    signal_size = abs(float(signal_size))  # Ensure positive
            
            # Determine signal type
            if last_entry and not last_exit:
                signal = SignalType.BUY
            elif last_exit and not last_entry:
                signal = SignalType.SELL
            else:
                signal = SignalType.HOLD
            
            # Create indicators dictionary
            indicators = self._clean_indicators({
                "last_entry": last_entry,
                "last_exit": last_exit,
                "current_price": current_price,
                "granularity": self.granularity,
                "pandas_freq": granularity_to_pandas_freq(self.granularity)
            })
            
            return TradingSignal(
                signal=signal,
                price=current_price,
                timestamp=data.index[-1],
                indicators=indicators,
                size=signal_size  # Include size if provided by strategy
            )
            
        except Exception as e:
            logger.error(f"Error extracting signal from last bar: {e}")
            return self._safe_hold(error=e)


class VectorBTMultiTickerSignalExtractor(BaseSignalExtractor, EngineSignalExtractor):
    """Multi-ticker signal extractor for VectorBT strategies"""
    
    def __init__(self, engine_strategy: VectorBTEngineStrategy, symbols: list[str], min_bars_required: int = 2, granularity: str = '1min', **strategy_params):
        super().__init__(engine_strategy)
        self.strategy_class = engine_strategy.strategy_class
        self.strategy_params = strategy_params
        self.min_bars_required = min_bars_required
        self.granularity = granularity
        self.symbols = symbols
        
    def extract_signals(self, multi_symbol_data: dict[str, pd.DataFrame]) -> dict[str, TradingSignal]:
        """Extract trading signals for multiple symbols using VectorBT vectorization"""
        try:
            # Check if we have data for all symbols
            missing_symbols = [symbol for symbol in self.symbols if symbol not in multi_symbol_data]
            if missing_symbols:
                logger.warning(f"Missing data for symbols: {missing_symbols}")
                # Return HOLD signals for missing symbols
                return {symbol: self._safe_hold() for symbol in missing_symbols}
            
            # Check minimum bars requirement for each symbol
            insufficient_symbols = []
            for symbol in self.symbols:
                if len(multi_symbol_data[symbol]) < self.min_bars_required:
                    insufficient_symbols.append(symbol)
            
            if insufficient_symbols:
                logger.warning(f"Insufficient data for symbols: {insufficient_symbols}")
                # Return HOLD signals for insufficient symbols, process the rest
                signals = {symbol: self._safe_hold() for symbol in insufficient_symbols}
                valid_symbols = [s for s in self.symbols if s not in insufficient_symbols]
                if valid_symbols:
                    valid_signals = self._process_multi_symbol_data(
                        {s: multi_symbol_data[s] for s in valid_symbols}
                    )
                    signals.update(valid_signals)
                return signals
            
            # All symbols have sufficient data - process them together
            return self._process_multi_symbol_data(multi_symbol_data)
            
        except Exception as e:
            logger.error(f"Error extracting VectorBT multi-ticker signals: {e}")
            # Return HOLD signals for all symbols
            return {symbol: self._safe_hold(error=e) for symbol in self.symbols}
    
    def _process_multi_symbol_data(self, symbol_data: dict[str, pd.DataFrame]) -> dict[str, TradingSignal]:
        """Process multiple symbols using per-symbol strategy execution for safety"""
        signals = {}
        
        for symbol, df in symbol_data.items():
            try:
                # Call strategy on single-symbol data using shared function
                entries, exits, size = call_vectorbt_strategy(self.strategy_class, df, **self.strategy_params)
                
                # Extract signal from the last timestep only
                signal = self._extract_last_bar_signal(symbol, df['Close'], entries, exits, size)
                signals[symbol] = signal
                
            except Exception as e:
                logger.error(f"Error processing symbol {symbol}: {e}")
                signals[symbol] = self._safe_hold(error=e)
        
        return signals
    
    def _extract_last_bar_signal(self, symbol: str, close: pd.Series, entries: pd.Series, exits: pd.Series, size: pd.Series = None) -> TradingSignal:
        """Extract trading signal from the last bar only (no portfolio needed)"""
        try:
            current_price = self._safe_get_last_value(close)
            
            # Check what happened on the last bar
            last_entry = bool(self._safe_get_last_value(entries, False))
            last_exit = bool(self._safe_get_last_value(exits, False))
            
            # Extract size if provided
            signal_size = None
            if size is not None:
                signal_size = self._safe_get_last_value(size, None)
                if signal_size is not None:
                    signal_size = abs(float(signal_size))  # Ensure positive
            
            # Determine signal type
            if last_entry and not last_exit:
                signal = SignalType.BUY
            elif last_exit and not last_entry:
                signal = SignalType.SELL
            else:
                signal = SignalType.HOLD
            
            indicators = self._clean_indicators({
                "symbol": symbol,
                "last_entry": last_entry,
                "last_exit": last_exit,
                "current_price": current_price,
                "granularity": self.granularity,
            })
            
            return TradingSignal(
                signal=signal,
                price=current_price,
                timestamp=close.index[-1],
                indicators=indicators,
                size=signal_size  # Include size if provided by strategy
            )
            
        except Exception as e:
            logger.error(f"Error extracting signal for {symbol}: {e}")
            return self._safe_hold(error=e)


class VectorBTEngine(TradingEngine):
    """Trading engine implementation for VectorBT"""
    
    # Set dependency management attributes
    _dependency_available_flag = VECTORBT_AVAILABLE
    _dependency_help = (
        "VectorBT support is not installed. Run:\n"
        "    pip install stratequeue[vectorbt]\n"
        "or\n"
        "    pip install vectorbt"
    )
    
    @classmethod
    def dependencies_available(cls) -> bool:
        """Check if VectorBT dependencies are available"""
        return VECTORBT_AVAILABLE
    
    def get_engine_info(self) -> EngineInfo:
        """Get information about this engine"""
        return build_engine_info(
            name="vectorbt",
            lib_version=vbt.__version__ if vbt else "unknown",
            description="High-performance vectorized backtesting library with Numba acceleration",
            vectorized_backtesting=True,
            numba_acceleration=True
        )
    
    def is_valid_strategy(self, name: str, obj: Any) -> bool:
        """Check if object is a valid VectorBT strategy"""
        # Look for functions that could be VectorBT strategies
        if inspect.isfunction(obj):
            # Check if function has data parameter and returns entries/exits
            sig = inspect.signature(obj)
            return 'data' in sig.parameters
        
        # Look for classes marked as VectorBT strategies
        elif inspect.isclass(obj):
            return (hasattr(obj, '__vbt_strategy__') or 
                    hasattr(obj, 'run') or 
                    name.endswith('Strategy'))
        
        return False
    
    def get_explicit_marker(self) -> str:
        """Get the explicit marker for VectorBT strategies"""
        return '__vbt_strategy__'
    
    def create_engine_strategy(self, strategy_obj: Any) -> VectorBTEngineStrategy:
        """Create a VectorBT engine strategy wrapper"""
        return VectorBTEngineStrategy(strategy_obj)
    
    def create_signal_extractor(self, engine_strategy: VectorBTEngineStrategy, 
                              **kwargs) -> VectorBTSignalExtractor:
        """Create a signal extractor for the given strategy"""
        return VectorBTSignalExtractor(engine_strategy, **kwargs)
    
    def create_multi_ticker_signal_extractor(self, engine_strategy: VectorBTEngineStrategy, 
                                           symbols: list[str], **kwargs) -> VectorBTMultiTickerSignalExtractor:
        """Create a multi-ticker signal extractor for processing multiple symbols in one shot"""
        return VectorBTMultiTickerSignalExtractor(engine_strategy, symbols, **kwargs) 