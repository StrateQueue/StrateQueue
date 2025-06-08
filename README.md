# Live Trading Infrastructure

A scalable live trading system that converts [backtesting.py](https://kernc.github.io/backtesting.py/) strategies into real-time signal generators with support for multiple data sources and symbols.

## 🚀 Features

- **Dynamic Strategy Loading**: Load any backtesting.py strategy file
- **Automatic Signal Extraction**: Convert strategy buy/sell calls into structured signals
- **Multiple Data Sources**: Demo data for testing, Polygon.io for live markets
- **Realistic Simulation**: Proper cumulative data handling (not regenerated each cycle)
- **Multi-Symbol Support**: Run strategies across multiple symbols simultaneously
- **Auto-Lookback Calculation**: Automatically determines required historical data
- **Live Monitoring**: Real-time signal display with confidence scoring

## 📦 Installation

```bash
pip install pandas numpy requests websocket-client python-dotenv backtesting
```

## 🎯 Quick Start

### 1. Create a Strategy
```python
# my_strategy.py
from backtesting import Strategy
import random

class MyStrategy(Strategy):
    def init(self):
        pass
    
    def next(self):
        if random.random() < 0.1:  # 10% chance
            self.buy()
```

### 2. Run Live System
```bash
# Demo mode (synthetic data)
python main.py --strategy examples/strategies/sma.py --symbols AAPL,MSFT --data-source demo --duration 5

# Live mode (requires Polygon.io API key)
export POLYGON_API_KEY="your_key_here"
python main.py --strategy examples/strategies/sma.py --symbols AAPL --data-source polygon --duration 60
```

### 3. Monitor Signals
```
🎯 SIGNAL #1 - 2025-06-07 14:13:00
Symbol: AAPL
Action: 📈 BUY
Price: $357.40
Confidence: 80.0%
Indicators:
  • price: 350.05
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Layer    │    │  Strategy Layer │    │ Signal Output   │
│                 │    │                 │    │                 │
│ • Polygon.io    │───▶│ • backtesting.py│───▶│ • Structured    │
│ • Demo Data     │    │ • Auto-convert  │    │   Signals       │
│ • Cumulative    │    │ • Signal Extract│    │ • Confidence    │
│   Updates       │    │                 │    │ • Indicators    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📁 Key Files

- **`main.py`**: Main orchestrator and CLI interface
- **`src/trading_system/`**: Core trading system modules
  - **`data_ingestion.py`**: Data sources (Polygon.io + synthetic)
  - **`signal_extractor.py`**: Strategy-to-signal conversion
  - **`config.py`**: Environment configuration
- **`examples/strategies/`**: Example trading strategies
  - **`sma.py`**: SMA crossover strategy
  - **`random_strategy.py`**: Random trading strategy

## 🔧 Configuration

Create a `.env` file:
```bash
POLYGON_API_KEY=your_polygon_api_key
TRADING_SYMBOLS=AAPL,MSFT,GOOGL
HISTORICAL_DAYS=30
```

## 💡 How It Works

1. **Load Strategy**: Dynamically imports any backtesting.py strategy
2. **Calculate Lookback**: Analyzes strategy parameters to determine required data
3. **Initialize Data**: Fetches initial historical data (demo or real)
4. **Live Loop**: 
   - Append 1 new bar to cumulative dataset
   - Run strategy on complete data
   - Extract signals from buy/sell calls
   - Display actionable signals
5. **Signal Output**: Structured signals with confidence and metadata

## 🎲 Example Strategies

### SMA Crossover
```python
class SmaCross(Strategy):
    n1 = 10  # Fast SMA
    n2 = 20  # Slow SMA
    
    def init(self):
        from backtesting.test import SMA
        close = self.data.Close
        self.sma1 = self.I(SMA, close, self.n1)
        self.sma2 = self.I(SMA, close, self.n2)
    
    def next(self):
        if crossover(self.sma1, self.sma2):
            self.buy()
        elif crossover(self.sma2, self.sma1):
            self.sell()
```

### Random Strategy
```python
class RandomStrategy(Strategy):
    buy_probability = 0.15
    
    def next(self):
        if random.random() < self.buy_probability:
            self.buy()
```

## 🔮 Future Enhancements

- **Trade Execution**: Integration with Alpaca for actual trading
- **Performance Tracking**: Live PnL, Sharpe ratio, drawdown monitoring  
- **Risk Management**: Position sizing, stop losses, portfolio limits
- **Multi-Engine Support**: Zipline, LEAN compatibility
- **Web Dashboard**: Real-time monitoring interface
- **Strategy Marketplace**: Share and discover strategies

## 📊 CLI Options

```bash
python main.py --help

Options:
  --strategy STRATEGY     Path to strategy file (required)
  --symbols SYMBOLS       Comma-separated symbols (default: AAPL)
  --data-source {demo,polygon}  Data source (default: demo)
  --lookback LOOKBACK     Override calculated lookback period
  --duration DURATION     Runtime in minutes (default: 60)
  --verbose              Enable debug logging
```

## ⚠️ Disclaimer

This is educational software for learning algorithmic trading concepts. Not financial advice. Use at your own risk. 