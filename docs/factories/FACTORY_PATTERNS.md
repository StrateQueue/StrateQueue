# Factory Patterns Documentation

This document describes the standardized factory patterns implemented across the trading system's core modules: Brokers, Engines, and Data Providers.

## Overview

The trading system uses consistent factory patterns across all major sub-modules to provide:

- **Unified API**: All factories follow the same method naming and parameter conventions
- **Auto-detection**: Automatic detection of available components based on environment
- **Configuration Management**: Standardized configuration objects and environment variable handling
- **Extensibility**: Easy addition of new implementations without breaking existing code
- **Backward Compatibility**: Existing code continues to work while new factory patterns are available

## Factory Components

### 1. Data Provider Factory

**Location**: `src/StrateQueue/data/provider_factory.py`
**Advanced Documentation**: See [Data Provider Guide](data/data_provider_guide.md) and [Integration Examples](data/data_provider_examples.md)

#### Classes
- `DataProviderFactory`: Main factory class
- `DataProviderConfig`: Configuration object for providers
- `DataProviderInfo`: Information about provider capabilities

#### Supported Providers
- **Polygon**: Professional market data (stocks, crypto, forex)
- **CoinMarketCap**: Cryptocurrency market data
- **Demo**: Simulated data for testing and development

#### Usage Examples

```python
from StrateQueue.data import (
    DataProviderFactory, 
    DataProviderConfig,
    auto_create_provider,
    detect_provider_type
)

# Method 1: Direct factory usage
config = DataProviderConfig(
    provider_type='demo',
    granularity='1m'
)
provider = DataProviderFactory.create_provider('demo', config)

# Method 2: Auto-detection
provider = auto_create_provider(granularity='5m')

# Method 3: Environment-based detection
provider_type = detect_provider_type()
provider = DataProviderFactory.create_provider(provider_type)

# Get provider information
info = DataProviderFactory.get_provider_info('polygon')
print(f"Provider: {info.name}")
print(f"Markets: {info.supported_markets}")
print(f"Requires API Key: {info.requires_api_key}")
```

#### Environment Variables
- `POLYGON_API_KEY`: For Polygon.io data
- `CMC_API_KEY`: For CoinMarketCap data
- `DATA_PROVIDER`: Explicit provider selection
- `DATA_GRANULARITY`: Default granularity setting

### 2. Broker Factory

**Location**: `src/StrateQueue/brokers/broker_factory.py`

#### Classes
- `BrokerFactory`: Main factory class
- `BrokerConfig`: Configuration object for brokers
- `BrokerInfo`: Information about broker capabilities

#### Supported Brokers
- **Alpaca**: Commission-free trading platform

#### Usage Examples

```python
from StrateQueue.brokers import (
    BrokerFactory,
    BrokerConfig,
    auto_create_broker,
    detect_broker_type
)

# Method 1: Direct factory usage
config = BrokerConfig(
    broker_type='alpaca',
    paper_trading=True
)
broker = BrokerFactory.create_broker('alpaca', config)

# Method 2: Auto-detection
broker = auto_create_broker()

# Method 3: Environment-based detection
broker_type = detect_broker_type()
broker = BrokerFactory.create_broker(broker_type)

# Get broker information
info = BrokerFactory.get_broker_info('alpaca')
print(f"Broker: {info.name}")
print(f"Markets: {info.supported_markets}")
print(f"Paper Trading: {info.paper_trading}")
```

### 3. Engine Factory

**Location**: `src/StrateQueue/engines/engine_factory.py`
**Advanced Documentation**: See [Engine Factory Guide](engines/engine_factory_guide.md) and [Integration Examples](engines/engine_integration_examples.md)

#### Classes
- `EngineFactory`: Main factory class
- `EngineInfo`: Information about engine capabilities (via base classes)

#### Supported Engines
- **Backtesting**: Strategy backtesting framework

#### Usage Examples

