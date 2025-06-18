"""
VectorBT Engine Implementation

Implements the trading engine interface for VectorBT strategies.
This module contains all the VectorBT-specific logic for loading strategies
and extracting signals using the high-performance vectorbt library.
"""

import pandas as pd
import numpy as np
import os
import importlib.util
import inspect
import re
import logging
from typing import Type, Dict, Any, Tuple, Callable
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

try:
    import vectorbt as vbt
    VECTORBT_AVAILABLE = True
except ImportError as e:
    VECTORBT_AVAILABLE = False
    vbt = None
    logger.warning(f"VectorBT not available: {e}")
except Exception as e:
    # Handle other import-related issues (like telegram dependency conflicts)
    VECTORBT_AVAILABLE = False
    vbt = None
    logger.warning(f"VectorBT import error: {e}. This is often due to telegram dependency conflicts.")

from .engine_base import TradingEngine, EngineStrategy, EngineSignalExtractor, EngineInfo
from ..core.signal_extractor import TradingSignal, SignalType, SignalExtractorStrategy
from ..core.base_signal_extractor import BaseSignalExtractor
from ..core.strategy_loader import StrategyLoader


def is_available() -> bool:
    """Check if VectorBT dependencies are available"""
    return VECTORBT_AVAILABLE


class VectorBTEngineStrategy(EngineStrategy):
    """Wrapper for VectorBT strategies"""
    
    def __init__(self, strategy_class: Type, strategy_params: Dict[str, Any] = None):
        super().__init__(strategy_class, strategy_params)
        
    def get_lookback_period(self) -> int:
        """Get the minimum number of bars required by this strategy"""
        # VectorBT strategies can work with small datasets - default to 10 bars
        # Users can override this with --lookback if they need more
        return 10
    
    def get_strategy_name(self) -> str:
        """Get a human-readable name for this strategy"""
        return self.strategy_class.__name__
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get strategy parameters"""
        params = {}
        
        # Extract class-level parameters if it's a class
        if inspect.isclass(self.strategy_class):
            for attr_name in dir(self.strategy_class):
                if (not attr_name.startswith('_') and 
                    not callable(getattr(self.strategy_class, attr_name))):
                    try:
                        params[attr_name] = getattr(self.strategy_class, attr_name)
                    except (AttributeError, TypeError):
                        pass
        
        # Add strategy_params passed to constructor
        params.update(self.strategy_params)
        
        return params


class VectorBTSignalExtractor(BaseSignalExtractor, EngineSignalExtractor):
    """Signal extractor for VectorBT strategies"""
    
    def __init__(self, engine_strategy: VectorBTEngineStrategy, min_bars_required: int = 2, granularity: str = '1min', **strategy_params):
        super().__init__(engine_strategy)
        self.strategy_class = engine_strategy.strategy_class
        self.strategy_params = strategy_params
        self.min_bars_required = min_bars_required
        self.granularity = granularity
        
    def extract_signal(self, historical_data: pd.DataFrame) -> TradingSignal:
        """Extract trading signal from historical data using VectorBT"""
        try:
            # Ensure we have enough data
            if len(historical_data) < self.min_bars_required:
                logger.warning("Insufficient historical data for signal extraction")
                return TradingSignal(
                    signal=SignalType.HOLD,
                    confidence=0.0,
                    price=0.0,
                    timestamp=pd.Timestamp.now(),
                    indicators={}
                )
            
            # Prepare data for VectorBT format
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            if not all(col in historical_data.columns for col in required_columns):
                logger.error(f"Historical data missing required columns: {required_columns}")
                raise ValueError("Invalid data format")
            
            data = historical_data[required_columns].copy()
            
            # Call the strategy function to get entries and exits
            entries, exits = self._call_strategy(data)
            
            # Build a tiny portfolio (for NAV / PnL metrics) with granularity-aware frequency
            pf = vbt.Portfolio.from_signals(
                close=data['Close'],
                entries=entries,
                exits=exits,
                init_cash=10_000,
                freq=self._convert_granularity_to_freq(self.granularity)
            )
            
            # --- Decide what signal to emit (event-driven first) -------------
            current_price = self._safe_get_last_value(data['Close'])

            # 1. Did the strategy fire on THIS bar?
            last_entry = bool(self._safe_get_last_value(entries, False))
            last_exit  = bool(self._safe_get_last_value(exits, False))

            if last_entry and not last_exit:
                signal     = SignalType.BUY
                confidence = 1.0
            elif last_exit and not last_entry:
                signal     = SignalType.SELL
                confidence = 1.0
            else:
                # 2. No new event – use portfolio exposure for context
                _pos_attr2 = getattr(pf, "position_now", None)
                if callable(_pos_attr2):
                    pos_now = _pos_attr2()
                else:
                    pos_now = _pos_attr2 if _pos_attr2 is not None else 0

                if pos_now > 0:
                    signal     = SignalType.BUY
                    confidence = min(abs(pos_now), 1.0)
                elif pos_now < 0:
                    signal     = SignalType.SELL
                    confidence = min(abs(pos_now), 1.0)
                else:
                    signal     = SignalType.HOLD
                    confidence = 0.0

            # Portfolio / debug metrics --------------------------------------
            nav_now = getattr(pf, "value_now", None)
            if callable(nav_now):
                nav_now = nav_now()
            if nav_now is None:
                nav_now = pf.value().iloc[-1]

            # Current exposure (works on every VectorBT version)
            pos_now = 0
            _pos_attr = getattr(pf, "position_now", None)
            if callable(_pos_attr):
                pos_now = _pos_attr()
            elif _pos_attr is not None:
                pos_now = _pos_attr

            indicators = self._clean_indicators({
                "vectorbt_nav": nav_now,
                "position": pos_now,
                "entries_count": entries.sum(),
                "exits_count": exits.sum(),
                "current_price": current_price,
                "granularity": self.granularity,
            })
            
            logger.debug(f"VectorBT signal: {signal.value} "
                        f"(confidence: {confidence:.2f}) "
                        f"at price: ${current_price:.2f}")
            
            return TradingSignal(
                signal=signal,
                confidence=confidence,
                price=current_price,
                timestamp=data.index[-1],
                indicators=indicators
            )
            
        except Exception as e:
            logger.error(f"Error extracting VectorBT signal: {e}")
            # Return safe default signal
            return TradingSignal(
                signal=SignalType.HOLD,
                confidence=0.0,
                price=historical_data['Close'].iloc[-1] if len(historical_data) > 0 else 0.0,
                timestamp=pd.Timestamp.now(),
                indicators={},
                metadata={'error': str(e)}
            )
    
    def _convert_granularity_to_freq(self, granularity: str) -> str:
        """Convert StrateQueue granularity format to pandas/VectorBT frequency string"""
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
    
    def _call_strategy(self, data: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Call the strategy function and return entries/exits"""
        try:
            if inspect.isfunction(self.strategy_class):
                # Function-based strategy
                result = self.strategy_class(data, **self.strategy_params)
            elif inspect.isclass(self.strategy_class):
                # Class-based strategy ─ create an instance first
                instance = self.strategy_class(**self.strategy_params)

                if hasattr(instance, "run") and callable(getattr(instance, "run")):
                    # Preferred: instance.run(data)
                    result = instance.run(data)
                elif callable(instance):
                    # Fallback: class implements __call__(data)
                    result = instance(data)
                else:
                    raise ValueError(
                        "VectorBT strategy class must implement a 'run' method "
                        "or be directly callable (__call__)."
                    )
            else:
                raise ValueError("Strategy must be a function or a class")
            
            # Ensure result is a tuple of entries, exits
            if not isinstance(result, tuple) or len(result) != 2:
                raise ValueError("VectorBT strategy must return (entries, exits) tuple")
            
            entries, exits = result
            
            # Convert to pandas Series if needed
            if not isinstance(entries, pd.Series):
                entries = pd.Series(entries, index=data.index)
            if not isinstance(exits, pd.Series):
                exits = pd.Series(exits, index=data.index)
            
            return entries, exits
            
        except Exception as e:
            logger.error(f"Error calling VectorBT strategy: {e}")
            # Return empty signals
            empty_signal = pd.Series(False, index=data.index)
            return empty_signal, empty_signal
    
    def get_minimum_bars_required(self) -> int:
        """Get minimum number of bars needed for signal extraction"""
        return max(self.min_bars_required, self.engine_strategy.get_lookback_period())


