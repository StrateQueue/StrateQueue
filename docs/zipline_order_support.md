# Zipline Order Support in StrateQueue

StrateQueue now provides **comprehensive support for all Zipline order mechanisms**, enabling you to deploy any Zipline strategy live within seconds while preserving the exact order intent and execution style.

## 🎯 Overview

The enhanced Zipline engine captures and translates **every order type** from Zipline strategies into detailed `TradingSignal` objects that preserve:

- **Order function used** (`order`, `order_value`, `order_percent`, etc.)
- **Execution style** (market, limit, stop, stop-limit)
- **All parameters** (quantities, prices, percentages, targets)
- **Buy/sell direction** and **position sizing**

## 📋 Supported Order Functions

### Basic Order Functions

```python
# Order specific number of shares
order(asset, amount, limit_price=None, stop_price=None, style=None)

# Order specific dollar value
order_value(asset, value, limit_price=None, stop_price=None, style=None)

# Order percentage of portfolio
order_percent(asset, percent, limit_price=None, stop_price=None, style=None)
```

### Target-Based Order Functions

```python
# Target specific number of shares
order_target(asset, target, limit_price=None, stop_price=None, style=None)

# Target specific dollar value
order_target_value(asset, target, limit_price=None, stop_price=None, style=None)

# Target percentage of portfolio
order_target_percent(asset, target, limit_price=None, stop_price=None, style=None)
```

## 🎨 Execution Styles

### Market Orders (Default)
```python
from zipline.api import order

def handle_data(context, data):
    # Simple market order
    order(context.asset, 100)
```

### Limit Orders
```python
from zipline.api import order
from zipline.finance.execution import LimitOrder

def handle_data(context, data):
    current_price = data.current(context.asset, 'price')
    
    # Method 1: Using limit_price parameter
    order(context.asset, 100, limit_price=current_price * 0.99)
    
    # Method 2: Using LimitOrder style
    order(context.asset, 100, style=LimitOrder(current_price * 0.99))
```

### Stop Orders
```python
from zipline.api import order
from zipline.finance.execution import StopOrder

def handle_data(context, data):
    current_price = data.current(context.asset, 'price')
    
    # Method 1: Using stop_price parameter
    order(context.asset, -100, stop_price=current_price * 0.95)
    
    # Method 2: Using StopOrder style
    order(context.asset, -100, style=StopOrder(current_price * 0.95))
```

### Stop-Limit Orders
```python
from zipline.api import order
from zipline.finance.execution import StopLimitOrder

def handle_data(context, data):
    current_price = data.current(context.asset, 'price')
    
    # Method 1: Using both parameters
    order(context.asset, -100, 
          limit_price=current_price * 0.94, 
          stop_price=current_price * 0.95)
    
    # Method 2: Using StopLimitOrder style
    order(context.asset, -100, 
          style=StopLimitOrder(limit_price=current_price * 0.94, 
                               stop_price=current_price * 0.95))
```

## 🔧 Enhanced Signal Structure

The enhanced `TradingSignal` includes all order information:

```python
@dataclass
class TradingSignal:
    # Basic signal info
    signal: SignalType          # BUY/SELL/HOLD
    price: float               # Current market price
    timestamp: pd.Timestamp    # Signal timestamp
    indicators: dict          # Strategy indicators
    
    # Order function details
    order_function: OrderFunction     # Which function was called
    execution_style: ExecStyle       # Market/Limit/Stop/StopLimit
    
    # Order parameters
    quantity: float | None           # Shares (for order())
    value: float | None             # Dollar amount (for order_value())
    percent: float | None           # Portfolio % (for order_percent())
    target_quantity: float | None   # Target shares (for order_target())
    target_value: float | None      # Target $ (for order_target_value())
    target_percent: float | None    # Target % (for order_target_percent())
    
    # Execution parameters
    limit_price: float | None       # Limit price
    stop_price: float | None        # Stop price
    exchange: str | None            # Exchange routing
    
    # Metadata
    order_id: str | None           # Zipline order ID
    metadata: dict | None          # Additional data
```

## 📊 Complete Example Strategy

