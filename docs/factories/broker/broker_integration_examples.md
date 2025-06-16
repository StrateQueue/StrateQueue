# Broker Integration Examples

This document provides practical examples of integrating different brokers with the Stratequeue trading system.

## Interactive Brokers Integration

### Implementation Example

```python
"""
Interactive Brokers Implementation

Example implementation using the IB Python API
"""

import logging
from typing import Dict, Optional, List, Any
from decimal import Decimal
from threading import Event
import time

from ib_insync import IB, Stock, MarketOrder, LimitOrder
from .base import (
    BaseBroker, BrokerConfig, BrokerInfo, AccountInfo, 
    Position, OrderResult, OrderType, OrderSide
)

logger = logging.getLogger(__name__)


class InteractiveBrokersExecutor(BaseBroker):
    """Interactive Brokers implementation using ib_insync"""
    
    def __init__(self, config: BrokerConfig, portfolio_manager=None):
        super().__init__(config, portfolio_manager)
        self.ib = IB()
        self.connected = False
        
    def connect(self) -> bool:
        """Connect to IB TWS or Gateway"""
        try:
            host = self.config.credentials.get('host', 'localhost')
            port = int(self.config.credentials.get('port', '7497'))
            client_id = int(self.config.credentials.get('client_id', '1'))
            
            self.ib.connect(host, port, clientId=client_id, timeout=10)
            self.connected = True
            
            # Test connection by requesting account info
            account_summary = self.ib.accountSummary()
            logger.info(f"Connected to IB - Account: {self.ib.managedAccounts()[0]}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Interactive Brokers: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from IB"""
        if self.connected and self.ib.isConnected():
            self.ib.disconnect()
            self.connected = False
            logger.info("Disconnected from Interactive Brokers")
    
    def get_account_info(self) -> AccountInfo:
        """Get IB account information"""
        account_values = {av.tag: av.value for av in self.ib.accountValues()}
        
        return AccountInfo(
            account_id=self.ib.managedAccounts()[0],
            buying_power=Decimal(account_values.get('BuyingPower', '0')),
            total_value=Decimal(account_values.get('NetLiquidation', '0')),
            cash=Decimal(account_values.get('TotalCashValue', '0'))
        )
    
    def get_positions(self) -> List[Position]:
        """Get current IB positions"""
        positions = []
        
        for pos in self.ib.positions():
            if pos.position != 0:  # Only non-zero positions
                positions.append(Position(
                    symbol=pos.contract.symbol,
                    quantity=Decimal(str(pos.position)),
                    market_value=Decimal(str(pos.marketValue)),
                    average_cost=Decimal(str(pos.averageCost))
                ))
        
        return positions
    
    def place_order(self, symbol: str, order_type: OrderType, 
                   side: OrderSide, quantity: Decimal, 
                   price: Optional[Decimal] = None, 
                   metadata: Optional[Dict[str, Any]] = None) -> OrderResult:
        """Place order through IB"""
        try:
            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)
            
            # Create order
            action = 'BUY' if side == OrderSide.BUY else 'SELL'
            
            if order_type == OrderType.MARKET:
                order = MarketOrder(action, float(quantity))
            elif order_type == OrderType.LIMIT:
                if not price:
                    raise ValueError("Limit orders require a price")
                order = LimitOrder(action, float(quantity), float(price))
            else:
                raise ValueError(f"Unsupported order type: {order_type}")
            
            # Submit order
            trade = self.ib.placeOrder(contract, order)
            
            # Wait briefly for order to be submitted
            self.ib.sleep(1)
            
            return OrderResult(
                success=True,
                order_id=str(trade.order.orderId),
                message=f"IB order submitted: {trade.orderStatus.status}",
                broker_response={'trade': trade}
            )
            
        except Exception as e:
            logger.error(f"Failed to place IB order: {e}")
            return OrderResult(
                success=False,
                error_code="IB_ORDER_FAILED",
                message=str(e)
            )
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel IB order"""
        try:
            # Find the trade by order ID
            for trade in self.ib.trades():
                if str(trade.order.orderId) == order_id:
                    self.ib.cancelOrder(trade.order)
                    return True
            return False
        except Exception as e:
            logger.error(f"Failed to cancel IB order {order_id}: {e}")
            return False


def create_interactive_brokers_from_env(portfolio_manager=None) -> InteractiveBrokersExecutor:
    """Create IB executor from environment variables"""
    from .utils import get_broker_config_from_env
    
    config_dict = get_broker_config_from_env('interactive_brokers')
    
    config = BrokerConfig(
        broker_type='interactive_brokers',
        paper_trading=config_dict.get('paper_trading', True),
        credentials=config_dict
    )
    
    return InteractiveBrokersExecutor(config, portfolio_manager)
```

