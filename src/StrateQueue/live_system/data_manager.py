"""
Data Manager

Handles all data-related operations for the live trading system:
- Historical data initialization
- Real-time data updates
- Cumulative data management
- Data source coordination
"""

import asyncio
import logging

import pandas as pd

from ..data.ingestion import IngestionInit, setup_data_ingestion

logger = logging.getLogger(__name__)


class DataManager:
    """Manages data loading and real-time updates for live trading"""

    def __init__(
        self, symbols: list[str], data_source: str, granularity: str, lookback_period: int
    ):
        """
        Initialize DataManager

        Args:
            symbols: List of symbols to manage data for
            data_source: Data source type ("demo", "polygon", etc.)
            granularity: Data granularity (e.g., "1m", "5m")
            lookback_period: Required lookback period for strategies
        """
        self.symbols = symbols
        self.data_source = data_source
        self.granularity = granularity
        self.lookback_period = lookback_period

        # Data storage
        self.cumulative_data = {}
        self.data_ingester = None

    def initialize_data_source(self):
        """Initialize data ingestion source with real-time feed setup"""
        import os

        # Get API key if needed
        api_key = None
        if self.data_source == "polygon":
            api_key = os.getenv("POLYGON_API_KEY")
        elif self.data_source == "coinmarketcap":
            api_key = os.getenv("CMC_API_KEY")

        # Use the public helper with ONLINE mode (real-time feed + subscribe, no historical)
        self.data_ingester = setup_data_ingestion(
            data_source=self.data_source,
            symbols=self.symbols,
            days_back=max(5, self.lookback_period // 100),  # Not used in ONLINE mode
            api_key=api_key,
            granularity=self.granularity,
            mode=IngestionInit.ONLINE,
        )

        return self.data_ingester

    async def initialize_historical_data(self):
        """Initialize historical data for all symbols"""
        logger.info("Fetching initial historical data...")

        # Start real-time feed first so we can get live data even if historical fails
        self.data_ingester.start_realtime_feed()

        for symbol in self.symbols:
            try:
                # Subscribe to real-time data for this symbol
                self.data_ingester.subscribe_to_symbol(symbol)

                # Try to fetch historical data with granularity
                historical_data = await self.data_ingester.fetch_historical_data(
                    symbol,
                    days_back=max(5, self.lookback_period // 100),
                    granularity=self.granularity,
                )

                # Store the initial cumulative data
                self.cumulative_data[symbol] = historical_data.copy()

                logger.info(
                    f"✅ Loaded {len(historical_data)} initial historical bars for {symbol}"
                )

            except Exception as e:
                logger.error(f"Error loading historical data for {symbol}: {e}")

                # If historical data fails, start with empty DataFrame - we'll build from real-time
                self.cumulative_data[symbol] = pd.DataFrame()
                logger.info(
                    f"📊 Will build {symbol} data from real-time feeds only (no historical data available)"
                )

        # Give real-time feed a moment to get initial data
        await asyncio.sleep(2)

        # Check if we got any initial real-time data
        for symbol in self.symbols:
            current_data = self.data_ingester.get_current_data(symbol)
            if current_data and len(self.cumulative_data[symbol]) == 0:
                # Add the first real-time bar to start building data
                first_bar = pd.DataFrame(
                    {
                        "Open": [current_data.open],
                        "High": [current_data.high],
                        "Low": [current_data.low],
                        "Close": [current_data.close],
                        "Volume": [current_data.volume],
                    },
                    index=[current_data.timestamp],
                )

                self.cumulative_data[symbol] = first_bar
                logger.info(
                    f"🚀 Started building {symbol} data from first real-time bar: ${current_data.close:.2f}"
                )

    async def update_symbol_data(self, symbol: str):
        """Update data for a single symbol"""
        if self.data_source == "demo":
            # Append one new bar to cumulative data (simulating live environment)
            updated_data = self.data_ingester.append_new_bar(symbol)
            if len(updated_data) > 0:
                self.cumulative_data[symbol] = updated_data
                # Keep only the most recent `lookback_period` bars to cap memory usage
                if len(self.cumulative_data[symbol]) > self.lookback_period:
                    self.cumulative_data[symbol] = self.cumulative_data[symbol].tail(self.lookback_period).copy()
        else:
            # For real data sources (like CoinMarketCap), get current real-time data
            current_data = self.data_ingester.get_current_data(symbol)

            if current_data:
                # Add current real-time bar to cumulative data
                new_bar = pd.DataFrame(
                    {
                        "Open": [current_data.open],
                        "High": [current_data.high],
                        "Low": [current_data.low],
                        "Close": [current_data.close],
                        "Volume": [current_data.volume],
                    },
                    index=[current_data.timestamp],
                )

                if symbol in self.cumulative_data and len(self.cumulative_data[symbol]) > 0:
                    # Check if this is a new timestamp (avoid duplicates)
                    last_timestamp = self.cumulative_data[symbol].index[-1]
                    time_diff = (current_data.timestamp - last_timestamp).total_seconds()

                    # Add a new bar whenever we move to a *new* timestamp,
                    # or while we are still building up the initial look-back window.
                    need_more_bars = len(self.cumulative_data[symbol]) < self.lookback_period

                    if time_diff > 0 or need_more_bars:
                        self.cumulative_data[symbol] = pd.concat(
                            [self.cumulative_data[symbol], new_bar]
                        )
                        # Cap the stored history to the most recent `lookback_period` bars
                        if len(self.cumulative_data[symbol]) > self.lookback_period:
                            self.cumulative_data[symbol] = (
                                self.cumulative_data[symbol]
                                .tail(self.lookback_period)
                                .copy()
                            )
                        logger.debug(
                            f"📊 Added new bar for {symbol}: ${current_data.close:.8f} "
                            f"(time_diff: {time_diff}s, need_more: {need_more_bars})"
                        )
                    else:
                        logger.debug(
                            f"⏭️  Skipping duplicate bar for {symbol}: identical timestamp ({current_data.timestamp})"
                        )
                else:
                    # First bar
                    self.cumulative_data[symbol] = new_bar
                    logger.info(f"🎬 First bar for {symbol}: ${current_data.close:.2f}")
                    # No need to trim here – only one bar so far

    def get_symbol_data(self, symbol: str) -> pd.DataFrame:
        """Get cumulative data for a symbol"""
        data = self.cumulative_data.get(symbol, pd.DataFrame())
        # Always return at most the lookback window to avoid accidental over-allocation
        if len(data) > self.lookback_period:
            return data.tail(self.lookback_period).copy()
        return data

    def has_sufficient_data(self, symbol: str) -> bool:
        """Check if symbol has sufficient data for strategy"""
        data = self.get_symbol_data(symbol)
        return len(data) >= self.lookback_period

    def add_symbol_runtime(self, symbol: str) -> bool:
        """
        Add a new symbol to track at runtime

        Args:
            symbol: Symbol to add for data tracking

        Returns:
            True if symbol was added successfully
        """
        try:
            if symbol in self.symbols:
                logger.info(f"Symbol {symbol} already being tracked")
                return True

            # Add to symbol list
            self.symbols.append(symbol)

            # Initialize empty data storage
            self.cumulative_data[symbol] = pd.DataFrame()

            # Subscribe to symbol if using real data source
            if self.data_ingester and self.data_source != "demo":
                self.data_ingester.subscribe_to_symbol(symbol)

            logger.info(f"🔥 Added symbol {symbol} to data tracking at runtime")
            return True

        except Exception as e:
            logger.error(f"Failed to add symbol {symbol} at runtime: {e}")
            return False

    def get_tracked_symbols(self) -> list[str]:
        """Get list of currently tracked symbols"""
        return self.symbols.copy()

    def get_data_progress(self, symbol: str) -> tuple[int, int, float]:
        """Get data collection progress for a symbol"""
        data = self.get_symbol_data(symbol)
        current_bars = len(data)
        required_bars = self.lookback_period
        progress_pct = (current_bars / required_bars * 100) if required_bars > 0 else 100
        return current_bars, required_bars, progress_pct
