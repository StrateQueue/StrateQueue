# Data Provider Integration Examples

This document provides practical examples of integrating different data providers with the Stratequeue trading system.

## Polygon.io Integration

### Implementation Example

```python
"""
Polygon.io Data Provider Implementation

Enhanced implementation using Polygon's REST API and WebSocket feeds
"""

import pandas as pd
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp
import websockets
import json
import time

from .base import BaseDataIngestion, MarketData

logger = logging.getLogger(__name__)


class PolygonDataIngestion(BaseDataIngestion):
    """Enhanced Polygon.io implementation with advanced features"""
    
    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
        self.ws_url = "wss://socket.polygon.io"
        self.session = None
        self.websocket = None
        self.rate_limiter = RateLimiter(5, 60)  # 5 calls per minute
        
    async def _get_session(self):
        """Get or create aiohttp session with retry logic"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def fetch_historical_data(self, symbol: str, days_back: int = 30, 
                                  granularity: str = "1m") -> pd.DataFrame:
        """Fetch historical data with advanced error handling"""
        try:
            # Rate limiting
            await self.rate_limiter.acquire()
            
            session = await self._get_session()
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Convert granularity to Polygon format
            timespan, multiplier = self._parse_granularity(granularity)
            
            # Build API request
            url = f"{self.base_url}/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
            
            params = {
                'adjusted': 'true',
                'sort': 'asc',
                'limit': 50000,
                'apikey': self.api_key
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 429:  # Rate limited
                    await asyncio.sleep(60)  # Wait and retry
                    return await self.fetch_historical_data(symbol, days_back, granularity)
                
                if response.status != 200:
                    error_msg = await response.text()
                    raise Exception(f"Polygon API error {response.status}: {error_msg}")
                
                data = await response.json()
                
                # Parse response
                df = self._parse_polygon_response(data, symbol)
                
                # Validate data quality
                df = self._validate_and_clean_data(df, symbol)
                
                # Cache the data
                self.historical_data[symbol] = df
                
                logger.info(f"Fetched {len(df)} bars for {symbol} from Polygon")
                return df
                
        except Exception as e:
            logger.error(f"Error fetching Polygon data for {symbol}: {e}")
            return pd.DataFrame()
    
    def _parse_granularity(self, granularity: str) -> tuple:
        """Parse granularity into Polygon timespan and multiplier"""
        if granularity.endswith('s'):
            return 'second', int(granularity[:-1])
        elif granularity.endswith('m'):
            return 'minute', int(granularity[:-1])
        elif granularity.endswith('h'):
            return 'hour', int(granularity[:-1])
        elif granularity.endswith('d'):
            return 'day', int(granularity[:-1])
        else:
            raise ValueError(f"Invalid granularity format: {granularity}")
    
    def _parse_polygon_response(self, data: Dict, symbol: str) -> pd.DataFrame:
        """Parse Polygon API response into DataFrame"""
        if 'results' not in data or not data['results']:
            logger.warning(f"No data returned for {symbol}")
            return pd.DataFrame()
        
        bars = []
        for result in data['results']:
            bars.append({
                'Open': float(result['o']),
                'High': float(result['h']),
                'Low': float(result['l']),
                'Close': float(result['c']),
                'Volume': int(result['v']),
                'timestamp': pd.to_datetime(result['t'], unit='ms')
            })
        
        df = pd.DataFrame(bars)
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        
        return df
    
    def _validate_and_clean_data(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Validate and clean market data"""
        if df.empty:
            return df
        
        original_len = len(df)
        
        # Remove invalid prices
        df = df[(df['Open'] > 0) & (df['High'] > 0) & (df['Low'] > 0) & (df['Close'] > 0)]
        
        # Remove bars where high < low
        df = df[df['High'] >= df['Low']]
        
        # Remove extreme outliers (prices that change more than 50% in one bar)
        df['price_change'] = df['Close'].pct_change()
        df = df[abs(df['price_change']) < 0.5]
        df.drop('price_change', axis=1, inplace=True)
        
        if len(df) < original_len:
            logger.warning(f"Cleaned {original_len - len(df)} invalid bars for {symbol}")
        
        return df
    
    async def start_realtime_feed(self):
        """Start Polygon WebSocket feed"""
        if self.websocket:
            return
        
        try:
            self.websocket = await websockets.connect(f"{self.ws_url}/stocks")
            
            # Authenticate
            auth_msg = {
                "action": "auth",
                "params": self.api_key
            }
            await self.websocket.send(json.dumps(auth_msg))
            
            # Wait for auth response
            response = await self.websocket.recv()
            auth_data = json.loads(response)
            
            if auth_data.get('status') != 'auth_success':
                raise Exception(f"Authentication failed: {auth_data}")
            
            logger.info("Polygon WebSocket authenticated successfully")
            
            # Start message processing
            asyncio.create_task(self._process_websocket_messages())
            
        except Exception as e:
            logger.error(f"Failed to start Polygon WebSocket: {e}")
    
    def subscribe_to_symbol(self, symbol: str):
        """Subscribe to real-time trades and quotes"""
        if symbol not in self.subscribed_symbols:
            self.subscribed_symbols.append(symbol)
            
            if self.websocket:
                # Subscribe to trades and quotes
                subscribe_msg = {
                    "action": "subscribe",
                    "params": f"T.{symbol},Q.{symbol}"  # Trades and quotes
                }
                asyncio.create_task(self.websocket.send(json.dumps(subscribe_msg)))
            
            logger.info(f"Subscribed to Polygon data for {symbol}")
    
    async def _process_websocket_messages(self):
        """Process incoming WebSocket messages"""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                
                for event in data:
                    if event.get('ev') == 'T':  # Trade event
                        await self._process_trade_event(event)
                    elif event.get('ev') == 'Q':  # Quote event
                        await self._process_quote_event(event)
                        
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            self.websocket = None
    
    async def _process_trade_event(self, event: Dict):
        """Process trade event from Polygon"""
        symbol = event.get('sym')
        if not symbol:
            return
        
        # Create market data from trade
        market_data = MarketData(
            symbol=symbol,
            timestamp=pd.to_datetime(event['t'], unit='ms'),
            open=float(event['p']),  # Use trade price for all OHLC
            high=float(event['p']),
            low=float(event['p']),
            close=float(event['p']),
            volume=int(event['s'])
        )
        
        # Update current bars
        self.current_bars[symbol] = market_data
        
        # Notify callbacks
        self._notify_callbacks(market_data)


class RateLimiter:
    """Simple rate limiter for API calls"""
    
    def __init__(self, calls: int, period: int):
        self.calls = calls
        self.period = period
        self.call_times = []
    
    async def acquire(self):
        """Wait if necessary to respect rate limits"""
        now = time.time()
        
        # Remove old calls outside the period
        self.call_times = [t for t in self.call_times if now - t < self.period]
        
        # Wait if we've hit the limit
        if len(self.call_times) >= self.calls:
            sleep_time = self.period - (now - self.call_times[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        self.call_times.append(now)
```

