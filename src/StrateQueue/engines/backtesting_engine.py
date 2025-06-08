"""
Backtesting.py Engine Implementation

Implements the trading engine interface for backtesting.py strategies.
This module contains all the backtesting.py-specific logic for loading strategies
and extracting signals.
"""

import contextlib
import inspect
import logging
from typing import Any

import pandas as pd

# Conditional import for backtesting library
try:
    from backtesting import Backtest
    BACKTESTING_AVAILABLE = True
except ImportError as e:
    BACKTESTING_AVAILABLE = False
    Backtest = None

from ..core.signal_extractor import SignalType, TradingSignal
from ..core.strategy_loader import StrategyLoader
from ..core.base_signal_extractor import BaseSignalExtractor
from .engine_base import (
    EngineInfo, EngineSignalExtractor, EngineStrategy, TradingEngine, 
    build_engine_info
)

# Import persistent backtest for step-wise execution
try:
    from .step_backtest import PersistentBacktest
    PERSISTENT_AVAILABLE = True
except ImportError:
    PERSISTENT_AVAILABLE = False
    PersistentBacktest = None

logger = logging.getLogger(__name__)


class BacktestingEngineStrategy(EngineStrategy):
    """Wrapper for backtesting.py strategies"""

    # Skip backtesting.py internal attributes when collecting parameters
    _skip_attrs = {"data", "broker", "position"}

    def __init__(self, strategy_class: type, strategy_params: dict[str, Any] = None):
        super().__init__(strategy_class, strategy_params)

    def get_lookback_period(self) -> int:
        """Get the minimum number of bars required by this strategy"""
        # Return a simple default - lookback is now handled by CLI
        from ..multi_strategy.strategy_config import DEFAULT_LOOKBACK_PERIOD
        return DEFAULT_LOOKBACK_PERIOD


