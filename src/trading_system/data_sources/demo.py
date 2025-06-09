"""
Demo/Test Data Source

Simulated market data for testing and development
"""

import pandas as pd
import random
import threading
import time
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

from .base import BaseDataIngestion, MarketData

logger = logging.getLogger(__name__)


class TestDataIngestion(BaseDataIngestion):
    """Test data ingestor that generates realistic random market data for testing"""
    
    def __init__(self, base_prices: Optional[Dict[str, float]] = None):
        super().__init__()
        
        # Base prices for different symbols (defaults if not provided)
        self.base_prices = base_prices or {
            'AAPL': 175.0,
            'MSFT': 400.0,
            'GOOGL': 140.0,
            'TSLA': 250.0,
            'NVDA': 480.0,
            'BTC': 45000.0,
            'ETH': 3000.0
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
        self.subscribed_symbols: List[str] = []
        
    async def fetch_historical_data(self, symbol: str, days_back: int = 30, 
                                  timespan: str = "minute", multiplier: int = 1) -> pd.DataFrame:
        """
        Generate historical test data that looks realistic
        
        Args:
            symbol: Symbol to generate data for
            days_back: Number of days of historical data
            timespan: 'minute', 'hour', 'day'
            multiplier: Size of timespan (e.g., 5 for 5-minute bars)
        """
        
        # Calculate time parameters
        if timespan == "minute":
            total_bars = days_back * 24 * 60 // multiplier  # Total minutes / multiplier
            time_delta = timedelta(minutes=multiplier)
        elif timespan == "hour":
            total_bars = days_back * 24 // multiplier  # Total hours / multiplier
            time_delta = timedelta(hours=multiplier)
        elif timespan == "day":
            total_bars = days_back // multiplier  # Total days / multiplier
            time_delta = timedelta(days=multiplier)
        else:
            total_bars = days_back * 24 * 60  # Default to minutes
            time_delta = timedelta(minutes=1)
        
        # Limit total bars for performance
        total_bars = min(total_bars, 10000)
        
        # Generate timestamps
        end_time = datetime.now()
        timestamps = []
        current_time = end_time - (time_delta * total_bars)
        
        for i in range(total_bars):
            timestamps.append(current_time)
            current_time += time_delta
        
        # Get base price for symbol
        base_price = self.base_prices.get(symbol, random.uniform(50, 500))
        
        # Generate realistic OHLCV data using random walk
        data = []
        current_price = base_price
        
        for timestamp in timestamps:
            # Random walk with mean reversion
            price_change_pct = random.gauss(0, self.price_volatility)
            
            # Add some mean reversion
            if current_price > base_price * 1.1:
                price_change_pct -= 0.01  # Slight downward bias
            elif current_price < base_price * 0.9:
                price_change_pct += 0.01  # Slight upward bias
            
            # Calculate new price
            new_price = current_price * (1 + price_change_pct)
            
            # Generate OHLC around the price movement
            if new_price > current_price:
                # Upward movement
                open_price = current_price
                close_price = new_price
                high_price = close_price * (1 + random.uniform(0, 0.01))
                low_price = open_price * (1 - random.uniform(0, 0.005))
            else:
                # Downward movement
                open_price = current_price
                close_price = new_price
                low_price = close_price * (1 - random.uniform(0, 0.01))
                high_price = open_price * (1 + random.uniform(0, 0.005))
            
            # Generate volume (higher volume on bigger price movements)
            volume_base = random.randint(100000, 1000000)
            volume_multiplier = 1 + abs(price_change_pct) * 10
            volume = int(volume_base * volume_multiplier)
            
            data.append({
                'Open': round(open_price, 2),
                'High': round(high_price, 2),
                'Low': round(low_price, 2),
                'Close': round(close_price, 2),
                'Volume': volume,
                'timestamp': timestamp
            })
            
            current_price = close_price
        
        # Create DataFrame
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        df.index = pd.to_datetime(df.index)
        
        # Cache the data
        self.historical_data[symbol] = df
        
        # Update current price
        if len(df) > 0:
            self.current_prices[symbol] = df['Close'].iloc[-1]
        
        logger.info(f"Generated {len(df)} test historical bars for {symbol}")
        return df
    
    def append_new_bar(self, symbol: str) -> pd.DataFrame:
        """Generate and append one new bar to historical data"""
        
        if symbol not in self.historical_data:
            logger.warning(f"No historical data for {symbol}, generating minimal data")
            # Generate a small amount of historical data first
            import asyncio
            historical_data = asyncio.run(self.fetch_historical_data(symbol, days_back=1))
            if len(historical_data) == 0:
                return pd.DataFrame()
        
        # Get current price
        current_price = self.current_prices.get(symbol, self.base_prices.get(symbol, 100.0))
        
        # Generate new bar data similar to real-time simulation
        new_bar = self._generate_realtime_bar(symbol)
        
        if new_bar:
            # Convert to DataFrame row
            new_row = pd.DataFrame({
                'Open': [new_bar.open],
                'High': [new_bar.high],
                'Low': [new_bar.low],
                'Close': [new_bar.close],
                'Volume': [new_bar.volume]
            }, index=[new_bar.timestamp])
            
            # Append to existing data
            if symbol in self.historical_data:
                self.historical_data[symbol] = pd.concat([self.historical_data[symbol], new_row])
            else:
                self.historical_data[symbol] = new_row
            
            # Update current price
            self.current_prices[symbol] = new_bar.close
            
            # Update current bar
            self.current_bars[symbol] = new_bar
            
            return self.historical_data[symbol]
        
        return self.get_backtesting_data(symbol)
    
    def _generate_realtime_bar(self, symbol: str) -> MarketData:
        """Generate a single realistic bar for real-time simulation"""
        
        base_price = self.base_prices.get(symbol, 100.0)
        current_price = self.current_prices.get(symbol, base_price)
        
        # Random price movement with mean reversion
        price_change_pct = random.gauss(0, self.price_volatility)
        
        # Add mean reversion tendency
        if current_price > base_price * 1.15:
            price_change_pct -= 0.005  # Downward bias when too high
        elif current_price < base_price * 0.85:
            price_change_pct += 0.005  # Upward bias when too low
        
        # Calculate new close price
        new_close = current_price * (1 + price_change_pct)
        
        # Generate OHLC
        if new_close > current_price:
            # Up bar
            open_price = current_price
            close_price = new_close
            high_price = close_price * (1 + random.uniform(0, 0.005))
            low_price = open_price * (1 - random.uniform(0, 0.002))
        else:
            # Down bar
            open_price = current_price
            close_price = new_close
            low_price = close_price * (1 - random.uniform(0, 0.005))
            high_price = open_price * (1 + random.uniform(0, 0.002))
        
        # Generate volume
        volume = random.randint(50000, 500000)
        
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