```python
"""
Comprehensive Order Demo Strategy
Demonstrates all order types and execution styles
"""

__zipline_strategy__ = True

from zipline.api import (
    order, order_value, order_percent,
    order_target, order_target_value, order_target_percent,
    symbol, record
)
from zipline.finance.execution import LimitOrder, StopOrder, StopLimitOrder

def initialize(context):
    context.asset = symbol('AAPL')
    context.cycle = 0

def handle_data(context, data):
    current_price = data.current(context.asset, 'price')
    
    # Cycle through different order types
    order_type = context.cycle % 9
    
    if order_type == 0:
        # Market order for 100 shares
        order(context.asset, 100)
        
    elif order_type == 1:
        # Limit order - buy 50 shares at 1% below market
        order(context.asset, 50, limit_price=current_price * 0.99)
        
    elif order_type == 2:
        # Stop order - sell 75 shares if price drops 2%
        order(context.asset, -75, stop_price=current_price * 0.98)
        
    elif order_type == 3:
        # Stop-limit order - complex exit strategy
        order(context.asset, -50,
              stop_price=current_price * 0.97,
              limit_price=current_price * 0.96)
              
    elif order_type == 4:
        # Order $10,000 worth of shares
        order_value(context.asset, 10000)
        
    elif order_type == 5:
        # Order 5% of portfolio value
        order_percent(context.asset, 0.05)
        
    elif order_type == 6:
        # Target 200 shares total
        order_target(context.asset, 200)
        
    elif order_type == 7:
        # Target $25,000 position value
        order_target_value(context.asset, 25000)
        
    elif order_type == 8:
        # Target 15% of portfolio in this asset
        order_target_percent(context.asset, 0.15)
    
    context.cycle += 1
    
    # Record for analysis
    record(order_type=order_type, price=current_price)
```

## 🚀 Live Deployment

Deploy any strategy with full order support:

```bash
# Deploy with comprehensive order capture
stratequeue deploy \
  --strategy examples/strategies/zipline-reloaded/order_showcase.py \
  --symbol AAPL,MSFT \
  --engine zipline \
  --data-source demo \
  --no-trading \
  --duration 60

# All order types and execution styles are captured and logged
```

## 🔍 Signal Analysis

View captured order details in the live system:

```
🎯 SIGNAL #4 - 2025-06-23 16:34:15
Symbol: AAPL
Action: 📈 BUY
Price: $150.25
Order Details:
  • Function: order_target_percent
  • Style: limit
  • Target %: 15.0%
  • Limit Price: $148.75
Indicators:
  • zipline_algorithm: 1.00
  • algorithm_result: success
```

## 🛡️ Backward Compatibility

**100% backward compatible** - existing strategies continue to work:

```python
# This still works exactly as before
def handle_data(context, data):
    order_target_percent(context.asset, 0.1)
```

The new fields are added without breaking existing code.

## ⚡ Performance Impact

- **Zero overhead** for strategies that don't use advanced features
- **Minimal capture cost** - only active during signal extraction
- **Efficient patching** - functions restored after each extraction
- **Queue-based** - fast signal capture and processing

## 🔧 Integration with Brokers

The enhanced signals can be translated by broker adapters:

```python
# Broker adapter can handle any order type
def translate_signal(signal: TradingSignal) -> BrokerOrder:
    if signal.execution_style == ExecStyle.LIMIT:
        return create_limit_order(
            symbol=signal.symbol,
            quantity=signal.quantity,
            limit_price=signal.limit_price
        )
    elif signal.execution_style == ExecStyle.STOP_LIMIT:
        return create_stop_limit_order(
            symbol=signal.symbol,
            quantity=signal.quantity,
            stop_price=signal.stop_price,
            limit_price=signal.limit_price
        )
    # ... handle all order types
```

## 🧪 Testing

Run comprehensive tests for order capture:

```bash
# Test all order mechanisms
python -m pytest tests/test_zipline_order_capture.py -v

# Test specific order functions
python -m pytest tests/test_zipline_order_capture.py::TestZiplineOrderCapture::test_order_function_capture -v
```

## 📈 Benefits

1. **Complete Fidelity** - Every order detail preserved
2. **Any Strategy** - Deploy existing Zipline strategies unchanged  
3. **Professional Trading** - Support for complex order types
4. **Risk Management** - Detailed order tracking and analysis
5. **Broker Agnostic** - Rich signals work with any broker API

## 🚨 Important Notes

- **Daily Data Limitation**: Some execution styles work best with minute data
- **Mock Execution**: Orders are captured, not actually executed in Zipline
- **Signal Translation**: Broker adapters handle actual order placement
- **Error Handling**: Invalid orders result in HOLD signals

---

**Result**: Any Zipline strategy can now be deployed live with **complete order type support** in the same few seconds as before, but with professional-grade order handling capabilities. 🎉 