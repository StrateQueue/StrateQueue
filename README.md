# Stratequeue

**Professional Multi-Strategy Live Trading Infrastructure**

Transform your backtesting.py strategies into a sophisticated multi-strategy live trading system with real-time signal generation, portfolio management, and optional execution.

## 🚀 Key Features

### **Multi-Strategy Portfolio Management**
- **Run multiple strategies simultaneously** with intelligent capital allocation
- **Strategy isolation** - each strategy operates independently with dedicated capital
- **Conflict resolution** - automatic handling of overlapping symbol trades
- **Performance tracking** per strategy and overall portfolio

### **Professional Trading Infrastructure** 
- **Real-time signal generation** from backtesting.py strategies
- **Multiple data sources**: Polygon.io, CoinMarketCap, and realistic demo data
- **Flexible timeframes**: 1s to 1d granularities
- **Paper & live trading** via Alpaca integration
- **Risk management** with position sizing and portfolio controls

### **Easy Installation & Usage**
- **Professional packaging** - install via pip like any Python package
- **Clean CLI interface** with intuitive commands
- **Modular dependencies** - install only what you need
- **Comprehensive documentation** and examples

## 📦 Installation

### Quick Start
```bash
# Install core package
pip install stratequeue

# Or with trading capabilities
pip install stratequeue[trading]

# Or with everything
pip install stratequeue[all]
```

### Development Installation
```bash
git clone https://github.com/yourusername/Live-Trading-Infrastructure.git
cd Live-Trading-Infrastructure
pip install -e .[dev,all]
```

## 🎯 Quick Examples

### Single Strategy
```bash
# Demo trading with one strategy
stratequeue --strategy examples/strategies/sma.py --symbols AAPL --data-source demo

# Live signals with real data (requires API keys)
stratequeue --strategy examples/strategies/sma.py --symbols AAPL --data-source polygon
```

### Multi-Strategy Portfolio (NEW!)
```bash
# Run multiple strategies simultaneously
stratequeue --strategies strategies.txt --symbols AAPL,MSFT,BTC --data-source demo

# With live trading enabled
stratequeue --strategies strategies.txt --symbols AAPL,MSFT --enable-trading
```

### Short Command Alias
```bash
# Use 'sq' for quick access
sq --strategy my_algo.py --symbols TSLA --data-source demo --duration 30
```

## 📋 Multi-Strategy Configuration

Create a `strategies.txt` file to define your portfolio:

```txt
# filename,strategy_id,allocation
examples/strategies/sma.py,sma_short,0.4
examples/strategies/momentum.py,momentum_1h,0.3
examples/strategies/mean_revert.py,mean_rev,0.3
```

**Powerful Portfolio Management:**
- Each strategy gets dedicated capital allocation (40%, 30%, 30%)
- Automatic conflict resolution when strategies target the same symbol
- Independent performance tracking per strategy
- Real-time capital rebalancing

## 🛠️ Installation Options

| Package | Dependencies | Use Case |
|---------|-------------|----------|
| `stratequeue` | Core only | Signal generation, demo trading |
| `stratequeue[trading]` | + Alpaca API | Live/paper trading |
| `stratequeue[backtesting]` | + backtesting.py | Strategy development |
| `stratequeue[analytics]` | + scipy, ta-lib | Advanced analysis |
| `stratequeue[all]` | Everything | Full featured setup |

## 📊 Usage Patterns

### 1. Strategy Development
```bash
# Quick test new strategy
stratequeue --strategy my_new_algo.py --symbols AAPL --data-source demo --duration 5

# Validate with real data
stratequeue --strategy my_new_algo.py --symbols AAPL --data-source polygon --duration 60
```

### 2. Portfolio Simulation
```bash
# Test multi-strategy portfolio
stratequeue --strategies portfolio.txt --symbols AAPL,MSFT,TSLA --data-source demo

# With detailed logging
stratequeue --strategies portfolio.txt --symbols AAPL,MSFT --verbose
```

