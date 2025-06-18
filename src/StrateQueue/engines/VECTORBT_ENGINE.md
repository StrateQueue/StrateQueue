# VectorBT Engine

The VectorBT engine integrates the high-performance [VectorBT](https://vectorbt.pro/) library with StrateQueue, enabling fast vectorized backtesting and signal generation using Numba-accelerated computations.

## Overview

VectorBT is a Python library for quantitative analysis, particularly backtesting trading strategies. It leverages NumPy, Pandas, and Numba to achieve high performance through vectorized operations and JIT compilation.

### Key Features

- **High Performance**: Numba-accelerated computations run at near C speed
- **Vectorized Operations**: Process multiple strategy variants simultaneously  
- **Memory Efficient**: Optimized data structures and broadcasting
- **Rich Analysis**: Built-in portfolio metrics and visualization tools
- **Flexible Architecture**: Supports both function and class-based strategies

## Installation

```bash
pip3.10 install vectorbt>=0.25.0 numba>=0.58.0
```

**Note**: VectorBT has many dependencies. If you encounter import issues (especially with telegram dependencies), try:

```bash
pip3.10 install "vectorbt==0.25.4"  # Stable version
```

## Strategy Format

VectorBT strategies in StrateQueue should return a tuple of `(entries, exits)` as boolean pandas Series.

### Function-based Strategy

```python
import pandas as pd
import vectorbt as vbt

def sma_crossover(data: pd.DataFrame, fast_period: int = 5, slow_period: int = 20):
    """
    Simple Moving Average Crossover Strategy
    
    Args:
        data: DataFrame with OHLCV columns
        fast_period: Fast MA period
        slow_period: Slow MA period
        
    Returns:
        tuple: (entries, exits) as boolean Series
    """
    close = data['Close']
    
    # Calculate moving averages
    fast_ma = vbt.MA.run(close, fast_period).ma
    slow_ma = vbt.MA.run(close, slow_period).ma
    
    # Generate signals
    entries = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
    exits = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))
    
    return entries, exits
```

### Class-based Strategy

```python
class VectorBTStrategy:
    """Class-based VectorBT strategy"""
    __vbt_strategy__ = True  # Mark as VectorBT strategy
    
    def __init__(self, rsi_period: int = 14, ma_period: int = 20):
        self.rsi_period = rsi_period
        self.ma_period = ma_period
    
    @staticmethod
    def run(data: pd.DataFrame, rsi_period: int = 14, ma_period: int = 20):
        close = data['Close']
        
        rsi = vbt.RSI.run(close, rsi_period).rsi
        ma = vbt.MA.run(close, ma_period).ma
        
        entries = (rsi > 70) & (close > ma)
        exits = (rsi < 30) & (close < ma)
        
        return entries, exits
    
    def __call__(self, data: pd.DataFrame):
        return self.run(data, self.rsi_period, self.ma_period)
```

## Usage

### Command Line

```bash
# Explicit engine specification
python3.10 main.py deploy \
    --engine vectorbt \
    --strategy examples/strategies/vbt_sma.py \
    --symbol AAPL \
    --granularity 1m \
    --allocation 0.1 \
    --data-source demo

# Auto-detection (if strategy has VectorBT imports)
python3.10 main.py deploy \
    --strategy examples/strategies/vbt_sma.py \
    --symbol BTC-USD \
    --granularity 5m \
    --allocation 0.2 \
    --data-source demo
```

### Programmatic

```python
from StrateQueue.engines.engine_factory import EngineFactory

# Create VectorBT engine
engine = EngineFactory.create_engine('vectorbt')

# Load strategy
strategy = engine.load_strategy_from_file('my_vbt_strategy.py')

# Create signal extractor
extractor = engine.create_signal_extractor(strategy)

# Extract signals from historical data
signal = extractor.extract_signal(historical_data)
print(f"Signal: {signal.signal.value}")
```

## Signal Extraction

The VectorBT engine extracts signals by:

1. **Strategy Execution**: Calls your strategy function with historical data
2. **Portfolio Simulation**: Runs a minimal VectorBT portfolio simulation
3. **Position Analysis**: Determines current position from portfolio state
4. **Signal Translation**: Converts position to StrateQueue signal format

```python
# Position -> Signal mapping
if position > 0:    signal = SignalType.BUY
elif position < 0:  signal = SignalType.SELL  
else:               signal = SignalType.HOLD
```

## Engine Detection

StrateQueue automatically detects VectorBT strategies by looking for:

- `import vectorbt` or `from vectorbt import ...`
- `.vbt.` accessor usage
- `vbt.*.run(...)` method calls
- `Portfolio.from_signals(...)` usage
- `__vbt_strategy__` class attribute
- Functions with `data` parameter returning tuples

## Performance Notes

### Vectorization Benefits

VectorBT's main advantage is processing multiple strategy variants simultaneously:

```python
# Test multiple parameter combinations efficiently
fast_periods = [5, 10, 15]
slow_periods = [20, 30, 40]

# VectorBT broadcasts these automatically
pf = vbt.Portfolio.from_signals(
    close=data['Close'],
    entries=generate_entries(data, fast_periods, slow_periods),
    exits=generate_exits(data, fast_periods, slow_periods)
)
# Returns 3x3=9 strategy results in single operation
```

### Numba Acceleration

VectorBT uses Numba JIT compilation for custom indicators:

```python
from numba import njit

@njit
def custom_indicator(price_array, window):
    # This runs at C speed
    result = np.empty_like(price_array)
    for i in range(len(price_array)):
        # Custom calculation
        result[i] = np.mean(price_array[max(0, i-window):i+1])
    return result
```

## Examples

See `examples/strategies/vbt_sma.py` for a complete working example with multiple strategy implementations.

## Troubleshooting

### Import Errors

If you get telegram/dependency errors:
```bash
pip3.10 uninstall vectorbt -y
pip3.10 install "vectorbt==0.25.4"
```

### Memory Issues

For large datasets, use VectorBT's chunking:
```python
# Process data in chunks
pf = vbt.Portfolio.from_signals(
    close=data['Close'],
    entries=entries,
    exits=exits,
    freq='1min',
    chunked=True  # Enable chunking
)
```

### Performance Optimization

1. **Minimize Data Copying**: Work with views when possible
2. **Use Built-in Indicators**: VectorBT's indicators are highly optimized
3. **Batch Operations**: Process multiple timeframes/symbols together
4. **Cache Results**: Store intermediate calculations

## Integration with StrateQueue

The VectorBT engine integrates seamlessly with StrateQueue's architecture:

- **Live Trading**: Signals are extracted in real-time from streaming data
- **Multi-Strategy**: Multiple VectorBT strategies can run concurrently  
- **Portfolio Management**: Strategy signals feed into StrateQueue's portfolio system
- **Risk Management**: Stop-losses and position sizing are handled by StrateQueue
- **Monitoring**: Performance metrics are tracked and visualized

For more information, see the [VectorBT documentation](https://vectorbt.pro/documentation/) and [StrateQueue documentation](../../README.md). 