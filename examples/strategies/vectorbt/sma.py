"""
VectorBT SMA Crossover Strategy

A simple moving average crossover strategy implemented using VectorBT.
This strategy generates buy signals when a fast SMA crosses above a slow SMA,
and sell signals when the fast SMA crosses below the slow SMA.
"""

import pandas as pd
import numpy as np

# Strategy parameters
FAST_PERIOD = 1
SLOW_PERIOD = 3

def sma_crossover_strategy(data, fast_period=FAST_PERIOD, slow_period=SLOW_PERIOD):
    """
    VectorBT SMA Crossover Strategy
    
    Args:
        data: DataFrame with OHLCV data
        fast_period: Period for fast moving average
        slow_period: Period for slow moving average
        
    Returns:
        tuple: (entries, exits) as pandas Series
    """
    # Import vectorbt
    try:
        import vectorbt as vbt
    except ImportError:
        raise ImportError("VectorBT is required for this strategy. Install with: pip install vectorbt")
    
    # Calculate moving averages
    close = data['Close']
    fast_ma = vbt.MA.run(close, fast_period).ma
    slow_ma = vbt.MA.run(close, slow_period).ma
    
    # Generate crossover signals using plain Pandas logic
    # Entry: fast MA crosses above slow MA
    entries = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
    
    # Exit: fast MA crosses below slow MA
    exits  = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))
    
    return entries, exits


# Mark this as a VectorBT strategy for auto-detection
sma_crossover_strategy.__vbt_strategy__ = True

# Alternative class-based approach
class SMACrossoverStrategy:
    """Class-based SMA Crossover Strategy for VectorBT"""
    
    def __init__(self, fast_period=FAST_PERIOD, slow_period=SLOW_PERIOD):
        self.fast_period = fast_period
        self.slow_period = slow_period
    
    def run(self, data):
        """Run the strategy on the given data"""
        return sma_crossover_strategy(data, self.fast_period, self.slow_period)
