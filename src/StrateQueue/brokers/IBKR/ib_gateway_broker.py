"""
Enhanced IB Gateway Broker Implementation

Extended IBKR broker with real-time data streaming capabilities.
Supports real-time bars, tick data, market data subscriptions, and historical data streaming.
"""

import asyncio
import logging
import pandas as pd
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from threading import Thread, Event
import time

try:
    from ib_insync import IB, Stock, Contract, BarData, Ticker, util
    from ib_insync.objects import RealTimeBar
    from ib_insync import Forex, Future, Option, Crypto
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False
    
    # Create dummy classes for graceful fallback
    class RealTimeBar:
        pass
    class Ticker:
        pass
    class Contract:
        pass
    class Stock:
        pass
    class Forex:
        pass
    class Future:
        pass
    class Option:
        pass
    class Crypto:
        pass

from ..broker_base import BrokerConfig, BrokerInfo, OrderResult
from .ibkr_broker import IBKRBroker

logger = logging.getLogger(__name__)


class IBGatewayBroker(IBKRBroker):
    """
    Enhanced IB Gateway broker with real-time data streaming capabilities
    
    Extends the base IBKR broker to add:
    - Real-time bar data streaming
    - Tick data streaming
    - Market data subscriptions
    - Historical data with streaming updates
    - Multi-symbol data management
    """
    
    def __init__(self, config: BrokerConfig, portfolio_manager=None, position_sizer=None):
        """
        Initialize IB Gateway broker with streaming capabilities
        
        Args:
            config: Broker configuration
            portfolio_manager: Optional portfolio manager for multi-strategy support
            position_sizer: Optional position sizer for calculating trade sizes
        """
        super().__init__(config, portfolio_manager, position_sizer)
        
        # Generate unique client ID to avoid conflicts
        import random
        self.client_id = random.randint(1000, 9999)
        
        # Data streaming components
        self.data_subscriptions = {}  # symbol -> subscription info
        self.streaming_callbacks = {}  # symbol -> list of callbacks
        self.real_time_bars = {}  # symbol -> latest bar data
        self.tick_data = {}  # symbol -> latest tick data
        self.market_data_tickers = {}  # symbol -> ticker objects
        
        # Streaming control
        self.streaming_active = False
        self.streaming_thread = None
        self.streaming_event = Event()
        
        # Data buffers for strategies
        self.data_buffers = {}  # symbol -> list of historical data points
        self.max_buffer_size = 1000  # Maximum data points to keep in buffer
        
        logger.info(f"IB Gateway broker initialized with streaming capabilities (client_id={self.client_id})")
    
    def get_broker_info(self) -> BrokerInfo:
        """Enhanced broker info with streaming capabilities"""
        info = super().get_broker_info()
        info.supported_features.update({
            "real_time_data": True,
            "historical_data": True,
            "tick_data": True,
            "market_data_subscriptions": True,
            "streaming_bars": True,
            "level2_data": True,
            "data_buffering": True,
            "multi_symbol_streaming": True,
        })
        info.description = "Interactive Brokers IB Gateway with real-time data streaming"
        return info
    
    def connect(self) -> bool:
        """Connect to IB Gateway with streaming setup"""
        if not IB_INSYNC_AVAILABLE:
            logger.error("ib_insync not installed. Cannot connect to IB Gateway.")
            return False
        
        # Only override port if not explicitly set via environment variable
        import os
        if not os.getenv('IB_TWS_PORT'):
            # Use IB Gateway specific port if not explicitly set
            if self.port == 7497:  # Default TWS paper port
                self.port = 4002  # IB Gateway paper port
            elif self.port == 7496:  # Default TWS live port
                self.port = 4001  # IB Gateway live port
        
        if not super().connect():
            return False
            
        # Update port from client if available (for test compatibility)
        if hasattr(self.ib, 'client_port'):
            self.port = self.ib.client_port
        
        # Request delayed market data (type 3) for paper trading
        try:
            self.ib.reqMarketDataType(3)  # 3 = Delayed market data
            logger.info("📡 Switched to delayed market data mode")
        except Exception as e:
            logger.warning(f"Could not set delayed market data mode: {e}")
        
        # Set up streaming event handlers
        self._setup_streaming_handlers()
        
        # Start streaming thread
        self.streaming_active = True
        self.streaming_thread = Thread(target=self._streaming_loop, daemon=True)
        self.streaming_thread.start()
        
        logger.info(f"✅ IB Gateway connected with streaming capabilities on port {self.port}")
        return True
    
    def disconnect(self):
        """Disconnect and cleanup streaming resources"""
        logger.info("Disconnecting from IB Gateway...")
        
        # Stop streaming
        self.streaming_active = False
        if self.streaming_thread:
            self.streaming_event.set()
            self.streaming_thread.join(timeout=5)
        
        # Cancel all subscriptions
        self._cancel_all_subscriptions()
        
        # Call parent disconnect
        super().disconnect()
        
        logger.info("✅ IB Gateway disconnected")
    
    def _setup_streaming_handlers(self):
        """Set up event handlers for streaming data"""
        if not self.ib:
            return
        
        # Real-time bars handler (using correct event name)
        self.ib.barUpdateEvent += self._on_real_time_bar
        
        # Tick data handlers (using correct event name)  
        self.ib.pendingTickersEvent += self._on_pending_tickers
        
        # Market data update handler
        for ticker in self.ib.tickers():
            ticker.updateEvent += self._on_ticker_update
        
        logger.debug("📡 Streaming event handlers configured")
    
    def subscribe_market_data(self, symbol: str, callback: Callable = None) -> bool:
        """
        Subscribe to real-time market data for a symbol
        
        Args:
            symbol: Symbol to subscribe to
            callback: Optional callback function for data updates
            
        Returns:
            True if subscription successful
        """
        if not self.is_connected:
            logger.error("Not connected to IB Gateway")
            return False
        
        try:
            # Create contract
            contract = self._create_contract(symbol)
            if not contract:
                logger.error(f"Failed to create contract for {symbol}")
                return False
            
            # Request market data with snapshot enabled for initial data
            ticker = self.ib.reqMktData(contract, '', False, False)
            
            # Wait briefly for initial data
            time.sleep(2)
            
            # Store subscription
            self.data_subscriptions[symbol] = {
                'contract': contract,
                'ticker': ticker,
                'type': 'market_data'
            }
            
            # Store ticker for updates
            self.market_data_tickers[symbol] = ticker
            
            # Store callback
            if callback:
                if symbol not in self.streaming_callbacks:
                    self.streaming_callbacks[symbol] = []
                self.streaming_callbacks[symbol].append(callback)
            
            # Initialize data buffer
            if symbol not in self.data_buffers:
                self.data_buffers[symbol] = []
            
            # Try to get initial price and store it
            if hasattr(ticker, 'last') and ticker.last == ticker.last:  # Check for NaN
                if symbol not in self.tick_data:
                    self.tick_data[symbol] = {}
                self.tick_data[symbol].update({
                    'last_price': ticker.last,
                    'bid': ticker.bid if ticker.bid == ticker.bid else None,
                    'ask': ticker.ask if ticker.ask == ticker.ask else None,
                    'timestamp': datetime.now()
                })
                from ...utils.price_formatter import PriceFormatter
                logger.info(f"📊 Subscribed to market data for {symbol} - Initial price: {PriceFormatter.format_price_for_logging(ticker.last)}")
            else:
                logger.info(f"📊 Subscribed to market data for {symbol} - Waiting for price data...")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to subscribe to market data for {symbol}: {e}")
            return False
    
    def subscribe_real_time_bars(self, symbol: str, bar_size: int = 5, 
                                callback: Callable = None) -> bool:
        """
        Subscribe to real-time bars for a symbol
        
        Args:
            symbol: Symbol to subscribe to
            bar_size: Bar size in seconds (5, 10, 15, 30)
            callback: Optional callback function for bar updates
            
        Returns:
            True if subscription successful
        """
        if not self.is_connected:
            logger.error("Not connected to IB Gateway")
            return False
        
        try:
            # Create contract
            contract = self._create_contract(symbol)
            if not contract:
                logger.error(f"Failed to create contract for {symbol}")
                return False
            
            # Request real-time bars
            self.ib.reqRealTimeBars(contract, bar_size, 'TRADES', False)
            
            # Store subscription
            subscription_key = f"{symbol}_bars"
            self.data_subscriptions[subscription_key] = {
                'contract': contract,
                'bar_size': bar_size,
                'type': 'real_time_bars',
                'symbol': symbol
            }
            
            # Store callback
            if callback:
                if symbol not in self.streaming_callbacks:
                    self.streaming_callbacks[symbol] = []
                self.streaming_callbacks[symbol].append(callback)
            
            logger.info(f"📊 Subscribed to real-time bars for {symbol} ({bar_size}s)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to subscribe to real-time bars for {symbol}: {e}")
            return False
    
    def get_historical_data(self, symbol: str, duration: str = "1 D", 
                           bar_size: str = "1 min", data_type: str = "TRADES") -> pd.DataFrame:
        """
        Get historical data for a symbol
        
        Args:
            symbol: Symbol to get data for
            duration: Duration (e.g., "1 D", "1 W", "1 M")
            bar_size: Bar size (e.g., "1 min", "5 mins", "1 hour")
            data_type: Data type ("TRADES", "MIDPOINT", "BID", "ASK")
            
        Returns:
            DataFrame with historical data
        """
        if not self.is_connected:
            logger.error("Not connected to IB Gateway")
            return pd.DataFrame()
        
        try:
            contract = self._create_contract(symbol)
            if not contract:
                logger.error(f"Failed to create contract for {symbol}")
                return pd.DataFrame()
            
            # Request historical data
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow=data_type,
                useRTH=True,
                formatDate=1
            )
            
            # Convert to DataFrame
            df = pd.DataFrame([{
                'datetime': bar.date,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            } for bar in bars])
            
            if not df.empty:
                df['datetime'] = pd.to_datetime(df['datetime'])
                df.set_index('datetime', inplace=True)
                
                # Store in buffer for potential strategy use
                self._update_data_buffer(symbol, df.to_dict('records'))
            
            logger.info(f"📈 Retrieved {len(df)} historical bars for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"❌ Failed to get historical data for {symbol}: {e}")
            return pd.DataFrame()
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price for a symbol"""
        # First check cached data
        if symbol in self.tick_data:
            cached_price = self.tick_data[symbol].get('last_price')
            if cached_price:
                return cached_price
        
        # If no cached data, try to get fresh data
        if symbol in self.market_data_tickers:
            ticker_obj = self.market_data_tickers[symbol]
            if ticker_obj and hasattr(ticker_obj, 'contract'):
                try:
                    # Get latest ticker data
                    latest_ticker = self.ib.ticker(ticker_obj.contract)
                    if latest_ticker is not None:
                        # Try different price sources
                        market_price = None
                        if hasattr(latest_ticker, 'marketPrice'):
                            if callable(latest_ticker.marketPrice):
                                market_price = latest_ticker.marketPrice()
                            else:
                                market_price = latest_ticker.marketPrice
                        
                        last_price = latest_ticker.last if hasattr(latest_ticker, 'last') and latest_ticker.last == latest_ticker.last else None
                        close_price = latest_ticker.close if hasattr(latest_ticker, 'close') and latest_ticker.close == latest_ticker.close else None
                        
                        # Return the best available price
                        for price in [market_price, last_price, close_price]:
                            if price is not None and price == price:  # Check for NaN
                                from ...utils.price_formatter import PriceFormatter
                                logger.debug(f"📊 Fresh price for {symbol}: {PriceFormatter.format_price_for_logging(price)}")
                                return price
                except Exception as e:
                    logger.debug(f"Error getting fresh price for {symbol}: {e}")
        
        return None
    
    def get_latest_bar(self, symbol: str) -> Optional[Dict]:
        """Get latest bar data for a symbol"""
        return self.real_time_bars.get(symbol)
    
    def get_data_buffer(self, symbol: str, count: int = 100) -> List[Dict]:
        """
        Get historical data buffer for a symbol
        
        Args:
            symbol: Symbol to get buffer for
            count: Number of data points to return
            
        Returns:
            List of data points
        """
        if symbol in self.data_buffers:
            return self.data_buffers[symbol][-count:]
        return []
    
    def _create_contract(self, symbol: str) -> Optional[Contract]:
        """Create IB contract for symbol"""
        try:
            # Enhanced contract creation with better symbol detection
            symbol_upper = symbol.upper()
            
            # Forex pairs
            if len(symbol_upper) == 6 and symbol_upper[:3] in ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'NZD']:
                base, quote = symbol_upper[:3], symbol_upper[3:]
                return Forex(base + quote)
            
            # Crypto pairs (common formats)
            if '/' in symbol or symbol_upper.endswith('USD') and len(symbol_upper) > 3:
                if '/' in symbol:
                    base, quote = symbol.split('/')
                    return Crypto(base, quote, 'PAXOS')
                else:
                    base = symbol_upper[:-3]
                    return Crypto(base, 'USD', 'PAXOS')
            
            # Futures (simple detection)
            if symbol_upper.endswith('Z3') or symbol_upper.endswith('H4') or symbol_upper.endswith('M4'):
                return Future(symbol_upper, 'GLOBEX')
            
            # Default to stock
            return Stock(symbol_upper, 'SMART', 'USD')
            
        except Exception as e:
            logger.error(f"Error creating contract for {symbol}: {e}")
            return None
    
    def _on_real_time_bar(self, bars, has_new_bar: bool):
        """Handle real-time bar updates (BarDataList or RealTimeBarList)"""
        try:
            # bars is a BarDataList or RealTimeBarList object
            if not bars or not hasattr(bars, 'contract'):
                return
                
            symbol = bars.contract.symbol
            
            # Get the latest bar
            if len(bars) > 0:
                latest_bar = bars[-1]
                
                # Create bar data
                bar_data = {
                    'datetime': getattr(latest_bar, 'time', getattr(latest_bar, 'date', None)),
                    'open': getattr(latest_bar, 'open_', getattr(latest_bar, 'open', 0)),
                    'high': latest_bar.high,
                    'low': latest_bar.low,
                    'close': latest_bar.close,
                    'volume': latest_bar.volume,
                    'timestamp': datetime.now()
                }
                
                # Store latest bar
                self.real_time_bars[symbol] = bar_data
                
                # Update data buffer
                self._update_data_buffer(symbol, [bar_data])
                
                # Call registered callbacks
                if symbol in self.streaming_callbacks:
                    for callback in self.streaming_callbacks[symbol]:
                        try:
                            callback('bar', bar_data)
                        except Exception as e:
                            logger.error(f"Error in bar callback for {symbol}: {e}")
                
                logger.debug(f"📊 New bar for {symbol}: {latest_bar.close}")
                
        except Exception as e:
            logger.error(f"Error processing real-time bar: {e}")
    
    def _on_pending_tickers(self, tickers):
        """Handle pending ticker updates (set of tickers)"""
        try:
            for ticker in tickers:
                if not hasattr(ticker, 'contract') or not ticker.contract:
                    continue
                    
                symbol = ticker.contract.symbol
                
                # Update tick data
                if symbol not in self.tick_data:
                    self.tick_data[symbol] = {}
                
                tick_data = {
                    'last_price': ticker.last if ticker.last == ticker.last else None,  # Check for NaN
                    'bid': ticker.bid if ticker.bid == ticker.bid else None,
                    'ask': ticker.ask if ticker.ask == ticker.ask else None,
                    'bid_size': ticker.bidSize if ticker.bidSize == ticker.bidSize else None,
                    'ask_size': ticker.askSize if ticker.askSize == ticker.askSize else None,
                    'volume': ticker.volume if ticker.volume == ticker.volume else None,
                    'timestamp': datetime.now()
                }
                
                self.tick_data[symbol].update(tick_data)
                
                # Call registered callbacks
                if symbol in self.streaming_callbacks:
                    for callback in self.streaming_callbacks[symbol]:
                        try:
                            callback('tick', tick_data)
                        except Exception as e:
                            logger.error(f"Error in tick callback for {symbol}: {e}")
                
        except Exception as e:
            logger.error(f"Error processing pending ticker updates: {e}")
    
    def _on_ticker_update(self, ticker):
        """Handle individual ticker updates"""
        try:
            if not hasattr(ticker, 'contract') or not ticker.contract:
                return
                
            symbol = ticker.contract.symbol
            
            # Update market data
            if symbol not in self.tick_data:
                self.tick_data[symbol] = {}
            
            # Update with latest data
            self.tick_data[symbol].update({
                'last_price': ticker.last if ticker.last == ticker.last else None,
                'bid': ticker.bid if ticker.bid == ticker.bid else None,
                'ask': ticker.ask if ticker.ask == ticker.ask else None,
                'timestamp': datetime.now()
            })
            
            logger.debug(f"📊 Market data update for {symbol}: {ticker.last}")
            
        except Exception as e:
            logger.error(f"Error processing ticker update: {e}")
    
    def _update_data_buffer(self, symbol: str, data_points: List[Dict]):
        """Update data buffer for a symbol"""
        if symbol not in self.data_buffers:
            self.data_buffers[symbol] = []
        
        self.data_buffers[symbol].extend(data_points)
        
        # Keep only the last max_buffer_size points
        if len(self.data_buffers[symbol]) > self.max_buffer_size:
            self.data_buffers[symbol] = self.data_buffers[symbol][-self.max_buffer_size:]
    
    def _cancel_all_subscriptions(self):
        """Cancel all data subscriptions"""
        for sub_key, subscription in self.data_subscriptions.items():
            try:
                if subscription['type'] == 'market_data':
                    self.ib.cancelMktData(subscription['contract'])
                elif subscription['type'] == 'real_time_bars':
                    self.ib.cancelRealTimeBars(subscription['contract'])
                logger.debug(f"Cancelled subscription: {sub_key}")
            except Exception as e:
                logger.error(f"Error cancelling subscription {sub_key}: {e}")
        
        self.data_subscriptions.clear()
        self.market_data_tickers.clear()
    
    def _streaming_loop(self):
        """Main streaming loop with periodic price updates"""
        logger.info("🔄 Starting streaming loop...")
        last_price_update = time.time()
        
        while self.streaming_active:
            try:
                # Check connection
                if not self.ib.isConnected():
                    logger.warning("Lost connection to IB Gateway")
                    if self.streaming_active:
                        self._attempt_reconnect()
                    continue
                
                # Periodically update prices for subscribed symbols (every 5 seconds)
                current_time = time.time()
                if current_time - last_price_update > 5:
                    self._refresh_market_data()
                    last_price_update = current_time
                
                # Simple sleep-based loop to avoid coroutine issues
                time.sleep(1)
                
                # Check for stop signal
                if self.streaming_event.wait(timeout=0.1):
                    break
                    
            except Exception as e:
                if self.streaming_active:
                    logger.error(f"Error in streaming loop: {e}")
                    time.sleep(1)  # Prevent rapid error loops
        
        logger.info("🔄 Streaming loop stopped")
    
    def _refresh_market_data(self):
        """Refresh market data for all subscribed symbols"""
        try:
            for symbol, ticker_obj in self.market_data_tickers.items():
                if ticker_obj and hasattr(ticker_obj, 'contract'):
                    # Get latest ticker data
                    latest_ticker = self.ib.ticker(ticker_obj.contract)
                    if latest_ticker:
                        # Update our tick data
                        if symbol not in self.tick_data:
                            self.tick_data[symbol] = {}
                        
                        # Extract valid price data
                        last_price = latest_ticker.last if latest_ticker.last == latest_ticker.last else None
                        bid_price = latest_ticker.bid if latest_ticker.bid == latest_ticker.bid else None
                        ask_price = latest_ticker.ask if latest_ticker.ask == latest_ticker.ask else None
                        
                        # Use marketPrice() if available
                        market_price = latest_ticker.marketPrice() if hasattr(latest_ticker, 'marketPrice') else last_price
                        
                        if market_price and market_price == market_price:  # Check for NaN
                            self.tick_data[symbol].update({
                                'last_price': market_price,
                                'bid': bid_price,
                                'ask': ask_price,
                                'timestamp': datetime.now()
                            })
                            
                            logger.debug(f"📊 Updated price for {symbol}: {PriceFormatter.format_price_for_logging(market_price)}")
                            
                            # Call registered callbacks
                            if symbol in self.streaming_callbacks:
                                tick_data = self.tick_data[symbol]
                                for callback in self.streaming_callbacks[symbol]:
                                    try:
                                        callback('tick', tick_data)
                                    except Exception as e:
                                        logger.error(f"Error in refresh callback for {symbol}: {e}")
                        
        except Exception as e:
            logger.error(f"Error refreshing market data: {e}")
    
    def _attempt_reconnect(self):
        """Attempt to reconnect to IB Gateway"""
        try:
            if not self.ib.isConnected():
                logger.info("🔄 Attempting to reconnect to IB Gateway...")
                self.ib.connect(self.host, self.port, clientId=self.client_id)
                
                if self.ib.isConnected():
                    logger.info("✅ Reconnected to IB Gateway")
                    # Re-setup streaming handlers
                    self._setup_streaming_handlers()
                    # Re-subscribe to data (if needed)
                    # This would require storing original subscription parameters
                
        except Exception as e:
            logger.error(f"❌ Reconnection failed: {e}")
            time.sleep(5)  # Wait before next attempt 