```python
from StrateQueue.engines import (
    EngineFactory,
    auto_create_engine,
    detect_engine_type
)

# Method 1: Direct factory usage
engine = EngineFactory.create_engine('backtesting')

# Method 2: Strategy-based auto-detection
engine = auto_create_engine('path/to/strategy.py')

# Method 3: Manual detection
engine_type = detect_engine_type('path/to/strategy.py')
engine = EngineFactory.create_engine(engine_type)

# Validate strategy compatibility
is_compatible = validate_strategy_compatibility('path/to/strategy.py', 'backtesting')
```

## Standardized Factory Methods

All factories implement the following consistent interface:

### Core Methods
| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `create_*()` | Create instance | `type`, `config` | Instance |
| `get_supported_*()` | List supported types | None | `List[str]` |
| `is_*_supported()` | Check if type supported | `type` | `bool` |
| `get_*_info()` | Get type information | `type` | `InfoClass` |

### Detection Methods
| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `detect_*_type()` | Auto-detect type | `context` | `str` |
| `auto_create_*()` | Auto-create instance | `params` | Instance |
| `validate_*_credentials()` | Validate setup | `type` | `bool` |

## Configuration Objects

All factories use standardized configuration objects:

### Common Fields
- `*_type`: String identifier for the component type
- `additional_params`: Dict for custom parameters
- `timeout`: Connection timeout settings

### Provider-Specific Fields
- **Data**: `api_key`, `granularity`
- **Broker**: `credentials`, `paper_trading`
- **Engine**: (minimal configuration needed)

## Backward Compatibility

The factory system maintains backward compatibility:

```python
# Old API still works
from StrateQueue.data.ingestion import create_data_source
provider = create_data_source('demo', granularity='1m')

# New factory API available
from StrateQueue.data import DataProviderFactory
provider = DataProviderFactory.create_provider('demo')
```

## Environment-Based Configuration

### Data Providers
```bash
# Explicit provider selection
export DATA_PROVIDER=polygon
export DATA_GRANULARITY=5m

# Provider-specific API keys
export POLYGON_API_KEY=your_key_here
export CMC_API_KEY=your_key_here
```

### Brokers
```bash
# Alpaca configuration
export ALPACA_API_KEY=your_key_here
export ALPACA_SECRET_KEY=your_secret_here
export ALPACA_PAPER_KEY=your_paper_key_here
export ALPACA_PAPER_SECRET=your_paper_secret_here
```

## Adding New Implementations

### Adding a New Data Provider

1. **Create Provider Class**:
   ```python
   # src/StrateQueue/data/sources/new_provider.py
   class NewProviderDataIngestion(BaseDataIngestion):
       def __init__(self, api_key: str):
           super().__init__()
           self.api_key = api_key
       
       async def fetch_historical_data(self, symbol, days_back, granularity):
           # Implementation here
           pass
   ```

2. **Register in Factory**:
   ```python
   # In DataProviderFactory._initialize_providers()
   try:
       from .sources.new_provider import NewProviderDataIngestion
       cls._providers['new_provider'] = NewProviderDataIngestion
       logger.debug("Registered New Provider data provider")
   except ImportError as e:
       logger.warning(f"Could not load New Provider: {e}")
   ```

3. **Add Configuration Support**:
   ```python
   # In DataProviderFactory._create_provider_instance()
   elif provider_type == "new_provider":
       if not config.api_key:
           raise ValueError("New Provider requires an API key")
       return provider_class(config.api_key)
   ```

4. **Add Provider Info**:
   ```python
   # In DataProviderFactory._get_static_provider_info()
   elif provider_type == "new_provider":
       return DataProviderInfo(
           name="New Provider",
           version="1.0",
           supported_features={"historical_data": True, "real_time_data": True},
           description="New data provider description",
           supported_markets=["stocks"],
           requires_api_key=True,
           supported_granularities=["1m", "5m", "1h", "1d"]
       )
   ```

## Benefits of Standardization

1. **Consistency**: All factories follow the same patterns and naming conventions
2. **Discoverability**: Developers can easily find and use similar functionality across modules
3. **Maintainability**: Adding new implementations follows well-defined patterns
4. **Testing**: Standardized test patterns across all factories
5. **Documentation**: Consistent documentation structure
6. **Configuration**: Unified approach to environment variables and config objects
7. **Error Handling**: Consistent error messages and exception handling
