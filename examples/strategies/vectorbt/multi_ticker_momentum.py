"""
VectorBT Multi-Ticker Momentum Strategy

A momentum strategy that works across multiple symbols simultaneously,
leveraging VectorBT's vectorized capabilities for efficient processing.

This strategy:
1. Calculates RSI for all symbols at once
2. Generates cross-sectional momentum signals
3. Returns per-symbol entry/exit signals

Data Format Expected:
- MultiIndex DataFrame with (OHLCV_field, symbol) columns
- Example: ('Close', 'AAPL'), ('Close', 'MSFT'), ('High', 'AAPL'), etc.
"""

import pandas as pd
import numpy as np

# Strategy parameters
RSI_PERIOD = 14
OVERSOLD_THRESHOLD = 30
OVERBOUGHT_THRESHOLD = 70
MOMENTUM_LOOKBACK = 5


def multi_ticker_momentum_strategy(data, rsi_period=RSI_PERIOD, 
                                 oversold=OVERSOLD_THRESHOLD, 
                                 overbought=OVERBOUGHT_THRESHOLD,
                                 momentum_lookback=MOMENTUM_LOOKBACK):
    """
    Multi-ticker momentum strategy using VectorBT's vectorized operations
    
    Args:
        data: MultiIndex DataFrame with columns like ('Close', 'AAPL'), ('Close', 'MSFT'), etc.
        rsi_period: Period for RSI calculation
        oversold: RSI oversold threshold
        overbought: RSI overbought threshold
        momentum_lookback: Lookback period for momentum calculation
        
    Returns:
        tuple: (entries, exits) as DataFrames with symbol columns
    """
    try:
        import vectorbt as vbt
    except ImportError:
        # Fallback to pandas-only implementation for testing
        return _pandas_multi_ticker_momentum(data, rsi_period, oversold, overbought, momentum_lookback)
    
    # Extract close prices for all symbols
    close_prices = data['Close']  # This will be a DataFrame with symbol columns
    
    # Calculate RSI for all symbols simultaneously using VectorBT
    rsi_all = vbt.RSI.run(close_prices, window=rsi_period).rsi
    
    # Calculate momentum for all symbols
    momentum_all = close_prices.pct_change(momentum_lookback)
    
    # Cross-sectional momentum: rank symbols by momentum each period
    momentum_rank = momentum_all.rank(axis=1, pct=True)
    
    # Entry conditions (vectorized across all symbols):
    # 1. RSI is oversold AND symbol is in top 30% momentum performers
    entries = (rsi_all < oversold) & (momentum_rank > 0.7)
    
    # Exit conditions (vectorized across all symbols):
    # 1. RSI is overbought OR symbol drops to bottom 30% momentum performers
    exits = (rsi_all > overbought) | (momentum_rank < 0.3)
    
    return entries, exits


def _pandas_multi_ticker_momentum(data, rsi_period, oversold, overbought, momentum_lookback):
    """Pandas-only fallback implementation for testing without VectorBT"""
    close_prices = data['Close']
    
    # Simple RSI calculation using pandas
    def calculate_rsi_pandas(prices, window):
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    # Calculate RSI for all symbols
    rsi_all = close_prices.apply(lambda col: calculate_rsi_pandas(col, rsi_period))
    
    # Calculate momentum for all symbols
    momentum_all = close_prices.pct_change(momentum_lookback)
    
    # Cross-sectional momentum ranking
    momentum_rank = momentum_all.rank(axis=1, pct=True)
    
    # Entry and exit conditions
    entries = (rsi_all < oversold) & (momentum_rank > 0.7)
    exits = (rsi_all > overbought) | (momentum_rank < 0.3)
    
    return entries, exits


# Mark this as a VectorBT strategy for auto-detection
multi_ticker_momentum_strategy.__vbt_strategy__ = True


class MultiTickerMomentumStrategy:
    """Class-based multi-ticker momentum strategy"""
    
    def __init__(self, rsi_period=RSI_PERIOD, oversold=OVERSOLD_THRESHOLD, 
                 overbought=OVERBOUGHT_THRESHOLD, momentum_lookback=MOMENTUM_LOOKBACK):
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.momentum_lookback = momentum_lookback
    
    def run(self, data):
        """Run the multi-ticker momentum strategy"""
        return multi_ticker_momentum_strategy(
            data, 
            self.rsi_period, 
            self.oversold, 
            self.overbought,
            self.momentum_lookback
        )


# Usage Example:
"""
To use this strategy with multiple symbols:

from StrateQueue.engines.vectorbt_engine import VectorBTEngine

engine = VectorBTEngine()
strategy = engine.load_strategy_from_file('multi_ticker_momentum.py')

# Create multi-ticker extractor for multiple symbols
symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA']
extractor = engine.create_multi_ticker_signal_extractor(strategy, symbols)

# Process multiple symbols at once
symbol_data = {
    'AAPL': aapl_dataframe,    # Standard OHLCV DataFrame
    'MSFT': msft_dataframe,    # Standard OHLCV DataFrame
    'GOOGL': googl_dataframe,  # Standard OHLCV DataFrame
    'TSLA': tsla_dataframe     # Standard OHLCV DataFrame
}

# Get signals for all symbols in one vectorized operation
signals = extractor.extract_signals(symbol_data)
# Returns: {'AAPL': TradingSignal, 'MSFT': TradingSignal, ...}
""" 