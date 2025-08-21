"""
Demo/Test Data Source

Simulated market data for testing and development
"""

import logging
import random
import threading
import time
from datetime import datetime, timedelta

import pandas as pd

from .data_source_base import BaseDataIngestion, MarketData
from ...core.resample import plan_base_granularity, resample_ohlcv

logger = logging.getLogger(__name__)


class TestDataIngestion(BaseDataIngestion):
    """Test data ingestor that generates realistic random market data for testing"""

    # Unrestricted for demo purposes
    SUPPORTED_GRANULARITIES = {
        "1s", "5s", "10s", "30s", "1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1w"
    }
    DEFAULT_GRANULARITY = "1m"

    def __init__(self, base_prices: dict[str, float] | None = None):
        super().__init__()

        # Base prices for different symbols (defaults if not provided)
        self.base_prices = base_prices or {
            "AAPL": 175.0,
            "MSFT": 350.0,
            "GOOGL": 2800.0,
            "TSLA": 250.0,
            "NVDA": 500.0,
            "BTC": 45000.0,
            "ETH": 3000.0,
        }

        # Current prices (will fluctuate from base prices)
        self.current_prices = self.base_prices.copy()

        # Simulation parameters
        self.update_interval = 1.0  # seconds between updates
        self.price_volatility = 0.02  # 2% volatility

        # Real-time simulation tracking
        self.is_connected = False
        self.stop_simulation = False
        self.simulation_thread = None
        self.subscribed_symbols: list[str] = []

        # Simulated time tracking for demo mode
        self.simulated_time = datetime.now()
        self.granularity_seconds = 60  # Default 1 minute

        # ------------------------------------------------------------------
        # Internal cache → key: (symbol, days_back, granularity) → DataFrame
        # This allows fetch_historical_data to return an *identical* object
        # for repeat calls with the same parameters, satisfying the test
        # expectation that `df1 is df2`.
        # ------------------------------------------------------------------
        self._historical_cache: dict[tuple[str, int, str], pd.DataFrame] = {}

    async def fetch_historical_data(
        self, symbol: str, days_back: int = 30, granularity: str = "1m"
    ) -> pd.DataFrame:
        """
        Generate historical test data that looks realistic

        Args:
            symbol: Symbol to generate data for
            days_back: Number of days of historical data
            granularity: Data granularity (e.g., '1s', '1m', '5m', '1h', '1d')
        """

        cache_key = (symbol, days_back, granularity)
        if cache_key in self._historical_cache:
            # Return the exact same object that was previously generated
            return self._historical_cache[cache_key]

        # Parse granularity to determine time intervals (support resampling from 1m base)
        parsed_granularity = self._parse_granularity(granularity)
        interval_seconds = parsed_granularity.to_seconds()

        # Calculate number of bars needed
        total_seconds = days_back * 86400  # days_back * seconds_per_day
        total_bars = total_seconds // interval_seconds

        # Limit total bars for performance (but be more generous than before)
        total_bars = min(total_bars, 50000)

        # Generate timestamps
        end_time = datetime.now()
        timestamps = []
        current_time = end_time - timedelta(seconds=total_bars * interval_seconds)

        for _i in range(int(total_bars)):
            timestamps.append(current_time)
            current_time += timedelta(seconds=interval_seconds)

        # Get base price for symbol (random between 0.25-500)
        base_price = self.base_prices.get(symbol, random.uniform(0.25, 500))

        # Generate realistic OHLCV data using random walk
        data = []
        current_price = base_price

        for timestamp in timestamps:
            # Random walk with 0.1% max deviation between candles
            price_change_pct = random.gauss(0, self.price_volatility)
            price_change_pct = max(-0.001, min(0.001, price_change_pct))  # Cap at 0.1%

            # Calculate new price
            new_price = current_price * (1 + price_change_pct)

            # Generate OHLC with all values within 0.1% of each other
            open_price = current_price
            close_price = new_price
            
            # High and low within 0.1% of open/close
            if new_price > current_price:
                # Upward movement
                high_price = close_price * (1 + random.uniform(0, 0.001))  # Max 0.1% above close
                low_price = open_price * (1 - random.uniform(0, 0.001))   # Max 0.1% below open
            else:
                # Downward movement
                high_price = open_price * (1 + random.uniform(0, 0.001))  # Max 0.1% above open
                low_price = close_price * (1 - random.uniform(0, 0.001))  # Max 0.1% below close

            # Generate volume (random between 2000-20000)
            volume = random.randint(2000, 20000)

            data.append(
                {
                    "Open": round(open_price, 2),
                    "High": round(high_price, 2),
                    "Low": round(low_price, 2),
                    "Close": round(close_price, 2),
                    "Volume": volume,
                    "timestamp": timestamp,
                }
            )

            current_price = close_price

        # Create DataFrame
        if not data:
            # Handle empty data case (e.g., days_back=0)
            df = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
            df.index = pd.DatetimeIndex([], name="timestamp")
        else:
            df = pd.DataFrame(data)
            df.set_index("timestamp", inplace=True)
            df.index = pd.to_datetime(df.index)

        # Resample support: if requested is a multiple of 1m or 1s, we could resample here as well.
        try:
            base_supported = {"1m"}
            target_token = f"{parsed_granularity.multiplier}{parsed_granularity.unit.value}"
            plan = None
            if target_token not in base_supported and len(data) > 0:
                # Build 1m base on the fly then resample
                # Here we already generated at target step, so only resample when coarser than 1m
                if parsed_granularity.to_seconds() > 60:
                    # Rebuild at 1m if feasible: if interval_seconds divides 60, or else skip
                    # For simplicity, rely on existing df and resample only if coarser
                    df = resample_ohlcv(df, target_token)
        except Exception:
            pass

        # Store in dedicated memo-cache **before** logging/returning so that
        # immediate subsequent calls hit the fast path above.
        self._historical_cache[cache_key] = df

        # Keep legacy attribute in sync so downstream code/tests relying on
        # provider.historical_data continue to work.
        self.historical_data[symbol] = df

        # Update current price
        if len(df) > 0:
            self.current_prices[symbol] = df["Close"].iloc[-1]

        logger.info(
            f"Generated {len(df)} test historical bars for {symbol} with granularity {granularity}"
        )
        return df

    def append_new_bar(self, symbol: str) -> pd.DataFrame:
        """Generate and append one new bar to historical data"""

        if symbol not in self.historical_data:
            logger.warning(f"No historical data for {symbol}, generating minimal data")
            # Generate minimal historical data synchronously instead of using async call
            self._generate_minimal_historical_data(symbol)

        # Get current price
        self.current_prices.get(symbol, self.base_prices.get(symbol, 100.0))

        # Generate new bar data similar to real-time simulation
        new_bar = self._generate_realtime_bar(symbol)

        if new_bar:
            # Convert to DataFrame row
            new_row = pd.DataFrame(
                {
                    "Open": [new_bar.open],
                    "High": [new_bar.high],
                    "Low": [new_bar.low],
                    "Close": [new_bar.close],
                    "Volume": [new_bar.volume],
                },
                index=[new_bar.timestamp],
            )

            # Append to existing data
            if symbol in self.historical_data:
                self.historical_data[symbol] = pd.concat([self.historical_data[symbol], new_row])
                # Ensure data is sorted by timestamp to avoid backtesting.py warnings
                self.historical_data[symbol] = self.historical_data[symbol].sort_index()
            else:
                self.historical_data[symbol] = new_row

            # Update current price
            self.current_prices[symbol] = new_bar.close

            # Update current bar
            self.current_bars[symbol] = new_bar

            return self.historical_data[symbol]

        return self.get_backtesting_data(symbol)

    def _generate_minimal_historical_data(self, symbol: str):
        """Generate minimal historical data synchronously for a new symbol"""
        # Set up basic parameters
        base_price = self.base_prices.get(symbol, random.uniform(0.25, 500))
        self.current_prices[symbol] = base_price

        # Generate just a few bars to start with (synchronously)
        minimal_bars = 10  # Just enough to get started
        data = []
        current_price = base_price

        # Create timestamps for the last few intervals
        from datetime import datetime, timedelta

        end_time = datetime.now()
        interval_seconds = getattr(self, "granularity_seconds", 60)  # Default to 1 minute

        for i in range(minimal_bars):
            timestamp = end_time - timedelta(seconds=(minimal_bars - i) * interval_seconds)

            # Simple price walk with 0.1% max deviation
            price_change_pct = random.gauss(0, 0.001)  # 0.1% volatility
            price_change_pct = max(-0.001, min(0.001, price_change_pct))  # Cap at 0.1%
            new_price = current_price * (1 + price_change_pct)

            # Generate OHLC with all values within 0.1% of each other
            open_price = current_price
            close_price = new_price
            
            if new_price > current_price:
                # Upward movement
                high_price = close_price * (1 + random.uniform(0, 0.001))  # Max 0.1% above close
                low_price = open_price * (1 - random.uniform(0, 0.001))   # Max 0.1% below open
            else:
                # Downward movement
                high_price = open_price * (1 + random.uniform(0, 0.001))  # Max 0.1% above open
                low_price = close_price * (1 - random.uniform(0, 0.001))  # Max 0.1% below close

            volume = random.randint(2000, 20000)

            data.append(
                {
                    "Open": round(open_price, 2),
                    "High": round(high_price, 2),
                    "Low": round(low_price, 2),
                    "Close": round(close_price, 2),
                    "Volume": volume,
                    "timestamp": timestamp,
                }
            )

            current_price = close_price

        # Create DataFrame
        if not data:
            # Handle empty data case (shouldn't happen in minimal generation, but be safe)
            df = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
            df.index = pd.DatetimeIndex([], name="timestamp")
        else:
            df = pd.DataFrame(data)
            df.set_index("timestamp", inplace=True)
            df.index = pd.to_datetime(df.index)

        # Cache the data
        self.historical_data[symbol] = df
        self.current_prices[symbol] = current_price

        logger.info(f"Generated {len(df)} minimal historical bars for {symbol}")

    def _generate_realtime_bar(self, symbol: str) -> MarketData:
        """Generate a single realistic bar for real-time simulation"""

        base_price = self.base_prices.get(symbol, random.uniform(0.25, 500))
        current_price = self.current_prices.get(symbol, base_price)

        # Random price movement with 0.1% max deviation
        price_change_pct = random.gauss(0, self.price_volatility)
        price_change_pct = max(-0.001, min(0.001, price_change_pct))  # Cap at 0.1%

        # Calculate new close price
        new_close = current_price * (1 + price_change_pct)

        # Generate OHLC with all values within 0.1% of each other
        open_price = current_price
        close_price = new_close
        
        if new_close > current_price:
            # Up bar
            high_price = close_price * (1 + random.uniform(0, 0.001))  # Max 0.1% above close
            low_price = open_price * (1 - random.uniform(0, 0.001))   # Max 0.1% below open
        else:
            # Down bar
            high_price = open_price * (1 + random.uniform(0, 0.001))  # Max 0.1% above open
            low_price = close_price * (1 - random.uniform(0, 0.001))  # Max 0.1% below close

        # Generate volume (random between 2000-20000)
        volume = random.randint(2000, 20000)

        # Use simulated time progression for demo mode (advance by granularity interval)
        self.simulated_time += timedelta(seconds=self.granularity_seconds)

        return MarketData(
            symbol=symbol,
            timestamp=self.simulated_time,
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=volume,
        )

    def _simulation_loop(self):
        """Main simulation loop for generating real-time data"""
        logger.info("Starting test data simulation")

        while not self.stop_simulation:
            for symbol in self.subscribed_symbols:
                try:
                    # Generate new bar
                    market_data = self._generate_realtime_bar(symbol)

                    # Update current data
                    self.current_bars[symbol] = market_data
                    self.current_prices[symbol] = market_data.close

                    # Notify callbacks
                    self._notify_callbacks(market_data)

                except Exception as e:
                    logger.error(f"Error generating data for {symbol}: {e}")

            time.sleep(self.update_interval)

        logger.info("Test data simulation stopped")

    async def subscribe_to_symbol(self, symbol: str):
        """Subscribe to real-time data for a symbol"""
        if symbol not in self.subscribed_symbols:
            self.subscribed_symbols.append(symbol)
            logger.info(f"Subscribed to test data for {symbol}")

            # Initialize current price if not exists
            if symbol not in self.current_prices:
                self.current_prices[symbol] = self.base_prices.get(symbol, random.uniform(0.25, 500))

    def start_realtime_feed(self):
        """Start the real-time data simulation"""
        self.is_connected = True
        self.stop_simulation = False

        # Start simulation in separate thread
        self.simulation_thread = threading.Thread(target=self._simulation_loop)
        self.simulation_thread.daemon = True
        self.simulation_thread.start()

        logger.info("Test data real-time feed started")

    def stop_realtime_feed(self):
        """Stop the real-time data simulation"""
        self.stop_simulation = True
        self.is_connected = False

        if self.simulation_thread and self.simulation_thread.is_alive():
            self.simulation_thread.join(timeout=2.0)

        logger.info("Test data real-time feed stopped")

    def set_update_interval_from_granularity(self, granularity: str):
        """Set the update interval based on granularity"""
        try:
            parsed_granularity = self._parse_granularity(granularity)
            interval_seconds = parsed_granularity.to_seconds()

            # Use the exact granularity as the update interval (no artificial capping for demo)
            self.update_interval = interval_seconds
            self.granularity_seconds = interval_seconds  # Store for simulated time progression

            logger.info(
                f"Demo update interval set to {self.update_interval} seconds based on granularity {granularity}"
            )
        except Exception as e:
            logger.warning(
                f"Could not parse granularity {granularity}, using default interval: {e}"
            )

    def set_update_interval(self, seconds: float):
        """Set the interval between data updates"""
        self.update_interval = seconds

    def set_volatility(self, volatility: float):
        """Set the price volatility (e.g., 0.02 for 2%)"""
        self.price_volatility = volatility

    def set_base_price(self, symbol: str, price: float):
        """Set base price for a symbol"""
        self.base_prices[symbol] = price
        self.current_prices[symbol] = price
