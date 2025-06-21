# Broker Factory Guide

## Overview

The Stratequeue trading system includes a flexible broker factory that makes it easy to add new brokers and switch between different trading platforms. The factory pattern follows the same design as the existing engine factory, providing consistent interfaces and lazy loading capabilities.

## Architecture

### Core Components

1. **BaseBroker** - Abstract base class defining the broker interface
2. **BrokerFactory** - Factory class for creating broker instances
3. **Broker Utilities** - Environment detection and configuration helpers
4. **Broker Implementations** - Specific broker implementations (Alpaca, IB, etc.)

### Key Features

- **Lazy Loading**: Brokers are only loaded when requested
- **Auto-Detection**: Automatically detects available brokers from environment variables
- **Graceful Fallbacks**: Handles missing dependencies gracefully
- **Unified Interface**: Consistent API across all broker implementations
- **Environment-Based Configuration**: Configuration via environment variables
- **Multi-Strategy Support**: Built-in portfolio management integration

## Using the Broker Factory

### Basic Usage

```python
from StrateQueue.brokers import BrokerFactory, auto_create_broker

# Create a specific broker
broker = BrokerFactory.create_broker('alpaca')

# Auto-detect and create broker from environment
broker = auto_create_broker()

# Connect to the broker
if broker.connect():
    print(f"Connected to {broker.config.broker_type}")
    
    # Get account info
    account = broker.get_account_info()
    print(f"Account ID: {account.account_id}")
    print(f"Buying Power: ${account.buying_power:,.2f}")
```

### CLI Integration

The broker factory is fully integrated with the CLI:

```bash
# List available brokers
python3 main.py --list-brokers

# Check broker environment status
python3 main.py --broker-status

# Get setup instructions
python3 main.py --broker-setup alpaca

# Use specific broker for trading
python3 main.py --strategy sma.py --symbols AAPL --enable-trading --broker alpaca

# Auto-detect broker (default)
python3 main.py --strategy sma.py --symbols AAPL --enable-trading
```

### Environment Detection

The system automatically detects available brokers:

```python
from StrateQueue.brokers import (
    detect_broker_type, 
    get_supported_brokers,
    validate_broker_credentials
)

# Detect primary broker from environment
broker_type = detect_broker_type()

# Get all supported brokers
supported = get_supported_brokers()

# Validate credentials
is_valid = validate_broker_credentials('alpaca')
```

## Adding a New Broker

### Step 1: Create Broker Implementation

Create a new file `src/StrateQueue/brokers/your_broker.py`:

```python
"""
Your Broker Implementation

Implementation of BaseBroker for Your Trading Platform
"""

import logging
from typing import Dict, Optional, List, Any
from decimal import Decimal

from .base import (
    BaseBroker, BrokerConfig, BrokerInfo, AccountInfo, 
    Position, OrderResult, OrderType, OrderSide
)

logger = logging.getLogger(__name__)


class YourBrokerExecutor(BaseBroker):
    """Your Broker implementation of BaseBroker interface"""
    
    def __init__(self, config: BrokerConfig, portfolio_manager=None):
        super().__init__(config, portfolio_manager)
        self.api_client = None  # Your broker's API client
        
    def connect(self) -> bool:
        """Connect to Your Broker API"""
        try:
            # Initialize your broker's API client
            from your_broker_api import APIClient
            
            self.api_client = APIClient(
                api_key=self.config.credentials.get('api_key'),
                secret_key=self.config.credentials.get('secret_key'),
                paper_trading=self.config.paper_trading
            )
            
            # Test connection
            account = self.api_client.get_account()
            logger.info(f"Connected to Your Broker - Account: {account.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Your Broker: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from Your Broker API"""
        if self.api_client:
            self.api_client.close()
            self.api_client = None
            logger.info("Disconnected from Your Broker")
    
    def get_account_info(self) -> AccountInfo:
        """Get account information"""
        account = self.api_client.get_account()
        
        return AccountInfo(
            account_id=account.id,
            buying_power=Decimal(str(account.buying_power)),
            total_value=Decimal(str(account.total_value)),
            cash=Decimal(str(account.cash))
        )
    
    def get_positions(self) -> List[Position]:
        """Get current positions"""
        positions = []
        
        for pos in self.api_client.get_positions():
            positions.append(Position(
                symbol=pos.symbol,
                quantity=Decimal(str(pos.quantity)),
                market_value=Decimal(str(pos.market_value)),
                average_cost=Decimal(str(pos.avg_cost))
            ))
        
        return positions
    
    def place_order(self, symbol: str, order_type: OrderType, 
                   side: OrderSide, quantity: Decimal, 
                   price: Optional[Decimal] = None, 
                   metadata: Optional[Dict[str, Any]] = None) -> OrderResult:
        """Place an order"""
        try:
            # Convert to your broker's order format
            order_data = {
                'symbol': symbol,
                'side': side.value.lower(),
                'type': order_type.value.lower(),
                'quantity': str(quantity)
            }
            
            if price and order_type == OrderType.LIMIT:
                order_data['price'] = str(price)
            
            # Submit order
            order = self.api_client.submit_order(**order_data)
            
            return OrderResult(
                success=True,
                order_id=order.id,
                message=f"Order submitted successfully",
                broker_response=order.__dict__
            )
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return OrderResult(
                success=False,
                error_code="ORDER_FAILED",
                message=str(e)
            )
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            self.api_client.cancel_order(order_id)
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order status"""
        try:
            order = self.api_client.get_order(order_id)
            return {
                'id': order.id,
                'status': order.status,
                'filled_quantity': str(order.filled_qty),
                'remaining_quantity': str(order.qty - order.filled_qty)
            }
        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            return None


# Helper function for creating from environment
def create_your_broker_from_env(portfolio_manager=None) -> YourBrokerExecutor:
    """Create Your Broker executor from environment variables"""
    from .utils import get_broker_config_from_env
    
    config_dict = get_broker_config_from_env('your_broker')
    
    config = BrokerConfig(
        broker_type='your_broker',
        paper_trading=config_dict.get('paper_trading', True),
        credentials=config_dict
    )
    
    return YourBrokerExecutor(config, portfolio_manager)
```

