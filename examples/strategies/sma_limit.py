from backtesting import Backtest, Strategy
from backtesting.lib import crossover
from backtesting.test import SMA, GOOG


class SmaCrossLimitOrders(Strategy):
    """
    SMA crossover strategy using limit orders instead of market orders.
    
    - Buy limit orders are placed 0.2% below current market price
    - Sell limit orders are placed 0.2% above the buy price
    """
    n1 = 1
    n2 = 3
    limit_offset_pct = 0.002  # 0.2% offset for limit orders

    def init(self):
        close = self.data.Close
        self.sma1 = self.I(SMA, close, self.n1)
        self.sma2 = self.I(SMA, close, self.n2)
        self.last_buy_price = None  # Track our buy price for calculating sell limit

    def next(self):
        current_price = self.data.Close[-1]
        
        if crossover(self.sma1, self.sma2):
            # Fast MA crosses above slow MA - bullish signal
            self.position.close()  # Close any existing position first
            
            # Set buy limit 0.2% below current market price
            buy_limit_price = current_price * (1 - self.limit_offset_pct)
            self.last_buy_price = buy_limit_price  # Store for later sell calculation
            
            # Place limit buy order
            self.buy(size=0.1, limit=buy_limit_price)
            
        elif crossover(self.sma2, self.sma1):
            # Fast MA crosses below slow MA - bearish signal
            self.position.close()  # Close any existing position first
            
            # Set sell limit 0.2% above our last buy price (or current price if no buy price)
            if self.last_buy_price:
                sell_limit_price = self.last_buy_price * (1 + self.limit_offset_pct)
            else:
                # If we don't have a buy price, use current price + 0.2%
                sell_limit_price = current_price * (1 + self.limit_offset_pct)
            
            # Place limit sell order
            self.sell(limit=sell_limit_price)


# Example usage - same as original sma.py
if __name__ == "__main__":
    bt = Backtest(GOOG, SmaCrossLimitOrders,
                  cash=10000, commission=.002,
                  exclusive_orders=True)

    output = bt.run()
    print(f"Final equity: ${output['End']:.2f}")
    print(f"Total return: {output['Return [%]']:.2f}%")
    print(f"Number of trades: {output['# Trades']}")
    
    # Plot results
    bt.plot() 