class VectorBTMultiTickerSignalExtractor(BaseSignalExtractor, EngineSignalExtractor):
    """Multi-ticker signal extractor for VectorBT strategies - processes multiple symbols in one shot"""
    
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
                return {symbol: self._create_hold_signal() for symbol in missing_symbols}
            
            # Check minimum bars requirement for each symbol
            insufficient_symbols = []
            for symbol in self.symbols:
                if len(multi_symbol_data[symbol]) < self.min_bars_required:
                    insufficient_symbols.append(symbol)
            
            if insufficient_symbols:
                logger.warning(f"Insufficient data for symbols: {insufficient_symbols}")
                # Return HOLD signals for insufficient symbols, process the rest
                signals = {symbol: self._create_hold_signal() for symbol in insufficient_symbols}
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
            return {symbol: self._create_hold_signal(error=str(e)) for symbol in self.symbols}
    
    def _process_multi_symbol_data(self, symbol_data: dict[str, pd.DataFrame]) -> dict[str, TradingSignal]:
        """Process multiple symbols together using VectorBT's vectorized operations"""
        symbols = list(symbol_data.keys())
        
        # Create MultiIndex DataFrame for VectorBT
        multi_index_data = self._create_multiindex_dataframe(symbol_data)
        
        # Call the strategy on the multi-symbol data
        entries, exits = self._call_strategy_multi(multi_index_data)
        
        # Create portfolio for each symbol
        signals = {}
        for symbol in symbols:
            try:
                # Extract data for this symbol
                symbol_close = multi_index_data['Close'][symbol] if symbol in multi_index_data['Close'].columns else multi_index_data['Close']
                symbol_entries = entries[symbol] if symbol in entries.columns else entries
                symbol_exits = exits[symbol] if symbol in exits.columns else exits
                
                # Build portfolio for this symbol
                pf = vbt.Portfolio.from_signals(
                    close=symbol_close,
                    entries=symbol_entries,
                    exits=symbol_exits,
                    init_cash=10_000,
                    freq=self._convert_granularity_to_freq(self.granularity)
                )
                
                # Extract signal for this symbol
                signal = self._extract_symbol_signal(symbol, symbol_close, symbol_entries, symbol_exits, pf)
                signals[symbol] = signal
                
            except Exception as e:
                logger.error(f"Error processing symbol {symbol}: {e}")
                signals[symbol] = self._create_hold_signal(error=str(e))
        
        return signals
    
    def _create_multiindex_dataframe(self, symbol_data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Create a MultiIndex DataFrame suitable for VectorBT multi-asset processing"""
        # Get the common index (intersection of all symbol timestamps)
        common_index = None
        for symbol, data in symbol_data.items():
            if common_index is None:
                common_index = data.index
            else:
                common_index = common_index.intersection(data.index)
        
        if len(common_index) == 0:
            # Fallback: use union of all indices and forward-fill missing values
            logger.warning("No common timestamps found, using union of all timestamps with forward-fill")
            all_indices = []
            for symbol, data in symbol_data.items():
                all_indices.append(data.index)
            common_index = pd.Index([]).union_many(all_indices).sort_values()
            
            if len(common_index) == 0:
                raise ValueError("No valid timestamps found across any symbols")
        
        # Required columns for VectorBT
        required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        
        # Build MultiIndex DataFrame
        multi_data = {}
        for column in required_columns:
            multi_data[column] = pd.DataFrame(index=common_index)
            for symbol, data in symbol_data.items():
                if column in data.columns:
                    # Align data to common index with forward-fill for missing values
                    aligned_data = data[column].reindex(common_index, method='ffill')
                    multi_data[column][symbol] = aligned_data
                else:
                    raise ValueError(f"Missing column {column} for symbol {symbol}")
        
        # Combine into single DataFrame with MultiIndex columns
        result = pd.concat(multi_data, axis=1)
        
        # Drop any rows that are completely NaN (beginning of series before any data)
        result = result.dropna(how='all')
        
        if len(result) == 0:
            raise ValueError("No valid data remaining after alignment and cleaning")
        
        return result
    
    def _call_strategy_multi(self, data: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Call strategy on multi-symbol data"""
        try:
            if inspect.isfunction(self.strategy_class):
                # Function-based strategy
                result = self.strategy_class(data, **self.strategy_params)
            elif inspect.isclass(self.strategy_class):
                # Class-based strategy
                instance = self.strategy_class(**self.strategy_params)
                
                if hasattr(instance, "run") and callable(getattr(instance, "run")):
                    result = instance.run(data)
                elif callable(instance):
                    result = instance(data)
                else:
                    raise ValueError(
                        "VectorBT strategy class must implement a 'run' method "
                        "or be directly callable (__call__)."
                    )
            else:
                raise ValueError("Strategy must be a function or a class")
            
            # Ensure result is a tuple of entries, exits
            if not isinstance(result, tuple) or len(result) != 2:
                raise ValueError("VectorBT strategy must return (entries, exits) tuple")
            
            entries, exits = result
            
            # Convert to DataFrames with proper MultiIndex structure
            if isinstance(entries, pd.Series):
                # Single series - broadcast to all symbols
                entries_df = pd.DataFrame(index=data.index)
                for symbol in self.symbols:
                    entries_df[symbol] = entries
                entries = entries_df
            elif not isinstance(entries, pd.DataFrame):
                # Convert array-like to DataFrame
                entries = pd.DataFrame(entries, index=data.index, columns=self.symbols)
            
            if isinstance(exits, pd.Series):
                # Single series - broadcast to all symbols
                exits_df = pd.DataFrame(index=data.index)
                for symbol in self.symbols:
                    exits_df[symbol] = exits
                exits = exits_df
            elif not isinstance(exits, pd.DataFrame):
                # Convert array-like to DataFrame
                exits = pd.DataFrame(exits, index=data.index, columns=self.symbols)
            
            return entries, exits
            
        except Exception as e:
            logger.error(f"Error calling VectorBT multi-symbol strategy: {e}")
            # Return empty signals for all symbols
            empty_df = pd.DataFrame(False, index=data.index, columns=self.symbols)
            return empty_df, empty_df
    
    def _extract_symbol_signal(self, symbol: str, close: pd.Series, entries: pd.Series, exits: pd.Series, pf) -> TradingSignal:
        """Extract trading signal for a single symbol from portfolio results"""
        # --- Decide what signal to emit (event-driven first) -------------
        current_price = self._safe_get_last_value(close)

        # 1. Did the strategy fire on THIS bar?
        last_entry = bool(self._safe_get_last_value(entries, False))
        last_exit = bool(self._safe_get_last_value(exits, False))

        if last_entry and not last_exit:
            signal = SignalType.BUY
            confidence = 1.0
        elif last_exit and not last_entry:
            signal = SignalType.SELL
            confidence = 1.0
        else:
            # 2. No new event – use portfolio exposure for context
            _pos_attr = getattr(pf, "position_now", None)
            if callable(_pos_attr):
                pos_now = _pos_attr()
            else:
                pos_now = _pos_attr if _pos_attr is not None else 0

            if pos_now > 0:
                signal = SignalType.BUY
                confidence = min(abs(pos_now), 1.0)
            elif pos_now < 0:
                signal = SignalType.SELL
                confidence = min(abs(pos_now), 1.0)
            else:
                signal = SignalType.HOLD
                confidence = 0.0

        # Portfolio / debug metrics
        nav_now = getattr(pf, "value_now", None)
        if callable(nav_now):
            nav_now = nav_now()
        if nav_now is None:
            nav_now = pf.value().iloc[-1]

        # Current exposure
        pos_now = 0
        _pos_attr = getattr(pf, "position_now", None)
        if callable(_pos_attr):
            pos_now = _pos_attr()
        elif _pos_attr is not None:
            pos_now = _pos_attr

        indicators = self._clean_indicators({
            "symbol": symbol,
            "vectorbt_nav": nav_now,
            "position": pos_now,
            "entries_count": entries.sum(),
            "exits_count": exits.sum(),
            "current_price": current_price,
            "granularity": self.granularity,
        })
        
        return TradingSignal(
            signal=signal,
            confidence=confidence,
            price=current_price,
            timestamp=close.index[-1] if len(close) > 0 else pd.Timestamp.now(),
            indicators=indicators
        )
    
    def _create_hold_signal(self, error: str = None) -> TradingSignal:
        """Create a default HOLD signal"""
        metadata = {'error': error} if error else {}
        return TradingSignal(
            signal=SignalType.HOLD,
            confidence=0.0,
            price=0.0,
            timestamp=pd.Timestamp.now(),
            indicators={},
            metadata=metadata
        )
    
    def extract_signal(self, historical_data: pd.DataFrame) -> TradingSignal:
        """Single-symbol interface for compatibility - delegates to extract_signals"""
        # For backward compatibility, extract first symbol from multi-symbol result
        if self.symbols:
            symbol_data = {self.symbols[0]: historical_data}
            signals = self.extract_signals(symbol_data)
            return signals.get(self.symbols[0], self._create_hold_signal())
        else:
            return self._create_hold_signal()
    
    def get_minimum_bars_required(self) -> int:
        """Get minimum number of bars needed for signal extraction"""
        return max(self.min_bars_required, self.engine_strategy.get_lookback_period())


class VectorBTEngine(TradingEngine):
    """Trading engine implementation for VectorBT"""
    
    def __init__(self):
        if not VECTORBT_AVAILABLE:
            raise ImportError(
                "VectorBT support is not installed. Run:\n"
                "    pip install stratequeue[vectorbt]\n"
                "or\n"
                "    pip install vectorbt"
            )
    
    def get_engine_info(self) -> EngineInfo:
        """Get information about this engine"""
        return EngineInfo(
            name="vectorbt",
            version=vbt.__version__ if vbt else "unknown",
            supported_features={
                "signal_extraction": True,
                "live_trading": True,
                "multi_strategy": True,
                "limit_orders": True,
                "stop_orders": True,
                "vectorized_backtesting": True,
                "numba_acceleration": True
            },
            description="High-performance vectorized backtesting library with Numba acceleration"
        )
    
    def load_strategy_from_file(self, strategy_path: str) -> VectorBTEngineStrategy:
        """Load a VectorBT strategy from file"""
        try:
            if not os.path.exists(strategy_path):
                raise FileNotFoundError(f"Strategy file not found: {strategy_path}")
            
            # Load the module
            spec = importlib.util.spec_from_file_location("vectorbt_strategy", strategy_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find strategy functions or classes
            strategy_candidates = {}  # name -> obj mapping for better error messages
            
            for name, obj in inspect.getmembers(module):
                # Look for functions that could be VectorBT strategies
                if inspect.isfunction(obj):
                    # Check if function has data parameter and returns entries/exits
                    sig = inspect.signature(obj)
                    if 'data' in sig.parameters:
                        strategy_candidates[name] = obj
                
                # Look for classes marked as VectorBT strategies
                elif inspect.isclass(obj):
                    if (hasattr(obj, '__vbt_strategy__') or 
                        hasattr(obj, 'run') or 
                        name.endswith('Strategy')):
                        strategy_candidates[name] = obj
            
            if not strategy_candidates:
                raise ValueError(f"No valid VectorBT strategy found in {strategy_path}")
            
            # Check for explicit marker first
            marked_strategies = {
                name: obj for name, obj in strategy_candidates.items()
                if hasattr(obj, '__vbt_strategy__') and getattr(obj, '__vbt_strategy__', False)
            }
            
            if marked_strategies:
                if len(marked_strategies) == 1:
                    # Exactly one explicitly marked strategy
                    strategy_name, strategy_obj = next(iter(marked_strategies.items()))
                    logger.info(f"Using explicitly marked VectorBT strategy: {strategy_name}")
                else:
                    # Multiple marked strategies - this is an error
                    marked_names = list(marked_strategies.keys())
                    raise ValueError(
                        f"Multiple VectorBT strategies marked with __vbt_strategy__ = True in {strategy_path}: {marked_names}.\n"
                        "Only one strategy should be marked per file."
                    )
            else:
                # No explicit markers - check for single implicit candidate
                if len(strategy_candidates) == 1:
                    # Exactly one candidate - use it
                    strategy_name, strategy_obj = next(iter(strategy_candidates.items()))
                else:
                    # Multiple candidates without explicit selection - fail fast
                    candidate_names = list(strategy_candidates.keys())
                    raise ValueError(
                        f"Multiple VectorBT strategies detected in {strategy_path}: {candidate_names}.\n"
                        "Either:\n"
                        f"  • Keep only one strategy per file, or\n"
                        f"  • Add  __vbt_strategy__ = True  to exactly one of them."
                    )
            logger.info(f"Loaded VectorBT strategy: {strategy_name} from {strategy_path}")
            
            # Create wrapper
            engine_strategy = VectorBTEngineStrategy(strategy_obj)
            
            return engine_strategy
            
        except Exception as e:
            logger.error(f"Error loading VectorBT strategy from {strategy_path}: {e}")
            raise
    
    def create_signal_extractor(self, engine_strategy: VectorBTEngineStrategy, 
                              **kwargs) -> VectorBTSignalExtractor:
        """Create a signal extractor for the given strategy"""
        return VectorBTSignalExtractor(engine_strategy, **kwargs)
    
    def create_multi_ticker_signal_extractor(self, engine_strategy: VectorBTEngineStrategy, 
                                           symbols: list[str], **kwargs) -> VectorBTMultiTickerSignalExtractor:
        """Create a multi-ticker signal extractor for processing multiple symbols in one shot"""
        return VectorBTMultiTickerSignalExtractor(engine_strategy, symbols, **kwargs)
    
    def validate_strategy_file(self, strategy_path: str) -> bool:
        """Validate that a strategy file is compatible with this engine"""
        try:
            self.load_strategy_from_file(strategy_path)
            return True
        except Exception as e:
            logger.debug(f"VectorBT strategy validation failed: {e}")
            return False 
    
    # Convenience alias for consistent API
    load_strategy = load_strategy_from_file 