### Step 2: Register with Factory

Update `src/StrateQueue/brokers/broker_factory.py`:

```python
class BrokerFactory:
    """Factory for creating broker instances with lazy loading"""
    
    _brokers = {
        'alpaca': {
            'module': 'StrateQueue.brokers.alpaca_broker',
            'class': 'AlpacaBroker',
            'create_func': 'auto_create_broker'
        },
        'your_broker': {  # Add your broker here
            'module': 'StrateQueue.brokers.your_broker',
            'class': 'YourBrokerExecutor', 
            'create_func': 'create_your_broker_from_env'
        }
        # Add more brokers here...
    }
```

### Step 3: Add Environment Detection

Update `src/StrateQueue/brokers/utils.py`:

```python
def detect_broker_from_environment() -> Optional[str]:
    """Detect broker type from environment variables"""
    
    # Check for Alpaca credentials
    if (os.getenv('ALPACA_API_KEY') or os.getenv('PAPER_KEY')) and \
       (os.getenv('ALPACA_SECRET_KEY') or os.getenv('PAPER_SECRET')):
        return 'alpaca'
    
    # Check for Your Broker credentials
    if os.getenv('YOUR_BROKER_API_KEY') and os.getenv('YOUR_BROKER_SECRET'):
        return 'your_broker'
    
    # ... existing checks ...
    
    return None

def get_your_broker_config_from_env() -> Dict[str, Any]:
    """Extract Your Broker configuration from environment variables"""
    return {
        'api_key': os.getenv('YOUR_BROKER_API_KEY'),
        'secret_key': os.getenv('YOUR_BROKER_SECRET'),
        'base_url': os.getenv('YOUR_BROKER_BASE_URL', 'https://api.yourbroker.com'),
        'paper_trading': os.getenv('YOUR_BROKER_PAPER', 'true').lower() == 'true'
    }
```

### Step 4: Add Broker Information

Update `src/StrateQueue/brokers/__init__.py`:

```python
def list_broker_features() -> Dict[str, BrokerInfo]:
    """List features of all supported brokers"""
    return {
        'alpaca': BrokerInfo(
            name="Alpaca",
            version="2.0.0",
            description="Commission-free stock and crypto trading", 
            supported_markets=['stocks', 'crypto'],
            paper_trading=True,
            supported_features={
                'market_orders': True,
                'limit_orders': True, 
                'stop_orders': True,
                'crypto_trading': True,
                'multi_strategy': True,
                'portfolio_management': True
            }
        ),
        'your_broker': BrokerInfo(  # Add your broker info
            name="Your Broker",
            version="1.0.0",
            description="Your broker's description",
            supported_markets=['stocks', 'options', 'futures'],
            paper_trading=True,
            supported_features={
                'market_orders': True,
                'limit_orders': True,
                'stop_orders': True,
                'options_trading': True,
                'futures_trading': True,
                'multi_strategy': True,
                'portfolio_management': True
            }
        )
    }
```

### Step 5: Environment Setup Documentation

Update the setup instructions in utils.py:

```python
def suggest_environment_setup(broker_type: str) -> str:
    """Provide environment setup suggestions for a specific broker"""
    
    if broker_type == 'your_broker':
        return """
Environment setup for Your Broker:

export YOUR_BROKER_API_KEY="your_api_key"
export YOUR_BROKER_SECRET="your_secret_key"
export YOUR_BROKER_BASE_URL="https://api.yourbroker.com"
export YOUR_BROKER_PAPER="true"  # or "false" for live trading

Get credentials from: https://yourbroker.com/developers/
        """
    
    # ... existing setups ...
```

## Testing Your Implementation

### Unit Tests

Create `tests/test_your_broker.py`:

```python
import pytest
from unittest.mock import Mock, patch
from decimal import Decimal

from src.StrateQueue.brokers.your_broker import YourBrokerExecutor
from src.StrateQueue.brokers.base import BrokerConfig, OrderType, OrderSide


class TestYourBroker:
    
    @pytest.fixture
    def mock_config(self):
        return BrokerConfig(
            broker_type='your_broker',
            paper_trading=True,
            credentials={
                'api_key': 'test_key',
                'secret_key': 'test_secret'
            }
        )
    
    @patch('your_broker_api.APIClient')
    def test_connect_success(self, mock_client_class, mock_config):
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_account.return_value = Mock(id='test_account')
        
        broker = YourBrokerExecutor(mock_config)
        assert broker.connect() == True
        assert broker.api_client is not None
    
    @patch('your_broker_api.APIClient')
    def test_place_order_success(self, mock_client_class, mock_config):
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_order = Mock(id='order_123')
        mock_client.submit_order.return_value = mock_order
        
        broker = YourBrokerExecutor(mock_config)
        broker.api_client = mock_client
        
        result = broker.place_order(
            symbol='AAPL',
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=Decimal('10')
        )
        
        assert result.success == True
        assert result.order_id == 'order_123'
```

### Integration Tests

```python
def test_broker_factory_integration():
    """Test that your broker integrates properly with the factory"""
    from StrateQueue.brokers import get_supported_brokers, BrokerFactory
    
    # Check broker is supported
    supported = get_supported_brokers()
    assert 'your_broker' in supported
    
    # Test factory creation
    with patch.dict('os.environ', {
        'YOUR_BROKER_API_KEY': 'test_key',
        'YOUR_BROKER_SECRET': 'test_secret'
    }):
        broker = BrokerFactory.create_broker('your_broker')
        assert broker.config.broker_type == 'your_broker'
```

## Advanced Features

### Custom Portfolio Management

```python
class YourBrokerExecutor(BaseBroker):
    
    def execute_signal(self, symbol: str, signal) -> OrderResult:
        """Execute trading signal with portfolio management"""
        
        if self.portfolio_manager:
            # Use portfolio manager for position sizing
            position_size = self.portfolio_manager.calculate_position_size(
                symbol, signal.signal
            )
        else:
            # Default position sizing
            position_size = Decimal('100')
        
        # Determine order side
        side = OrderSide.BUY if signal.signal.value == 'BUY' else OrderSide.SELL
        
        # Place order
        return self.place_order(
            symbol=symbol,
            order_type=OrderType.MARKET,
            side=side,
            quantity=position_size,
            metadata={'strategy_signal': signal.__dict__}
        )
```

### Error Handling and Retries

```python
import time
from functools import wraps

def retry_on_failure(max_retries=3, delay=1.0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"Attempt {attempt + 1} failed: {e}")
                    time.sleep(delay * (2 ** attempt))  # Exponential backoff
            return None
        return wrapper
    return decorator

class YourBrokerExecutor(BaseBroker):
    
    @retry_on_failure(max_retries=3)
    def place_order(self, symbol: str, order_type: OrderType, 
                   side: OrderSide, quantity: Decimal, 
                   price: Optional[Decimal] = None, 
                   metadata: Optional[Dict[str, Any]] = None) -> OrderResult:
        # Your order placement logic with automatic retries
        pass
```

## Best Practices

### 1. Follow the Interface

Always implement all required methods from `BaseBroker`:
- `connect()` and `disconnect()`
- `get_account_info()` and `get_positions()`
- `place_order()`, `cancel_order()`, `get_order_status()`

### 2. Handle Errors Gracefully

```python
def connect(self) -> bool:
    try:
        # Connection logic
        return True
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        return False  # Never raise exceptions from connect()
```

### 3. Use Proper Logging

```python
import logging
logger = logging.getLogger(__name__)

# Log important events
logger.info("Connected to broker")
logger.warning("Order partially filled") 
logger.error("Order failed")
```

### 4. Validate Configuration

```python
def __init__(self, config: BrokerConfig, portfolio_manager=None):
    super().__init__(config, portfolio_manager)
    
    # Validate required credentials
    required_keys = ['api_key', 'secret_key']
    for key in required_keys:
        if not config.credentials.get(key):
            raise ValueError(f"Missing required credential: {key}")
```

### 5. Support Both Paper and Live Trading

```python
def connect(self) -> bool:
    base_url = "https://paper-api.yourbroker.com" if self.config.paper_trading else "https://api.yourbroker.com"
    
    self.api_client = APIClient(
        base_url=base_url,
        api_key=self.config.credentials['api_key'],
        secret_key=self.config.credentials['secret_key']
    )
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure your broker's API package is installed
2. **Authentication**: Verify environment variables are set correctly
3. **Connection Issues**: Check network connectivity and API status
4. **Order Failures**: Validate symbol format and market hours

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger('StrateQueue.brokers').setLevel(logging.DEBUG)
```

### Environment Validation

Use the built-in validation tools:

```bash
python3 main.py --broker-status
python3 main.py --broker-setup your_broker
```

## Contributing

When contributing a new broker implementation:

1. Follow the implementation template above
2. Include comprehensive unit tests
3. Add integration tests with the factory
4. Update documentation
5. Submit a pull request with examples

The broker factory makes it easy to extend Stratequeue with new trading platforms while maintaining a consistent interface and user experience. 