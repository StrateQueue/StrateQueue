"""
CCXT Data Provider

Provides market data from 250+ cryptocurrency exchanges via CCXT library.
"""

import logging
import os
from typing import Any, Dict, List, Optional
import pandas as pd
from datetime import datetime, timedelta

try:
    import ccxt
    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False
    ccxt = None

from .data_source_base import BaseDataIngestion
from ...core.resample import plan_base_granularity, resample_ohlcv

logger = logging.getLogger(__name__)


class CCXTDataIngestion(BaseDataIngestion):
    """CCXT data provider for cryptocurrency exchanges"""
    # Dynamic capability – per-exchange
    SUPPORTED_GRANULARITIES = None
    DEFAULT_GRANULARITY = "1m"
    
    def __init__(self, exchange_id: str = None, api_key: str = None, 
                 secret_key: str = None, passphrase: str = None,
                 granularity: str = "1m", sandbox: bool = True):
        """
        Initialize CCXT data provider
        
        Args:
            exchange_id: Exchange identifier (e.g., 'binance', 'coinbase')
            api_key: Exchange API key
            secret_key: Exchange secret key  
            passphrase: Exchange passphrase (if required)
            granularity: Data granularity
            sandbox: Use sandbox/testnet environment
        """
        super().__init__()
        
        if not CCXT_AVAILABLE:
            raise ImportError("CCXT library not available. Install with: pip install ccxt")
            
        # Auto-detect exchange from environment if not provided
        if not exchange_id:
            exchange_id = os.getenv('CCXT_EXCHANGE')
            if not exchange_id:
                raise ValueError("Exchange ID required. Set CCXT_EXCHANGE environment variable or pass exchange_id parameter")
        
        self.exchange_id = exchange_id
        self.granularity = granularity
        self.sandbox = sandbox
        
        # Get credentials using exchange-specific logic (same as broker)
        if not api_key or not secret_key:
            credentials = self._get_exchange_credentials(exchange_id)
            api_key = api_key or credentials.get('api_key')
            secret_key = secret_key or credentials.get('secret_key')
            passphrase = passphrase or credentials.get('passphrase', '')
        
        # Initialize exchange instance
        self.exchange = self._create_exchange_instance(
            exchange_id, api_key, secret_key, passphrase, sandbox
        )
        
        logger.info(f"Initialized CCXT data provider for {exchange_id}")
    
    def _get_exchange_credentials(self, exchange_id: str) -> dict:
        """Get credentials for specific exchange"""
        exchange_upper = exchange_id.upper()
        return {
            'api_key': os.getenv(f'CCXT_{exchange_upper}_API_KEY'),
            'secret_key': os.getenv(f'CCXT_{exchange_upper}_SECRET_KEY'),
            'passphrase': os.getenv(f'CCXT_{exchange_upper}_PASSPHRASE', ''),
        }
    
    def _create_exchange_instance(self, exchange_id: str, api_key: str = None,
                                secret_key: str = None, passphrase: str = None,
                                sandbox: bool = True) -> Any:
        """Create CCXT exchange instance"""
        
        if not hasattr(ccxt, exchange_id):
            available = [ex for ex in ccxt.exchanges if hasattr(ccxt, ex)]
            raise ValueError(f"Unsupported exchange '{exchange_id}'. Available: {available[:10]}...")
        
        exchange_class = getattr(ccxt, exchange_id)
        
        # Build exchange config
        config = {
            'enableRateLimit': True,
            'timeout': 30000,
        }
        
        # Add credentials if provided
        if api_key:
            config['apiKey'] = api_key
        if secret_key:
            config['secret'] = secret_key
        if passphrase:
            config['passphrase'] = passphrase
            
        # Enable sandbox if supported and requested
        if sandbox:
            config['sandbox'] = True
            
        exchange = exchange_class(config)
        
        # Test connection
        try:
            exchange.load_markets()
            logger.debug(f"Successfully connected to {exchange_id}")
        except Exception as e:
            logger.warning(f"Could not load markets for {exchange_id}: {e}")
            # Continue anyway - might work for historical data
            
        return exchange
    
    @staticmethod
    def dependencies_available() -> bool:
        """Check if CCXT dependencies are available"""
        return CCXT_AVAILABLE
    
    def get_historical_data(self, symbol: str, start_date: datetime = None,
                          end_date: datetime = None, limit: int = 1000) -> pd.DataFrame:
        """
        Get historical OHLCV data from exchange
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            start_date: Start date for data
            end_date: End date for data  
            limit: Maximum number of candles
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Determine base timeframe plan: if target not directly supported by
            # the exchange, fetch at a supported base and resample.
            supported = set(getattr(self.exchange, 'timeframes', {}) or {})
            if self.granularity in supported:
                plan = None
                base_token = self.granularity
            else:
                # Fall back to a conservative baseline if the exchange doesn't expose timeframes
                baselines = supported or self.get_supported_granularities()
                plan = plan_base_granularity(baselines, self.granularity)
                base_token = plan.source_granularity

            timeframe = self._convert_granularity_to_timeframe(base_token)
            
            # Prepare parameters
            since = None
            if start_date:
                since = int(start_date.timestamp() * 1000)
                
            # Fetch OHLCV data
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since,
                limit=limit
            )
            
            if not ohlcv:
                # Retry with a smaller base if possible to avoid empty results for odd targets
                try:
                    if plan is not None and plan.source_granularity != '1m' and '1m' in (supported or {}):
                        timeframe_retry = self._convert_granularity_to_timeframe('1m')
                        ohlcv = self.exchange.fetch_ohlcv(symbol=symbol, timeframe=timeframe_retry, since=since, limit=limit)
                except Exception:
                    pass
                if not ohlcv:
                    logger.warning(f"No data returned for {symbol}")
                    return pd.DataFrame()
            
            # Convert to DataFrame with title case columns (StrateQueue standard)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Filter by end_date if provided
            if end_date:
                df = df[df.index <= end_date]
            
            # Resample if a base plan is in effect
            if plan is not None and plan.target_granularity:
                df = resample_ohlcv(df, plan.target_granularity)

            logger.debug(f"Retrieved {len(df)} candles for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return pd.DataFrame()
    
    def get_current_price(self, symbol: str) -> float:
        """Get current price for symbol"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            logger.error(f"Error fetching current price for {symbol}: {e}")
            return 0.0
    
    def get_available_symbols(self) -> List[str]:
        """Get list of available trading pairs"""
        try:
            markets = self.exchange.load_markets()
            return list(markets.keys())
        except Exception as e:
            logger.error(f"Error fetching available symbols: {e}")
            return []
    
    def _convert_granularity_to_timeframe(self, granularity: str) -> str:
        """Convert StrateQueue granularity to CCXT timeframe.

        Prefer the exchange's advertised `timeframes` mapping when available.
        """
        tf_map = getattr(self.exchange, 'timeframes', None)
        if isinstance(tf_map, dict) and tf_map:
            if granularity in tf_map:
                return granularity
            # Fallback to 1m if available on the exchange
            if '1m' in tf_map:
                logger.warning(
                    f"Unsupported granularity {granularity} for {self.exchange_id}; falling back to 1m"
                )
                return '1m'
        # Conservative baseline if exchange has no map
        baseline = {
            '1s', '5s', '10s', '30s', '1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w'
        }
        if granularity in baseline:
            return granularity
        logger.warning(f"Unsupported granularity {granularity}; defaulting to 1m")
        return '1m'

    # Capability helpers -------------------------------------------------
    @classmethod
    def get_supported_granularities(cls, **context) -> set[str]:
        """Return supported granularities. If an `exchange` is provided in
        context, derive directly from `exchange.timeframes` keys; otherwise
        return a conservative baseline.
        """
        exchange = context.get('exchange')
        if exchange is not None and isinstance(getattr(exchange, 'timeframes', None), dict):
            return set(exchange.timeframes.keys())
        return {
            '1s', '5s', '10s', '30s', '1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w'
        }

    @classmethod
    def accepts_granularity(cls, granularity: str, **context) -> bool:
        return granularity in cls.get_supported_granularities(**context)
    
    def validate_symbol(self, symbol: str) -> bool:
        """Validate if symbol is available on exchange"""
        try:
            markets = self.exchange.load_markets()
            return symbol in markets
        except Exception as e:
            logger.error(f"Error validating symbol {symbol}: {e}")
            return False
    
    def get_exchange_info(self) -> Dict[str, Any]:
        """Get exchange information and capabilities"""
        try:
            return {
                'id': self.exchange.id,
                'name': self.exchange.name,
                'countries': getattr(self.exchange, 'countries', []),
                'has': self.exchange.has,
                'timeframes': getattr(self.exchange, 'timeframes', {}),
                'markets_count': len(self.exchange.markets) if self.exchange.markets else 0,
                'sandbox': self.sandbox
            }
        except Exception as e:
            logger.error(f"Error getting exchange info: {e}")
            return {}
    
    # Required abstract methods from BaseDataIngestion
    
    async def fetch_historical_data(self, symbol: str, days_back: int = 30,
                                  granularity: str = "1m") -> pd.DataFrame:
        """
        Fetch historical OHLCV data (async version of get_historical_data)
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            days_back: Number of days of historical data
            granularity: Data granularity
            
        Returns:
            DataFrame with OHLCV data
        """
        # For live trading, we want the most recent data up to now
        # Calculate start date to get enough historical data
        from datetime import datetime, timedelta
        start_date = datetime.now() - timedelta(days=days_back)
        end_date = datetime.now()  # Get data up to now
        
        # Use the synchronous method with end_date to ensure we get recent data
        df = self.get_historical_data(symbol, start_date=start_date, end_date=end_date)
        
        # Store in historical_data dict for BaseDataIngestion compatibility
        if not df.empty:
            # Columns are already in the correct format (title case)
            self.historical_data[symbol] = df
            from ...utils.price_formatter import PriceFormatter
            logger.info(f"Fetched {len(df)} bars for {symbol}, latest: {df.index[-1]} at {PriceFormatter.format_price_for_display(df['Close'].iloc[-1])}")
            
        return df
    
    async def subscribe_to_symbol(self, symbol: str):
        """Subscribe to real-time data for a symbol"""
        # For CCXT, we'll use polling to get current prices
        # Store the symbol for real-time updates
        if not hasattr(self, '_subscribed_symbols'):
            self._subscribed_symbols = set()
        self._subscribed_symbols.add(symbol)
        logger.info(f"Subscribed to CCXT real-time data for {symbol} (polling mode)")
    
    def start_realtime_feed(self):
        """Start the real-time data feed"""
        # For CCXT, we'll implement a polling-based real-time feed
        import asyncio
        import threading
        
        if not hasattr(self, '_subscribed_symbols'):
            self._subscribed_symbols = set()
        
        if not self._subscribed_symbols:
            logger.info("No symbols subscribed for real-time data")
            return
            
        logger.info(f"Starting CCXT real-time feed for {len(self._subscribed_symbols)} symbols (polling mode)")
        
        # Start polling thread
        self._stop_feed = False
        self._feed_thread = threading.Thread(target=self._run_realtime_feed, daemon=True)
        self._feed_thread.start()
    
    def stop_realtime_feed(self):
        """Stop the real-time data feed"""
        if hasattr(self, '_stop_feed'):
            self._stop_feed = True
        if hasattr(self, '_feed_thread'):
            self._feed_thread.join(timeout=1)
        logger.info("Stopped CCXT real-time feed")
    
    def _run_realtime_feed(self):
        """Run the real-time feed polling loop"""
        import time
        from datetime import datetime
        
        logger.info("CCXT real-time feed started")
        
        while not getattr(self, '_stop_feed', False):
            try:
                for symbol in getattr(self, '_subscribed_symbols', set()):
                    # Get current ticker data
                    ticker = self.exchange.fetch_ticker(symbol)
                    
                    # Create MarketData object
                    from .data_source_base import MarketData
                    market_data = MarketData(
                        symbol=symbol,
                        timestamp=datetime.now(),
                        open=float(ticker.get('open', ticker['last'])),
                        high=float(ticker.get('high', ticker['last'])),
                        low=float(ticker.get('low', ticker['last'])),
                        close=float(ticker['last']),
                        volume=int(ticker.get('baseVolume', 0))
                    )
                    
                    # Store current data
                    self.current_bars[symbol] = market_data
                    
                    # Notify callbacks
                    self._notify_callbacks(market_data)
                    
                    from ...utils.price_formatter import PriceFormatter
                    logger.debug(f"Updated {symbol}: {PriceFormatter.format_price_for_display(ticker['last'])}")
                
                # Sleep for 5 seconds between updates (adjust as needed)
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error in CCXT real-time feed: {e}")
                time.sleep(10)  # Wait longer on error
        
        logger.info("CCXT real-time feed stopped")