### Environment Setup

```bash
# Polygon.io Environment Variables
export POLYGON_API_KEY="your_polygon_api_key_here"
export DATA_PROVIDER="polygon"
export DATA_GRANULARITY="1m"

# For live data (requires paid plan)
export POLYGON_ENABLE_WEBSOCKET="true"
```

## Alpha Vantage Integration

### Implementation Example

```python
"""
Alpha Vantage Data Provider Implementation

Implementation using Alpha Vantage's free tier API
"""

import pandas as pd
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp
import time

from .base import BaseDataIngestion, MarketData

logger = logging.getLogger(__name__)


class AlphaVantageDataIngestion(BaseDataIngestion):
    """Alpha Vantage implementation with free tier optimizations"""
    
    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.session = None
        self.last_call_time = 0
        self.call_interval = 12  # 12 seconds between calls (5 per minute limit)
        
    async def _rate_limited_call(self):
        """Ensure we don't exceed Alpha Vantage rate limits"""
        now = time.time()
        time_since_last = now - self.last_call_time
        
        if time_since_last < self.call_interval:
            wait_time = self.call_interval - time_since_last
            logger.debug(f"Rate limiting: waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
        
        self.last_call_time = time.time()
    
    async def fetch_historical_data(self, symbol: str, days_back: int = 30, 
                                  granularity: str = "1m") -> pd.DataFrame:
        """Fetch data from Alpha Vantage with appropriate function selection"""
        try:
            await self._rate_limited_call()
            
            if self.session is None:
                self.session = aiohttp.ClientSession()
            
            # Select appropriate Alpha Vantage function
            if granularity in ['1m', '5m', '15m', '30m', '60m']:
                return await self._fetch_intraday_data(symbol, granularity)
            elif granularity in ['1d']:
                return await self._fetch_daily_data(symbol, days_back)
            else:
                raise ValueError(f"Unsupported granularity for Alpha Vantage: {granularity}")
                
        except Exception as e:
            logger.error(f"Error fetching Alpha Vantage data for {symbol}: {e}")
            return pd.DataFrame()
    
    async def _fetch_intraday_data(self, symbol: str, interval: str) -> pd.DataFrame:
        """Fetch intraday data (limited to last 30 days on free tier)"""
        params = {
            'function': 'TIME_SERIES_INTRADAY',
            'symbol': symbol,
            'interval': interval,
            'outputsize': 'full',
            'apikey': self.api_key
        }
        
        async with self.session.get(self.base_url, params=params) as response:
            data = await response.json()
            
            if 'Error Message' in data:
                raise Exception(f"Alpha Vantage error: {data['Error Message']}")
            
            if 'Note' in data:
                raise Exception(f"Rate limit exceeded: {data['Note']}")
            
            # Parse time series data
            time_series_key = f'Time Series ({interval})'
            if time_series_key not in data:
                raise Exception(f"No data found for {symbol}")
            
            return self._parse_time_series(data[time_series_key])
    
    async def _fetch_daily_data(self, symbol: str, days_back: int) -> pd.DataFrame:
        """Fetch daily data"""
        params = {
            'function': 'TIME_SERIES_DAILY',
            'symbol': symbol,
            'outputsize': 'full' if days_back > 100 else 'compact',
            'apikey': self.api_key
        }
        
        async with self.session.get(self.base_url, params=params) as response:
            data = await response.json()
            
            if 'Error Message' in data:
                raise Exception(f"Alpha Vantage error: {data['Error Message']}")
            
            if 'Time Series (Daily)' not in data:
                raise Exception(f"No daily data found for {symbol}")
            
            df = self._parse_time_series(data['Time Series (Daily)'])
            
            # Limit to requested days
            cutoff_date = datetime.now() - timedelta(days=days_back)
            df = df[df.index >= cutoff_date]
            
            return df
    
    def _parse_time_series(self, time_series: Dict) -> pd.DataFrame:
        """Parse Alpha Vantage time series format"""
        bars = []
        
        for timestamp, values in time_series.items():
            bars.append({
                'Open': float(values['1. open']),
                'High': float(values['2. high']),
                'Low': float(values['3. low']),
                'Close': float(values['4. close']),
                'Volume': int(values['5. volume']),
                'timestamp': pd.to_datetime(timestamp)
            })
        
        if not bars:
            return pd.DataFrame()
        
        df = pd.DataFrame(bars)
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        
        return df
    
    def subscribe_to_symbol(self, symbol: str):
        """Note: Alpha Vantage doesn't support real-time WebSocket feeds on free tier"""
        logger.warning("Alpha Vantage free tier doesn't support real-time feeds")
        if symbol not in self.subscribed_symbols:
            self.subscribed_symbols.append(symbol)
    
    def start_realtime_feed(self):
        """Simulate real-time feed with polling (free tier limitation)"""
        logger.info("Starting Alpha Vantage polling feed (no real-time WebSocket)")
        self.is_connected = True
        
        # Start polling task
        asyncio.create_task(self._polling_loop())
    
    async def _polling_loop(self):
        """Poll for updated data every few minutes"""
        while self.is_connected:
            for symbol in self.subscribed_symbols:
                try:
                    # Fetch latest quote
                    await self._fetch_latest_quote(symbol)
                except Exception as e:
                    logger.error(f"Error polling {symbol}: {e}")
            
            # Wait 5 minutes between polls (free tier limitation)
            await asyncio.sleep(300)
    
    async def _fetch_latest_quote(self, symbol: str):
        """Fetch latest quote data"""
        await self._rate_limited_call()
        
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol,
            'apikey': self.api_key
        }
        
        async with self.session.get(self.base_url, params=params) as response:
            data = await response.json()
            
            quote = data.get('Global Quote', {})
            if not quote:
                return
            
            # Create market data from quote
            market_data = MarketData(
                symbol=symbol,
                timestamp=pd.to_datetime(quote.get('07. latest trading day')),
                open=float(quote.get('02. open', 0)),
                high=float(quote.get('03. high', 0)),
                low=float(quote.get('04. low', 0)),
                close=float(quote.get('05. price', 0)),
                volume=int(quote.get('06. volume', 0))
            )
            
            self.current_bars[symbol] = market_data
            self._notify_callbacks(market_data)
```

