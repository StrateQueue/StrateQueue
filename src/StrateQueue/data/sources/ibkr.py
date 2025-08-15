"""
Interactive Brokers (IBKR) Data Source

Historical and real-time market data from Interactive Brokers using IB Gateway.
This data source uses the IB Gateway broker internally for data retrieval.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from .data_source_base import BaseDataIngestion, MarketData
from ...core.resample import plan_base_granularity, resample_ohlcv

logger = logging.getLogger(__name__)


class IBKRDataIngestion(BaseDataIngestion):
    """
    IBKR data ingestion using IB Gateway broker for historical and real-time data
    """
    SUPPORTED_GRANULARITIES = {
        "1s", "5s", "10s", "15s", "30s",
        "1m", "2m", "3m", "5m", "10m", "15m", "20m", "30m",
        "1h", "2h", "3h", "4h", "8h",
        "1d", "1w", "1mo",
    }
    DEFAULT_GRANULARITY = "1m"
    
    def __init__(self, granularity: str = "1m", paper_trading: bool = True):
        """
        Initialize IBKR data source
        
        Args:
            granularity: Data granularity (e.g., '1m', '5m', '1h', '1d')
            paper_trading: Whether to use paper trading mode
        """
        super().__init__()
        
        self.granularity = granularity
        self.paper_trading = paper_trading
        self.broker = None
        self.data_manager = None
        
        # Validate granularity
        parsed_granularity = self._parse_granularity(granularity)
        self.granularity_seconds = parsed_granularity.to_seconds()
        
        # Map StrateQueue granularities to IB bar sizes
        self.bar_size_map = {
            "1s": "1 sec",
            "5s": "5 secs",
            "10s": "10 secs",
            "15s": "15 secs",
            "30s": "30 secs",
            "1m": "1 min",
            "2m": "2 mins",
            "3m": "3 mins",
            "5m": "5 mins",
            "10m": "10 mins",
            "15m": "15 mins",
            "20m": "20 mins",
            "30m": "30 mins",
            "1h": "1 hour",
            "2h": "2 hours",
            "3h": "3 hours",
            "4h": "4 hours",
            "8h": "8 hours",
            "1d": "1 day",
            "1w": "1 week",
            "1mo": "1 month"
        }
        
        # Validate granularity is supported
        if granularity not in self.bar_size_map:
            supported = ", ".join(self.bar_size_map.keys())
            raise ValueError(f"Granularity '{granularity}' not supported by IBKR. Supported: {supported}")
        
        self.ib_bar_size = self.bar_size_map[granularity]
        
        # Duration mapping for historical data requests
        self.duration_map = {
            # Map days back to IB duration strings
            1: "1 D",
            7: "1 W",
            30: "1 M",
            90: "3 M",
            180: "6 M",
            365: "1 Y"
        }
        
        logger.info(f"IBKR data source initialized with granularity {granularity} (bar size: {self.ib_bar_size})")

    @classmethod
    def get_supported_granularities(cls, **_context) -> set[str]:
        return set(cls.SUPPORTED_GRANULARITIES)

    @classmethod
    def accepts_granularity(cls, granularity: str, **_context) -> bool:
        return granularity in cls.SUPPORTED_GRANULARITIES
    
    def _get_duration_string(self, days_back: int) -> str:
        """Convert days back to IB duration string"""
        # Find the best matching duration
        best_duration = "1 D"
        for days, duration in self.duration_map.items():
            if days_back <= days:
                best_duration = duration
                break
        
        # For very long periods, use years
        if days_back > 365:
            years = max(1, days_back // 365)
            best_duration = f"{years} Y"
        
        return best_duration
    
    def _ensure_broker_connected(self):
        """Ensure broker is connected"""
        if self.broker is None:
            try:
                from ...brokers import BrokerFactory
                from ...brokers.broker_base import BrokerConfig
                
                # Determine the correct port to use
                default_port = '7497'  # TWS paper trading (most common)
                if os.getenv('IB_GATEWAY_MODE', '').lower() == 'true':
                    default_port = '4002' if self.paper_trading else '4001'  # IB Gateway ports
                
                # Use a different client ID for data source to avoid conflicts
                base_client_id = int(os.getenv('IB_CLIENT_ID', '1'))
                data_client_id = base_client_id + 10  # Offset for data source
                
                # Create broker config - support data-specific credentials from broker setup
                config = BrokerConfig(
                    broker_type='ib_gateway',
                    paper_trading=self.paper_trading,
                    credentials={
                        'host': os.getenv('IBKR_DATA_HOST') or os.getenv('IB_TWS_HOST', 'localhost'),
                        'port': int(os.getenv('IBKR_DATA_PORT') or os.getenv('IB_TWS_PORT', default_port)),
                        'client_id': data_client_id,
                        'paper_trading': self.paper_trading
                    }
                )
                
                # Create broker
                self.broker = BrokerFactory.create_broker('ib_gateway', config)
                
                # Connect
                if not self.broker.connect():
                    raise RuntimeError("Failed to connect to IB Gateway")
                
                logger.info("✅ Connected to IB Gateway for data ingestion")
                
            except Exception as e:
                logger.error(f"❌ Failed to connect to IB Gateway: {e}")
                raise
    
    async def fetch_historical_data(self, symbol: str, days_back: int = 30, 
                                  granularity: str = "1m") -> pd.DataFrame:
        """
        Fetch historical OHLCV data from IB Gateway
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            days_back: Number of days of historical data
            granularity: Data granularity (e.g., '1m', '5m', '1h', '1d')
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Ensure broker is connected
            self._ensure_broker_connected()
            
            # Use provided granularity or fall back to instance default
            target_granularity = granularity or self.granularity
            
            # Validate / plan granularity
            if target_granularity in self.bar_size_map:
                plan = None
                ib_bar_size = self.bar_size_map[target_granularity]
            else:
                plan = plan_base_granularity(self.bar_size_map.keys(), target_granularity)
                ib_bar_size = self.bar_size_map[plan.source_granularity]
            duration = self._get_duration_string(days_back)
            
            # Get historical data from broker
            logger.info(f"Fetching {duration} of {symbol} data with {ib_bar_size} bars")
            
            df = self.broker.get_historical_data(
                symbol=symbol,
                duration=duration,
                bar_size=ib_bar_size,
                data_type="TRADES"
            )
            
            if df.empty:
                logger.warning(f"No historical data returned for {symbol}")
                return pd.DataFrame()
            
            # Ensure column names match StrateQueue format
            expected_columns = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in expected_columns):
                # Rename columns if needed
                df = df.rename(columns={
                    'Open': 'open',
                    'High': 'high',
                    'Low': 'low',
                    'Close': 'close',
                    'Volume': 'volume'
                })
            
            # Convert to uppercase for consistency with other data sources
            df.columns = [col.capitalize() for col in df.columns]
            
            # Remove any rows with NaN values
            df = df.dropna()
            
            # Ensure timezone-naive datetime index
            if hasattr(df.index, 'tz') and df.index.tz is not None:
                df.index = df.index.tz_convert(None)
            
            # Resample if needed
            if plan is not None and plan.target_granularity:
                df = resample_ohlcv(df, plan.target_granularity)

            # Cache the data
            self.historical_data[symbol] = df
            
            logger.info(f"✅ Fetched {len(df)} historical bars for {symbol} from IBKR")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error fetching IBKR historical data for {symbol}: {e}")
            return pd.DataFrame()
    
    async def subscribe_to_symbol(self, symbol: str):
        """Subscribe to real-time data for a symbol"""
        try:
            # Ensure broker is connected
            self._ensure_broker_connected()
            
            # Create data manager if not exists
            if self.data_manager is None:
                from ...live_system.ib_data_manager import IBDataManager
                self.data_manager = IBDataManager(self.broker)
            
            # Subscribe to real-time data
            def data_callback(symbol: str, data_type: str, data: Dict[str, Any]):
                """Handle real-time data updates"""
                try:
                    if data_type == 'tick' and 'last_price' in data:
                        # Convert tick data to MarketData
                        market_data = MarketData(
                            symbol=symbol,
                            timestamp=data.get('received_at', datetime.now()),
                            open=data['last_price'],  # Use last price for all OHLC
                            high=data['last_price'],
                            low=data['last_price'],
                            close=data['last_price'],
                            volume=0  # Tick data doesn't have volume
                        )
                        
                        self.current_bars[symbol] = market_data
                        self._notify_callbacks(market_data)
                        
                    elif data_type == 'bar':
                        # Convert bar data to MarketData
                        market_data = MarketData(
                            symbol=symbol,
                            timestamp=data.get('datetime', data.get('received_at', datetime.now())),
                            open=data['open'],
                            high=data['high'],
                            low=data['low'],
                            close=data['close'],
                            volume=data.get('volume', 0)
                        )
                        
                        self.current_bars[symbol] = market_data
                        self._notify_callbacks(market_data)
                        
                except Exception as e:
                    logger.error(f"Error processing real-time data for {symbol}: {e}")
            
            # Subscribe to both market data and bars
            success = self.data_manager.subscribe_to_symbol(
                symbol=symbol,
                callback=data_callback,
                subscription_type='both'
            )
            
            if success:
                logger.info(f"✅ Subscribed to real-time data for {symbol}")
            else:
                logger.error(f"❌ Failed to subscribe to real-time data for {symbol}")
                
        except Exception as e:
            logger.error(f"❌ Error subscribing to {symbol}: {e}")
    
    def start_realtime_feed(self):
        """Start the real-time data feed"""
        try:
            # Ensure broker is connected
            self._ensure_broker_connected()
            
            logger.info("🔄 IBKR real-time data feed started")
            
        except Exception as e:
            logger.error(f"❌ Error starting IBKR real-time feed: {e}")
            raise
    
    def stop_realtime_feed(self):
        """Stop the real-time data feed"""
        try:
            if self.data_manager:
                # Unsubscribe from all symbols
                for symbol in list(self.current_bars.keys()):
                    self.data_manager.unsubscribe_from_symbol(symbol)
            
            if self.broker:
                self.broker.disconnect()
                self.broker = None
                
            logger.info("✅ IBKR real-time data feed stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping IBKR real-time feed: {e}")
    
    def set_update_interval_from_granularity(self, granularity: str):
        """Set update interval based on granularity"""
        parsed = self._parse_granularity(granularity)
        self.update_interval = parsed.to_seconds()
        logger.info(f"IBKR update interval set to {self.update_interval} seconds")
    
    def set_update_interval(self, seconds: float):
        """Set update interval manually"""
        self.update_interval = seconds
        logger.info(f"IBKR update interval set to {self.update_interval} seconds")
    
    def get_current_data(self, symbol: str) -> MarketData | None:
        """Get the most recent data for a symbol"""
        return self.current_bars.get(symbol)
    
    def is_connected(self) -> bool:
        """Check if connection is active"""
        return self.broker is not None and self.broker.is_connected
    
    def __del__(self):
        """Cleanup on destruction"""
        try:
            self.stop_realtime_feed()
        except Exception:
            pass  # Ignore errors during cleanup 