### Environment Setup

```bash
# Interactive Brokers Environment Variables
export IB_TWS_HOST="localhost"
export IB_TWS_PORT="7497"  # 7497 for paper, 7496 for live
export IB_CLIENT_ID="1"
export IB_PAPER="true"

# Prerequisites:
# 1. Install TWS or IB Gateway
# 2. Enable API access in TWS settings
# 3. Start TWS/Gateway before running
```

## TD Ameritrade Integration

### Implementation Example

```python
"""
TD Ameritrade Implementation

Example using TD Ameritrade's REST API
"""

import logging
import requests
from typing import Dict, Optional, List, Any
from decimal import Decimal
import json

from .base import (
    BaseBroker, BrokerConfig, BrokerInfo, AccountInfo, 
    Position, OrderResult, OrderType, OrderSide
)

logger = logging.getLogger(__name__)


class TDAmeritradeBroker(BaseBroker):
    """TD Ameritrade implementation using REST API"""
    
    def __init__(self, config: BrokerConfig, portfolio_manager=None):
        super().__init__(config, portfolio_manager)
        self.access_token = None
        self.account_id = None
        self.base_url = "https://api.tdameritrade.com/v1"
        
    def connect(self) -> bool:
        """Connect to TD Ameritrade API"""
        try:
            # Get access token using refresh token
            refresh_token = self.config.credentials.get('refresh_token')
            client_id = self.config.credentials.get('client_id')
            
            if not refresh_token or not client_id:
                raise ValueError("Missing TD Ameritrade credentials")
            
            token_url = "https://api.tdameritrade.com/v1/oauth2/token"
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': client_id
            }
            
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            
            # Get account information
            accounts = self._make_request('GET', '/accounts')
            if accounts:
                self.account_id = accounts[0]['securitiesAccount']['accountId']
                logger.info(f"Connected to TD Ameritrade - Account: {self.account_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to connect to TD Ameritrade: {e}")
            return False
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Optional[Dict]:
        """Make authenticated request to TD Ameritrade API"""
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json() if response.content else {}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"TD Ameritrade API request failed: {e}")
            return None
    
    def get_account_info(self) -> AccountInfo:
        """Get TD Ameritrade account information"""
        account_data = self._make_request('GET', f'/accounts/{self.account_id}')
        
        if account_data:
            securities_account = account_data['securitiesAccount']
            current_balances = securities_account['currentBalances']
            
            return AccountInfo(
                account_id=self.account_id,
                buying_power=Decimal(str(current_balances['buyingPower'])),
                total_value=Decimal(str(current_balances['liquidationValue'])),
                cash=Decimal(str(current_balances['cashBalance']))
            )
        
        return AccountInfo(account_id=self.account_id)
    
    def place_order(self, symbol: str, order_type: OrderType, 
                   side: OrderSide, quantity: Decimal, 
                   price: Optional[Decimal] = None, 
                   metadata: Optional[Dict[str, Any]] = None) -> OrderResult:
        """Place order through TD Ameritrade"""
        try:
            order_data = {
                "orderType": order_type.value,
                "session": "NORMAL",
                "duration": "DAY",
                "orderStrategyType": "SINGLE",
                "orderLegCollection": [
                    {
                        "instruction": side.value,
                        "quantity": float(quantity),
                        "instrument": {
                            "symbol": symbol,
                            "assetType": "EQUITY"
                        }
                    }
                ]
            }
            
            if order_type == OrderType.LIMIT and price:
                order_data["price"] = float(price)
            
            response = self._make_request('POST', f'/accounts/{self.account_id}/orders', order_data)
            
            if response is not None:
                return OrderResult(
                    success=True,
                    message="TD Ameritrade order submitted",
                    broker_response=response
                )
            else:
                return OrderResult(
                    success=False,
                    error_code="TD_ORDER_FAILED",
                    message="Failed to submit order"
                )
                
        except Exception as e:
            logger.error(f"Failed to place TD Ameritrade order: {e}")
            return OrderResult(
                success=False,
                error_code="TD_ORDER_ERROR",
                message=str(e)
            )


def create_td_ameritrade_from_env(portfolio_manager=None) -> TDAmeritradeBroker:
    """Create TD Ameritrade executor from environment variables"""
    from .utils import get_broker_config_from_env
    
    config_dict = get_broker_config_from_env('td_ameritrade')
    
    config = BrokerConfig(
        broker_type='td_ameritrade',
        paper_trading=config_dict.get('paper_trading', True),
        credentials=config_dict
    )
    
    return TDAmeritradeBroker(config, portfolio_manager)
```