class BacktestingSignalExtractor(BaseSignalExtractor, EngineSignalExtractor):
    """Signal extractor for backtesting.py strategies"""

    def __init__(
        self,
        engine_strategy: BacktestingEngineStrategy,
        granularity: str,
        min_bars_required: int = 2,
        **strategy_params,
    ):
        super().__init__(engine_strategy)
        self.strategy_class = engine_strategy.strategy_class
        self.strategy_params = strategy_params
        self.min_bars_required = min_bars_required

        # Store granularity (in seconds) for open-candle trimming
        try:
            from ..core.granularity import parse_granularity
            self.granularity_seconds: int | None = parse_granularity(granularity).to_seconds()
        except Exception as _:
            # Invalid granularity string – disable trimming but log once
            import logging as _logging
            _logging.getLogger(__name__).warning(f"Invalid granularity '{granularity}' passed to BacktestingSignalExtractor; open-candle trimming disabled.")
            self.granularity_seconds = None

        # Convert original strategy to signal extractor
        self.signal_strategy_class = StrategyLoader.convert_to_signal_strategy(
            engine_strategy.strategy_class
        )
        
        # Persistent backtest for step-wise execution
        self.persistent_backtest = None
        self.last_processed_timestamp = None
        self.use_persistent = strategy_params.get("persistent", False) and PERSISTENT_AVAILABLE

    def extract_signal(self, historical_data: pd.DataFrame) -> TradingSignal:
        """Extract trading signal from historical data using full backtest approach"""
        try:
            # Check for insufficient data first
            if (hold_signal := self._abort_insufficient_bars(historical_data)):
                return hold_signal

            # Drop the still-forming open candle *unless* we are in persistent mode
            if not self.use_persistent and self.granularity_seconds is not None:
                historical_data = self._trim_open_candle(historical_data, self.granularity_seconds)

            # Apply history truncation to reduce latency (only for non-persistent mode)
            if not self.use_persistent:
                history_multiplier = self.strategy_params.get("history_multiplier", 3)
                historical_data = self._apply_memory_limit(historical_data, history_multiplier)

            # Prepare data for backtesting.py format
            required_columns = ["Open", "High", "Low", "Close", "Volume"]
            if not all(col in historical_data.columns for col in required_columns):
                logger.error(f"Historical data missing required columns: {required_columns}")
                raise ValueError("Invalid data format")

            data = historical_data[required_columns].copy()

            # Choose extraction method based on configuration
            if self.use_persistent:
                return self._extract_signal_persistent(data)
            else:
                # Use the reliable full backtest approach
                return self._extract_signal_legacy(data)

        except Exception as e:
            logger.error(f"Error extracting signal: {e}")
            # Return safe default signal
            price = self._safe_get_last_value(historical_data["Close"]) if len(historical_data) > 0 else 0.0
            return self._safe_hold(price=price, error=e)

    def _extract_signal_legacy(self, data: pd.DataFrame) -> TradingSignal:
        """Legacy signal extraction method (full backtest each time)"""
        # Pull explicit defaults then splat the rest
        strategy_params = self.strategy_params.copy()  # Don't modify original
        cash = strategy_params.pop("cash", 10000)
        commission = strategy_params.pop("commission", 0.0)
        
        # Remove StrateQueue-specific parameters that shouldn't go to Backtest
        strategy_params.pop("persistent", None)
        strategy_params.pop("history_multiplier", None)

        # Create a backtest instance and run full backtest
        bt = Backtest(
            data,
            self.signal_strategy_class,
            cash=cash,
            commission=commission,
            **strategy_params  # hedging, exclusive_orders, margin, ...
        )

        # Run the backtest to initialize strategy and process all historical data
        results = bt.run()

        # Extract the strategy instance to get the current signal
        strategy_instance = results._strategy

        # Get the current signal
        current_signal = strategy_instance.get_current_signal()

        logger.debug(
            f"Extracted signal: {current_signal.signal.value} "
            f"at price: ${current_signal.price:.2f}"
        )

        return current_signal

    def _extract_signal_persistent(self, data: pd.DataFrame) -> TradingSignal:
        """Extract signal using persistent step-wise execution"""
        try:
            current_timestamp = data.index[-1]
            
            # Initialize persistent backtest on first call
            if self.persistent_backtest is None:
                if len(data) < 2:
                    # Need at least 2 bars for initialization
                    return TradingSignal(
                        signal=SignalType.HOLD,
                        price=self._safe_get_last_value(data['Close']),
                        timestamp=current_timestamp,
                        indicators={'status': 'insufficient_data_for_persistent_init'}
                    )
                
                # Initialize with all but the last bar
                init_data = data.iloc[:-1].copy()
                
                # Prepare backtest kwargs
                strategy_params = self.strategy_params.copy()
                cash = strategy_params.pop("cash", 10000)
                commission = strategy_params.pop("commission", 0.0)
                
                bt_kwargs = {
                    'cash': cash,
                    'commission': commission,
                    **strategy_params
                }
                
                # Remove non-backtest parameters
                history_multiplier = strategy_params.pop('history_multiplier', 3)
                for key in ['persistent']:
                    bt_kwargs.pop(key, None)
                
                # Calculate max_bars for memory management
                lookback = self.get_minimum_bars_required()
                max_bars = lookback * history_multiplier
                
                logger.debug(f"Initializing persistent backtest with {len(init_data)} bars, max_bars={max_bars}")
                self.persistent_backtest = PersistentBacktest(
                    init_data,
                    self.signal_strategy_class,
                    max_bars=max_bars,
                    **bt_kwargs
                )
                self.last_processed_timestamp = init_data.index[-1]
            
            # Check if we've already processed this timestamp
            if self.last_processed_timestamp is not None and current_timestamp <= self.last_processed_timestamp:
                logger.debug(f"Timestamp {current_timestamp} already processed, returning cached signal")
                # Return last signal or a HOLD if none available
                return TradingSignal(
                    signal=SignalType.HOLD,
                    price=self._safe_get_last_value(data['Close']),
                    timestamp=current_timestamp,
                    indicators={'status': 'duplicate_timestamp'}
                )
            
            # Process the new bar
            new_bar = data.iloc[-1]
            signal = self.persistent_backtest.step(new_bar)
            
            # Update tracking
            self.last_processed_timestamp = current_timestamp
            
            logger.debug(f"Persistent backtest processed bar for {current_timestamp}: {signal.signal.name}")
            return signal
            
        except Exception as e:
            logger.error(f"Persistent signal extraction failed: {e}")
            # Fallback to legacy method
            logger.debug("Falling back to legacy extraction method")
            return self._extract_signal_legacy(data)

    def reset(self):
        """Reset the signal extractor state"""
        if self.persistent_backtest:
            self.persistent_backtest.stop()
            self.persistent_backtest = None
        self.last_processed_timestamp = None
        logger.debug("BacktestingSignalExtractor reset completed")

    def get_stats(self) -> dict:
        """Get extractor statistics"""
        stats = {
            'use_persistent': self.use_persistent,
            'last_processed_timestamp': str(self.last_processed_timestamp) if self.last_processed_timestamp else None,
            'persistent_available': PERSISTENT_AVAILABLE,
        }
        
        if self.persistent_backtest:
            stats.update(self.persistent_backtest.get_stats())
        
        return stats


class BacktestingEngine(TradingEngine):
    """Trading engine implementation for backtesting.py"""

    # Set dependency management attributes
    _dependency_available_flag = BACKTESTING_AVAILABLE
    _dependency_help = (
        "backtesting.py support is not installed. Run:\n"
        "    pip install stratequeue[backtesting]\n"
        "or\n"
        "    pip install backtesting"
    )

    @classmethod
    def dependencies_available(cls) -> bool:
        """Check if backtesting.py dependencies are available"""
        return BACKTESTING_AVAILABLE

    def get_engine_info(self) -> EngineInfo:
        """Get information about this engine"""
        return build_engine_info(
            name="backtesting.py",
            lib_version="0.3.3",  # Common version
            description="Python backtesting library for trading strategies"
        )

    def is_valid_strategy(self, name: str, obj: Any) -> bool:
        """Check if object is a valid backtesting.py strategy"""
        return (
            inspect.isclass(obj)
            and hasattr(obj, "init")
            and hasattr(obj, "next")
            and name != "Strategy"
            and name != "SignalExtractorStrategy"
        )

    def create_engine_strategy(self, strategy_obj: Any) -> BacktestingEngineStrategy:
        """Create a backtesting engine strategy wrapper"""
        return BacktestingEngineStrategy(strategy_obj)

    def create_signal_extractor(
        self,
        engine_strategy: BacktestingEngineStrategy,
        *,
        granularity: str,
        **kwargs,
    ) -> BacktestingSignalExtractor:
        """Create a signal extractor for the given strategy (granularity mandatory)"""
        return BacktestingSignalExtractor(engine_strategy, granularity=granularity, **kwargs)
