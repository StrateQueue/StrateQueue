# Strategy Configuration
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
from backtesting.test import SMA


class SmaCross(Strategy):
    """Simple 1-/3-period SMA crossover ensuring parity with other engine
    implementations.

    Rules:
    • When the 1-period SMA (current price) crosses *above* the 3-period SMA → BUY.
    • When the 3-period SMA crosses back above the 1-period SMA → CLOSE any open
      long position (no shorting).
    """

    n1 = 1  # fast SMA
    n2 = 3  # slow SMA

    def init(self):
        close = self.data.Close
        self.sma1 = self.I(SMA, close, self.n1)
        self.sma2 = self.I(SMA, close, self.n2)

    def next(self):
        # Price crosses above → enter long (only if not already in position)
        if crossover(self.sma1, self.sma2):
            if not self.position:
                self.buy()  # all in

        # Price crosses below → exit long if held
        elif crossover(self.sma2, self.sma1):
            if self.position:
                self.position.close()