### Environment Setup

```bash
# TD Ameritrade Environment Variables
export TD_CLIENT_ID="your_client_id@AMER.OAUTHAP"
export TD_REFRESH_TOKEN="your_refresh_token"
export TD_REDIRECT_URI="http://localhost"
export TD_PAPER="true"

# Getting credentials:
# 1. Create app at https://developer.tdameritrade.com/
# 2. Get client_id and redirect_uri
# 3. Follow OAuth flow to get refresh_token
```

## Crypto Exchange Integration (Coinbase Pro)

### Implementation Example

```python
"""
Coinbase Pro Integration

Example for cryptocurrency trading
"""

import logging
from typing import Dict, Optional, List, Any
from decimal import Decimal
import cbpro  # Coinbase Pro API

from .base import (
    BaseBroker, BrokerConfig, BrokerInfo, AccountInfo, 
    Position, OrderResult, OrderType, OrderSide
)

logger = logging.getLogger(__name__)


class CoinbaseBroker(BaseBroker):
    """Coinbase Pro implementation for crypto trading"""
    
    def __init__(self, config: BrokerConfig, portfolio_manager=None):
        super().__init__(config, portfolio_manager)
        self.client = None
        
    def connect(self) -> bool:
        """Connect to Coinbase Pro API"""
        try:
            api_key = self.config.credentials.get('api_key')
            api_secret = self.config.credentials.get('api_secret')
            passphrase = self.config.credentials.get('passphrase')
            
            sandbox = self.config.paper_trading
            
            self.client = cbpro.AuthenticatedClient(
                api_key, api_secret, passphrase, sandbox=sandbox
            )
            
            # Test connection
            accounts = self.client.get_accounts()
            logger.info(f"Connected to Coinbase Pro - {len(accounts)} accounts")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Coinbase Pro: {e}")
            return False
    
    def get_account_info(self) -> AccountInfo:
        """Get Coinbase Pro account information"""
        accounts = self.client.get_accounts()
        
        total_value = Decimal('0')
        cash_value = Decimal('0')
        
        for account in accounts:
            balance = Decimal(account['balance'])
            if account['currency'] == 'USD':
                cash_value += balance
            total_value += balance  # Simplified - would need price conversion
        
        return AccountInfo(
            account_id="coinbase_portfolio",
            buying_power=cash_value,
            total_value=total_value,
            cash=cash_value
        )
    
    def place_order(self, symbol: str, order_type: OrderType, 
                   side: OrderSide, quantity: Decimal, 
                   price: Optional[Decimal] = None, 
                   metadata: Optional[Dict[str, Any]] = None) -> OrderResult:
        """Place crypto order"""
        try:
            # Convert symbol format (BTC -> BTC-USD)
            if '-' not in symbol:
                symbol = f"{symbol}-USD"
            
            order_params = {
                'product_id': symbol,
                'side': side.value.lower(),
                'size': str(quantity)
            }
            
            if order_type == OrderType.MARKET:
                order_params['type'] = 'market'
            elif order_type == OrderType.LIMIT:
                order_params['type'] = 'limit'
                order_params['price'] = str(price)
            
            result = self.client.place_order(**order_params)
            
            if 'id' in result:
                return OrderResult(
                    success=True,
                    order_id=result['id'],
                    message="Coinbase Pro order submitted",
                    broker_response=result
                )
            else:
                return OrderResult(
                    success=False,
                    error_code="COINBASE_ORDER_FAILED",
                    message=result.get('message', 'Unknown error')
                )
                
        except Exception as e:
            logger.error(f"Failed to place Coinbase Pro order: {e}")
            return OrderResult(
                success=False,
                error_code="COINBASE_ERROR",
                message=str(e)
            )


def create_coinbase_from_env(portfolio_manager=None) -> CoinbaseBroker:
    """Create Coinbase Pro executor from environment variables"""
    from .utils import get_broker_config_from_env
    
    config_dict = get_broker_config_from_env('coinbase')
    
    config = BrokerConfig(
        broker_type='coinbase',
        paper_trading=config_dict.get('paper_trading', True),
        credentials=config_dict
    )
    
    return CoinbaseBroker(config, portfolio_manager)
```

