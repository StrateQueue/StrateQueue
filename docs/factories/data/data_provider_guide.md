# Data Provider Factory Guide

## Overview

The Stratequeue trading system includes a flexible data provider factory that makes it easy to add new data sources and switch between different market data platforms. The factory pattern follows the same design as the broker and engine factories, providing consistent interfaces and lazy loading capabilities.

## Architecture

### Core Components

1. **BaseDataIngestion** - Abstract base class defining the data provider interface
2. **DataProviderFactory** - Factory class for creating data provider instances
3. **Data Provider Utilities** - Environment detection and configuration helpers
4. **Data Provider Implementations** - Specific provider implementations (Polygon, CoinMarketCap, Demo)

### Key Features

- **Lazy Loading**: Data providers are only loaded when requested
- **Auto-Detection**: Automatically detects available providers from environment variables
- **Graceful Fallbacks**: Handles missing dependencies gracefully with demo data
- **Unified Interface**: Consistent API across all data provider implementations
- **Environment-Based Configuration**: Configuration via environment variables
- **Multi-Granularity Support**: Flexible time granularity handling
- **Real-time and Historical**: Support for both historical data and real-time feeds

## Using the Data Provider Factory

### Basic Usage

```python
from StrateQueue.data import (
    DataProviderFactory, 
    DataProviderConfig,
    auto_create_provider,
    detect_provider_type
)

# Create a specific provider
config = DataProviderConfig(
    provider_type='polygon',
    api_key='your_polygon_key',
    granularity='1m'
)
provider = DataProviderFactory.create_provider('polygon', config)

# Auto-detect and create provider from environment
provider = auto_create_provider(granularity='5m')

# Subscribe to real-time data
provider.subscribe_to_symbol('AAPL')
provider.start_realtime_feed()

# Fetch historical data
import asyncio
historical_data = asyncio.run(
    provider.fetch_historical_data('AAPL', days_back=30, granularity='1m')
)
print(f"Fetched {len(historical_data)} bars")
```

### CLI Integration

The data provider factory is fully integrated with the CLI:

```bash
# List available data providers
python3 main.py --list-data-providers

# Check data provider environment status
python3 main.py --data-status

# Get setup instructions
python3 main.py --data-setup polygon

# Use specific provider for trading
python3 main.py --strategy sma.py --symbols AAPL --data-source polygon --granularity 1m

# Auto-detect provider (default)
python3 main.py --strategy sma.py --symbols AAPL --granularity 5m
```

### Environment Detection

The system automatically detects available data providers:

```python
from StrateQueue.data import (
    detect_provider_type,
    get_supported_providers,
    validate_provider_credentials,
    list_provider_features
)

# Detect primary provider from environment
provider_type = detect_provider_type()

# Get all supported providers
supported = get_supported_providers()

# Validate credentials
is_valid = validate_provider_credentials('polygon')

# Get provider capabilities
features = list_provider_features()
for provider_type, info in features.items():
    print(f"{provider_type}: {info.supported_markets}")
```

## Adding a New Data Provider

### Step 1: Create Provider Implementation

Create a new file `src/StrateQueue/data/sources/your_provider.py`:

```python
"""
Your Data Provider Implementation

Implementation of BaseDataIngestion for Your Market Data Platform
"""

import pandas as pd
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp

from .base import BaseDataIngestion, MarketData

logger = logging.getLogger(__name__)


class YourProviderDataIngestion(BaseDataIngestion):
    """Your Provider implementation of BaseDataIngestion interface"""
    
    def __init__(self, api_key: str, granularity: str = "1m"):
        super().__init__()
        self.api_key = api_key
        self.granularity = granularity
        self.base_url = "https://api.yourprovider.com/v1"
        self.session = None
        
    async def _get_session(self):
        """Get or create aiohttp session"""
        if self.session is None:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'User-Agent': 'StrateQueue/1.0'
            }
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session
    
    async def fetch_historical_data(self, symbol: str, days_back: int = 30, 
                                  granularity: str = "1m") -> pd.DataFrame:
        """Fetch historical OHLCV data from Your Provider"""
        try:
            session = await self._get_session()
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Convert granularity to provider format
            interval = self._convert_granularity(granularity)
            
            # Build API request
            params = {
                'symbol': symbol,
                'interval': interval,
                'from': start_date.isoformat(),
                'to': end_date.isoformat(),
                'limit': 5000
            }
            
            url = f"{self.base_url}/historical"
            
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    raise Exception(f"API request failed: {response.status}")
                
                data = await response.json()
                
                # Convert to DataFrame
                df = self._parse_historical_data(data, symbol)
                
                # Cache the data
                self.historical_data[symbol] = df
                
                logger.info(f"Fetched {len(df)} historical bars for {symbol} from Your Provider")
                return df
                
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return pd.DataFrame()
    
    def _convert_granularity(self, granularity: str) -> str:
        """Convert standard granularity to provider-specific format"""
        granularity_map = {
            '1s': '1sec',
            '1m': '1min',
            '5m': '5min',
            '15m': '15min',
            '30m': '30min',
            '1h': '1hour',
            '1d': '1day'
        }
        return granularity_map.get(granularity, '1min')
    
    def _parse_historical_data(self, data: Dict, symbol: str) -> pd.DataFrame:
        """Parse API response into standardized DataFrame"""
        bars = []
        
        for bar in data.get('bars', []):
            bars.append({
                'Open': float(bar['open']),
                'High': float(bar['high']),
                'Low': float(bar['low']),
                'Close': float(bar['close']),
                'Volume': int(bar['volume']),
                'timestamp': pd.to_datetime(bar['timestamp'])
            })
        
        if not bars:
            return pd.DataFrame()
        
        df = pd.DataFrame(bars)
        df.set_index('timestamp', inplace=True)
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)
        
        return df
    
    def subscribe_to_symbol(self, symbol: str):
        """Subscribe to real-time data for a symbol"""
        if symbol not in self.subscribed_symbols:
            self.subscribed_symbols.append(symbol)
            logger.info(f"Subscribed to real-time data for {symbol}")
            
            # Initialize WebSocket connection for real-time data
            asyncio.create_task(self._start_websocket_feed(symbol))
    
    async def _start_websocket_feed(self, symbol: str):
        """Start WebSocket connection for real-time data"""
        try:
            import websockets
            
            ws_url = f"wss://api.yourprovider.com/v1/stream"
            
            async with websockets.connect(ws_url) as websocket:
                # Subscribe to symbol
                subscribe_msg = {
                    'action': 'subscribe',
                    'symbols': [symbol],
                    'auth': self.api_key
                }
                await websocket.send(json.dumps(subscribe_msg))
                
                # Listen for messages
                async for message in websocket:
                    data = json.loads(message)
                    await self._process_realtime_message(data)
                    
        except Exception as e:
            logger.error(f"WebSocket error for {symbol}: {e}")
    
    async def _process_realtime_message(self, data: Dict):
        """Process real-time market data message"""
        if data.get('type') == 'trade':
            symbol = data.get('symbol')
            
            # Create MarketData object
            market_data = MarketData(
                symbol=symbol,
                timestamp=pd.to_datetime(data['timestamp']),
                open=float(data.get('open', data['price'])),
                high=float(data.get('high', data['price'])),
                low=float(data.get('low', data['price'])),
                close=float(data['price']),
                volume=int(data.get('volume', 0))
            )
            
            # Update current bars
            self.current_bars[symbol] = market_data
            
            # Notify callbacks
            self._notify_callbacks(market_data)
    
    def start_realtime_feed(self):
        """Start the real-time data feed"""
        self.is_connected = True
        logger.info("Your Provider real-time feed started")
    
    def stop_realtime_feed(self):
        """Stop the real-time data feed"""
        self.is_connected = False
        if self.session:
            asyncio.create_task(self.session.close())
            self.session = None
        logger.info("Your Provider real-time feed stopped")
```

### Step 2: Register in Factory

Add your provider to `src/StrateQueue/data/provider_factory.py`:

```python
# In DataProviderFactory._initialize_providers()
try:
    from .sources.your_provider import YourProviderDataIngestion
    cls._providers['your_provider'] = YourProviderDataIngestion
    logger.debug("Registered Your Provider data provider")
except ImportError as e:
    logger.warning(f"Could not load Your Provider: {e}")
```

### Step 3: Add Configuration Support

```python
# In DataProviderFactory._create_provider_instance()
elif provider_type == "your_provider":
    if not config.api_key:
        raise ValueError("Your Provider requires an API key")
    return provider_class(config.api_key, config.granularity)
```

### Step 4: Add Provider Information

```python
# In DataProviderFactory._get_static_provider_info()
elif provider_type == "your_provider":
    return DataProviderInfo(
        name="Your Provider",
        version="1.0",
        supported_features={
            "historical_data": True,
            "real_time_data": True,
            "multiple_granularities": True,
            "stocks": True,
            "crypto": False,
            "forex": False
        },
        description="Your market data provider description",
        supported_markets=["stocks"],
        requires_api_key=True,
        supported_granularities=["1s", "1m", "5m", "15m", "30m", "1h", "1d"]
    )
```

