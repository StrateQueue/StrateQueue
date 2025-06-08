"""
Data Ingestion Utilities

High-level utilities for setting up data ingestion with historical data fetching.
"""

import asyncio
import logging
import time
from collections import defaultdict
from enum import Enum, auto

# Load environment variables from .env file
from dotenv import load_dotenv

# Import the factory system
from .provider_factory import create_data_source
from .sources import BaseDataIngestion, CoinMarketCapDataIngestion, MarketData, PolygonDataIngestion

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IngestionInit(Enum):
    """Initialization modes for data ingestion setup"""

    FULL = auto()  # build object, start real-time feed, subscribe, fetch history
    ONLINE = auto()  # build + start feed + subscribe, caller will fetch history later
    CONSTRUCT = auto()  # only build object, caller does the rest


def setup_data_ingestion(
    data_source: str,
    symbols: list[str],
    days_back: int = 30,
    api_key: str | None = None,
    granularity: str = "1m",
    mode: IngestionInit = IngestionInit.FULL,
) -> BaseDataIngestion:
    """
    Set up and initialize a data ingestion source with configurable initialization

    Args:
        data_source: Type of data source ('polygon', 'coinmarketcap', 'demo')
        symbols: List of symbols to fetch data for
        days_back: Number of days of historical data to fetch (only used in FULL mode)
        api_key: API key for external data sources
        granularity: Data granularity (e.g., '1s', '1m', '5m', '1h', '1d')
        mode: Initialization mode:
            - FULL: Complete setup with historical data (default, backward compatible)
            - ONLINE: Setup real-time feed but skip historical data fetch
            - CONSTRUCT: Only create the data source object, no additional setup

    Returns:
        Configured data ingestion instance
    """

    # Create data source using the factory
    data_ingestion = create_data_source(data_source, api_key, granularity)

    # Start real-time feed and subscribe to symbols for FULL and ONLINE modes
    if mode in (IngestionInit.FULL, IngestionInit.ONLINE):
        data_ingestion.start_realtime_feed()

        # For live data sources, subscribe to symbols
        if data_source != "demo":
            for symbol in symbols:
                data_ingestion.subscribe_to_symbol(symbol)

    # Fetch historical data only for FULL mode
    if mode == IngestionInit.FULL:
        # Fetch historical data for all symbols
        async def fetch_all_historical():
            tasks = []
            for symbol in symbols:
                task = data_ingestion.fetch_historical_data(symbol, days_back, granularity)
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for symbol, result in zip(symbols, results, strict=False):
                if isinstance(result, Exception):
                    logger.error(f"Failed to fetch historical data for {symbol}: {result}")
                else:
                    logger.info(f"Successfully fetched {len(result)} bars for {symbol}")

        # Run the historical data fetching
        try:
            asyncio.run(fetch_all_historical())
        except Exception as e:
            logger.error(f"Error during historical data setup: {e}")

    logger.info(
        f"Data ingestion setup complete for {data_source} with granularity {granularity} (mode: {mode.name})"
    )
    return data_ingestion


class MinimalSignalGenerator:
    """Minimal example of how to use the data for signal generation"""

    def __init__(self, data_ingestion: BaseDataIngestion):
        self.data_ingestion = data_ingestion
        self.data_ingestion.add_data_callback(self.on_new_data)

        # Simple moving average parameters
        self.short_window = 10
        self.long_window = 20
        self.price_history = defaultdict(list)

    def on_new_data(self, market_data: MarketData):
        """Process new market data and generate signals"""
        symbol = market_data.symbol
        price = market_data.close

        # Keep price history
        self.price_history[symbol].append(price)
        if len(self.price_history[symbol]) > self.long_window:
            self.price_history[symbol].pop(0)

        # Generate simple moving average crossover signal
        if len(self.price_history[symbol]) >= self.long_window:
            short_ma = sum(self.price_history[symbol][-self.short_window :]) / self.short_window
            long_ma = sum(self.price_history[symbol]) / len(self.price_history[symbol])

            if short_ma > long_ma:
                signal = "BUY"
            elif short_ma < long_ma:
                signal = "SELL"
            else:
                signal = "HOLD"

            logger.info(
                f"{symbol}: {signal} - Price: {price}, Short MA: {short_ma:.2f}, Long MA: {long_ma:.2f}"
            )


