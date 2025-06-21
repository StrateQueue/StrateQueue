"""
Backtesting.py Engine Implementation

Implements the trading engine interface for backtesting.py strategies.
This module contains all the backtesting.py-specific logic for loading strategies
and extracting signals.
"""

import contextlib
import importlib.util
import inspect
import logging
import os
from typing import Any

import pandas as pd

# Conditional import for backtesting library
try:
    from backtesting import Backtest
    BACKTESTING_AVAILABLE = True
except ImportError as e:
    BACKTESTING_AVAILABLE = False
    Backtest = None
    # Don't log warning here - let the engine factory handle it

from ..core.signal_extractor import SignalType, TradingSignal
from ..core.strategy_loader import StrategyLoader
from .engine_base import EngineInfo, EngineSignalExtractor, EngineStrategy, TradingEngine

logger = logging.getLogger(__name__)


def is_available() -> bool:
    """Check if backtesting.py dependencies are available"""
    return BACKTESTING_AVAILABLE


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


class BacktestingSignalExtractor(EngineSignalExtractor):
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
            # Ensure we have enough data
            if len(historical_data) < self.min_bars_required:
                logger.warning("Insufficient historical data for signal extraction")
                return TradingSignal(
                    signal=SignalType.HOLD,
                    price=0.0,
                    timestamp=pd.Timestamp.now(),
                    indicators={},
                )

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
            return TradingSignal(
                signal=SignalType.HOLD,
                price=historical_data["Close"].iloc[-1] if len(historical_data) > 0 else 0.0,
                timestamp=pd.Timestamp.now(),
                indicators={},
                metadata={"error": str(e)},
            )

    def get_minimum_bars_required(self) -> int:
        """Get minimum number of bars needed for signal extraction"""
        return max(self.min_bars_required, self.engine_strategy.get_lookback_period())

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

    def __init__(self):
        if not BACKTESTING_AVAILABLE:
            raise ImportError(
                "backtesting.py support is not installed. Run:\n"
                "    pip install stratequeue[backtesting]\n"
                "or\n"
                "    pip install backtesting"
            )

    def get_engine_info(self) -> EngineInfo:
        """Get information about this engine"""
        return EngineInfo(
            name="backtesting.py",
            version="0.3.3",  # Common version
            supported_features={
                "signal_extraction": True,
                "live_trading": True,
                "multi_strategy": True,
                "limit_orders": True,
                "stop_orders": True,
            },
            description="Python backtesting library for trading strategies",
        )

    def load_strategy_from_file(self, strategy_path: str) -> BacktestingEngineStrategy:
        """Load a backtesting.py strategy from file"""
        try:
            if not os.path.exists(strategy_path):
                raise FileNotFoundError(f"Strategy file not found: {strategy_path}")

            # Load the module
            spec = importlib.util.spec_from_file_location("strategy_module", strategy_path)
            module = importlib.util.module_from_spec(spec)

            # No need to inject Order class - backtesting.py uses different order syntax

            spec.loader.exec_module(module)

            # Find strategy classes
            strategy_classes = []
            for name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and hasattr(obj, "init")
                    and hasattr(obj, "next")
                    and name != "Strategy"
                    and name != "SignalExtractorStrategy"
                ):
                    strategy_classes.append(obj)

            if not strategy_classes:
                raise ValueError(f"No valid strategy class found in {strategy_path}")

            if len(strategy_classes) > 1:
                logger.warning(
                    f"Multiple strategy classes found, using first one: {strategy_classes[0].__name__}"
                )

            strategy_class = strategy_classes[0]
            logger.info(f"Loaded strategy: {strategy_class.__name__} from {strategy_path}")

            # Create wrapper
            engine_strategy = BacktestingEngineStrategy(strategy_class)

            return engine_strategy

        except Exception as e:
            logger.error(f"Error loading strategy from {strategy_path}: {e}")
            raise

    def create_signal_extractor(
        self, engine_strategy: BacktestingEngineStrategy, **kwargs
    ) -> BacktestingSignalExtractor:
        """Create a signal extractor for the given strategy"""
        return BacktestingSignalExtractor(engine_strategy, **kwargs)

    def validate_strategy_file(self, strategy_path: str) -> bool:
        """Validate that a strategy file is compatible with this engine"""
        try:
            self.load_strategy_from_file(strategy_path)
            return True
        except Exception as e:
            logger.error(f"Strategy validation failed: {e}")
            return False