### Step 5: Add Environment Detection

```python
# In DataProviderFactory._get_provider_config_from_env()
elif provider_type == "your_provider":
    api_key = os.getenv('YOUR_PROVIDER_API_KEY')
    if api_key:
        config['api_key'] = api_key
```

### Step 6: Update Detection Logic

```python
# In detect_provider_type()
if os.getenv('YOUR_PROVIDER_API_KEY'):
    logger.info("Detected Your Provider API key, suggesting your_provider")
    return 'your_provider'
```

## Advanced Usage Patterns

### Custom Data Processing Pipeline

```python
from StrateQueue.data import DataProviderFactory, DataProviderConfig
import pandas as pd
import numpy as np

class CustomDataProcessor:
    """Custom data processing pipeline"""
    
    def __init__(self, provider_type: str, symbols: List[str]):
        self.config = DataProviderConfig(
            provider_type=provider_type,
            granularity='1m'
        )
        self.provider = DataProviderFactory.create_provider(provider_type, self.config)
        self.symbols = symbols
        self.processed_data = {}
        
    async def fetch_and_process(self, days_back: int = 30):
        """Fetch and process data for all symbols"""
        for symbol in self.symbols:
            # Fetch raw data
            raw_data = await self.provider.fetch_historical_data(
                symbol, days_back, self.config.granularity
            )
            
            # Apply custom processing
            processed = self._apply_technical_indicators(raw_data)
            self.processed_data[symbol] = processed
            
    def _apply_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply technical indicators to raw OHLCV data"""
        df = df.copy()
        
        # Moving averages
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        
        # RSI
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Bollinger Bands
        rolling_mean = df['Close'].rolling(window=20).mean()
        rolling_std = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = rolling_mean + (rolling_std * 2)
        df['BB_Lower'] = rolling_mean - (rolling_std * 2)
        
        return df
```

### Multi-Provider Data Aggregation

```python
class MultiProviderAggregator:
    """Aggregate data from multiple providers for redundancy"""
    
    def __init__(self, provider_configs: List[DataProviderConfig]):
        self.providers = []
        for config in provider_configs:
            provider = DataProviderFactory.create_provider(config.provider_type, config)
            self.providers.append((config.provider_type, provider))
    
    async def fetch_with_fallback(self, symbol: str, days_back: int = 30) -> pd.DataFrame:
        """Fetch data with automatic fallback between providers"""
        for provider_type, provider in self.providers:
            try:
                data = await provider.fetch_historical_data(symbol, days_back)
                if len(data) > 0:
                    logger.info(f"Successfully fetched data from {provider_type}")
                    return data
            except Exception as e:
                logger.warning(f"Failed to fetch from {provider_type}: {e}")
                continue
        
        raise Exception("All data providers failed")
    
    def start_aggregated_feed(self, symbols: List[str]):
        """Start real-time feeds from all providers"""
        for symbol in symbols:
            for provider_type, provider in self.providers:
                try:
                    provider.subscribe_to_symbol(symbol)
                    provider.add_data_callback(self._handle_realtime_data)
                except Exception as e:
                    logger.warning(f"Failed to start feed for {provider_type}: {e}")
        
        # Start all feeds
        for provider_type, provider in self.providers:
            try:
                provider.start_realtime_feed()
            except Exception as e:
                logger.warning(f"Failed to start {provider_type} feed: {e}")
    
    def _handle_realtime_data(self, market_data: MarketData):
        """Handle real-time data from any provider"""
        # Implement data deduplication and quality checks
        logger.debug(f"Received data for {market_data.symbol}: ${market_data.close}")
```

## Best Practices

### 1. Error Handling
- Always wrap provider calls in try-catch blocks
- Implement proper logging for debugging
- Use circuit breakers for external API calls
- Have fallback data sources available

### 2. Performance
- Cache historical data appropriately
- Use batch operations when possible
- Implement rate limiting for API calls
- Monitor and optimize data quality

### 3. Configuration
- Use environment variables for API keys
- Make granularity configurable
- Support both historical and real-time modes
- Validate configuration on startup

### 4. Testing
- Use mock providers for unit tests
- Test with demo provider for integration
- Validate data quality and format
- Test error conditions and recovery

### 5. Monitoring
- Log all data provider operations
- Monitor API usage and limits
- Track data quality metrics
- Alert on provider failures 