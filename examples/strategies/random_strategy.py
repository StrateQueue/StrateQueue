from backtesting import Backtest, Strategy
import random


class RandomStrategy(Strategy):
    """
    A random trading strategy for testing the live trading system.
    This strategy makes random buy/sell/hold decisions.
    """
    
    # Strategy parameters
    buy_probability = 0.15      # 15% chance to buy
    sell_probability = 0.15     # 15% chance to sell  
    hold_probability = 0.70     # 70% chance to hold
    
    def init(self):
        """Initialize the strategy - no indicators needed for random strategy"""
        pass
    
    def next(self):
        """Make a random trading decision"""
        
        # Generate a random number to determine action
        decision = random.random()
        
        if decision < self.buy_probability:
            # Buy signal
            if not self.position:
                self.buy()
            
        elif decision < self.buy_probability + self.sell_probability:
            # Sell signal
            if self.position:
                self.position.close()
            self.sell()
            
        # Otherwise hold (do nothing)
        # This covers the remaining probability space


# Demo usage if run directly
if __name__ == "__main__":
    from backtesting.test import GOOG
    
    # Test the random strategy with sample data
    bt = Backtest(GOOG, RandomStrategy, cash=10000, commission=.002)
    output = bt.run()
    print(f"Random Strategy Results:")
    print(f"Return: {output['Return [%]']:.2f}%")
    print(f"Trades: {output['# Trades']}")
    
    # Optionally show plot (comment out if running headless)
    # bt.plot() 