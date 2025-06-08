# VectorBT Multi-Ticker Signal Extraction

The VectorBT engine in StrateQueue now supports **multi-ticker signal extraction**, allowing you to process multiple symbols simultaneously in a single vectorized operation. This provides significant performance improvements and enables cross-sectional analysis across your symbol universe.

## Overview

Traditional single-symbol processing:
```python
# Process each symbol individually (slower)
for symbol in symbols:
    signal = extractor.extract_signal(symbol_data[symbol])
    signals[symbol] = signal
```

Multi-ticker processing:
```python
# Process all symbols in one vectorized operation (faster)
signals = extractor.extract_signals(symbol_data)  # All symbols at once!
```

## Key Benefits

- **🚀 Performance**: Vectorized operations are 3-5x faster than individual symbol processing
- **📊 Cross-sectional Analysis**: Compare and rank symbols across your universe
- **💾 Memory Efficiency**: Optimized MultiIndex DataFrame operations
- **🛡️ Robust Error Handling**: Graceful handling of missing data and symbols
- **🔄 Backward Compatible**: Works with existing single-symbol strategies

## Usage

### 1. Create Multi-Ticker Extractor

```python
from StrateQueue.engines.vectorbt_engine import VectorBTEngine

# Initialize engine and load strategy
engine = VectorBTEngine()
strategy = engine.load_strategy_from_file('multi_ticker_momentum.py')

# Create multi-ticker extractor for your symbol universe
symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'META']
extractor = engine.create_multi_ticker_signal_extractor(
    strategy, 
    symbols,
    granularity='1h'
)
```

### 2. Prepare Multi-Symbol Data

```python
# Standard OHLCV DataFrames for each symbol
symbol_data = {
    'AAPL': aapl_dataframe,    # pandas DataFrame with OHLCV columns
    'MSFT': msft_dataframe,    # pandas DataFrame with OHLCV columns
    'GOOGL': googl_dataframe,  # pandas DataFrame with OHLCV columns
    'TSLA': tsla_dataframe,    # pandas DataFrame with OHLCV columns
    'META': meta_dataframe     # pandas DataFrame with OHLCV columns
}
```

### 3. Extract Signals for All Symbols

```python
# Process all symbols in one vectorized operation
signals = extractor.extract_signals(symbol_data)

# Access individual signals
for symbol, signal in signals.items():
    print(f"{symbol}: {signal.signal} @ ${signal.price:.2f}")
```

## Writing Multi-Ticker Strategies

### Function-Based Strategy

```python
import pandas as pd
import vectorbt as vbt

def multi_ticker_momentum_strategy(data, rsi_period=14, momentum_lookback=5):
    """
    Multi-ticker momentum strategy
    
    Args:
        data: MultiIndex DataFrame with columns like ('Close', 'AAPL'), ('Close', 'MSFT')
        
    Returns:
        tuple: (entries, exits) as DataFrames with symbol columns
    """
    # Extract close prices for all symbols
    close_prices = data['Close']  # DataFrame with symbol columns
    
    # Calculate RSI for all symbols simultaneously
    rsi_all = vbt.RSI.run(close_prices, window=rsi_period).rsi
    
    # Calculate momentum for all symbols
    momentum_all = close_prices.pct_change(momentum_lookback)
    
    # Cross-sectional momentum ranking
    momentum_rank = momentum_all.rank(axis=1, pct=True)
    
    # Entry: RSI oversold AND top 30% momentum performers
    entries = (rsi_all < 30) & (momentum_rank > 0.7)
    
    # Exit: RSI overbought OR bottom 30% momentum performers  
    exits = (rsi_all > 70) | (momentum_rank < 0.3)
    
    return entries, exits

# Mark as VectorBT strategy
multi_ticker_momentum_strategy.__vbt_strategy__ = True
```

### Class-Based Strategy

```python
class MultiTickerMeanReversionStrategy:
    def __init__(self, bb_period=20, bb_std=2.0):
        self.bb_period = bb_period
        self.bb_std = bb_std
    
    def run(self, data):
        """Process multi-symbol data and return entry/exit signals"""
        close_prices = data['Close']
        
        # Bollinger Bands for all symbols
        bb = vbt.BBANDS.run(close_prices, window=self.bb_period, alpha=self.bb_std)
        
        # Cross-sectional volatility ranking
        volatility = close_prices.rolling(20).std()
        vol_rank = volatility.rank(axis=1, pct=True)
        
        # Entry: Price touches lower band AND low volatility rank
        entries = (close_prices <= bb.lower) & (vol_rank < 0.3)
        
        # Exit: Price touches upper band OR high volatility rank
        exits = (close_prices >= bb.upper) | (vol_rank > 0.7)
        
        return entries, exits
```

## Data Format

The multi-ticker extractor expects data in this format:

