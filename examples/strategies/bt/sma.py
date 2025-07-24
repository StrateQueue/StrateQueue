"""
BT SMA Crossover Strategy

SMA crossover strategy implemented using the bt library for testing bt engine integration.
This strategy uses a 1-day and 3-day simple moving average crossover approach.

Strategy Logic:
- When 1-day SMA > 3-day SMA: Long position (+1 target weight)
- When 1-day SMA <= 3-day SMA: Short position (-1 target weight)
- Uses WeighTarget algo to set target weights based on SMA crossover signals

This strategy is designed for engine integration testing to ensure the bt engine
works correctly with the StrateQueue framework.
"""

try:
    import bt
    import pandas as pd
except ImportError:
    raise ImportError(
        "bt and pandas libraries are required for this strategy. Install with: pip install bt pandas"
    )


class WeighTarget(bt.Algo):
    """
    Sets target weights based on a target weight DataFrame.
    
    Args:
        * target_weights (DataFrame): DataFrame containing the target weights
    
    Sets:
        * weights
    """
    
    def __init__(self, target_weights):
        self.tw = target_weights
    
    def __call__(self, target):
        # get target weights on date target.now
        if target.now in self.tw.index:
            w = self.tw.loc[target.now]
            
            # save in temp - this will be used by the weighing algo
            # also dropping any na's just in case they pop up
            target.temp['weights'] = w.dropna()
        
        # return True because we want to keep on moving down the stack
        return True


def create_sma_crossover_strategy(data):
    """
    Create an SMA crossover strategy using 1-day and 3-day moving averages.
    
    This strategy:
    - Calculates 1-day and 3-day simple moving averages
    - Goes long (+1) when 1-day SMA > 3-day SMA
    - Goes short (-1) when 1-day SMA <= 3-day SMA
    - Uses WeighTarget algo to set target weights
    
    Args:
        data (DataFrame): Price data for calculating SMAs
    
    Returns:
        bt.Strategy: Configured bt strategy object
    """
    
    # Calculate SMAs
    sma1 = data.rolling(1).mean()  # 1-day SMA (essentially current price)
    sma3 = data.rolling(3).mean()  # 3-day SMA
    
    # Calculate target weights based on SMA crossover
    # First copy the sma3 DataFrame since our weights will have the same structure
    tw = sma3.copy()
    
    # Set appropriate target weights
    tw[sma1 > sma3] = 1.0   # Long when 1-day SMA > 3-day SMA
    tw[sma1 <= sma3] = 0.0  # Close position when 1-day SMA <= 3-day SMA
    
    # Set weight to 0 where SMA3 is null (insufficient data)
    # This happens for the first 2 data points since SMA3 needs 3 points
    tw[sma3.isnull()] = 0.0
    
    # Define the SMA crossover strategy using bt's algo composition
    strategy = bt.Strategy(
        'SMA_Crossover_1_3',
        [
            # Use our custom WeighTarget algo with calculated target weights
            WeighTarget(tw),
            
            # Rebalance the portfolio based on the target weights
            bt.algos.Rebalance()
        ]
    )
    
    return strategy


class DynamicSMAStrategy(bt.Strategy):
    """
    Dynamic SMA crossover strategy that calculates weights on-the-fly.
    
    This strategy calculates 1-day vs 3-day SMA crossover signals dynamically
    during the backtest execution, rather than pre-calculating weights.
    """
    
    def __init__(self, name='SMA_Crossover_1_3'):
        # Create algos that will calculate SMA crossover dynamically
        algos = [
            SMAWeightCalculator(),  # Custom algo to calculate weights dynamically
            bt.algos.Rebalance()
        ]
        super().__init__(name, algos)
    
    def get_lookback_period(self):
        """Return the minimum lookback period needed for this strategy"""
        # For 1-day vs 3-day SMA crossover, we need at least 3 bars
        return 3


class SMAWeightCalculator(bt.Algo):
    """
    Algo that calculates SMA crossover weights dynamically during backtest.
    """
    
    def __call__(self, target):
        # Get the current data up to target.now
        data = target.universe
        
        if data is None or data.empty:
            return True
            
        # For SMA crossover, we only need Close prices
        if 'Close' not in data.columns:
            return True
            
        close_data = data['Close']
        
        # Calculate SMAs for Close prices only
        sma1 = close_data.rolling(1).mean()  # 1-day SMA
        sma3 = close_data.rolling(3).mean()  # 3-day SMA
        
        # Get current date weights
        current_date = target.now
        if current_date not in sma1.index or current_date not in sma3.index:
            return True
            
        current_sma1 = sma1.loc[current_date]
        current_sma3 = sma3.loc[current_date]
        
        # Calculate weight for the security based on Close price SMA crossover
        if pd.isna(current_sma3):
            # Insufficient data for 3-day SMA
            weight = 0.0
        elif current_sma1 > current_sma3:
            # Long signal
            weight = 1.0
        else:
            # Short signal  
            weight = -1.0
        
        # Set weights for Close column only (this represents the security)
        weights = {'Close': weight}
        
        # Set weights in target temp for Rebalance algo
        target.temp['weights'] = pd.Series(weights)
        
        return True


def create_default_strategy():
    """
    Create a default SMA strategy for engine discovery.
    
    Returns:
        bt.Strategy: Configured bt strategy object
    """
    return DynamicSMAStrategy()


# Create the strategy instance for the engine to discover
sma_strategy = create_default_strategy()

# Mark this module as containing a bt strategy for engine detection
__bt_strategy__ = True