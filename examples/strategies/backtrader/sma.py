"""
Simple Moving Average Crossover Strategy for Backtrader

This strategy generates BUY signals when the fast SMA crosses above the slow SMA,
and SELL signals when the fast SMA crosses below the slow SMA.
"""

import backtrader as bt


class SMAStrategy(bt.Strategy):
    """Simple Moving Average Crossover Strategy"""
    
    params = (
        ('fast_period', 10),
        ('slow_period', 20),
    )
    
    def __init__(self):
        # Create the moving averages
        self.fast_sma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.fast_period
        )
        self.slow_sma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.slow_period
        )
        
        # Create crossover signal
        self.crossover = bt.indicators.CrossOver(self.fast_sma, self.slow_sma)
    
    def next(self):
        # Check for crossover signals
        if self.crossover > 0:  # Fast SMA crosses above slow SMA
            self.buy()
        elif self.crossover < 0:  # Fast SMA crosses below slow SMA
            self.sell()


# Example usage with Backtrader directly (for testing)
if __name__ == "__main__":
    import datetime
    
    print("Testing SMACrossover Strategy...")
    
    cerebro = bt.Cerebro()
    cerebro.addstrategy(SMAStrategy)
    
    # Add some dummy data for testing
    # In real usage, this would be replaced with actual crypto data
    data = bt.feeds.YahooFinanceData(
        dataname='BTC-USD',
        fromdate=datetime.datetime(2023, 1, 1),
        todate=datetime.datetime(2023, 12, 31)
    )
    cerebro.adddata(data)
    
    # Set initial cash and commission
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.001)  # 0.1% commission
    
    print(f'Starting Portfolio Value: ${cerebro.broker.getvalue():.2f}')
    cerebro.run()
    print(f'Final Portfolio Value: ${cerebro.broker.getvalue():.2f}') 