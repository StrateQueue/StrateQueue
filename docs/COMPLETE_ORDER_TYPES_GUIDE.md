# Complete Order Types Guide for Live Trading System

## Overview

Your live trading system now supports **ALL** order types available in backtesting.py and maps them directly to Alpaca's native order types. This provides complete control over your trade execution.

## Supported Order Types

### 1. **Market Orders** (Immediate Execution)
- **Execute immediately** at current market price
- **Guaranteed execution** but unpredictable price

**Backtesting.py Usage:**
```python
self.buy()  # Market buy
self.sell() # Market sell
```

**Live Trading:** → `MarketOrderRequest`

---

### 2. **Limit Orders** (Price Control)
- **Execute only at specified price or better**
- **Predictable price** but no guarantee of execution

**Backtesting.py Usage:**
```python
self.buy(limit=99.50)   # Buy only at $99.50 or lower
self.sell(limit=101.50) # Sell only at $101.50 or higher
```

**Live Trading:** → `LimitOrderRequest`

---

### 3. **Stop Orders** (Breakout/Breakdown)
- **Trigger when price hits stop level**, then execute as market order
- Used for breakout strategies or stop-loss protection

**Backtesting.py Usage:**
```python
from backtesting import Order

# Stop buy: buy when price rises to $102
self.buy(exectype=Order.Stop, stop=102.00)

# Stop sell: sell when price falls to $98  
self.sell(exectype=Order.Stop, stop=98.00)
```

**Live Trading:** → `StopOrderRequest`

---

### 4. **Stop-Limit Orders** (Controlled Stop)
- **Trigger at stop price**, then place **limit order** at limit price
- Combines stop trigger with price protection

**Backtesting.py Usage:**
```python
# Stop-limit buy: trigger at $102, but only buy up to $103
self.buy(exectype=Order.StopLimit, stop=102.00, limit=103.00)

# Stop-limit sell: trigger at $98, but only sell down to $97
self.sell(exectype=Order.StopLimit, stop=98.00, limit=97.00)
```

**Live Trading:** → `StopLimitOrderRequest`

---

### 5. **Trailing Stop Orders** (Dynamic Protection)
- **Follows price movement** in favorable direction
- **Triggers when price reverses** by specified amount
- Only supported for sell orders (profit protection)

**Note:** Backtesting.py doesn't have native trailing stops, but our system detects patterns and converts appropriately.

**Live Trading Direct Usage:**
Your system generates `TRAILING_STOP_SELL` signals that map to `TrailingStopOrderRequest` with either:
- `trail_percent=0.03` (3% trailing stop)
- `trail_price=5.00` (absolute $5 trailing stop)

---

### 6. **Time In Force** (Order Duration)
- **GTC (Good Till Canceled)**: Order stays active until filled or manually canceled
- **DAY**: Order expires at end of trading day if not filled

**Backtesting.py Usage:**
```python
self.buy(limit=99.50, valid=0)  # Day order (valid=0)
self.buy(limit=99.50)           # GTC order (default)
```

**Live Trading:** → `time_in_force` parameter in all order types

---

## Complete Example Strategy

Here's a strategy using all order types:

```python
from backtesting import Strategy, Order
from backtesting.lib import crossover
from backtesting.test import SMA

class AllOrderTypesStrategy(Strategy):
    def init(self):
        self.sma_fast = self.I(SMA, self.data.Close, 10)
        self.sma_slow = self.I(SMA, self.data.Close, 20)
        self.entry_price = None
        
    def next(self):
        price = self.data.Close[-1]
        
        if not self.position:
            # 1. Market order on strong signal
            if crossover(self.sma_fast, self.sma_slow):
                self.buy(size=0.3)  # 30% allocation
                self.entry_price = price
                
            # 2. Limit order for better entry
            elif self.sma_fast[-1] > self.sma_slow[-1]:
                self.buy(size=0.2, limit=price * 0.99)  # 1% below
                
            # 3. Stop buy for breakout
            elif price < self.sma_slow[-1]:
                self.buy(size=0.1, exectype=Order.Stop, stop=self.sma_slow[-1])
                
        else:  # We have a position
            # 4. Stop-loss protection
            stop_price = self.entry_price * 0.95  # 5% stop loss
            self.sell(size=0.5, exectype=Order.Stop, stop=stop_price)
            
            # 5. Take profit with limit
            if price > self.entry_price * 1.1:  # 10% profit
                self.sell(size=0.3, limit=price * 1.02)  # 2% above current
                
            # 6. Stop-limit for controlled exit
            stop_price = self.entry_price * 0.97  # 3% stop
            limit_price = self.entry_price * 0.95  # 5% limit
            self.sell(size=0.2, exectype=Order.StopLimit, 
                     stop=stop_price, limit=limit_price)
```

## System Flow

1. **Strategy Generation**: Your backtesting.py strategy calls `buy()`/`sell()` with parameters
2. **Signal Conversion**: System detects order type from parameters and `exectype`
3. **Signal Mapping**: Converts to appropriate `SignalType` (`LIMIT_BUY`, `STOP_SELL`, etc.)
4. **Alpaca Execution**: Maps to corresponding Alpaca order request type
5. **Order Placement**: Submits to Alpaca with all parameters preserved

## Order Type Mapping Table

| Backtesting.py | Signal Type | Alpaca Order Type | Key Parameters |
|---|---|---|---|
| `buy()` | `BUY` | `MarketOrderRequest` | `size` |
| `buy(limit=X)` | `LIMIT_BUY` | `LimitOrderRequest` | `size`, `limit_price` |
| `buy(exectype=Order.Stop, stop=X)` | `STOP_BUY` | `StopOrderRequest` | `size`, `stop_price` |
| `buy(exectype=Order.StopLimit, stop=X, limit=Y)` | `STOP_LIMIT_BUY` | `StopLimitOrderRequest` | `size`, `stop_price`, `limit_price` |
| `sell()` | `SELL` | `MarketOrderRequest` | `size` |
| `sell(limit=X)` | `LIMIT_SELL` | `LimitOrderRequest` | `size`, `limit_price` |
| `sell(exectype=Order.Stop, stop=X)` | `STOP_SELL` | `StopOrderRequest` | `size`, `stop_price` |
| `sell(exectype=Order.StopLimit, stop=X, limit=Y)` | `STOP_LIMIT_SELL` | `StopLimitOrderRequest` | `size`, `stop_price`, `limit_price` |
| (Generated by system) | `TRAILING_STOP_SELL` | `TrailingStopOrderRequest` | `size`, `trail_percent` or `trail_price` |

## Benefits

✅ **Complete Coverage**: All backtesting.py order types supported  
✅ **Seamless Transition**: Same strategy works for both backtesting and live trading  
✅ **Native Mapping**: Direct translation to Alpaca's order types  
✅ **Parameter Preservation**: All order parameters (prices, sizes, time-in-force) maintained  
✅ **Professional Trading**: Access to advanced order types used by professional traders

Your system now provides institutional-grade order management capabilities! 