## YFinance Integration

### Implementation Example

```python
"""
Yahoo Finance Data Provider Implementation

Using yfinance library for free historical data
"""

import pandas as pd
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor

from .base import BaseDataIngestion, MarketData

logger = logging.getLogger(__name__)


class YFinanceDataIngestion(BaseDataIngestion):
    """Yahoo Finance implementation using yfinance library"""
    
    def __init__(self):
        super().__init__()
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    async def fetch_historical_data(self, symbol: str, days_back: int = 30, 
                                  granularity: str = "1m") -> pd.DataFrame:
        """Fetch historical data from Yahoo Finance"""
        try:
            # Run in thread pool since yfinance is synchronous
            df = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._fetch_yfinance_data,
                symbol, days_back, granularity
            )
            
            # Cache the data
            self.historical_data[symbol] = df
            
            logger.info(f"Fetched {len(df)} bars for {symbol} from Yahoo Finance")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching Yahoo Finance data for {symbol}: {e}")
            return pd.DataFrame()
    
    def _fetch_yfinance_data(self, symbol: str, days_back: int, granularity: str) -> pd.DataFrame:
        """Synchronous fetch using yfinance"""
        # Convert granularity to yfinance format
        interval = self._convert_granularity(granularity)
        
        # Calculate period
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Create ticker object
        ticker = yf.Ticker(symbol)
        
        # Fetch data
        df = ticker.history(
            start=start_date,
            end=end_date,
            interval=interval,
            auto_adjust=True,
            prepost=True
        )
        
        if df.empty:
            return pd.DataFrame()
        
        # Standardize column names
        df = df.rename(columns={
            'Open': 'Open',
            'High': 'High', 
            'Low': 'Low',
            'Close': 'Close',
            'Volume': 'Volume'
        })
        
        # Keep only OHLCV columns
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        
        return df
    
    def _convert_granularity(self, granularity: str) -> str:
        """Convert to yfinance interval format"""
        granularity_map = {
            '1m': '1m',
            '2m': '2m',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '60m': '60m',
            '90m': '90m',
            '1h': '1h',
            '1d': '1d',
            '5d': '5d',
            '1wk': '1wk',
            '1mo': '1mo',
            '3mo': '3mo'
        }
        return granularity_map.get(granularity, '1d')
    
    def subscribe_to_symbol(self, symbol: str):
        """Yahoo Finance doesn't support real-time WebSocket"""
        if symbol not in self.subscribed_symbols:
            self.subscribed_symbols.append(symbol)
            logger.info(f"Added {symbol} to polling list")
    
    def start_realtime_feed(self):
        """Start polling-based 'real-time' feed"""
        self.is_connected = True
        asyncio.create_task(self._polling_loop())
        logger.info("Started Yahoo Finance polling feed")
    
    async def _polling_loop(self):
        """Poll for latest prices"""
        while self.is_connected:
            for symbol in self.subscribed_symbols:
                try:
                    # Get latest data
                    df = await asyncio.get_event_loop().run_in_executor(
                        self.executor,
                        self._get_latest_data,
                        symbol
                    )
                    
                    if not df.empty:
                        # Create market data from latest bar
                        latest = df.iloc[-1]
                        market_data = MarketData(
                            symbol=symbol,
                            timestamp=df.index[-1],
                            open=float(latest['Open']),
                            high=float(latest['High']),
                            low=float(latest['Low']),
                            close=float(latest['Close']),
                            volume=int(latest['Volume'])
                        )
                        
                        self.current_bars[symbol] = market_data
                        self._notify_callbacks(market_data)
                        
                except Exception as e:
                    logger.error(f"Error polling {symbol}: {e}")
            
            # Poll every 60 seconds
            await asyncio.sleep(60)
    
    def _get_latest_data(self, symbol: str) -> pd.DataFrame:
        """Get latest 1-day data"""
        ticker = yf.Ticker(symbol)
        return ticker.history(period="1d", interval="1m")
```

