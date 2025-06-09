# Limit Orders in Your Live Trading System

## Overview

Your live trading system currently uses **market orders** that execute immediately. However, I've extended it to support **limit orders**, which offer more precise control over execution prices.

## Market Orders vs Limit Orders

### Market Orders (Current System)
- **Execute immediately** at the current market price
- **Guaranteed execution** but unpredictable price
- Best for: When you need immediate execution and don't care about small price differences

### Limit Orders (New Enhancement)
- **Execute only at your specified price or better**
- **Predictable price** but no guarantee of execution
- Best for: When you want to control your entry/exit price precisely

## How Limit Orders Work in Your System

### 1. Signal Generation
Your strategies can now generate limit order signals by using the new signal types:
- `SignalType.LIMIT_BUY` - Buy at specified limit price or lower
- `SignalType.LIMIT_SELL` - Sell at specified limit price or higher

### 2. Order Execution Flow
```
Strategy Signal → Signal Extractor → Alpaca Executor → Alpaca API → Market
```

**For Limit Orders:**
1. Strategy calculates desired limit price
2. Signal includes both `signal_type` and `limit_price`
3. Alpaca Executor creates `LimitOrderRequest` instead of `MarketOrderRequest`
4. Order waits in the order book until market price reaches your limit

### 3. Practical Example

```python
# Market Order (current)
current_price = 100.00
# Order executes immediately at ~$100.00 (could be $99.95 or $100.05)

# Limit Order (new)
limit_price = 99.50  # Buy only if price drops to $99.50 or lower
# Order waits until price reaches $99.50, then executes
# If price never drops to $99.50, order never executes
```

## Example Strategy Implementation

Here's how to create a strategy that uses limit orders:

```python
class LimitOrderStrategy(SignalExtractorStrategy):
    def next(self):
        current_price = self.data.Close[-1]
        
        # Bullish signal with limit order
        if some_bullish_condition:
            # Set buy limit 1% below current price
            limit_price = current_price * 0.99
            self.set_limit_buy_signal(
                limit_price=limit_price,
                size=0.1,  # 10% of portfolio
                confidence=0.8
            )
        
        # Bearish signal with limit order  
        elif some_bearish_condition:
            # Set sell limit 1% above current price
            limit_price = current_price * 1.01
            self.set_limit_sell_signal(
                limit_price=limit_price,
                size=0.1,  # 10% of portfolio
                confidence=0.8
            )
```

## Advantages of Limit Orders

### 1. **Price Control**
- Set exact maximum buy price or minimum sell price
- Avoid overpaying in volatile markets
- Get better entries during price dips

### 2. **Risk Management**
- Prevent bad fills from market spikes
- More predictable position sizing
- Better cost basis for long-term holdings

### 3. **Strategic Patience**
- Wait for favorable prices rather than chasing
- Catch pullbacks in trending markets
- Scale into positions gradually

## Disadvantages of Limit Orders

### 1. **Execution Risk**
- May never fill if price doesn't reach your limit
- Could miss opportunities in fast-moving markets
- Partial fills possible

### 2. **Timing Issues**
- May fill at worst possible moments (market crashes)
- Requires more monitoring and management
- Can create stale orders in changing conditions

## Best Practices for Your System

### 1. **Choose Appropriate Offset**
```python
# Conservative (higher fill probability)
limit_price = current_price * 0.995  # 0.5% offset

# Aggressive (better price, lower fill probability)  
limit_price = current_price * 0.98   # 2% offset
```

### 2. **Time Management**
- Use `TimeInForce.DAY` for short-term signals
- Use `TimeInForce.GTC` for longer-term targets
- Consider order expiry in volatile markets

### 3. **Monitoring**
- Check order status regularly
- Cancel stale orders when conditions change
- Adjust limits based on market conditions

## Running Limit Order Strategies

To use the new limit order functionality:

1. **Create a limit order strategy** (see `examples/strategies/limit_order_sma.py`)

2. **Run the system** with your new strategy:
```bash
python3.10 main.py --strategy examples/strategies/limit_order_sma.py --symbols AAPL --enable-trading
```

3. **Monitor execution** in the logs:
```
✅ LIMIT BUY order placed for AAPL: Notional=$1000.00, Limit=$99.50, Order ID: abc123
```

## Technical Implementation Details

### New Signal Types
- `LIMIT_BUY`: Places buy limit order
- `LIMIT_SELL`: Places sell limit order

### Enhanced TradingSignal
```python
@dataclass
class TradingSignal:
    signal: SignalType
    confidence: float
    price: float
    timestamp: pd.Timestamp
    indicators: Dict[str, float]
    metadata: Dict[str, Any] = None
    size: Optional[float] = None
    limit_price: Optional[float] = None  # NEW: For limit orders
```

### New Executor Methods
- `_execute_limit_buy()`: Handles limit buy orders
- `_execute_limit_sell()`: Handles limit sell orders

## Order Status Monitoring

Limit orders have different lifecycle states:
- **NEW**: Order submitted to exchange
- **PENDING**: Waiting for price to reach limit
- **PARTIALLY_FILLED**: Some shares filled
- **FILLED**: Completely executed
- **CANCELED**: Order canceled
- **EXPIRED**: Order expired

## Conclusion

Limit orders add sophisticated price control to your trading system while maintaining the same strategy development pattern. They're particularly valuable for:

- **Volatile markets** where price precision matters
- **Larger position sizes** where market impact is a concern  
- **Patient strategies** that can wait for better prices
- **Risk management** to avoid bad fills

The implementation integrates seamlessly with your existing infrastructure - you just need to use the new signal types and specify limit prices in your strategies. 