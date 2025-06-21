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
        min_bars_required: int = 2,
        **strategy_params,
    ):
        super().__init__(engine_strategy)
        self.strategy_class = engine_strategy.strategy_class
        self.strategy_params = strategy_params
        self.min_bars_required = min_bars_required

        # Convert original strategy to signal extractor
        self.signal_strategy_class = StrategyLoader.convert_to_signal_strategy(
            engine_strategy.strategy_class
        )

    def extract_signal(self, historical_data: pd.DataFrame) -> TradingSignal:
        """Extract trading signal from historical data using full backtest approach"""
        try:
            # Check for insufficient data first
            if (hold_signal := self._abort_insufficient_bars(historical_data)):
                return hold_signal

            # Prepare data for backtesting.py format
            required_columns = ["Open", "High", "Low", "Close", "Volume"]
            if not all(col in historical_data.columns for col in required_columns):
                logger.error(f"Historical data missing required columns: {required_columns}")
                raise ValueError("Invalid data format")

            data = historical_data[required_columns].copy()

            # Use the reliable full backtest approach
            return self._extract_signal_legacy(data)

        except Exception as e:
            logger.error(f"Error extracting signal: {e}")
            # Return safe default signal
            price = self._safe_get_last_value(historical_data["Close"]) if len(historical_data) > 0 else 0.0
            return self._safe_hold(price=price, error=e)

    def _extract_signal_legacy(self, data: pd.DataFrame) -> TradingSignal:
        """Legacy signal extraction method (full backtest each time)"""
        # Create a backtest instance and run full backtest
        bt = Backtest(
            data, self.signal_strategy_class, cash=10000, commission=0.0  # Dummy cash amount
        )  # No commission for signal extraction

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
        self, engine_strategy: BacktestingEngineStrategy, **kwargs
    ) -> BacktestingSignalExtractor:
        """Create a signal extractor for the given strategy"""
        return BacktestingSignalExtractor(engine_strategy, **kwargs)
