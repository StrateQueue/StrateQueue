#!/usr/bin/env python3.10
"""
IB Gateway Streaming Example

This example demonstrates how to use the IB Gateway broker with real-time data streaming
capabilities for live trading strategies.

Prerequisites:
1. Install ib_insync: pip install ib_insync
2. Install StrateQueue with IBKR support: pip install stratequeue[ibkr]
3. Set up IB Gateway environment variables
4. Start IB Gateway and enable API access

Environment Variables:
export IB_TWS_HOST="127.0.0.1"
export IB_TWS_PORT="4002"  # 4002 for paper, 4001 for live
export IB_CLIENT_ID="1"
export IB_PAPER="true"
export IB_GATEWAY_MODE="true"
"""

import sys
import time
import logging
import pandas as pd
from datetime import datetime
from typing import Dict, Any

# Add StrateQueue to path
sys.path.append('../src')

from StrateQueue.brokers import BrokerFactory
from StrateQueue.live_system.ib_data_manager import IBDataManager
from StrateQueue.core.signal_extractor import TradingSignal, SignalType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StreamingStrategy:
    """
    Example streaming strategy that uses real-time data from IB Gateway
    """
    
    def __init__(self, data_manager: IBDataManager):
        self.data_manager = data_manager
        self.positions = {}  # Track our positions
        self.last_signals = {}  # Track last signals per symbol
        
        # Strategy parameters
        self.price_change_threshold = 0.005  # 0.5% price change threshold
        self.max_position_size = 1000  # Maximum position size
        
        logger.info("StreamingStrategy initialized")
    
    def on_market_data(self, symbol: str, data_type: str, data: Dict[str, Any]):
        """
        Callback function for market data updates
        
        Args:
            symbol: Symbol that was updated
            data_type: Type of data ('tick', 'bar')
            data: Data dictionary
        """
        try:
            if data_type == 'tick' and 'last_price' in data:
                current_price = data['last_price']
                
                if current_price is None:
                    return
                
                from src.StrateQueue.utils.price_formatter import PriceFormatter
                bid_str = PriceFormatter.format_price_for_display(data.get('bid')) if data.get('bid') != 'N/A' else 'N/A'
                ask_str = PriceFormatter.format_price_for_display(data.get('ask')) if data.get('ask') != 'N/A' else 'N/A'
                logger.info(f"📊 {symbol}: {PriceFormatter.format_price_for_display(current_price)} (bid: {bid_str}, ask: {ask_str})")
                
                # Simple momentum strategy logic
                self._check_momentum_signal(symbol, current_price)
                
            elif data_type == 'bar':
                logger.info(f"📈 {symbol} Bar: O:{data['open']:.2f} H:{data['high']:.2f} L:{data['low']:.2f} C:{data['close']:.2f} V:{data['volume']}")
                
                # Bar-based strategy logic
                self._check_bar_signal(symbol, data)
                
        except Exception as e:
            logger.error(f"Error processing market data for {symbol}: {e}")
    
    def _check_momentum_signal(self, symbol: str, current_price: float):
        """Check for momentum-based trading signals"""
        try:
            # Get recent price history
            price_series = self.data_manager.get_price_series(symbol, count=50)
            
            if len(price_series) < 10:
                return  # Not enough data
            
            # Calculate simple momentum
            recent_prices = price_series.tail(10)
            price_change = (current_price - recent_prices.iloc[0]) / recent_prices.iloc[0]
            
            # Generate signals based on momentum
            if price_change > self.price_change_threshold:
                if self.last_signals.get(symbol) != 'BUY':
                    logger.info(f"🟢 BUY signal for {symbol} - momentum: {price_change:.2%}")
                    self.last_signals[symbol] = 'BUY'
                    # Here you would execute the buy order
                    
            elif price_change < -self.price_change_threshold:
                if self.last_signals.get(symbol) != 'SELL':
                    logger.info(f"🔴 SELL signal for {symbol} - momentum: {price_change:.2%}")
                    self.last_signals[symbol] = 'SELL'
                    # Here you would execute the sell order
            
        except Exception as e:
            logger.error(f"Error in momentum signal check for {symbol}: {e}")
    
    def _check_bar_signal(self, symbol: str, bar_data: Dict):
        """Check for bar-based trading signals"""
        try:
            # Get OHLCV dataframe
            ohlcv_df = self.data_manager.get_ohlcv_dataframe(symbol, count=20)
            
            if len(ohlcv_df) < 5:
                return  # Not enough bar data
            
            # Simple moving average crossover
            ohlcv_df['sma_5'] = ohlcv_df['close'].rolling(5).mean()
            ohlcv_df['sma_10'] = ohlcv_df['close'].rolling(10).mean()
            
            if len(ohlcv_df) >= 2:
                current_sma5 = ohlcv_df['sma_5'].iloc[-1]
                current_sma10 = ohlcv_df['sma_10'].iloc[-1]
                prev_sma5 = ohlcv_df['sma_5'].iloc[-2]
                prev_sma10 = ohlcv_df['sma_10'].iloc[-2]
                
                # Golden cross (bullish)
                if current_sma5 > current_sma10 and prev_sma5 <= prev_sma10:
                    logger.info(f"🌟 Golden Cross detected for {symbol} - SMA5 crossed above SMA10")
                
                # Death cross (bearish)
                elif current_sma5 < current_sma10 and prev_sma5 >= prev_sma10:
                    logger.info(f"💀 Death Cross detected for {symbol} - SMA5 crossed below SMA10")
            
        except Exception as e:
            logger.error(f"Error in bar signal check for {symbol}: {e}")


