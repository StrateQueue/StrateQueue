"""
Data Ingestion Module

Main entry point for data ingestion with factory function to create appropriate data sources.
"""

import os
import asyncio
import time
import logging
from typing import Dict, Optional
from collections import defaultdict

from .data_sources import (
    BaseDataIngestion, 
    MarketData,
    PolygonDataIngestion, 
    CoinMarketCapDataIngestion, 
    TestDataIngestion
)

# Load environment variables from .env file  
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_data_ingestion(data_source: str = "demo", base_prices: Optional[Dict[str, float]] = None) -> BaseDataIngestion:
    """
    Setup function to initialize data ingestion
    
    Args:
        data_source: Data source to use ("demo", "polygon", or "coinmarketcap")
        base_prices: Base prices for test data (only used when data_source="demo")
        
    Returns:
        Configured data ingestion instance
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
            short_ma = sum(self.price_history[symbol][-self.short_window:]) / self.short_window
            long_ma = sum(self.price_history[symbol]) / len(self.price_history[symbol])
            
            if short_ma > long_ma:
                signal = "BUY"
            elif short_ma < long_ma:
                signal = "SELL"
            else:
                signal = "HOLD"
            
            logger.info(f"{symbol}: {signal} - Price: {price}, Short MA: {short_ma:.2f}, Long MA: {long_ma:.2f}")


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
            print("  python3.10 data_ingestion.py demo    - Run test data demo")
            print("  python3.10 data_ingestion.py test    - Quick test")
            print("  python3.10 data_ingestion.py         - Run with real/fallback data")
            
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("Stopping data ingestion...")
        except Exception as e:
            logger.error(f"Error: {e}") 