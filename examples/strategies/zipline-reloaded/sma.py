"""
Simple Moving Average (SMA) Crossover Strategy for Zipline-Reloaded

This strategy uses a very short-term crossover between 1-period and 3-period 
moving averages. When the 1-period MA (essentially current price) crosses above 
the 3-period MA, we go long. When it crosses below, we exit.

This is designed for high-frequency trading on 1-minute timeframes.
"""

from zipline.api import order_target_percent, record, symbol


def initialize(context):
    """
    Called once at the start of the algorithm.
    """
    context.asset = symbol('AAVE')
    context.short_window = 1  # 1-period moving average (current price)
    context.long_window = 3   # 3-period moving average
    
    # Track position state
    context.invested = False


def handle_data(context, data):
    """
    Called every minute during market hours.
    """
    # Skip first few bars to get full windows
    if context.long_window > len(data.history(context.asset, 'price', context.long_window, '1m')):
        return

    # Get current price and short MA (1-period is just current price)
    current_price = data.current(context.asset, 'price')
    
    # Get 3-period moving average
    long_mavg = data.history(
        context.asset, 'price', bar_count=context.long_window, frequency="1m"
    ).mean()

    # Trading logic: Buy when current price > 3-period MA, sell when below
    if current_price > long_mavg and not context.invested:
        # Go long with 95% of portfolio
        order_target_percent(context.asset, 0.95)
        context.invested = True
        
    elif current_price < long_mavg and context.invested:
        # Exit position
        order_target_percent(context.asset, 0.0)
        context.invested = False

    # Record values for analysis
    record(
        AAVE=current_price,
        current_price=current_price,
        sma_3=long_mavg,
        invested=context.invested
    )


# Mark this as a Zipline strategy for StrateQueue detection
__zipline_strategy__ = True 