## Multi-Broker Portfolio Strategy

### Advanced Usage Example

```python
"""
Multi-Broker Strategy Example

Distribute trades across multiple brokers for diversification
"""

from typing import Dict, List
from StrateQueue.brokers import BrokerFactory, auto_create_broker


class MultiBrokerStrategy:
    """Strategy that uses multiple brokers"""
    
    def __init__(self):
        self.brokers = {}
        self.broker_allocations = {
            'alpaca': 0.6,      # 60% allocation
            'interactive_brokers': 0.4  # 40% allocation
        }
        
    def initialize_brokers(self):
        """Initialize all configured brokers"""
        for broker_type in self.broker_allocations.keys():
            try:
                broker = BrokerFactory.create_broker(broker_type)
                if broker.connect():
                    self.brokers[broker_type] = broker
                    print(f"✅ Connected to {broker_type}")
                else:
                    print(f"❌ Failed to connect to {broker_type}")
            except Exception as e:
                print(f"❌ Error with {broker_type}: {e}")
    
    def execute_distributed_order(self, symbol: str, total_quantity: int, order_side: str):
        """Distribute order across multiple brokers"""
        results = {}
        
        for broker_type, allocation in self.broker_allocations.items():
            if broker_type in self.brokers:
                broker = self.brokers[broker_type]
                quantity = int(total_quantity * allocation)
                
                if quantity > 0:
                    result = broker.place_order(
                        symbol=symbol,
                        order_type=OrderType.MARKET,
                        side=OrderSide.BUY if order_side == 'buy' else OrderSide.SELL,
                        quantity=Decimal(str(quantity))
                    )
                    results[broker_type] = result
        
        return results
    
    def get_combined_portfolio(self) -> Dict:
        """Get combined portfolio from all brokers"""
        combined_portfolio = {
            'total_value': Decimal('0'),
            'positions': {},
            'brokers': {}
        }
        
        for broker_type, broker in self.brokers.items():
            account_info = broker.get_account_info()
            positions = broker.get_positions()
            
            combined_portfolio['total_value'] += account_info.total_value
            combined_portfolio['brokers'][broker_type] = {
                'value': account_info.total_value,
                'positions': len(positions)
            }
            
            # Aggregate positions
            for position in positions:
                if position.symbol in combined_portfolio['positions']:
                    combined_portfolio['positions'][position.symbol] += position.quantity
                else:
                    combined_portfolio['positions'][position.symbol] = position.quantity
        
        return combined_portfolio
```

