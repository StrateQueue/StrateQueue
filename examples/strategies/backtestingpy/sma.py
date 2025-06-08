# Strategy Configuration
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
from backtesting.test import SMA


class SmaCross(Strategy):
    n1 = 1
    n2 = 3

    def init(self):
        close = self.data.Close
        self.sma1 = self.I(SMA, close, self.n1)
        self.sma2 = self.I(SMA, close, self.n2)

    def next(self):
        if crossover(self.sma1, self.sma2):
            self.position.close()
            self.buy(size=0.1)  # Use 10% of available capital
        elif crossover(self.sma2, self.sma1):
            self.position.close()
            self.sell()

