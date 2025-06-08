import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import pandas as pd

# Conditional imports for backtesting library
try:
    from backtesting import Backtest, Strategy
    from backtesting.lib import crossover
    BACKTESTING_AVAILABLE = True
except ImportError as e:
    BACKTESTING_AVAILABLE = False
    Backtest = None
    Strategy = None
    crossover = None

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Types of trading signals"""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE = "CLOSE"
    LIMIT_BUY = "LIMIT_BUY"
    LIMIT_SELL = "LIMIT_SELL"
    STOP_BUY = "STOP_BUY"
    STOP_SELL = "STOP_SELL"
    STOP_LIMIT_BUY = "STOP_LIMIT_BUY"
    STOP_LIMIT_SELL = "STOP_LIMIT_SELL"
    TRAILING_STOP_SELL = "TRAILING_STOP_SELL"
    TRAILING_STOP_BUY = "TRAILING_STOP_BUY"
    BRACKET_BUY = "BRACKET_BUY"
    BRACKET_SELL = "BRACKET_SELL"


class OrderFunction(str, Enum):
    """Zipline order function types"""
    ORDER = "order"
    ORDER_VALUE = "order_value"
    ORDER_PERCENT = "order_percent"
    ORDER_TARGET = "order_target"
    ORDER_TARGET_VALUE = "order_target_value"
    ORDER_TARGET_PERCENT = "order_target_percent"


class ExecStyle(str, Enum):
    """Zipline execution style types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


@dataclass
class TradingSignal:
    """Structured trading signal output with comprehensive order support"""

    signal: SignalType
    price: float
    timestamp: pd.Timestamp
    indicators: dict[str, float]  # Current indicator values
    metadata: dict[str, Any] = None
    
    # Original fields (backward compatibility)
    size: float | None = None  # Position size (e.g., 0.5 for 50% of equity)
    limit_price: float | None = None  # For limit orders
    stop_price: float | None = None  # For stop orders
    trail_percent: float | None = None  # For trailing stop orders (percentage)
    trail_price: float | None = None  # For trailing stop orders (absolute price)
    time_in_force: str = "gtc"  # Time in force (gtc, day, ioc, fok, opg, cls, etc.)
    strategy_id: str | None = None  # Strategy identifier for multi-strategy mode
    
    # New Zipline order mechanism fields
    order_function: OrderFunction = OrderFunction.ORDER  # Which Zipline helper was used
    execution_style: ExecStyle = ExecStyle.MARKET  # Execution style
    quantity: float | None = None  # Shares for order() function
    value: float | None = None  # Dollar value for order_value()
    percent: float | None = None  # Percentage for order_percent() (0.0-1.0)
    target_quantity: float | None = None  # Target shares for order_target()
    target_value: float | None = None  # Target value for order_target_value()
    target_percent: float | None = None  # Target percent for order_target_percent()
    
    # Exchange and routing
    exchange: str | None = None  # Specific exchange for routing
    
    # Order management
    order_id: str | None = None  # Order ID from Zipline (if any)
    
    def __post_init__(self):
        """Post-initialization to set defaults and validate data"""
        if self.metadata is None:
            self.metadata = {}
        
        # Backward compatibility: if size is set but quantity is not, copy it
        if self.size is not None and self.quantity is None:
            self.quantity = self.size


class SignalExtractorStrategy(Strategy if BACKTESTING_AVAILABLE else object):
    """
    Modified strategy that captures signals instead of executing trades.
    This allows us to extract the current signal from the last timestep.
    """

    def __init__(self, *args, **kwargs):
        if not BACKTESTING_AVAILABLE:
            raise ImportError(
                "backtesting.py support is not installed. Run:\n"
                "    pip install stratequeue[backtesting]\n"
                "or\n"
                "    pip install backtesting"
            )
        # Initialize with any arguments backtesting.py provides
        super().__init__(*args, **kwargs)

        self.current_signal = SignalType.HOLD
        self.indicators_values = {}
        self.signal_history = []

    def next(self):
        """
        Override this method in your strategy to:
        1. Calculate indicators
        2. Determine signal
        3. Store signal instead of executing trades
        """
        # This will be overridden by actual strategy implementations
        pass

    def set_signal(
        self,
        signal: SignalType,
        metadata: dict[str, Any] = None,
        size: float | None = None,
        limit_price: float | None = None,
        stop_price: float | None = None,
        trail_percent: float | None = None,
        trail_price: float | None = None,
        time_in_force: str = "gtc",
    ):
        """Set the current signal instead of calling buy/sell"""
        self.current_signal = signal

        # Store signal with current data
        # For live trading, use the data timestamp; for demo, the data timestamp will be simulated time
        signal_obj = TradingSignal(
            signal=signal,
            price=self.data.Close[-1],
            timestamp=(
                self.data.index[-1]
                if hasattr(self.data.index, "__getitem__")
                else pd.Timestamp.now()
            ),
            indicators=self.indicators_values.copy(),
            metadata=metadata or {},
            size=size,
            limit_price=limit_price,
            stop_price=stop_price,
            trail_percent=trail_percent,
            trail_price=trail_price,
            time_in_force=time_in_force,
        )

        self.signal_history.append(signal_obj)

    def set_limit_buy_signal(
        self,
        limit_price: float,
        size: float | None = None,
        metadata: dict[str, Any] = None,
    ):
        """Set a limit buy signal with specified limit price"""
        self.set_signal(SignalType.LIMIT_BUY, metadata, size, limit_price)

    def set_limit_sell_signal(
        self,
        limit_price: float,
        size: float | None = None,
        metadata: dict[str, Any] = None,
    ):
        """Set a limit sell signal with specified limit price"""
        self.set_signal(SignalType.LIMIT_SELL, metadata, size, limit_price)

    def get_current_signal(self) -> TradingSignal:
        """Get the most recent signal"""
        if self.signal_history:
            return self.signal_history[-1]
        else:
            return TradingSignal(
                signal=SignalType.HOLD,
                price=self.data.Close[-1] if len(self.data.Close) > 0 else 0.0,
                timestamp=pd.Timestamp.now(),
                indicators=self.indicators_values.copy(),
            )