## Testing and Validation

### Integration Test Framework

```python
"""
Broker Testing Framework

Comprehensive testing for broker implementations
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch

from StrateQueue.brokers.base import OrderType, OrderSide
from StrateQueue.brokers import BrokerFactory


class BrokerTestSuite:
    """Standard test suite for broker implementations"""
    
    @pytest.fixture
    def broker_type(self):
        """Override this in broker-specific test classes"""
        raise NotImplementedError("Must specify broker_type")
    
    @pytest.fixture
    def mock_credentials(self):
        """Override this with broker-specific credentials"""
        raise NotImplementedError("Must specify mock_credentials")
    
    def test_broker_creation(self, broker_type, mock_credentials):
        """Test broker can be created via factory"""
        with patch.dict('os.environ', mock_credentials):
            broker = BrokerFactory.create_broker(broker_type)
            assert broker.config.broker_type == broker_type
    
    def test_connection_success(self, broker_type, mock_credentials):
        """Test successful connection"""
        with patch.dict('os.environ', mock_credentials):
            broker = BrokerFactory.create_broker(broker_type)
            # Mock the underlying API calls
            with patch.object(broker, '_connect_api', return_value=True):
                assert broker.connect() == True
    
    def test_connection_failure(self, broker_type, mock_credentials):
        """Test connection failure handling"""
        with patch.dict('os.environ', mock_credentials):
            broker = BrokerFactory.create_broker(broker_type)
            with patch.object(broker, '_connect_api', side_effect=Exception("Network error")):
                assert broker.connect() == False
    
    def test_account_info(self, broker_type, mock_credentials):
        """Test account info retrieval"""
        with patch.dict('os.environ', mock_credentials):
            broker = BrokerFactory.create_broker(broker_type)
            
            # Mock successful connection and account data
            mock_account = Mock()
            mock_account.buying_power = 10000.0
            mock_account.total_value = 15000.0
            
            with patch.object(broker, 'connect', return_value=True), \
                 patch.object(broker, '_get_account_data', return_value=mock_account):
                
                broker.connect()
                account_info = broker.get_account_info()
                
                assert account_info.buying_power >= 0
                assert account_info.total_value >= 0
    
    def test_market_order(self, broker_type, mock_credentials):
        """Test market order placement"""
        with patch.dict('os.environ', mock_credentials):
            broker = BrokerFactory.create_broker(broker_type)
            
            with patch.object(broker, 'connect', return_value=True), \
                 patch.object(broker, '_submit_order') as mock_submit:
                
                mock_submit.return_value = Mock(id='test_order_123')
                broker.connect()
                
                result = broker.place_order(
                    symbol='AAPL',
                    order_type=OrderType.MARKET,
                    side=OrderSide.BUY,
                    quantity=Decimal('10')
                )
                
                assert result.success == True
                assert result.order_id is not None
```

### Specific Broker Tests

```python
class TestAlpacaBroker(BrokerTestSuite):
    """Test suite for Alpaca broker"""
    
    @pytest.fixture
    def broker_type(self):
        return 'alpaca'
    
    @pytest.fixture
    def mock_credentials(self):
        return {
            'PAPER_KEY': 'test_key',
            'PAPER_SECRET': 'test_secret',
            'PAPER_ENDPOINT': 'https://paper-api.alpaca.markets'
        }


class TestInteractiveBrokers(BrokerTestSuite):
    """Test suite for Interactive Brokers"""
    
    @pytest.fixture
    def broker_type(self):
        return 'interactive_brokers'
    
    @pytest.fixture
    def mock_credentials(self):
        return {
            'IB_TWS_HOST': 'localhost',
            'IB_TWS_PORT': '7497',
            'IB_CLIENT_ID': '1'
        }
```

This comprehensive example system demonstrates how to implement, test, and integrate multiple brokers with the Stratequeue trading platform using the unified broker factory pattern. 