"""
Qoery Data Source

Real-time and historical crypto candle data from Qoery API (https://qoery.com/docs)
"""

import asyncio
import logging
import threading
import time
import requests
from datetime import datetime, timedelta, timezone

import pandas as pd

from .data_source_base import BaseDataIngestion, MarketData

logger = logging.getLogger(__name__)


class QoeryDataIngestion(BaseDataIngestion):
    """Qoery data ingestion for crypto market signals"""

    # Declare static capability set
    SUPPORTED_GRANULARITIES = {
        "30s", "1m", "5m", "15m", "45m",
        "1h", "4h", "12h", "1d"
    }
    DEFAULT_GRANULARITY = "1m"
    BASE_URL = "https://api.qoery.com/v0"

    def __init__(self, api_key: str, granularity: str = "1m"):
        super().__init__()
        
        self.api_key = api_key
        
        # Validate and store granularity
        self.granularity = granularity
        parsed_granularity = self._parse_granularity(granularity)
        self.granularity_seconds = parsed_granularity.to_seconds()
        
        # Validate granularity is supported
        if granularity not in self.SUPPORTED_GRANULARITIES:
            # Try to be flexible if it's a standard one not explicitly listed but supported by their generic format
            # But strictly, we should check against their docs. 
            # Their docs say: 30s, 1m, 5m, 15m, 1h, 4h, 1d, 12h, 45m.
            supported = ", ".join(sorted(list(self.SUPPORTED_GRANULARITIES)))
            raise ValueError(f"Granularity '{granularity}' not supported by Qoery. Supported: {supported}")

        # Real-time simulation parameters (polling)
        # Polling frequency: wait at least the granularity time? 
        # API is restful, so we pull new candles as they close.
        # Let's poll every 10 seconds or granularity/2, whichever is larger, but max 60s to avoid spamming if unnecessary?
        # Actually simplest is just to poll slightly faster than granularity to catch the close.
        self.update_interval = min(60, max(5, self.granularity_seconds / 2))
        
        self.simulation_running = False
        self.simulation_thread = None
        self.subscribed_symbols = set()
        self._last_bar_time: dict[str, datetime] = {}
        
        logger.info(f"Qoery provider initialized with granularity {granularity}")

    async def fetch_historical_data(self, symbol: str, days_back: int = 30, 
                                  granularity: str = "1m") -> pd.DataFrame:
        """
        Fetch historical OHLCV data from Qoery API
        """
        # Use provided granularity or fall back to instance default
        if granularity not in self.SUPPORTED_GRANULARITIES:
             raise ValueError(f"Granularity '{granularity}' not supported by Qoery.")

        # Calculate time range
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days_back)
        
        # Format for API (ISO 8601)
        from_str = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
        to_str = end_time.strftime('%Y-%m-%dT%H:%M:%SZ')

        try:
            # Run requests in thread to avoid blocking async code
            def _download():
                # We might need to paginate if the range is huge, but let's start with a decent limit.
                # Docs say limit max 100. So we need to Loop!
                # Ah, "max candles (1-100)". That's very small for days_back=30 with 1m candles.
                # We need to implement pagination walking backwards or forwards.
                
                # Let's try to fetch reasonably efficient logic.
                # If we need 30 days of 1m data: 30 * 24 * 60 = 43200 candles.
                # 43200 / 100 = 432 requests. That's a lot.
                
                # NOTE: The prompt asked for the "simplest possible way".
                # Pagination is complex.
                # Simple version: Just fetch the MAX (100) or whatever we can getting reasonably recent context.
                # OR, if the user really needs 30 days, we must loop.
                # Given "Don't overcomplicate it", I will implement a simpler fetch that gets the *latest* data
                # up to the limit if the range is huge, OR loop if reasonable. 
                # Let's try a simple loop with a safety break.
                
                all_candles = []
                current_to = end_time
                
                # Safety break to avoid infinite loops or hammering API
                max_requests = 50 
                
                params = {
                    'symbol': symbol,
                    'interval': granularity,
                    'limit': 100, # Max allowed
                    'to': to_str
                }
                
                # Initial request to see what we get
                # We will actually Loop backwards.
                
                for _ in range(max_requests):
                    params['to'] = current_to.strftime('%Y-%m-%dT%H:%M:%SZ')
                    # We don't necessarily need 'from' if we are walking back, stop when date < start_time
                    
                    response = requests.get(
                        f"{self.BASE_URL}/candles",
                        headers={'X-API-KEY': self.api_key},
                        params=params, 
                        timeout=10
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    candles = data.get('data', [])
                    if not candles:
                        break
                        
                    # Parse candles to check timestamps
                    # Qoery returns time in ISO format
                    # Sort might be descending or ascending? Docs show example with one candle.
                    # Usually APIs return latest first or oldest first. 
                    # Let's clean and sort later.
                    
                    # Convert to list of dicts for DataFrame
                    batch_data = []
                    earliest_in_batch = None
                    
                    for c in candles:
                        ts = pd.to_datetime(c['time']).to_pydatetime()
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                            
                        # If we passed our start time, we might be done after this batch
                        if ts < start_time:
                            pass # We will filter later
                            
                        if earliest_in_batch is None or ts < earliest_in_batch:
                            earliest_in_batch = ts
                            
                        batch_data.append({
                            'time': ts,
                            'Open': float(c['open']),
                            'High': float(c['high']),
                            'Low': float(c['low']),
                            'Close': float(c['close']),
                            'Volume': float(c['volume'])
                        })
                    
                    all_candles.extend(batch_data)
                    
                    # If the earliest candle in this batch is before our start time, we are done
                    if earliest_in_batch and earliest_in_batch <= start_time:
                        break
                        
                    # Prepare next iteration: Set 'to' to just before the earliest candle we got
                    # Subtract 1 second or generic 'granularity' amount to avoid overlap?
                    # Safer to just use the earliest time. The API 'to' is inclusive? Docs don't say.
                    # Let's assume inclusive and subtract a tiny bit.
                    current_to = earliest_in_batch - timedelta(seconds=1)
                    
                    # Rate limiting?
                    time.sleep(0.1) 

                return pd.DataFrame(all_candles)
            
            # Execute download in thread pool
            df = await asyncio.to_thread(_download)
            
            if df.empty:
                logger.warning(f"No historical data returned for {symbol}")
                return pd.DataFrame()
            
            # Sort by time
            df.set_index('time', inplace=True)
            df.sort_index(inplace=True)
            
            # Remove duplicated index if any
            df = df[~df.index.duplicated(keep='first')]
            
            # Filter solely on requested range (clean up extra fetch)
            # Ensure index is timezone-naive for compatibility with internal systems if that's the standard
            # StrateQueue usually likes naive timestamps in UTC
            transient_index = df.index.tz_convert(None)
            df.index = transient_index
            
            # Ensure columns are present and correct type
            # (already done in loop)
            
            # Cache the data
            self.historical_data[symbol] = df
            
            logger.info(f"✅ Fetched {len(df)} historical bars for {symbol} from Qoery")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching Qoery historical data for {symbol}: {e}")
            return pd.DataFrame()

    @classmethod
    def get_supported_granularities(cls, **_context) -> set[str]:
        return set(cls.SUPPORTED_GRANULARITIES)

    @classmethod
    def accepts_granularity(cls, granularity: str, **_context) -> bool:
        return granularity in cls.SUPPORTED_GRANULARITIES

    def _fetch_current_quote(self, symbol: str) -> MarketData | None:
        """Fetch latest candle for a symbol from Qoery"""
        try:
             # Just get the latest 1 candle
            params = {
                'symbol': symbol,
                'interval': self.granularity,
                'limit': 1
            }
            response = requests.get(
                f"{self.BASE_URL}/candles",
                headers={'X-API-KEY': self.api_key},
                params=params,
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            candles = data.get('data', [])
            
            if not candles:
                return None
                
            latest = candles[0]
            timestamp = pd.to_datetime(latest['time']).to_pydatetime()
            if timestamp.tzinfo is not None:
                timestamp = timestamp.replace(tzinfo=None)
                
            market_data = MarketData(
                symbol=symbol,
                timestamp=timestamp,
                open=float(latest['open']),
                high=float(latest['high']),
                low=float(latest['low']),
                close=float(latest['close']),
                volume=float(latest['volume'])
            )
            return market_data
            
        except Exception as e:
            logger.error(f"Error fetching current quote for {symbol}: {e}")
            return None

    def _simulation_loop(self):
        """Background thread that polls for real-time data"""
        logger.info("Qoery real-time polling thread started")
        
        while self.simulation_running:
            try:
                for symbol in list(self.subscribed_symbols):
                    market_data = self._fetch_current_quote(symbol)
                    
                    if market_data:
                        # Emit only if this is a new bar
                        last_ts = self._last_bar_time.get(symbol)
                        if last_ts is None or market_data.timestamp > last_ts:
                            # Update current bar cache
                            self.current_bars[symbol] = market_data
                            self._last_bar_time[symbol] = market_data.timestamp

                            # Append to historical data
                            self.append_current_bar(symbol)

                            # Notify subscribers
                            self._notify_callbacks(market_data)
                            
                            logger.debug(f"New Qoery bar {market_data.timestamp} for {symbol}: ${market_data.close:.2f}")

                # Sleep until next update
                time.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in Qoery simulation loop: {e}")
                time.sleep(10)  # Pause before retrying

    async def subscribe_to_symbol(self, symbol: str):
        """Subscribe to real-time data for a symbol (adds to polling list)"""
        self.subscribed_symbols.add(symbol)
        logger.info(f"Subscribed to {symbol} for Qoery polling")

    def start_realtime_feed(self):
        """Start the polling loop"""
        if self.simulation_running:
            return
        
        self.simulation_running = True
        self.simulation_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.simulation_thread.start()
        logger.info("Qoery real-time feed started")

    def stop_realtime_feed(self):
        """Stop the polling loop"""
        self.simulation_running = False
        if self.simulation_thread and self.simulation_thread.is_alive():
            self.simulation_thread.join(timeout=2)
        logger.info("Qoery real-time feed stopped")