def main():
    """Main function to demonstrate IB Gateway streaming"""
    logger.info("🚀 Starting IB Gateway Streaming Example")
    
    try:
        # Create IB Gateway broker
        logger.info("Creating IB Gateway broker...")
        broker = BrokerFactory.create_broker('ib_gateway')
        
        # Connect to IB Gateway
        logger.info("Connecting to IB Gateway...")
        if not broker.connect():
            logger.error("❌ Failed to connect to IB Gateway")
            logger.info("💡 Make sure IB Gateway is running and API is enabled")
            logger.info("💡 Check your environment variables:")
            logger.info("   IB_TWS_HOST, IB_TWS_PORT, IB_CLIENT_ID, IB_GATEWAY_MODE")
            return
        
        logger.info("✅ Connected to IB Gateway")
        
        # Create data manager
        data_manager = IBDataManager(broker)
        
        # Create strategy
        strategy = StreamingStrategy(data_manager)
        
        # Subscribe to symbols for real-time data
        symbols = ['AAPL', 'MSFT', 'GOOGL']  # You can modify this list
        
        logger.info(f"📊 Subscribing to symbols: {symbols}")
        for symbol in symbols:
            success = data_manager.subscribe_to_symbol(
                symbol=symbol,
                callback=strategy.on_market_data,
                subscription_type='both'  # Both market data and bars
            )
            
            if success:
                logger.info(f"✅ Subscribed to {symbol}")
            else:
                logger.error(f"❌ Failed to subscribe to {symbol}")
        
        # Display broker info
        broker_info = broker.get_broker_info()
        logger.info(f"📋 Broker: {broker_info.name} v{broker_info.version}")
        logger.info(f"📋 Description: {broker_info.description}")
        logger.info(f"📋 Supported markets: {broker_info.supported_markets}")
        
        # Get account info
        account_info = broker.get_account_info()
        if account_info:
            logger.info(f"💰 Account ID: {account_info.account_id}")
            logger.info(f"💰 Total Value: ${account_info.total_value:,.2f}")
            logger.info(f"💰 Cash: ${account_info.cash:,.2f}")
        
        # Run the streaming loop
        logger.info("🔄 Starting data streaming...")
        logger.info("Press Ctrl+C to stop")
        
        try:
            while True:
                time.sleep(10)  # Sleep for 10 seconds
                
                # Print statistics every 10 seconds
                stats = data_manager.get_statistics()
                logger.info(f"📈 Statistics: {stats['subscribed_symbols']} symbols, "
                           f"{stats['total_data_points']} data points")
                
                # Print latest data for each symbol
                for symbol in symbols:
                    latest_data = data_manager.get_latest_data(symbol)
                    if latest_data:
                        data_type = latest_data.get('data_type', 'unknown')
                        if data_type == 'tick' and 'last_price' in latest_data:
                            price = latest_data['last_price']
                            if price:
                                logger.info(f"💹 {symbol}: ${price:.2f}")
                
        except KeyboardInterrupt:
            logger.info("🛑 Received interrupt signal")
    
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        logger.info("🧹 Cleaning up...")
        try:
            if 'broker' in locals() and broker:
                broker.disconnect()
                logger.info("✅ Disconnected from IB Gateway")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        
        logger.info("👋 Example finished")


def test_historical_data():
    """Test historical data retrieval"""
    logger.info("🔍 Testing historical data retrieval...")
    
    try:
        # Create and connect broker
        broker = BrokerFactory.create_broker('ib_gateway')
        if not broker.connect():
            logger.error("❌ Failed to connect for historical data test")
            return
        
        # Get historical data
        logger.info("📈 Requesting historical data for AAPL...")
        historical_data = broker.get_historical_data(
            symbol='AAPL',
            duration='1 D',
            bar_size='1 min'
        )
        
        if not historical_data.empty:
            logger.info(f"✅ Retrieved {len(historical_data)} historical bars")
            logger.info(f"📊 Data range: {historical_data.index[0]} to {historical_data.index[-1]}")
            logger.info(f"📊 Latest close: ${historical_data['close'].iloc[-1]:.2f}")
            
            # Display first few rows
            print("\nFirst 5 bars:")
            print(historical_data.head())
            
            print("\nLast 5 bars:")
            print(historical_data.tail())
        else:
            logger.warning("⚠️ No historical data retrieved")
        
        broker.disconnect()
        
    except Exception as e:
        logger.error(f"❌ Error in historical data test: {e}")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--test-historical':
        test_historical_data()
    else:
        main() 