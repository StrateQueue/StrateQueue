"""
Yahoo! Finance Data Source

Real-time and historical stock market data from Yahoo! Finance via yfinance library
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from .data_source_base import BaseDataIngestion, MarketData

logger = logging.getLogger(__name__)


class YahooFinanceDataIngestion(BaseDataIngestion):
    """Yahoo! Finance data ingestion for stock market signals"""

    def __init__(self, granularity: str = "1m"):
        super().__init__()
        
        # Validate and store granularity
        self.granularity = granularity
        parsed_granularity = self._parse_granularity(granularity)
        self.granularity_seconds = parsed_granularity.to_seconds()
        
        # Map StrateQueue granularities to yfinance intervals
        self.interval_map = {
            "1m": "1m",
            "2m": "2m", 
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "60m": "60m",
            "90m": "90m",
            "1h": "1h",
            "1d": "1d",
            "5d": "5d",
            "1wk": "1wk",
            "1mo": "1mo",
            "3mo": "3mo"
        }
        
        # Validate granularity is supported
        if granularity not in self.interval_map:
            supported = ", ".join(self.interval_map.keys())
            raise ValueError(f"Granularity '{granularity}' not supported by Yahoo Finance. Supported: {supported}")
        
        self.yf_interval = self.interval_map[granularity]
        
        # Real-time simulation parameters
        self.update_interval = max(60, self.granularity_seconds)  # Yahoo data updates every minute at best
        self.simulation_running = False
        self.simulation_thread = None
        self.subscribed_symbols = set()
        self._last_bar_time: dict[str, datetime] = {}
        
        logger.info(f"Yahoo Finance provider initialized with granularity {granularity} (interval: {self.yf_interval})")

    async def fetch_historical_data(self, symbol: str, days_back: int = 30, 
                                  granularity: str = "1m") -> pd.DataFrame:
        """
        Fetch historical OHLCV data from Yahoo Finance

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            days_back: Number of days of historical data
            granularity: Data granularity (e.g., '1m', '5m', '1h', '1d')
        """
        # Use provided granularity or fall back to instance default
        target_granularity = granularity
        if target_granularity not in self.interval_map:
            raise ValueError(f"Granularity '{target_granularity}' not supported by Yahoo Finance")
        
        yf_interval = self.interval_map[target_granularity]
        
        try:
            # Run yfinance download in thread to avoid blocking async code
            def _download():
                ticker = yf.Ticker(symbol)
                
                # For intraday data, Yahoo has limitations on historical range
                if yf_interval in ["1m", "2m", "5m", "15m", "30m"]:
                    # Intraday data limited to last 60 days
                    period = f"{min(days_back, 60)}d"
                else:
                    # Daily and longer intervals can go back further
                    period = f"{days_back}d"
                
                # Add retry logic for rate limiting
                import time
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        return ticker.history(
                            period=period,
                            interval=yf_interval,
                            auto_adjust=False,  # Keep raw OHLC data
                            prepost=False       # Regular trading hours only
                        )
                    except Exception as e:
                        if "Rate limited" in str(e) or "Too Many Requests" in str(e):
                            if attempt < max_retries - 1:
                                wait_time = (attempt + 1) * 2  # Exponential backoff
                                logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                                time.sleep(wait_time)
                                continue
                        raise e
                
                raise Exception("Max retries exceeded")
            
            # Execute download in thread pool
            df = await asyncio.to_thread(_download)
            
            if df.empty:
                logger.warning(f"No historical data returned for {symbol} with granularity {target_granularity}")
                return pd.DataFrame()
            
            # Normalize column names to match StrateQueue format
            df = df.rename(columns={
                'Open': 'Open',
                'High': 'High', 
                'Low': 'Low',
                'Close': 'Close',
                'Volume': 'Volume'
            })
            
            # Ensure we have the required columns
            required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                raise ValueError(f"Missing required columns in Yahoo Finance data: {missing_cols}")
            
            # Remove any rows with NaN values
            df = df.dropna()
            
            # Ensure timezone-naive datetime index
            if df.index.tz is not None:
                df.index = df.index.tz_convert(None)
            
            # Cache the data
            self.historical_data[symbol] = df
            
            logger.info(f"✅ Fetched {len(df)} historical bars for {symbol} from Yahoo Finance ({target_granularity})")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching Yahoo Finance historical data for {symbol}: {e}")
            return pd.DataFrame()

    def _fetch_current_quote(self, symbol: str) -> MarketData | None:
        """Fetch current quote for a symbol from Yahoo Finance"""
        try:
            ticker = yf.Ticker(symbol)
            
            # Get most recent data point
            hist = ticker.history(period="1d", interval=self.yf_interval)
            
            if hist.empty:
                logger.warning(f"No current data available for {symbol}")
                return None
            
            # Get the latest bar
            latest = hist.iloc[-1]
            timestamp = hist.index[-1].to_pydatetime()
            
            # Ensure timestamp is timezone-naive
            if timestamp.tzinfo is not None:
                timestamp = timestamp.replace(tzinfo=None)
            
            market_data = MarketData(
                symbol=symbol,
                timestamp=timestamp,
                open=float(latest['Open']),
                high=float(latest['High']),
                low=float(latest['Low']),
                close=float(latest['Close']),
                volume=int(latest['Volume'])
            )
            
            return market_data
            
        except Exception as e:
            logger.error(f"Error fetching current quote for {symbol}: {e}")
            return None

    def _simulation_loop(self):
        """Background thread that polls Yahoo Finance for real-time data simulation"""
        logger.info("Yahoo Finance real-time simulation started")
        
        while self.simulation_running:
            try:
                for symbol in list(self.subscribed_symbols):
                    market_data = self._fetch_current_quote(symbol)
                    
                    if market_data:
                        # Emit only if this is a new bar
                        last_ts = self._last_bar_time.get(symbol)
                        if last_ts is None or market_data.timestamp > last_ts:
                            # Update current bar cache and history
                            self.current_bars[symbol] = market_data
                            self._last_bar_time[symbol] = market_data.timestamp

                            # Append to historical data (avoids duplicates internally)
                            self.append_current_bar(symbol)

                            # Notify subscribers
                            self._notify_callbacks(market_data)

                            logger.debug(f"New bar {market_data.timestamp} for {symbol}: ${market_data.close:.2f}")
                        else:
                            logger.debug(f"Duplicate bar for {symbol} at {market_data.timestamp}, skipping")
                
                # Sleep until next update
                time.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in Yahoo Finance simulation loop: {e}")
                time.sleep(5)  # Brief pause before retrying

    def subscribe_to_symbol(self, symbol: str):
        """Subscribe to real-time data for a symbol"""
        symbol = symbol.upper()
        self.subscribed_symbols.add(symbol)
        logger.info(f"Subscribed to Yahoo Finance data for {symbol}")

    def start_realtime_feed(self):
        """Start the real-time data simulation"""
        if self.simulation_running:
            logger.warning("Yahoo Finance real-time feed already running")
            return
        
        self.simulation_running = True
        self.simulation_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.simulation_thread.start()
        logger.info("Yahoo Finance real-time feed started")

    def stop_realtime_feed(self):
        """Stop the real-time data simulation"""
        if not self.simulation_running:
            return
            
        self.simulation_running = False
        
        if self.simulation_thread and self.simulation_thread.is_alive():
            self.simulation_thread.join(timeout=2)
        
        logger.info("Yahoo Finance real-time feed stopped")

    def set_update_interval_from_granularity(self, granularity: str):
        """Set update interval based on granularity"""
        parsed = self._parse_granularity(granularity)
        # Yahoo Finance updates every minute at best, so minimum 60 seconds
        self.update_interval = max(60, parsed.to_seconds())
        logger.info(f"Yahoo Finance update interval set to {self.update_interval} seconds")

    def set_update_interval(self, seconds: float):
        """Set update interval manually"""
        # Minimum 60 seconds for Yahoo Finance
        self.update_interval = max(60, seconds)
        logger.info(f"Yahoo Finance update interval manually set to {self.update_interval} seconds") 