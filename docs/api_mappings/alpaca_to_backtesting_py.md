# Alpaca Trading API ↔ backtesting.py Cross-Reference

This document provides a comprehensive mapping between [Alpaca Trading API v2](https://docs.alpaca.markets/docs/orders-at-alpaca) and [backtesting.py](https://kernc.github.io/backtesting.py/) to help developers translate concepts, orders, and workflows between live trading and backtesting.

**Legend:**
- `alp` = Alpaca Trading API v2 (stocks)
- `btp` = backtesting.py (latest release 0.6.x)
- `→` = same concept / direct translation
- `≈` = closest practical analogue (behavior differs, see notes)
- `✗` = not supported / no equivalent

---

## 1. Order Creation & Types

| Concept                    | Alpaca REST API (POST /v2/orders)               | backtesting.py Strategy Methods                |
|----------------------------|--------------------------------------------------|-----------------------------------------------|
| **Order Side**             |                                                  |                                               |
| Long position              | `"side": "buy"`                                  | `self.buy()`                                  |
| Short position             | `"side": "sell"`                                 | `self.sell()`                                 |
| **Basic Order Types**      |                                                  |                                               |
| Market order               | `"type": "market"`                               | `self.buy()` (default, no limit/stop)         |
| Limit order                | `"type": "limit", "limit_price": "100.50"`       | `self.buy(limit=100.50)`                      |
| Stop-market order          | `"type": "stop", "stop_price": "95.00"`          | `self.buy(stop=95.00)`                        |
| Stop-limit order           | `"type": "stop_limit", "stop_price": "95", "limit_price": "94.50"` | `self.buy(stop=95.00, limit=94.50)` |
| Trailing stop order        | `"type": "trailing_stop", "trail_percent": "2"` | Manual update loop or `TrailingStrategy` ≈   |
| **Advanced Order Types**   |                                                  |                                               |
| Bracket order (entry+SL+TP)| `"order_class": "bracket", "take_profit": {...}, "stop_loss": {...}` | `self.buy(sl=98, tp=110)` |
| OCO (exit-only SL+TP)      | `"order_class": "oco", "take_profit": {...}, "stop_loss": {...}` | Set `Trade.sl` & `Trade.tp` on live trade |
| OTO (entry + one exit)     | `"order_class": "oto", "stop_loss": {...}` or `"take_profit": {...}` | `self.buy(sl=98)` or `self.buy(tp=110)` |

### Code Examples - Order Creation

```python
# ═══════════════════════════════════════════════════════════════════════════
# MARKET BUY 100 shares
# ═══════════════════════════════════════════════════════════════════════════
# Alpaca
{
  "symbol": "AAPL",
  "side": "buy", 
  "type": "market",
  "qty": "100",
  "time_in_force": "day"
}

# backtesting.py
self.buy(size=100)

# ═══════════════════════════════════════════════════════════════════════════
# LIMIT SELL with Stop-Loss and Take-Profit
# ═══════════════════════════════════════════════════════════════════════════
# Alpaca - bracket exit order
{
  "symbol": "AAPL",
  "side": "sell",
  "type": "limit", 
  "qty": "100",
  "limit_price": "102.00",
  "time_in_force": "gtc",
  "order_class": "oco",
  "take_profit": {"limit_price": "98.00"},
  "stop_loss": {"stop_price": "105.00"}
}

# backtesting.py
self.sell(
    size=self.position.size,
    limit=102.00,
    sl=105.00,  # Stop-loss (sell stops go above current price)
    tp=98.00    # Take-profit
)
```

---

## 2. Order Parameters & Sizing

| Parameter                  | Alpaca                                          | backtesting.py                               |
|----------------------------|------------------------------------------------|----------------------------------------------|
| **Quantity/Sizing**        |                                                |                                              |
| Whole shares               | `"qty": "100"`                                 | `size=100`                                   |
| Fractional/Notional        | `"notional": "1000.00"` (USD amount)          | `size=0.25` (25% of available equity) ≈     |
| **Pricing**                |                                                |                                              |
| Limit price                | `"limit_price": "150.50"`                     | `limit=150.50`                               |
| Stop price                 | `"stop_price": "145.00"`                      | `stop=145.00`                                |
| Trail amount (dollars)     | `"trail_price": "2.50"`                       | Manual: `trade.sl = max(trade.sl, current_price - 2.50)` |
| Trail amount (percent)     | `"trail_percent": "2.0"`                      | Manual: `trade.sl = max(trade.sl, current_price * 0.98)` |
| **Order Management**       |                                                |                                              |
| Client order ID            | `"client_order_id": "my_order_123"`           | `tag="my_order_123"` (set on buy/sell)       |
| Time in force              | `"time_in_force": "day"/"gtc"/"ioc"/"fok"`    | ✗ (all orders are GTC; manual expiry only)   |
| Extended hours trading     | `"extended_hours": true`                       | ✗ (not applicable to backtesting)            |

---

## 3. Order Status & Lifecycle Management

| Action/Status              | Alpaca API                                     | backtesting.py                               |
|----------------------------|------------------------------------------------|----------------------------------------------|
| **Order States**           |                                                |                                              |
| Order submitted            | `"status": "new"`                              | Order in `self.orders` list                  |
| Partially filled           | `"status": "partially_filled"`                | ✗ (fills are atomic in backtesting)          |
| Completely filled          | `"status": "filled"`                          | Order removed from `self.orders`, creates `Trade` |
| Canceled                   | `"status": "canceled"`                        | Order removed from `self.orders`             |
| Expired                    | `"status": "expired"`                         | Manual expiry via `order.cancel()`           |
| **Order Management**       |                                                |                                              |
| Cancel specific order      | `DELETE /v2/orders/{order_id}`                | `order.cancel()`                              |
| Cancel all orders          | `DELETE /v2/orders`                           | `for o in self.orders: o.cancel()`            |
| Modify order               | `PATCH /v2/orders/{order_id}`                 | `order.cancel(); self.buy(new_params)` ≈     |
| Get order status           | `GET /v2/orders/{order_id}`                   | Check if order in `self.orders`              |

### Code Examples - Order Management

```python
# ═══════════════════════════════════════════════════════════════════════════
# Cancel all pending orders
# ═══════════════════════════════════════════════════════════════════════════
# Alpaca
DELETE /v2/orders

# backtesting.py  
for order in self.orders:
    order.cancel()

# ═══════════════════════════════════════════════════════════════════════════
# Modify stop-loss on existing trade
# ═══════════════════════════════════════════════════════════════════════════
# Alpaca - patch the child stop-loss order
PATCH /v2/orders/{stop_loss_order_id}
{"stop_price": "96.00"}

# backtesting.py - direct property assignment
for trade in self.trades:
    trade.sl = 96.00  # Tighten stop-loss
```

---

## 4. Position & Account Information

| Information                | Alpaca API                                     | backtesting.py                               |
|----------------------------|------------------------------------------------|----------------------------------------------|
| **Account Data**           |                                                |                                              |
| Account info               | `GET /v2/account`                             | `self.equity` (current account value)        |
| Buying power               | `account.buying_power`                        | ✗ (implicitly unlimited in backtesting)      |
| Cash balance               | `account.cash`                                | ✗ (managed internally)                       |
| **Position Data**          |                                                |                                              |
| All positions              | `GET /v2/positions`                           | `self.position` (aggregate) or `self.trades` (individual) |
| Position for symbol        | `GET /v2/positions/{symbol}`                  | `self.position.size` (net quantity)          |
| Unrealized P&L             | `position.unrealized_pl`                      | `self.position.pl` or `trade.pl`             |
| Realized P&L               | Via account activities API                    | `self.closed_trades` (completed trades)      |
| **Trade History**          |                                                |                                              |
| Recent orders              | `GET /v2/orders?status=all`                  | `self.orders` + `self.closed_trades`         |
| Recent fills               | `GET /v2/account/activities?activity_type=FILL` | Individual `Trade` objects in `self.closed_trades` |

### Code Examples - Positions

```python
# ═══════════════════════════════════════════════════════════════════════════
# Check current position and close if profitable
# ═══════════════════════════════════════════════════════════════════════════
# Alpaca
positions = api.get_positions()
for pos in positions:
    if float(pos.unrealized_pl) > 100:  # $100 profit
        api.submit_order(
            symbol=pos.symbol,
            side='sell' if pos.side == 'long' else 'buy',
            type='market',
            qty=abs(int(pos.qty))
        )

# backtesting.py
if self.position and self.position.pl > 100:
    self.position.close()

# ═══════════════════════════════════════════════════════════════════════════
# Close 50% of position
# ═══════════════════════════════════════════════════════════════════════════
# Alpaca  
api.submit_order(
    symbol='AAPL',
    side='sell',
    type='market', 
    qty=str(int(position_size / 2))
)

# backtesting.py
self.position.close(portion=0.5)
```

---

## 5. Event Handling & Streaming

| Event Type                 | Alpaca                                         | backtesting.py                               |
|----------------------------|------------------------------------------------|----------------------------------------------|
| **Real-time Updates**      |                                                |                                              |
| Order status changes       | WebSocket `trade_updates` channel             | Internal (automatic in `next()`)             |
| Position changes           | WebSocket `trade_updates` channel             | `self.position` updated automatically        |
| Account updates            | WebSocket `trade_updates` channel             | `self.equity` updated automatically          |
| Market data                | SIP WebSocket streams                         | `self.data.Close[-1]` etc. (bar-by-bar)     |
| **Callback Methods**       |                                                |                                              |
| Order filled               | WebSocket message handling                    | `Strategy.next()` sees updated trades        |
| Order rejected             | WebSocket message handling                    | ✗ (orders don't fail in backtesting)         |

---

## 6. Key Differences & Limitations

### Features Available in Alpaca but NOT in backtesting.py

| Feature                    | Alpaca                                         | backtesting.py Alternative                   |
|----------------------------|------------------------------------------------|----------------------------------------------|
| **Time-in-Force Options**  | IOC, FOK, OPG, CLS                            | ✗ Manual expiry via cancel after N bars     |
| **Extended Hours**         | 4:00am-9:30am, 4:00pm-8:00pm ET              | ✗ Not applicable                             |
| **Fractional Shares**      | Notional orders in USD                        | Size as percentage of equity ≈               |
| **Real-time Execution**    | Sub-second fills                              | ✗ Next-bar execution only                    |
| **Slippage/Commissions**   | Real market conditions                        | Must configure manually in `Backtest()`     |
| **Aged Order Policy**      | Orders auto-expire after 90 days             | ✗ Manual management required                 |

### Features Available in backtesting.py but NOT in Alpaca

| Feature                    | backtesting.py                                | Alpaca Alternative                           |
|----------------------------|-----------------------------------------------|----------------------------------------------|
| **Simultaneous Long/Short** | `hedging=True` allows both directions       | ✗ Must use separate account or ETFs         |
| **Infinite Buying Power**  | Default behavior                              | ✗ Limited by account equity                 |
| **Perfect Order Fills**    | Always fill at exact limit price when touched | Real market liquidity constraints            |
| **Vectorized Indicators**  | `self.I()` wrapper for efficient computation | Must calculate externally                    |

---

## 7. Migration Checklist

### From backtesting.py to Alpaca Live Trading

- [ ] **Replace order sizing logic**: Convert percentage-based sizing to absolute quantities
- [ ] **Add time-in-force parameters**: Specify `"day"` or `"gtc"` explicitly  
- [ ] **Handle order rejections**: Add error handling for insufficient buying power, invalid symbols
- [ ] **Implement position management**: Replace `self.position.close()` with explicit sell orders
- [ ] **Add commission/slippage**: Account for real trading costs
- [ ] **Handle partial fills**: Orders may not fill completely or immediately
- [ ] **Set up WebSocket listeners**: Replace `next()` callback with real-time event handling

### From Alpaca to backtesting.py Testing

- [ ] **Simplify order types**: Use basic market/limit/stop instead of advanced order classes
- [ ] **Remove time-in-force**: All orders become GTC automatically
- [ ] **Convert to percentage sizing**: Use `size=0.1` for 10% of equity instead of absolute quantities
- [ ] **Use synthetic positions**: Replace explicit position tracking with `self.position`
- [ ] **Implement manual trailing**: Replace `trailing_stop` orders with manual stop updates
- [ ] **Add indicator calculations**: Use `self.I()` wrapper for vectorized technical analysis

---

## 8. Common Patterns & Examples

### Pattern: Bracket Order with Trailing Stop

```python
# ═══════════════════════════════════════════════════════════════════════════
# Alpaca - Fixed bracket with 2% stop, 3% target
# ═══════════════════════════════════════════════════════════════════════════
entry_price = current_price
{
  "symbol": "AAPL",
  "side": "buy",
  "type": "market", 
  "qty": "100",
  "order_class": "bracket",
  "take_profit": {"limit_price": str(entry_price * 1.03)},
  "stop_loss": {"stop_price": str(entry_price * 0.98)}
}

# ═══════════════════════════════════════════════════════════════════════════  
# backtesting.py - Bracket with manual trailing (in Strategy class)
# ═══════════════════════════════════════════════════════════════════════════
def next(self):
    if not self.position and self.buy_signal:
        # Entry with initial stops
        self.buy(
            size=0.1,  # 10% of equity
            sl=self.data.Close[-1] * 0.98,  # 2% stop
            tp=self.data.Close[-1] * 1.03   # 3% target
        )
    
    # Trail the stop-loss  
    elif self.position.is_long:
        for trade in self.trades:
            new_stop = self.data.Close[-1] * 0.98
            if new_stop > trade.sl:  # Only move up
                trade.sl = new_stop
```

### Pattern: Risk Management - Max Daily Loss

```python
# ═══════════════════════════════════════════════════════════════════════════
# Alpaca - Check account P&L before placing orders
# ═══════════════════════════════════════════════════════════════════════════
account = api.get_account()
daily_pl = float(account.equity) - float(account.last_equity)
MAX_DAILY_LOSS = -500

if daily_pl > MAX_DAILY_LOSS:
    # OK to place new orders
    api.submit_order(...)
else:
    # Stop trading, close positions
    api.close_all_positions()

# ═══════════════════════════════════════════════════════════════════════════
# backtesting.py - Track P&L within strategy
# ═══════════════════════════════════════════════════════════════════════════
class RiskManagedStrategy(bt.Strategy):
    def __init__(self):
        self.daily_start_equity = 10000  # Track start of day
        self.MAX_DAILY_LOSS = 500
        
    def next(self):
        # Check daily P&L
        daily_pl = self.equity - self.daily_start_equity
        
        if daily_pl < -self.MAX_DAILY_LOSS:
            # Close all positions
            self.position.close()
            return  # Stop further trading
            
        # Normal strategy logic...
        if self.buy_signal:
            self.buy(size=0.1)
```

---

## References

- **Alpaca Trading API Documentation**: https://docs.alpaca.markets/docs/orders-at-alpaca
- **Alpaca API Reference**: https://docs.alpaca.markets/reference/postorder  
- **backtesting.py Documentation**: https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html
- **backtesting.py Examples**: https://kernc.github.io/backtesting.py/doc/examples/Quick%20Start%20User%20Guide.html 