### 3. Live Trading
```bash
# Paper trading (safe testing)
stratequeue --strategies portfolio.txt --symbols AAPL,MSFT --enable-trading

# Real trading (after thorough testing)
stratequeue --strategy proven_algo.py --symbols AAPL --enable-trading --data-source polygon
```

## 🔧 Configuration

### Environment Setup (.env)
```env
# Data Sources
POLYGON_API_KEY=your_polygon_key
CMC_API_KEY=your_coinmarketcap_key

# Trading (Alpaca)
ALPACA_API_KEY=your_alpaca_key
ALPACA_SECRET_KEY=your_alpaca_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Optional Defaults
TRADING_SYMBOLS=AAPL,MSFT,GOOGL
HISTORICAL_DAYS=30
```

### Data Sources
| Source | Purpose | Granularities | Requirements |
|--------|---------|---------------|--------------|
| `demo` | Testing & development | 1s, 1m, 5m, 1h, 1d | None |
| `polygon` | Real market data | 1s, 1m, 5m, 15m, 1h, 1d | API key |
| `coinmarketcap` | Cryptocurrency | 1m, 5m, 15m, 30m, 1h, 1d | API key |

## 📈 Strategy Development

### Simple Strategy Example
```python
# examples/strategies/sma_crossover.py
LOOKBACK = 20  # Required historical bars

from backtesting import Strategy
from backtesting.lib import crossover
from backtesting.test import SMA

class SmaCrossover(Strategy):
    fast = 10
    slow = 20
    
    def init(self):
        self.sma_fast = self.I(SMA, self.data.Close, self.fast)
        self.sma_slow = self.I(SMA, self.data.Close, self.slow)
    
    def next(self):
        if crossover(self.sma_fast, self.sma_slow):
            self.buy(size=0.25)  # 25% of allocated capital
        elif crossover(self.sma_slow, self.sma_fast):
            self.sell()
```

### Strategy Requirements
1. **LOOKBACK variable** - minimum historical bars needed
2. **Strategy class** inheriting from backtesting.Strategy
3. **init()** method for indicator setup
4. **next()** method for trading logic

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Strategies    │    │   Data Sources   │    │   Portfolio     │
│                 │    │                  │    │   Manager       │
│ • SMA Cross     │    │ • Polygon.io     │    │                 │
│ • Momentum      │───▶│ • CoinMarketCap  │───▶│ • Capital Alloc │
│ • Mean Revert   │    │ • Demo Data      │    │ • Risk Control  │
│ • Custom Algos  │    │                  │    │ • Conflict Res  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                       │
         ▼                        ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Signal Extractor│    │ Real-time Data   │    │ Alpaca Executor │
│                 │    │ Processing       │    │                 │
│ • Convert Logic │    │                  │    │ • Paper Trading │
│ • Generate Sigs │    │ • Live Updates   │    │ • Live Trading  │
│ • Multi-Strategy│    │ • Historical     │    │ • Order Mgmt    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 📋 Command Reference

### Core Commands
```bash
# Main command (matches package name)
stratequeue [options]

# Short alias for power users  
sq [options]

# Legacy aliases (for compatibility)
live-trading [options]
trading-system [options]
```

### Essential Arguments
| Flag | Description | Example |
|------|-------------|---------|
| `--strategy` | Single strategy file | `--strategy sma.py` |
| `--strategies` | Multi-strategy config | `--strategies portfolio.txt` |
| `--symbols` | Trading symbols | `--symbols AAPL,MSFT,BTC` |
| `--data-source` | Data provider | `--data-source polygon` |
| `--enable-trading` | Enable live trading | `--enable-trading` |
| `--duration` | Runtime in minutes | `--duration 120` |
| `--verbose` | Detailed logging | `--verbose` |