## Multi-Provider Strategy

### Failover Data Provider

```python
class FailoverDataProvider(BaseDataIngestion):
    """Data provider that automatically fails over between providers"""
    
    def __init__(self, provider_configs: List[DataProviderConfig]):
        super().__init__()
        self.providers = []
        self.current_provider_index = 0
        
        # Initialize all providers
        for config in provider_configs:
            try:
                provider = DataProviderFactory.create_provider(config.provider_type, config)
                self.providers.append((config.provider_type, provider))
                logger.info(f"Initialized failover provider: {config.provider_type}")
            except Exception as e:
                logger.error(f"Failed to initialize {config.provider_type}: {e}")
    
    async def fetch_historical_data(self, symbol: str, days_back: int = 30, 
                                  granularity: str = "1m") -> pd.DataFrame:
        """Fetch with automatic failover"""
        for i, (provider_type, provider) in enumerate(self.providers):
            try:
                data = await provider.fetch_historical_data(symbol, days_back, granularity)
                if len(data) > 0:
                    logger.info(f"Successfully fetched from {provider_type}")
                    self.current_provider_index = i
                    return data
            except Exception as e:
                logger.warning(f"Provider {provider_type} failed: {e}")
                continue
        
        logger.error("All providers failed")
        return pd.DataFrame()
    
    def subscribe_to_symbol(self, symbol: str):
        """Subscribe using current provider"""
        if self.providers:
            _, provider = self.providers[self.current_provider_index]
            provider.subscribe_to_symbol(symbol)
            provider.add_data_callback(self._notify_callbacks)
    
    def start_realtime_feed(self):
        """Start feed using current provider"""
        if self.providers:
            _, provider = self.providers[self.current_provider_index]
            provider.start_realtime_feed()
            self.is_connected = True
```

