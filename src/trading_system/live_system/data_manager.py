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
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)

class DataManager:
    """Manages data loading and real-time updates for live trading"""
    
    def __init__(self, symbols: List[str], data_source: str, granularity: str, lookback_period: int):
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
        
    def setup_data_ingestion(self):
        """Setup data ingestion based on data source"""
        import os
        from ..data.ingestion import create_data_source
        
        # Get API key if needed
        api_key = None
        if self.data_source == "polygon":
            api_key = os.getenv('POLYGON_API_KEY')
        elif self.data_source == "coinmarketcap":
            api_key = os.getenv('CMC_API_KEY')
        
        # Create data source with granularity support
        self.data_ingester = create_data_source(self.data_source, api_key, self.granularity)
        
        # For live data, start real-time feed and subscribe to symbols
        if self.data_source != "demo":
            for symbol in self.symbols:
                self.data_ingester.subscribe_to_symbol(symbol)
                
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
                    granularity=self.granularity
                )
                
                # Store the initial cumulative data
                self.cumulative_data[symbol] = historical_data.copy()
                
                logger.info(f"✅ Loaded {len(historical_data)} initial historical bars for {symbol}")
                
            except Exception as e:
                logger.error(f"Error loading historical data for {symbol}: {e}")
                
                # If historical data fails, start with empty DataFrame - we'll build from real-time
                self.cumulative_data[symbol] = pd.DataFrame()
                logger.info(f"📊 Will build {symbol} data from real-time feeds only (no historical data available)")
        
        # Give real-time feed a moment to get initial data
        await asyncio.sleep(2)
        
        # Check if we got any initial real-time data
        for symbol in self.symbols:
            current_data = self.data_ingester.get_current_data(symbol)
            if current_data and len(self.cumulative_data[symbol]) == 0:
                # Add the first real-time bar to start building data
                first_bar = pd.DataFrame({
                    'Open': [current_data.open],
                    'High': [current_data.high],
                    'Low': [current_data.low],
                    'Close': [current_data.close],
                    'Volume': [current_data.volume]
                }, index=[current_data.timestamp])
                
                self.cumulative_data[symbol] = first_bar
                logger.info(f"🚀 Started building {symbol} data from first real-time bar: ${current_data.close:.2f}")
    
    async def update_symbol_data(self, symbol: str):
        """Update data for a single symbol"""
        if self.data_source == "demo":
            # Append one new bar to cumulative data (simulating live environment)
            updated_data = self.data_ingester.append_new_bar(symbol)
            if len(updated_data) > 0:
                self.cumulative_data[symbol] = updated_data
        else:
            # For real data sources (like CoinMarketCap), get current real-time data
            current_data = self.data_ingester.get_current_data(symbol)
            
            if current_data:
                # Add current real-time bar to cumulative data
                new_bar = pd.DataFrame({
                    'Open': [current_data.open],
                    'High': [current_data.high],
                    'Low': [current_data.low],
                    'Close': [current_data.close],
                    'Volume': [current_data.volume]
                }, index=[current_data.timestamp])
                
                if symbol in self.cumulative_data and len(self.cumulative_data[symbol]) > 0:
                    # Check if this is a new timestamp (avoid duplicates)
                    last_timestamp = self.cumulative_data[symbol].index[-1]
                    time_diff = (current_data.timestamp - last_timestamp).total_seconds()
                    
                    # Add new bar if: significant time difference OR price changed OR first few bars
                    last_price = self.cumulative_data[symbol]['Close'].iloc[-1]
                    price_changed = abs(current_data.close - last_price) > 0.01  # Price changed by more than 1 cent
                    need_more_bars = len(self.cumulative_data[symbol]) < self.lookback_period
                    
                    if time_diff >= 30 or price_changed or need_more_bars:
                        self.cumulative_data[symbol] = pd.concat([self.cumulative_data[symbol], new_bar])
                        logger.debug(f"📊 Added new bar for {symbol}: ${current_data.close:.2f} (time_diff: {time_diff}s, price_changed: {price_changed}, need_more: {need_more_bars})")
                    else:
                        logger.debug(f"⏭️  Skipping duplicate bar for {symbol}: same timestamp and price")
                else:
                    # First bar
                    self.cumulative_data[symbol] = new_bar
                    logger.info(f"🎬 First bar for {symbol}: ${current_data.close:.2f}")
    
    def get_symbol_data(self, symbol: str) -> pd.DataFrame:
        """Get cumulative data for a symbol"""
        return self.cumulative_data.get(symbol, pd.DataFrame())
    
    def has_sufficient_data(self, symbol: str) -> bool:
        """Check if symbol has sufficient data for strategy"""
        data = self.get_symbol_data(symbol)
        return len(data) >= self.lookback_period
    
    def get_data_progress(self, symbol: str) -> tuple[int, int, float]:
        """Get data collection progress for a symbol"""
        data = self.get_symbol_data(symbol)
        current_bars = len(data)
        required_bars = self.lookback_period
        progress_pct = (current_bars / required_bars * 100) if required_bars > 0 else 100
        return current_bars, required_bars, progress_pct 