### Advanced Examples
```bash
# List available granularities
stratequeue --list-granularities

# Custom granularity and lookback
stratequeue --strategy algo.py --symbols AAPL --granularity 5m --lookback 100

# Multi-strategy with specific duration
stratequeue --strategies portfolio.txt --symbols AAPL,MSFT --duration 480  # 8 hours

# Verbose logging for debugging
stratequeue --strategy debug_algo.py --symbols TSLA --verbose --data-source demo
```

## 🎯 Use Cases

### **Quantitative Research**
```bash
# Quick strategy validation
stratequeue --strategy research_idea.py --symbols SPY --data-source demo --duration 10
```

### **Portfolio Management**
```bash
# Multi-strategy portfolio with real data
stratequeue --strategies diversified_portfolio.txt --symbols AAPL,MSFT,GOOGL,TSLA --data-source polygon
```

### **Crypto Trading**
```bash
# Crypto strategy with CoinMarketCap data  
stratequeue --strategy crypto_momentum.py --symbols BTC,ETH --data-source coinmarketcap
```

### **Live Trading**
```bash
# Paper trading for testing
stratequeue --strategies tested_portfolio.txt --symbols AAPL,MSFT --enable-trading

# Production trading (after extensive testing)
stratequeue --strategy proven_strategy.py --symbols AAPL --enable-trading --data-source polygon
```

## 🔍 Monitoring & Output

### Real-time Signal Display
```
🎯 MULTI-STRATEGY SIGNALS - 2024-06-09 14:30:00

📈 sma_short → AAPL: BUY @ $185.45 (Conf: 85%)
  └─ Allocation: $2,500 (25% of strategy capital)
  
📉 momentum_1h → MSFT: SELL @ $340.12 (Conf: 78%)
  └─ Allocation: $1,800 (18% of strategy capital)

📊 PORTFOLIO STATUS:
  • Total Value: $12,450.67
  • Active Strategies: 3/3
  • Open Positions: 5
  • Available Cash: $3,234.21
```

### Performance Tracking
```
📈 STRATEGY PERFORMANCE:
┌─────────────────┬─────────────┬─────────────┬─────────────┐
│ Strategy        │ Allocation  │ P&L         │ Win Rate    │
├─────────────────┼─────────────┼─────────────┼─────────────┤
│ sma_short       │ $5,000 (40%)│ +$234.56    │ 67%         │
│ momentum_1h     │ $3,750 (30%)│ +$123.45    │ 72%         │
│ mean_revert     │ $3,750 (30%)│ -$45.23     │ 58%         │
└─────────────────┴─────────────┴─────────────┴─────────────┘
```

## 🚨 Important Notes

### **Risk Management**
- **Always test with demo data first**
- **Use paper trading before live trading**
- **Start with small position sizes**
- **Monitor multi-strategy interactions**

### **Best Practices**
- **Strategy isolation**: Each strategy should be independent
- **Capital allocation**: Don't over-allocate to any single strategy
- **Regular monitoring**: Watch for unexpected correlations
- **Gradual scaling**: Increase allocation as strategies prove themselves

## 🆘 Troubleshooting

### Installation Issues
```bash
# Missing trading dependencies
pip install stratequeue[trading]

# Import errors
pip install --upgrade stratequeue

# Permission issues
pip install --user stratequeue
```

### Configuration Issues
```bash
# Check installed commands
which stratequeue

# Verify installation
stratequeue --help

# Debug mode
stratequeue --strategy test.py --symbols AAPL --verbose --data-source demo
```

### Multi-Strategy Issues
- **Capital conflicts**: Check strategy allocations sum to ≤ 1.0
- **Symbol conflicts**: Monitor which strategies trade overlapping symbols
- **Performance attribution**: Use `--verbose` to track per-strategy signals

## 🔗 Additional Resources

- **Strategy Examples**: See `examples/strategies/` directory
- **Configuration Templates**: Sample multi-strategy configs included
- **API Documentation**: Auto-generated docs from docstrings
- **Community**: GitHub issues for support and feature requests

---

**Stratequeue** - Professional multi-strategy trading infrastructure for Python developers. 