### Data Quality Aggregator

```python
class DataQualityAggregator:
    """Aggregate data from multiple providers and select best quality"""
    
    def __init__(self, providers: List[BaseDataIngestion]):
        self.providers = providers
        self.quality_scores = {i: 1.0 for i in range(len(providers))}
        
    async def fetch_best_quality_data(self, symbol: str, days_back: int = 30, 
                                    granularity: str = "1m") -> pd.DataFrame:
        """Fetch from all providers and return best quality data"""
        results = []
        
        # Fetch from all providers
        for i, provider in enumerate(self.providers):
            try:
                data = await provider.fetch_historical_data(symbol, days_back, granularity)
                if len(data) > 0:
                    quality_score = self._calculate_quality_score(data, symbol)
                    results.append((i, data, quality_score))
            except Exception as e:
                logger.warning(f"Provider {i} failed: {e}")
                self.quality_scores[i] *= 0.9  # Reduce score for failures
        
        if not results:
            return pd.DataFrame()
        
        # Select best quality data
        best_idx, best_data, best_score = max(results, key=lambda x: x[2])
        logger.info(f"Selected provider {best_idx} with quality score {best_score:.3f}")
        
        return best_data
    
    def _calculate_quality_score(self, df: pd.DataFrame, symbol: str) -> float:
        """Calculate data quality score based on various metrics"""
        if df.empty:
            return 0.0
        
        score = 1.0
        
        # Check for missing data
        missing_ratio = df.isnull().sum().sum() / (len(df) * len(df.columns))
        score *= (1 - missing_ratio)
        
        # Check for zero volume bars
        zero_volume_ratio = (df['Volume'] == 0).sum() / len(df)
        score *= (1 - zero_volume_ratio * 0.5)
        
        # Check for price consistency
        invalid_prices = ((df['High'] < df['Low']) | 
                         (df['Close'] <= 0) | 
                         (df['Open'] <= 0)).sum()
        score *= (1 - invalid_prices / len(df))
        
        # Check for reasonable price movements
        price_changes = df['Close'].pct_change().abs()
        extreme_moves = (price_changes > 0.2).sum()  # More than 20% change
        score *= (1 - extreme_moves / len(df) * 0.3)
        
        return score
```

## Testing and Validation

### Data Provider Test Suite