class SmaCrossSignalStrategy(SignalExtractorStrategy):
    """
    Modified SMA Cross strategy that generates signals instead of trades
    """

    n1 = 10
    n2 = 20

    def init(self):
        # Import the SMA function
        if not BACKTESTING_AVAILABLE:
            raise ImportError(
                "backtesting.py support is not installed. Run:\n"
                "    pip install stratequeue[backtesting]\n"
                "or\n"
                "    pip install backtesting"
            )
        from backtesting.test import SMA

        close = self.data.Close
        self.sma1 = self.I(SMA, close, self.n1)
        self.sma2 = self.I(SMA, close, self.n2)

    def next(self):
        # Update indicator values for signal output
        self.indicators_values = {
            f"SMA_{self.n1}": self.sma1[-1],
            f"SMA_{self.n2}": self.sma2[-1],
            "price": self.data.Close[-1],
        }

        # Determine signal based on crossover
        if crossover(self.sma1, self.sma2):
            # Fast MA crosses above slow MA - bullish signal
            self.set_signal(SignalType.BUY)

        elif crossover(self.sma2, self.sma1):
            # Fast MA crosses below slow MA - bearish signal
            self.set_signal(SignalType.SELL)

        else:
            # No crossover - hold current position
            self.set_signal(SignalType.HOLD)


class LiveSignalExtractor:
    """
    Extracts live trading signals from backtesting.py strategies
    """

    def __init__(self, strategy_class, min_bars_required: int = 2, **strategy_params):
        """
        Initialize with a strategy class and its parameters

        Args:
            strategy_class: A SignalExtractorStrategy subclass
            min_bars_required: Minimum number of bars needed for signal extraction
            **strategy_params: Parameters to pass to the strategy
        """
        if not BACKTESTING_AVAILABLE:
            raise ImportError(
                "backtesting.py support is not installed. Run:\n"
                "    pip install stratequeue[backtesting]\n"
                "or\n"
                "    pip install backtesting"
            )
        self.strategy_class = strategy_class
        self.strategy_params = strategy_params
        self.min_bars_required = min_bars_required
        self.last_signal = None

    def extract_signal(self, historical_data: pd.DataFrame) -> TradingSignal:
        """
        Extract current trading signal from historical data

        Args:
            historical_data: DataFrame with OHLCV data, indexed by timestamp

        Returns:
            TradingSignal object with current signal
        """
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
            # Ensure columns are properly named
            required_columns = ["Open", "High", "Low", "Close", "Volume"]
            if not all(col in historical_data.columns for col in required_columns):
                logger.error(f"Historical data missing required columns: {required_columns}")
                raise ValueError("Invalid data format")

            data = historical_data[required_columns].copy()

            # Create a backtest instance but don't run full backtest
            # We'll manually step through to the last bar
            bt = Backtest(
                data,
                self.strategy_class,
                cash=10000,  # Dummy cash amount
                commission=0.0,  # No commission for signal extraction
                **self.strategy_params,
            )

            # Run the backtest to initialize strategy and process all historical data
            results = bt.run()

            # Extract the strategy instance to get the current signal
            strategy_instance = results._strategy

            # Get the current signal
            current_signal = strategy_instance.get_current_signal()

            self.last_signal = current_signal

            logger.info(
                f"Extracted signal: {current_signal.signal.value} "
                f"at price: ${current_signal.price:.2f}"
            )

            return current_signal

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


# Example usage and testing
if __name__ == "__main__":
    # Test the signal extractor with sample data
    import asyncio

    from data_ingestion import TestDataIngestion

    async def test_signal_extraction():
        """Test signal extraction with generated data"""
        print("=== Signal Extraction Test ===")

        # Generate test data
        data_ingestion = TestDataIngestion()
        historical_data = await data_ingestion.fetch_historical_data("AAPL", days_back=30)

        if len(historical_data) == 0:
            print("No historical data available for testing")
            return

        print(f"Generated {len(historical_data)} bars of test data")
        print(
            f"Price range: ${historical_data['Low'].min():.2f} - ${historical_data['High'].max():.2f}"
        )

        # Initialize signal extractor
        signal_extractor = LiveSignalExtractor(SmaCrossSignalStrategy, n1=10, n2=20)

        # Extract signal from different data windows to simulate live updates
        print("\nExtracting signals from different time windows:")

        for i in range(5):
            # Use progressively more data (simulating live updates)
            end_idx = len(historical_data) - 5 + i
            if end_idx <= 20:  # Need minimum data for indicators
                continue

            data_window = historical_data.iloc[:end_idx]
            signal = signal_extractor.extract_signal(data_window)

            print(
                f"Window {i+1}: {signal.signal.value} "
                f"at ${signal.price:.2f}"
            )

    # Run the test
    asyncio.run(test_signal_extraction())
