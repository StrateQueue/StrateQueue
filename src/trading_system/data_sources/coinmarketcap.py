"""
CoinMarketCap Data Source

Cryptocurrency data from CoinMarketCap Pro API
"""

import asyncio
import pandas as pd
import requests
import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from .base import BaseDataIngestion, MarketData

logger = logging.getLogger(__name__)


class CoinMarketCapDataIngestion(BaseDataIngestion):
    """CoinMarketCap data ingestion for cryptocurrency signals"""
    
    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        self.rest_base_url = "https://pro-api.coinmarketcap.com"
        self.symbol_to_id: Dict[str, int] = {}  # Map symbols to CMC IDs
        
        # Real-time simulation
        self.simulation_running = False
        self.simulation_thread = None
        self.update_interval = 60.0  # 60 seconds between updates (CMC API rate limits)
        
    async def _fetch_symbol_id(self, symbol: str) -> Optional[int]:
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
                                  timespan: str = "daily", multiplier: int = 1) -> pd.DataFrame:
        """
        Fetch historical cryptocurrency data from CoinMarketCap
        
        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTC')
            days_back: Number of days of historical data
            timespan: 'daily' (only option for CMC historical data)
            multiplier: Not used for CMC (always 1 day)
        """
        # Get CMC ID for the symbol
        cmc_id = await self._fetch_symbol_id(symbol)
        if not cmc_id:
            logger.error(f"Cannot fetch historical data for {symbol} - no CMC ID found")
            return pd.DataFrame()
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        url = f"{self.rest_base_url}/v1/cryptocurrency/ohlcv/historical"
        headers = {
            'X-CMC_PRO_API_KEY': self.api_key,
            'Content-Type': 'application/json'
        }
        params = {
            'id': cmc_id,
            'time_start': start_date.strftime('%Y-%m-%d'),
            'time_end': end_date.strftime('%Y-%m-%d'),
            'count': days_back
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'data' not in data or not data['data'].get('quotes'):
                logger.warning(f"No historical data returned for {symbol}")
                return pd.DataFrame()
            
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
            
            df = pd.DataFrame(df_data)
            df.set_index('timestamp', inplace=True)
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()  # Ensure chronological order
            
            # Cache the data
            self.historical_data[symbol] = df
            
            logger.info(f"Fetched {len(df)} historical bars for {symbol} from CoinMarketCap")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol} from CoinMarketCap: {e}")
            # For simple strategies that don't need historical data, create minimal dummy data
            logger.info(f"Creating minimal dummy historical data for {symbol}")
            try:
                # Try to get current price first
                current_quote = await self._fetch_current_quote(symbol)
                if current_quote:
                    price = current_quote.close
                else:
                    # Use a reasonable default price for crypto
                    price = 50000.0 if symbol == 'BTC' else 3000.0 if symbol == 'ETH' else 100.0
                
                # Create minimal historical data with just a few bars
                timestamps = [datetime.now() - timedelta(days=i) for i in range(days_back, 0, -1)]
                df_data = []
                for ts in timestamps[-5:]:  # Only last 5 days
                    df_data.append({
                        'Open': price,
                        'High': price * 1.02,
                        'Low': price * 0.98,
                        'Close': price,
                        'Volume': 1000000,
                        'timestamp': ts
                    })
                
                df = pd.DataFrame(df_data)
                df.set_index('timestamp', inplace=True)
                df.index = pd.to_datetime(df.index)
                
                # Cache the dummy data
                self.historical_data[symbol] = df
                
                logger.info(f"Created {len(df)} dummy historical bars for {symbol}")
                return df
                
            except Exception as fallback_error:
                logger.error(f"Failed to create dummy data: {fallback_error}")
                return pd.DataFrame()
    
    async def _fetch_current_quote(self, symbol: str) -> Optional[MarketData]:
        """Fetch current quote for a symbol"""
        url = f"{self.rest_base_url}/v1/cryptocurrency/quotes/latest"
        headers = {
            'X-CMC_PRO_API_KEY': self.api_key,
            'Content-Type': 'application/json'
        }
        params = {
            'symbol': symbol
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'data' not in data or symbol not in data['data']:
                logger.warning(f"No current quote data for {symbol}")
                return None
            
            quote_data = data['data'][symbol]['quote']['USD']
            timestamp = datetime.now()
            
            # Since CMC doesn't provide OHLC for current quotes, use price as all values
            price = quote_data['price']
            market_data = MarketData(
                symbol=symbol,
                timestamp=timestamp,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=int(quote_data.get('volume_24h', 0))
            )
            
            return market_data
            
        except Exception as e:
            logger.error(f"Error fetching current quote for {symbol}: {e}")
            return None
    
    def _simulation_loop(self):
        """Simulate real-time data updates by fetching current quotes periodically"""
        logger.info("Starting CoinMarketCap real-time simulation")
        
        while self.simulation_running:
            for symbol in list(self.current_bars.keys()):
                try:
                    # Use asyncio.run to handle async call in thread
                    market_data = asyncio.run(self._fetch_current_quote(symbol))
                    
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
        # Initialize with empty data - will be populated by simulation
        if symbol not in self.current_bars:
            self.current_bars[symbol] = None
    
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
    
    def set_update_interval(self, seconds: float):
        """Set the update interval for real-time simulation"""
        # Enforce minimum interval due to CMC API rate limits
        self.update_interval = max(seconds, 30.0)  # Minimum 30 seconds
        logger.info(f"CMC update interval set to {self.update_interval} seconds") 