```python
import pytest
import asyncio
from unittest.mock import Mock, patch

class TestDataProviderSuite:
    """Comprehensive test suite for data providers"""
    
    @pytest.fixture
    def mock_provider(self):
        """Create mock data provider"""
        provider = Mock(spec=BaseDataIngestion)
        provider.fetch_historical_data = Mock()
        provider.subscribe_to_symbol = Mock()
        provider.start_realtime_feed = Mock()
        return provider
    
    @pytest.mark.asyncio
    async def test_polygon_historical_data(self):
        """Test Polygon historical data fetching"""
        if not os.getenv('POLYGON_API_KEY'):
            pytest.skip("No Polygon API key available")
        
        provider = PolygonDataIngestion(os.getenv('POLYGON_API_KEY'))
        data = await provider.fetch_historical_data('AAPL', days_back=1, granularity='1m')
        
        assert not data.empty
        assert all(col in data.columns for col in ['Open', 'High', 'Low', 'Close', 'Volume'])
        assert data.index.dtype.kind == 'M'  # Datetime index
        assert (data['High'] >= data['Low']).all()
        assert (data['Close'] > 0).all()
    
    @pytest.mark.asyncio
    async def test_data_quality_validation(self):
        """Test data quality validation"""
        # Create test data with quality issues
        dates = pd.date_range('2023-01-01', periods=100, freq='1min')
        bad_data = pd.DataFrame({
            'Open': [100.0] * 90 + [0.0] * 10,  # Some zero prices
            'High': [101.0] * 100,
            'Low': [99.0] * 80 + [102.0] * 20,  # Some high < low
            'Close': [100.5] * 100,
            'Volume': [1000] * 50 + [0] * 50  # Half zero volume
        }, index=dates)
        
        aggregator = DataQualityAggregator([])
        score = aggregator._calculate_quality_score(bad_data, 'TEST')
        
        assert score < 0.8  # Should be low quality
    
    def test_rate_limiter(self):
        """Test rate limiting functionality"""
        limiter = RateLimiter(calls=2, period=1)
        
        start_time = time.time()
        
        # First two calls should be immediate
        asyncio.run(limiter.acquire())
        asyncio.run(limiter.acquire())
        
        # Third call should be delayed
        asyncio.run(limiter.acquire())
        
        elapsed = time.time() - start_time
        assert elapsed >= 1.0  # Should have waited at least 1 second
```

## Performance Monitoring

### Data Provider Metrics

```python
class DataProviderMetrics:
    """Collect and monitor data provider performance metrics"""
    
    def __init__(self):
        self.metrics = {
            'api_calls': 0,
            'failed_calls': 0,
            'total_latency': 0.0,
            'data_quality_scores': [],
            'symbols_tracked': set(),
            'last_update': None
        }
    
    def record_api_call(self, latency: float, success: bool, symbol: str):
        """Record API call metrics"""
        self.metrics['api_calls'] += 1
        self.metrics['total_latency'] += latency
        self.metrics['symbols_tracked'].add(symbol)
        
        if not success:
            self.metrics['failed_calls'] += 1
        
        self.metrics['last_update'] = datetime.now()
    
    def record_data_quality(self, score: float):
        """Record data quality score"""
        self.metrics['data_quality_scores'].append(score)
        
        # Keep only last 100 scores
        if len(self.metrics['data_quality_scores']) > 100:
            self.metrics['data_quality_scores'] = self.metrics['data_quality_scores'][-100:]
    
    def get_performance_report(self) -> Dict:
        """Generate performance report"""
        if self.metrics['api_calls'] == 0:
            return {"status": "No data"}
        
        avg_latency = self.metrics['total_latency'] / self.metrics['api_calls']
        success_rate = 1 - (self.metrics['failed_calls'] / self.metrics['api_calls'])
        avg_quality = sum(self.metrics['data_quality_scores']) / len(self.metrics['data_quality_scores']) if self.metrics['data_quality_scores'] else 0
        
        return {
            'total_api_calls': self.metrics['api_calls'],
            'success_rate': f"{success_rate:.2%}",
            'average_latency_ms': f"{avg_latency * 1000:.1f}",
            'symbols_tracked': len(self.metrics['symbols_tracked']),
            'average_data_quality': f"{avg_quality:.3f}",
            'last_update': self.metrics['last_update']
        }
```

This comprehensive documentation provides practical examples for implementing various data providers, handling multiple providers, and ensuring data quality and performance monitoring. 