def demo_test_data_ingestion():
    """Demonstration of test data ingestion functionality"""
    print("\n=== Test Data Ingestion Demo ===")

    # Setup test data ingestion
    data_ingestion = setup_data_ingestion(
        data_source="demo", symbols=["AAPL", "MSFT", "TSLA"], days_back=5, granularity="1m"
    )

    # Setup signal generator
    MinimalSignalGenerator(data_ingestion)

    # Test symbols
    symbols = ["AAPL", "MSFT", "TSLA"]

    print("Generating historical data...")
    # Fetch historical data
    for symbol in symbols:
        historical_data = asyncio.run(
            data_ingestion.fetch_historical_data(
                symbol, days_back=5, granularity="1m"  # Shorter for demo
            )
        )
        print(f"Generated {len(historical_data)} historical bars for {symbol}")
        if len(historical_data) > 0:
            print(
                f"  Price range: ${historical_data['Low'].min():.2f} - ${historical_data['High'].max():.2f}"
            )

    print("\nStarting real-time data simulation...")

    # Configure simulation parameters
    data_ingestion.set_update_interval(0.5)  # Update every 0.5 seconds for faster demo
    data_ingestion.set_volatility(0.01)  # Lower volatility for demo

    # Start real-time feed
    data_ingestion.start_realtime_feed()

    # Wait for connection
    time.sleep(1)

    # Subscribe to symbols
    for symbol in symbols:
        data_ingestion.subscribe_to_symbol(symbol)

    print("Test data simulation running...")
    print("Real-time data updates (press Ctrl+C to stop):")

    try:
        # Let it run for a demo period
        start_time = time.time()
        while time.time() - start_time < 30:  # Run for 30 seconds
            time.sleep(1)

            # Show current prices
            current_prices = {}
            for symbol in symbols:
                current_data = data_ingestion.get_current_data(symbol)
                if current_data:
                    current_prices[symbol] = current_data.close

            if current_prices:
                price_str = " | ".join(
                    [f"{sym}: ${price:.2f}" for sym, price in current_prices.items()]
                )
                print(f"Current prices: {price_str}")

    except KeyboardInterrupt:
        print("\nDemo interrupted by user")

    finally:
        # Stop simulation
        data_ingestion.stop_realtime_feed()
        print("Test data simulation stopped")
        print("Demo completed!")


if __name__ == "__main__":
    # Parse command line arguments for demo selection
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        # Run test data demo
        demo_test_data_ingestion()
    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        # Run quick test mode
        print("Quick test mode - generating sample data...")

        # Quick test of demo data ingestor
        test_ingestion = setup_data_ingestion(data_source="demo")

        # Generate some historical data
        symbols = ["AAPL", "MSFT"]
        for symbol in symbols:
            data = asyncio.run(test_ingestion.fetch_historical_data(symbol, days_back=2))
            print(f"{symbol}: Generated {len(data)} bars")
            if len(data) > 0:
                print(f"  Latest close: ${data['Close'].iloc[-1]:.2f}")

        print("Quick test completed!")

    else:
        # Original example usage with real data
        try:
            # Setup - will try real data first, fall back to test data
            try:
                data_ingestion = setup_data_ingestion(data_source="polygon")
                print("Using real Polygon.io data")
            except ValueError as e:
                print(f"Polygon API key not found: {e}")
                print("Falling back to test data...")
                data_ingestion = setup_data_ingestion(data_source="demo")

            signal_generator = MinimalSignalGenerator(data_ingestion)

            # Fetch historical data first
            symbols = ["AAPL", "MSFT", "GOOGL"]
            for symbol in symbols:
                historical_data = asyncio.run(
                    data_ingestion.fetch_historical_data(symbol, days_back=30)
                )
                print(f"Historical data for {symbol}: {len(historical_data)} bars")

            # Start real-time feed
            if isinstance(data_ingestion, PolygonDataIngestion):
                # Real data - use WebSocket thread
                import threading

                ws_thread = threading.Thread(target=data_ingestion.start_realtime_feed)
                ws_thread.daemon = True
                ws_thread.start()
            elif isinstance(data_ingestion, CoinMarketCapDataIngestion):
                # CoinMarketCap data - start simulation
                data_ingestion.start_realtime_feed()
            else:
                # Test data - start simulation
                data_ingestion.start_realtime_feed()

            # Wait for connection
            time.sleep(2)

            # Subscribe to symbols
            for symbol in symbols:
                data_ingestion.subscribe_to_symbol(symbol)

            # Keep running
            print("Data ingestion started. Press Ctrl+C to stop.")
            print("Commands:")
            print("  python3.10 data_ingestion.py demo    - Run test data demo")
            print("  python3.10 data_ingestion.py test    - Quick test")
            print("  python3.10 data_ingestion.py         - Run with real/fallback data")

            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            print("Stopping data ingestion...")
        except Exception as e:
            logger.error(f"Error: {e}")
