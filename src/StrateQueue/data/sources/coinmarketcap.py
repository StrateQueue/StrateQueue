"""
CoinMarketCap Data Source

Cryptocurrency data from CoinMarketCap Pro API
"""

import logging
import os
import threading
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

from ...core.granularity import TimeUnit
from .data_source_base import BaseDataIngestion, MarketData

logger = logging.getLogger(__name__)


class CoinMarketCapDataIngestion(BaseDataIngestion):
    """CoinMarketCap data ingestion for cryptocurrency signals"""

    def __init__(self, api_key: str = None, granularity: str = "1d"):
        """Initialize CoinMarketCap data source with granularity validation"""
        super().__init__()

        # Validate granularity early
        parsed_granularity = self._parse_granularity(granularity)
        if parsed_granularity.to_seconds() < 60:
            raise Exception(f"CoinMarketCap does not support {granularity} granularity. CMC only updates every 60 seconds, so minimum supported granularity is 1 minute ('1m').")

        self.api_key = api_key or os.getenv('CMC_API_KEY')
        if not self.api_key:
            raise ValueError("CoinMarketCap API key is required. Set CMC_API_KEY environment variable.")

        self.rest_base_url = "https://pro-api.coinmarketcap.com"
        self.ws_base_url = None  # CMC doesn't have public WebSocket API

        # Track subscribed symbols
        self.subscribed_symbols = set()
        self.historical_data = {}
        self.symbol_id_cache = {}
        self.symbol_to_id = {}  # Initialize symbol to ID mapping

        # Set granularity and calculate update interval
        self.granularity = granularity
        parsed = self._parse_granularity(granularity)
        self.granularity_seconds = parsed.to_seconds()

        # CMC updates every 60 seconds, so for granularities >= 1m, use that interval
        # For exactly 1m, update every 60s. For longer intervals, still check every 60s
        # but only emit signals at the appropriate granularity boundary
        if self.granularity_seconds >= 60:
            self.update_interval = 60  # Always check every 60s for fresh data
            logger.info(f"CMC update interval set to 60 seconds based on granularity {granularity}")
        else:
            # This should not happen due to validation above, but just in case
            raise Exception(f"Unsupported granularity {granularity} for CoinMarketCap")

        # For simulation and time tracking
        self.simulated_time = datetime.utcnow()
        self.last_signal_time = None

        # Real-time simulation
        self.simulation_running = False
        self.simulation_thread = None

    async def _fetch_symbol_id(self, symbol: str) -> int | None:
        """Fetch CoinMarketCap ID for a symbol"""
        if symbol in self.symbol_to_id:
            return self.symbol_to_id[symbol]

        url = f"{self.rest_base_url}/v1/cryptocurrency/map"
        headers = {
            'X-CMC_PRO_API_KEY': self.api_key,
            'Content-Type': 'application/json'
        }
        params = {
            'symbol': symbol,
            'limit': 1
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get('data') and len(data['data']) > 0:
                cmc_id = data['data'][0]['id']
                self.symbol_to_id[symbol] = cmc_id
                logger.info(f"Found CMC ID {cmc_id} for symbol {symbol}")
                return cmc_id
            else:
                logger.warning(f"No CMC ID found for symbol {symbol}")
                return None

        except Exception as e:
            logger.error(f"Error fetching CMC ID for {symbol}: {e}")
            return None

    async def fetch_historical_data(self, symbol: str, days_back: int = 30,
                                  granularity: str = "1d") -> pd.DataFrame:
        """
        Fetch historical cryptocurrency data from CoinMarketCap

        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTC')
            days_back: Number of days of historical data
            granularity: Data granularity (e.g., '1d' for daily)
        """
        # Parse granularity to determine if we can fetch historical data
        parsed_granularity = self._parse_granularity(granularity)

        # CMC historical API only supports daily data
        if parsed_granularity.unit == TimeUnit.DAY:
            return await self._fetch_daily_historical_data(symbol, days_back)
        else:
            # For intraday granularities, we cannot provide historical data
            # But we should clarify that real-time data is available for 1m+
            if parsed_granularity.to_seconds() >= 60:
                raise Exception(f"CoinMarketCap does not support {granularity} historical data. Only daily ('1d') historical data is available. However, real-time {granularity} data updates are available via live feeds (CMC updates every 60 seconds).")
            else:
                raise Exception(f"CoinMarketCap does not support {granularity} granularity. CMC only updates every 60 seconds, so minimum supported granularity is 1 minute ('1m').")

    async def _fetch_daily_historical_data(self, symbol: str, days_back: int) -> pd.DataFrame:
        """Fetch actual daily historical data from CMC"""
        # Get CMC ID for the symbol
        cmc_id = await self._fetch_symbol_id(symbol)
        if not cmc_id:
            raise Exception(f"Cannot fetch historical data for {symbol} - symbol not found in CoinMarketCap")

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        url = f"{self.rest_base_url}/v1/cryptocurrency/ohlcv/historical"
        headers = {
            'X-CMC_PRO_API_KEY': self.api_key,
            'Accept': 'application/json'
        }
        params = {
            'id': cmc_id,
            'time_start': start_date.strftime('%Y-%m-%d'),
            'time_end': end_date.strftime('%Y-%m-%d'),
            'count': days_back
        }

        try:
            logger.info(f"Fetching {days_back} days of historical data for {symbol} from CoinMarketCap...")
            response = requests.get(url, headers=headers, params=params, timeout=15)

            if response.status_code == 401:
                raise Exception("CoinMarketCap API authentication failed - check your API key. Status: 401")
            elif response.status_code == 403:
                raise Exception("CoinMarketCap API rate limit exceeded or access forbidden. Status: 403")
            elif response.status_code != 200:
                raise Exception(f"CoinMarketCap historical API returned error status {response.status_code}: {response.text}")

            data = response.json()

            if 'data' not in data or not data['data'].get('quotes'):
                raise Exception(f"No historical data returned for {symbol} from CoinMarketCap API")

            # Convert to backtesting.py compatible format
            df_data = []
            for quote in data['data']['quotes']:
                quote_data = quote['quote']['USD']
                df_data.append({
                    'Open': quote_data['open'],
                    'High': quote_data['high'],
                    'Low': quote_data['low'],
                    'Close': quote_data['close'],
                    'Volume': quote_data['volume'],
                    'timestamp': datetime.fromisoformat(quote['timestamp'].replace('Z', '+00:00'))
                })

            if not df_data:
                raise Exception(f"No historical data points found for {symbol}")

            df = pd.DataFrame(df_data)
            df.set_index('timestamp', inplace=True)
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()  # Ensure chronological order

            # Cache the data
            self.historical_data[symbol] = df

            logger.info(f"✅ Fetched {len(df)} daily historical bars for {symbol} from CoinMarketCap")
            return df

        except requests.exceptions.Timeout:
            raise Exception(f"CoinMarketCap historical API timeout for {symbol} - network connectivity issue")
        except requests.exceptions.ConnectionError:
            raise Exception(f"CoinMarketCap historical API connection error for {symbol} - check internet connection")
        except Exception as e:
            # Re-raise any exception to ensure we don't silently fail
            if "CoinMarketCap" in str(e):
                raise  # Already has good error message
            else:
                raise Exception(f"Error fetching CoinMarketCap historical data for {symbol}: {e}")

    async def _create_dummy_historical_data(self, symbol: str, days_back: int, granularity: str) -> pd.DataFrame:
        """REMOVED: No more dummy data - system should fail instead"""
        raise Exception("Dummy historical data disabled - system should use real data only")

    def _fetch_current_quote(self, symbol: str) -> MarketData | None:
        """Fetch current quote for a symbol using V2 API - FAILS if API is not working"""
        # Use V2 API endpoint exactly like the working test script
        url = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest"
        headers = {
            'X-CMC_PRO_API_KEY': self.api_key,
            'Accept': 'application/json'
        }
        params = {
            'symbol': symbol,
            'convert': 'USD'
        }

        try:
            logger.info(f"🌐 Fetching real-time quote for {symbol} from CoinMarketCap V2 API...")
            response = requests.get(url, headers=headers, params=params, timeout=10)

            if response.status_code == 401:
                raise Exception("CoinMarketCap API authentication failed - check your API key. Status: 401")
            elif response.status_code == 403:
                raise Exception("CoinMarketCap API rate limit exceeded or access forbidden. Status: 403")
            elif response.status_code != 200:
                raise Exception(f"CoinMarketCap API returned error status {response.status_code}: {response.text}")

            data = response.json()

            if 'data' not in data or symbol not in data['data']:
                raise Exception(f"No current quote data for {symbol} in CoinMarketCap API response")

            # V2 API returns an array - get the first entry which is the real cryptocurrency
            # For BTC, this filters out the meme tokens that also use "BTC" symbol
            symbol_data_array = data['data'][symbol]
            if not symbol_data_array or len(symbol_data_array) == 0:
                raise Exception(f"No data entries found for {symbol} in API response")

            # Get the first entry (real Bitcoin has id=1 and is always first)
            btc_data = symbol_data_array[0]
            quote_data = btc_data['quote']['USD']

            # Log what we found
            logger.info(f"📊 Found {btc_data['name']} (ID: {btc_data['id']}, Rank: {btc_data.get('cmc_rank', 'N/A')})")

            # Use the API's last_updated timestamp from the quote
            api_timestamp = None
            if 'last_updated' in quote_data:
                try:
                    api_timestamp = datetime.fromisoformat(quote_data['last_updated'].replace('Z', '+00:00'))
                    logger.info(f"📅 Using quote timestamp: {api_timestamp}")
                except Exception as e:
                    logger.warning(f"Could not parse quote timestamp: {e}")

            # For real-time data, use the API timestamp or current time
            timestamp = api_timestamp or datetime.utcnow()

            # Get the real price from CoinMarketCap
            price = float(quote_data['price'])
            volume_24h = int(quote_data.get('volume_24h', 0))

            logger.info(f"✅ Real CMC data for {symbol}: ${price:.2f} (24h volume: ${volume_24h:,})")

            # Status info from API response
            if 'status' in data:
                status = data['status']
                logger.info(f"🕐 API Timestamp: {status['timestamp']}, Credits: {status['credit_count']}, Response: {status['elapsed']}ms")

            # Since CMC doesn't provide OHLC for current quotes, use price as all values
            # This is exactly how the test script works
            market_data = MarketData(
                symbol=symbol,
                timestamp=timestamp,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume_24h
            )

            return market_data

        except requests.exceptions.Timeout:
            raise Exception(f"CoinMarketCap API timeout for {symbol} - network connectivity issue")
        except requests.exceptions.ConnectionError:
            raise Exception(f"CoinMarketCap API connection error for {symbol} - check internet connection")
        except Exception as e:
            # Re-raise any exception to ensure we don't silently fail
            if "CoinMarketCap" in str(e):
                raise  # Already has good error message
            else:
                raise Exception(f"Error fetching CoinMarketCap quote for {symbol}: {e}")

    def _create_simulated_quote(self, symbol: str) -> MarketData:
        """REMOVED: No more fallback data - system should fail instead"""
        raise Exception("Simulated quotes disabled - system should use real data only")

    def _simulation_loop(self):
        """Simulate real-time data updates by fetching current quotes periodically"""
        logger.info("Starting CoinMarketCap real-time simulation")

        while self.simulation_running:
            for symbol in list(self.subscribed_symbols):
                try:
                    market_data = self._fetch_current_quote(symbol)

                    if market_data:
                        self.current_bars[symbol] = market_data

                        # Notify callbacks
                        self._notify_callbacks(market_data)

                except Exception as e:
                    logger.error(f"Error updating {symbol} from CoinMarketCap: {e}")

            # Wait for next update
            time.sleep(self.update_interval)

        logger.info("CoinMarketCap simulation stopped")

    def subscribe_to_symbol(self, symbol: str):
        """Subscribe to real-time data for a symbol"""
        logger.info(f"Subscribed to {symbol} on CoinMarketCap")
        self.subscribed_symbols.add(symbol)

        # Initialize with empty data - will be populated by simulation
        if symbol not in self.current_bars:
            self.current_bars[symbol] = None

        # Try to get initial data immediately
        try:
            initial_data = self._fetch_current_quote(symbol)
            if initial_data:
                self.current_bars[symbol] = initial_data
                logger.info(f"✅ Got initial data for {symbol}: ${initial_data.close:.2f}")
        except Exception as e:
            logger.warning(f"Could not get initial data for {symbol}: {e}")

    def start_realtime_feed(self):
        """Start the real-time data simulation"""
        if not self.simulation_running:
            self.simulation_running = True
            self.simulation_thread = threading.Thread(target=self._simulation_loop)
            self.simulation_thread.daemon = True
            self.simulation_thread.start()
            logger.info("CoinMarketCap real-time feed started")

    def stop_realtime_feed(self):
        """Stop the real-time data simulation"""
        self.simulation_running = False
        if self.simulation_thread:
            self.simulation_thread.join(timeout=5)
        logger.info("CoinMarketCap real-time feed stopped")

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
                # Ensure we don't duplicate the same timestamp (within 1 minute)
                existing_data = self.historical_data[symbol]
                last_timestamp = existing_data.index[-1] if len(existing_data) > 0 else None

                if last_timestamp is None or (current_data.timestamp - last_timestamp).total_seconds() > 60:
                    self.historical_data[symbol] = pd.concat([existing_data, new_row])
            else:
                self.historical_data[symbol] = new_row

            return self.historical_data[symbol]

        return self.get_backtesting_data(symbol)

    def set_update_interval_from_granularity(self, granularity: str):
        """Set the update interval based on granularity"""
        try:
            parsed_granularity = self._parse_granularity(granularity)
            interval_seconds = parsed_granularity.to_seconds()

            # Respect CMC API rate limits (minimum 30 seconds for real API calls)
            # But allow shorter intervals for demo/simulation purposes
            if interval_seconds < 30:
                logger.warning(f"CMC granularity {granularity} is shorter than recommended 30s minimum for API rate limits")

            self.update_interval = interval_seconds
            self.granularity_seconds = interval_seconds  # Store for simulated time progression

            logger.info(f"CMC update interval set to {self.update_interval} seconds based on granularity {granularity}")
        except Exception as e:
            logger.warning(f"Could not parse granularity {granularity}, using default interval: {e}")

    def set_update_interval(self, seconds: float):
        """Set the update interval for real-time simulation"""
        # Enforce minimum interval due to CMC API rate limits
        self.update_interval = max(seconds, 30.0)  # Minimum 30 seconds
        logger.info(f"CMC update interval set to {self.update_interval} seconds")
