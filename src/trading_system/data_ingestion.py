import os
import asyncio
import websocket
import json
import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
import logging
from dataclasses import dataclass
from collections import defaultdict
from dotenv import load_dotenv
import random
import numpy as np
import threading
import time

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

class PolygonDataIngestion:
    """Minimal Polygon.io data ingestion for live trading signals"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.rest_base_url = "https://api.polygon.io"
        self.ws_url = f"wss://socket.polygon.io/stocks"
        
        # Data storage
        self.current_bars: Dict[str, MarketData] = {}
        self.historical_data: Dict[str, pd.DataFrame] = {}
        
        # WebSocket connection
        self.ws = None
        self.is_connected = False
        
        # Callbacks for real-time data
        self.data_callbacks: List[Callable[[MarketData], None]] = []
        
    def add_data_callback(self, callback: Callable[[MarketData], None]):
        """Add callback function to receive real-time data updates"""
        self.data_callbacks.append(callback)
    
    async def fetch_historical_data(self, symbol: str, days_back: int = 30, 
                                  timespan: str = "minute", multiplier: int = 1) -> pd.DataFrame:
        """
        Fetch historical OHLCV data for backtesting.py compatibility
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            days_back: Number of days of historical data
            timespan: 'minute', 'hour', 'day'
            multiplier: Size of timespan (e.g., 5 for 5-minute bars)
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        url = f"{self.rest_base_url}/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
        
        params = {
            'adjusted': 'true',
            'sort': 'asc',
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'results' not in data:
                logger.warning(f"No data returned for {symbol}")
                return pd.DataFrame()
            
            # Convert to backtesting.py compatible format
            df_data = []
            for bar in data['results']:
                df_data.append({
                    'Open': bar['o'],
                    'High': bar['h'],
                    'Low': bar['l'],
                    'Close': bar['c'],
                    'Volume': bar['v'],
                    'timestamp': datetime.fromtimestamp(bar['t'] / 1000)
                })
            
            df = pd.DataFrame(df_data)
            df.set_index('timestamp', inplace=True)
            df.index = pd.to_datetime(df.index)
            
            # Cache the data
            self.historical_data[symbol] = df
            
            logger.info(f"Fetched {len(df)} historical bars for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return pd.DataFrame()
    
    def _on_ws_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            
            # Handle different message types
            for item in data:
                if item.get('ev') == 'AM':  # Aggregate (OHLCV) message
                    market_data = MarketData(
                        symbol=item['sym'],
                        timestamp=datetime.fromtimestamp(item['s'] / 1000),
                        open=item['o'],
                        high=item['h'],
                        low=item['l'],
                        close=item['c'],
                        volume=item['v']
                    )
                    
                    # Update current data
                    self.current_bars[market_data.symbol] = market_data
                    
                    # Notify callbacks
                    for callback in self.data_callbacks:
                        try:
                            callback(market_data)
                        except Exception as e:
                            logger.error(f"Error in data callback: {e}")
                            
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
    
    def _on_ws_error(self, ws, error):
        """Handle WebSocket errors"""
        logger.error(f"WebSocket error: {error}")
        self.is_connected = False
    
    def _on_ws_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        logger.info("WebSocket connection closed")
        self.is_connected = False
    
    def _on_ws_open(self, ws):
        """Handle WebSocket open"""
        logger.info("WebSocket connection opened")
        self.is_connected = True
        
        # Authenticate
        auth_message = {
            "action": "auth",
            "params": self.api_key
        }
        ws.send(json.dumps(auth_message))
    
    def subscribe_to_symbol(self, symbol: str):
        """Subscribe to real-time data for a symbol"""
        if not self.is_connected:
            logger.warning("WebSocket not connected. Cannot subscribe.")
            return
        
        subscribe_message = {
            "action": "subscribe",
            "params": f"AM.{symbol}"  # Aggregate minute bars
        }
        self.ws.send(json.dumps(subscribe_message))
        logger.info(f"Subscribed to {symbol}")
    
    def start_realtime_feed(self):
        """Start the real-time WebSocket connection"""
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close,
            on_open=self._on_ws_open
        )
        
        # Run in a separate thread
        self.ws.run_forever()
    
    def get_current_data(self, symbol: str) -> Optional[MarketData]:
        """Get the most recent data for a symbol"""
        return self.current_bars.get(symbol)
    
    def get_backtesting_data(self, symbol: str) -> pd.DataFrame:
        """Get historical data formatted for backtesting.py"""
        return self.historical_data.get(symbol, pd.DataFrame())
    
    def append_current_bar(self, symbol: str) -> pd.DataFrame:
        """
        Append the current real-time bar to historical data for live trading simulation
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Updated DataFrame with current bar appended, or existing data if no new bar
        """
        if symbol not in self.historical_data or len(self.historical_data[symbol]) == 0:
            logger.warning(f"No historical data for {symbol}, cannot append current bar")
            return pd.DataFrame()
        
        # Get current real-time data
        current_data = self.get_current_data(symbol)
        if current_data is None:
            # No new data available, return existing
            return self.historical_data[symbol]
        
        # Get existing historical data
        existing_data = self.historical_data[symbol].copy()
        
        # Check if this bar is newer than the last historical bar
        last_timestamp = existing_data.index[-1]
        if current_data.timestamp <= last_timestamp:
            # Current bar is not newer, return existing data
            return existing_data
        
        # Create new bar from current real-time data
        new_bar = pd.DataFrame({
            'Open': [current_data.open],
            'High': [current_data.high],
            'Low': [current_data.low],
            'Close': [current_data.close],
            'Volume': [current_data.volume]
        }, index=[current_data.timestamp])
        
        # Append to existing data
        updated_data = pd.concat([existing_data, new_bar])
        
        # Update cache
        self.historical_data[symbol] = updated_data
        
        logger.debug(f"Appended real-time bar for {symbol}: {current_data.timestamp} - Close: ${current_data.close:.2f}")
        
        return updated_data

class CoinMarketCapDataIngestion:
    """CoinMarketCap data ingestion for cryptocurrency signals"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.rest_base_url = "https://pro-api.coinmarketcap.com"
        
        # Data storage
        self.current_bars: Dict[str, MarketData] = {}
        self.historical_data: Dict[str, pd.DataFrame] = {}
        self.symbol_to_id: Dict[str, int] = {}  # Map symbols to CMC IDs
        
        # Real-time simulation
        self.simulation_running = False
        self.simulation_thread = None
        self.update_interval = 60.0  # 60 seconds between updates (CMC API rate limits)
        
        # Callbacks for real-time data
        self.data_callbacks: List[Callable[[MarketData], None]] = []
        
    def add_data_callback(self, callback: Callable[[MarketData], None]):
        """Add callback function to receive real-time data updates"""
        self.data_callbacks.append(callback)
    
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
                        for callback in self.data_callbacks:
                            try:
                                callback(market_data)
                            except Exception as e:
                                logger.error(f"Error in CMC data callback: {e}")
                                
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
    
    def get_current_data(self, symbol: str) -> Optional[MarketData]:
        """Get the most recent data for a symbol"""
        return self.current_bars.get(symbol)
    
    def get_backtesting_data(self, symbol: str) -> pd.DataFrame:
        """Get historical data formatted for backtesting.py"""
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

class TestDataIngestion:
    """Test data ingestor that generates realistic random market data for testing"""
    
    def __init__(self, base_prices: Optional[Dict[str, float]] = None):
        """
        Initialize test data ingestor
        
        Args:
            base_prices: Dictionary of symbol -> base price. If None, uses realistic defaults.
        """
        # Default base prices for common stocks
        self.base_prices = base_prices or {
            'AAPL': 175.0,
            'MSFT': 380.0,
            'GOOGL': 140.0,
            'TSLA': 200.0,
            'AMZN': 150.0,
            'NVDA': 450.0,
            'META': 300.0,
            'NFLX': 400.0
        }
        
        # Data storage - same interface as PolygonDataIngestion
        self.current_bars: Dict[str, MarketData] = {}
        self.historical_data: Dict[str, pd.DataFrame] = {}
        
        # Simulation state
        self.is_connected = False
        self.subscribed_symbols: List[str] = []
        self.data_callbacks: List[Callable[[MarketData], None]] = []
        
        # Random walk parameters for realistic price movement
        self.price_volatility = 0.02  # 2% volatility
        self.trend_strength = 0.001   # Small trend component
        self.volume_base = 1000000    # Base volume
        self.volume_volatility = 0.3  # Volume volatility
        
        # Simulation control
        self.simulation_thread = None
        self.stop_simulation = False
        self.update_interval = 1.0  # seconds between updates
        
        # Current prices for random walk
        self.current_prices = self.base_prices.copy()
        
    def add_data_callback(self, callback: Callable[[MarketData], None]):
        """Add callback function to receive real-time data updates"""
        self.data_callbacks.append(callback)
    
    async def fetch_historical_data(self, symbol: str, days_back: int = 30, 
                                  timespan: str = "minute", multiplier: int = 1) -> pd.DataFrame:
        """
        Generate synthetic historical OHLCV data for backtesting.py compatibility
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            days_back: Number of days of historical data
            timespan: 'minute', 'hour', 'day' (currently only 'minute' supported)
            multiplier: Size of timespan (e.g., 5 for 5-minute bars)
        """
        if symbol not in self.base_prices:
            # Add new symbol with random base price
            self.base_prices[symbol] = random.uniform(50, 500)
            self.current_prices[symbol] = self.base_prices[symbol]
        
        base_price = self.base_prices[symbol]
        
        # Calculate number of bars needed
        if timespan == "minute":
            bars_per_day = 390  # 6.5 hours * 60 minutes
        elif timespan == "hour":
            bars_per_day = 7  # 6.5 hours
        elif timespan == "day":
            bars_per_day = 1
        else:
            bars_per_day = 390  # Default to minute
        
        total_bars = int(days_back * bars_per_day / multiplier)
        
        # Generate realistic OHLCV data using geometric Brownian motion
        df_data = []
        current_price = base_price
        
        start_time = datetime.now() - timedelta(days=days_back)
        
        for i in range(total_bars):
            if timespan == "minute":
                timestamp = start_time + timedelta(minutes=i * multiplier)
            elif timespan == "hour":
                timestamp = start_time + timedelta(hours=i * multiplier)
            elif timespan == "day":
                timestamp = start_time + timedelta(days=i * multiplier)
            else:
                timestamp = start_time + timedelta(minutes=i * multiplier)
            
            # For test data, we'll generate data 24/7 for simplicity
            # In production, you might want to add market hours filtering
            
            # Generate OHLCV for this bar
            # Random walk with small trend
            price_change = np.random.normal(
                self.trend_strength * current_price,  # Small upward trend
                self.price_volatility * current_price  # Volatility
            )
            
            new_price = max(0.01, current_price + price_change)  # Ensure positive price
            
            # Generate OHLC within reasonable bounds
            open_price = current_price
            close_price = new_price
            
            # High and low based on volatility
            intrabar_volatility = self.price_volatility * 0.5
            high_price = max(open_price, close_price) + abs(np.random.normal(0, intrabar_volatility * current_price))
            low_price = min(open_price, close_price) - abs(np.random.normal(0, intrabar_volatility * current_price))
            
            # Ensure OHLC relationships are maintained
            high_price = max(high_price, open_price, close_price)
            low_price = min(low_price, open_price, close_price)
            low_price = max(0.01, low_price)  # Ensure positive
            
            # Volume with some randomness
            volume = int(self.volume_base * (1 + np.random.normal(0, self.volume_volatility)))
            volume = max(1000, volume)  # Minimum volume
            
            df_data.append({
                'Open': round(open_price, 2),
                'High': round(high_price, 2),
                'Low': round(low_price, 2),
                'Close': round(close_price, 2),
                'Volume': volume,
                'timestamp': timestamp
            })
            
            current_price = new_price
        
        df = pd.DataFrame(df_data)
        if len(df) > 0:
            df.set_index('timestamp', inplace=True)
            df.index = pd.to_datetime(df.index)
            
            # Cache the data
            self.historical_data[symbol] = df
            
            # Update current price for real-time simulation
            self.current_prices[symbol] = df['Close'].iloc[-1]
            
            logger.info(f"Generated {len(df)} historical bars for {symbol}")
        else:
            df = pd.DataFrame()
            logger.warning(f"No historical data generated for {symbol}")
        
        return df
    
    def append_new_bar(self, symbol: str) -> pd.DataFrame:
        """
        Append one new bar to existing historical data to simulate live trading
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Updated DataFrame with the new bar appended
        """
        if symbol not in self.historical_data or len(self.historical_data[symbol]) == 0:
            # If no historical data exists, we need to initialize it first
            # This should be called after initial data is loaded
            logger.warning(f"No historical data for {symbol}, cannot append new bar")
            return pd.DataFrame()
        
        # Get existing data
        existing_data = self.historical_data[symbol].copy()
        
        # Generate next timestamp (1 minute after the last bar)
        last_timestamp = existing_data.index[-1]
        next_timestamp = last_timestamp + timedelta(minutes=1)
        
        # Get current price (last close price)
        current_price = self.current_prices.get(symbol, existing_data['Close'].iloc[-1])
        
        # Generate price movement
        price_change = np.random.normal(
            self.trend_strength * current_price,
            self.price_volatility * current_price
        )
        
        new_price = max(0.01, current_price + price_change)
        
        # Generate OHLC for this bar
        open_price = current_price
        close_price = new_price
        
        # High and low based on volatility
        intrabar_volatility = self.price_volatility * 0.5
        high_price = max(open_price, close_price) + abs(np.random.normal(0, intrabar_volatility * current_price))
        low_price = min(open_price, close_price) - abs(np.random.normal(0, intrabar_volatility * current_price))
        
        # Ensure OHLC relationships
        high_price = max(high_price, open_price, close_price)
        low_price = min(low_price, open_price, close_price)
        low_price = max(0.01, low_price)
        
        # Generate volume
        volume = int(self.volume_base * (1 + np.random.normal(0, self.volume_volatility)))
        volume = max(1000, volume)
        
        # Create new bar
        new_bar = pd.DataFrame({
            'Open': [round(open_price, 2)],
            'High': [round(high_price, 2)],
            'Low': [round(low_price, 2)],
            'Close': [round(close_price, 2)],
            'Volume': [volume]
        }, index=[next_timestamp])
        
        # Append to existing data
        updated_data = pd.concat([existing_data, new_bar])
        
        # Update cache
        self.historical_data[symbol] = updated_data
        self.current_prices[symbol] = new_price
        
        logger.debug(f"Appended new bar for {symbol}: {next_timestamp} - Close: ${new_price:.2f}")
        
        return updated_data
    
    def _generate_realtime_bar(self, symbol: str) -> MarketData:
        """Generate a single real-time market data bar"""
        if symbol not in self.current_prices:
            self.current_prices[symbol] = self.base_prices.get(symbol, 100.0)
        
        current_price = self.current_prices[symbol]
        
        # Random walk for price movement
        price_change = np.random.normal(
            self.trend_strength * current_price,
            self.price_volatility * current_price
        )
        
        new_price = max(0.01, current_price + price_change)
        
        # Generate OHLC
        open_price = current_price
        close_price = new_price
        
        # Intrabar high/low
        intrabar_volatility = self.price_volatility * 0.3
        high_price = max(open_price, close_price) + abs(np.random.normal(0, intrabar_volatility * current_price))
        low_price = min(open_price, close_price) - abs(np.random.normal(0, intrabar_volatility * current_price))
        
        # Ensure OHLC relationships
        high_price = max(high_price, open_price, close_price)
        low_price = min(low_price, open_price, close_price)
        low_price = max(0.01, low_price)
        
        # Volume
        volume = int(self.volume_base * (1 + np.random.normal(0, self.volume_volatility)))
        volume = max(1000, volume)
        
        # Update current price
        self.current_prices[symbol] = new_price
        
        return MarketData(
            symbol=symbol,
            timestamp=datetime.now(),
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=volume
        )
    
    def _simulation_loop(self):
        """Main simulation loop that generates real-time data"""
        logger.info("Starting test data simulation")
        
        while not self.stop_simulation:
            if self.is_connected and self.subscribed_symbols:
                for symbol in self.subscribed_symbols:
                    try:
                        # Generate new market data
                        market_data = self._generate_realtime_bar(symbol)
                        
                        # Update current bars
                        self.current_bars[market_data.symbol] = market_data
                        
                        # Notify callbacks
                        for callback in self.data_callbacks:
                            try:
                                callback(market_data)
                            except Exception as e:
                                logger.error(f"Error in data callback: {e}")
                                
                    except Exception as e:
                        logger.error(f"Error generating data for {symbol}: {e}")
            
            time.sleep(self.update_interval)
        
        logger.info("Test data simulation stopped")
    
    def subscribe_to_symbol(self, symbol: str):
        """Subscribe to real-time data for a symbol"""
        if symbol not in self.subscribed_symbols:
            self.subscribed_symbols.append(symbol)
            logger.info(f"Subscribed to test data for {symbol}")
            
            # Initialize current price if not exists
            if symbol not in self.current_prices:
                self.current_prices[symbol] = self.base_prices.get(symbol, random.uniform(50, 500))
    
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
    
    def get_current_data(self, symbol: str) -> Optional[MarketData]:
        """Get the most recent data for a symbol"""
        return self.current_bars.get(symbol)
    
    def get_backtesting_data(self, symbol: str) -> pd.DataFrame:
        """Get historical data formatted for backtesting.py"""
        return self.historical_data.get(symbol, pd.DataFrame())
    
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

# Simple usage example
class MinimalSignalGenerator:
    """Minimal example of how to use the data for signal generation"""
    
    def __init__(self, data_ingestion):
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
            short_ma = sum(self.price_history[symbol][-self.short_window:]) / self.short_window
            long_ma = sum(self.price_history[symbol]) / len(self.price_history[symbol])
            
            if short_ma > long_ma:
                signal = "BUY"
            elif short_ma < long_ma:
                signal = "SELL"
            else:
                signal = "HOLD"
            
            logger.info(f"{symbol}: {signal} - Price: {price}, Short MA: {short_ma:.2f}, Long MA: {long_ma:.2f}")

# Configuration and setup
def setup_data_ingestion(data_source: str = "demo", base_prices: Optional[Dict[str, float]] = None):
    """
    Setup function to initialize data ingestion
    
    Args:
        data_source: Data source to use ("demo", "polygon", or "coinmarketcap")
        base_prices: Base prices for test data (only used when data_source="demo")
    """
    
    if data_source == "demo":
        # Use test data ingestor
        logger.info("Using test data ingestor")
        return TestDataIngestion(base_prices=base_prices)
    elif data_source == "coinmarketcap":
        # Use CoinMarketCap data
        api_key = os.getenv('CMC_API_KEY')
        if not api_key:
            raise ValueError("CMC_API_KEY environment variable not set")
        
        logger.info("Using CoinMarketCap data ingestor")
        return CoinMarketCapDataIngestion(api_key)
    else:  # polygon or default to polygon
        # Use real Polygon.io data
        api_key = os.getenv('POLYGON_API_KEY')
        if not api_key:
            raise ValueError("POLYGON_API_KEY environment variable not set")
        
        logger.info("Using real Polygon.io data ingestor")
        return PolygonDataIngestion(api_key)

def demo_test_data_ingestion():
    """Demonstration of test data ingestion functionality"""
    print("\n=== Test Data Ingestion Demo ===")
    
    # Setup test data ingestion
    data_ingestion = setup_data_ingestion(
        data_source="demo",
        base_prices={
            'AAPL': 175.0,
            'MSFT': 400.0,
            'TSLA': 250.0
        }
    )
    
    # Setup signal generator
    signal_generator = MinimalSignalGenerator(data_ingestion)
    
    # Test symbols
    symbols = ['AAPL', 'MSFT', 'TSLA']
    
    print("Generating historical data...")
    # Fetch historical data
    for symbol in symbols:
        historical_data = asyncio.run(data_ingestion.fetch_historical_data(
            symbol, 
            days_back=5,  # Shorter for demo
            timespan="minute"
        ))
        print(f"Generated {len(historical_data)} historical bars for {symbol}")
        if len(historical_data) > 0:
            print(f"  Price range: ${historical_data['Low'].min():.2f} - ${historical_data['High'].max():.2f}")
    
    print("\nStarting real-time data simulation...")
    
    # Configure simulation parameters
    data_ingestion.set_update_interval(0.5)  # Update every 0.5 seconds for faster demo
    data_ingestion.set_volatility(0.01)      # Lower volatility for demo
    
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
                price_str = " | ".join([f"{sym}: ${price:.2f}" for sym, price in current_prices.items()])
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
        symbols = ['AAPL', 'MSFT']
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
            symbols = ['AAPL', 'MSFT', 'GOOGL']
            for symbol in symbols:
                historical_data = asyncio.run(data_ingestion.fetch_historical_data(symbol, days_back=30))
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
            print("  python3.11 data_ingestion.py demo    - Run test data demo")
            print("  python3.11 data_ingestion.py test    - Quick test")
            print("  python3.11 data_ingestion.py         - Run with real/fallback data")
            
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("Stopping data ingestion...")
        except Exception as e:
            logger.error(f"Error: {e}") 