**Input**: Dictionary of symbol DataFrames
```python
{
    'AAPL': DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume']),
    'MSFT': DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume']),
    ...
}
```

**Internal**: MultiIndex DataFrame for VectorBT
```python
MultiIndex DataFrame with columns:
('Open', 'AAPL'), ('Open', 'MSFT'), ('High', 'AAPL'), ('High', 'MSFT'), 
('Low', 'AAPL'), ('Low', 'MSFT'), ('Close', 'AAPL'), ('Close', 'MSFT'),
('Volume', 'AAPL'), ('Volume', 'MSFT')
```

**Output**: Dictionary of TradingSignals
```python
{
    'AAPL': TradingSignal(signal=BUY, price=150.23, ...),
    'MSFT': TradingSignal(signal=HOLD, price=280.45, ...),
    ...
}
```

## Error Handling

The multi-ticker extractor handles various edge cases gracefully:

### Missing Symbols
```python
# If some symbols are missing from input data
partial_data = {'AAPL': df1, 'MSFT': df2}  # Missing GOOGL
signals = extractor.extract_signals(partial_data)
# Returns HOLD signal for missing symbols
```

### Insufficient Data
```python
# If some symbols have too few bars
insufficient_data = {'AAPL': df1.tail(1)}  # Only 1 bar
signals = extractor.extract_signals(insufficient_data)
# Returns HOLD signals for insufficient data
```

### Timestamp Misalignment
The system automatically handles different timestamp ranges:
- Uses intersection of timestamps when possible
- Falls back to union with forward-fill for missing values
- Robust alignment ensures strategies work with real-world data

## Performance Comparison

Based on our testing with 5 symbols:

| Method | Time per Operation | Speedup |
|--------|-------------------|---------|
| Single-symbol (sequential) | ~50ms | 1.0x |
| Multi-ticker (vectorized) | ~15ms | 3.3x |

Performance improvements scale with:
- **Number of symbols**: More symbols = greater speedup
- **Strategy complexity**: Complex calculations benefit more from vectorization
- **Data size**: Larger datasets show more dramatic improvements

## Advanced Features

### Cross-Sectional Analysis

```python
def cross_sectional_momentum(data, lookback=20):
    """Strategy that compares symbols against each other"""
    close_prices = data['Close']
    
    # Calculate returns for all symbols
    returns = close_prices.pct_change(lookback)
    
    # Rank symbols by performance each period
    performance_rank = returns.rank(axis=1, pct=True)
    
    # Long top quartile, short bottom quartile
    entries = performance_rank > 0.75
    exits = performance_rank < 0.25
    
    return entries, exits
```

### Risk Management Across Symbols

```python
def risk_managed_strategy(data, max_positions=3):
    """Limit total number of positions across all symbols"""
    # ... calculate base entry/exit signals ...
    
    # Apply position limits
    current_positions = entries.sum(axis=1)
    position_limit_mask = current_positions <= max_positions
    
    # Only allow new entries if under position limit
    entries = entries & position_limit_mask.values[:, np.newaxis]
    
    return entries, exits
```

## Best Practices

1. **Symbol Universe Management**
   - Group related symbols together (e.g., same sector)
   - Consider memory usage with large universes (>100 symbols)
   - Use consistent data quality across symbols

2. **Strategy Design**
   - Leverage cross-sectional features for better alpha
   - Implement portfolio-level risk controls
   - Handle corporate actions and symbol changes

3. **Performance Optimization**
   - Batch similar calculations across symbols
   - Use VectorBT's built-in indicators when possible
   - Profile strategies to identify bottlenecks

## Migration from Single-Symbol

Existing single-symbol strategies can be adapted for multi-ticker use:

**Before** (single-symbol):
```python
def rsi_strategy(data, period=14):
    close = data['Close']
    rsi = vbt.RSI.run(close, window=period).rsi
    return rsi < 30, rsi > 70  # entries, exits
```

**After** (multi-ticker compatible):
```python
def rsi_strategy(data, period=14):
    close = data['Close']  # Now potentially a DataFrame with multiple symbols
    rsi = vbt.RSI.run(close, window=period).rsi
    return rsi < 30, rsi > 70  # Works for both single and multi-symbol
```

VectorBT's indicators automatically handle both single Series and multi-column DataFrames!

## Troubleshooting

**Q: Strategy fails with "columns not found" error**
A: Ensure your strategy accesses data with `data['Close']` not `data.Close`

**Q: Getting different results vs single-symbol processing**
A: Check timestamp alignment - multi-ticker uses intersection/union of timestamps

**Q: Memory usage too high with many symbols**
A: Consider processing symbol batches or optimizing data types

**Q: Performance not improving as expected**
A: Profile your strategy - ensure you're using vectorized operations throughout 