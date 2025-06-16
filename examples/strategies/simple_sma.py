"""
Simple SMA Live Trading Strategy

A basic moving average crossover strategy designed for live trading.
This strategy generates buy/sell/hold signals based on SMA crossovers.
"""

from typing import Optional, Dict, Any
import pandas as pd
import numpy as np

from StrateQueue.core.signal_extractor import SignalType, SignalExtractorStrategy


class SimpleSMA(SignalExtractorStrategy):
    """
    Simple Moving Average crossover strategy for live trading.
    
    Generates signals when a fast SMA crosses above/below a slow SMA.
    """
    
    # Strategy parameters
    fast_period = 5
    slow_period = 20
    
    def init(self):
        """Initialize the strategy indicators"""
        from backtesting.test import SMA
        
        close = self.data.Close
        self.fast_sma = self.I(SMA, close, self.fast_period)
        self.slow_sma = self.I(SMA, close, self.slow_period)
        
    def next(self):
        """Generate trading signal based on SMA crossover"""
        from backtesting.lib import crossover
        
        # Update indicator values for signal output
        self.indicators_values = {
            f'SMA_{self.fast_period}': self.fast_sma[-1],
            f'SMA_{self.slow_period}': self.slow_sma[-1],
            'price': self.data.Close[-1]
        }
        
        # Check for crossover signals
        if crossover(self.fast_sma, self.slow_sma):
            # Fast SMA crosses above slow SMA - bullish signal
            confidence = abs(self.fast_sma[-1] - self.slow_sma[-1]) / self.slow_sma[-1]
            self.set_signal(SignalType.BUY, confidence=min(confidence * 10, 1.0))
            
        elif crossover(self.slow_sma, self.fast_sma):
            # Fast SMA crosses below slow SMA - bearish signal  
            confidence = abs(self.fast_sma[-1] - self.slow_sma[-1]) / self.slow_sma[-1]
            self.set_signal(SignalType.SELL, confidence=min(confidence * 10, 1.0))
            
        else:
            # No crossover - hold current position
            self.set_signal(SignalType.HOLD, confidence=0.1)
    
    def get_strategy_info(self) -> dict:
        """Get strategy information"""
        return {
            "name": "SimpleSMA",
            "type": "Moving Average Crossover",
            "fast_period": self.fast_period,
            "slow_period": self.slow_period,
            "description": f"SMA({self.fast_period}) x SMA({self.slow_period}) crossover strategy"
        } 