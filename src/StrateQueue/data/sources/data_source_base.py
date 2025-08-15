"""
Base Data Ingestion Classes

Defines the common interface that all data sources should implement.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

# Import granularity utilities
from ...core.granularity import Granularity, parse_granularity


@dataclass
class MarketData:
    """Standardized market data structure"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class BaseDataIngestion(ABC):
    """Abstract base class for all data ingestion sources"""

    # Granularity capability contract
    # None means "unrestricted or dynamic; provider should override classmethods"
    SUPPORTED_GRANULARITIES: set[str] | None = None
    DEFAULT_GRANULARITY: str = "1m"

    def __init__(self):
        self.current_bars: dict[str, MarketData] = {}
        self.historical_data: dict[str, pd.DataFrame] = {}
        self.data_callbacks: list[Callable[[MarketData], None]] = []

    def add_data_callback(self, callback: Callable[[MarketData], None]):
        """Add callback function to receive real-time data updates"""
        self.data_callbacks.append(callback)

    @abstractmethod
    async def fetch_historical_data(self, symbol: str, days_back: int = 30,
                                  granularity: str = "1m") -> pd.DataFrame:
        """
        Fetch historical OHLCV data

        Args:
            symbol: Symbol to fetch (e.g., 'AAPL', 'BTC')
            days_back: Number of days of historical data
            granularity: Data granularity (e.g., '1s', '1m', '5m', '1h', '1d')

        Returns:
            DataFrame with OHLCV data indexed by timestamp
        """
        pass



    @abstractmethod
    async def subscribe_to_symbol(self, symbol: str):
        """Subscribe to real-time data for a symbol (async for providers that need it)"""
        pass

    @abstractmethod
    def start_realtime_feed(self):
        """Start the real-time data feed"""
        pass

    def stop_realtime_feed(self):
        """Stop the real-time data feed (default implementation)"""
        pass

    def get_current_data(self, symbol: str) -> MarketData | None:
        """Get the most recent data for a symbol"""
        return self.current_bars.get(symbol)

    def get_backtesting_data(self, symbol: str) -> pd.DataFrame:
        """Get historical data formatted for backtesting"""
        return self.historical_data.get(symbol, pd.DataFrame())

    def append_current_bar(self, symbol: str) -> pd.DataFrame:
        """Append current real-time bar to historical data"""
        current_data = self.get_current_data(symbol)

        if current_data:
            # Convert current data to DataFrame row
            new_row = pd.DataFrame({
                'Open': [current_data.open],
                'High': [current_data.high],
                'Low': [current_data.low],
                'Close': [current_data.close],
                'Volume': [current_data.volume]
            }, index=[current_data.timestamp])

            # Append to historical data
            if symbol in self.historical_data:
                existing_data = self.historical_data[symbol]
                # Basic duplicate prevention
                if len(existing_data) == 0 or current_data.timestamp not in existing_data.index:
                    self.historical_data[symbol] = pd.concat([existing_data, new_row])
            else:
                self.historical_data[symbol] = new_row

            return self.historical_data[symbol]

        return self.get_backtesting_data(symbol)

    def _notify_callbacks(self, market_data: MarketData):
        """Notify all registered callbacks of new data"""
        for callback in self.data_callbacks:
            try:
                callback(market_data)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error in data callback: {e}")

    def _parse_granularity(self, granularity_str: str) -> Granularity:
        """Parse granularity string with validation"""
        return parse_granularity(granularity_str)

    # ------------------------------------------------------------------
    # Granularity capability helpers (override in providers as needed)
    # ------------------------------------------------------------------
    @classmethod
    def get_supported_granularities(cls, **_context) -> set[str]:
        """Return supported granularity tokens for this provider.

        If `SUPPORTED_GRANULARITIES` is None, treat as unrestricted/dynamic.
        Providers with dynamic capabilities should override this method and
        compute support from runtime context (e.g., exchange features).
        """
        return set(cls.SUPPORTED_GRANULARITIES or [])

    @classmethod
    def accepts_granularity(cls, granularity: str, **context) -> bool:
        """Return True if this provider accepts the given granularity token.

        Default behavior uses `SUPPORTED_GRANULARITIES` when present. Dynamic
        providers should override and use `get_supported_granularities(**context)`.
        """
        if cls.SUPPORTED_GRANULARITIES is None:
            # Unrestricted or dynamically determined – assume accepted by default
            return True
        return granularity in cls.SUPPORTED_GRANULARITIES

    def to_native_timeframe(self, g: Granularity):
        """Convert a parsed granularity to the provider's native timeframe.

        Default implementation returns the original token string. Providers
        should override if their SDK requires a specialized enum/object.
        """
        return str(g)

    def granularity_to_native(self, granularity: str):
        """Parse and convert a granularity token to native provider value."""
        return self.to_native_timeframe(self._parse_granularity(granularity))
