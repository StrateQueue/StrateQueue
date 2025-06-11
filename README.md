# Stratequeue

**Transform your backtesting.py strategies into live trading**

Turn your strategy backtests into a professional live trading system with just one command. Run multiple strategies simultaneously, manage risk automatically, and trade on real markets.

## 🚀 What does this do?

**You have a trading strategy in backtesting.py → Stratequeue makes it trade live**

```python
# Your strategy (examples/strategies/sma.py)
class SmaCross(Strategy):
    def init(self):
        self.sma1 = self.I(SMA, self.data.Close, 10)
        self.sma2 = self.I(SMA, self.data.Close, 20)
    
    def next(self):
        if crossover(self.sma1, self.sma2):
            self.buy()
        elif crossover(self.sma2, self.sma1):
            self.sell()
```

```bash
# One command to start live trading
stratequeue deploy --strategy sma.py --symbols AAPL --paper
```

**That's it!** Your strategy is now running live, generating real-time signals and executing trades.

## 📦 Installation

```bash
# Install the complete package
pip install stratequeue[all]

# Or just the core (for testing strategies)
pip install stratequeue
```

## ⚡ Quick Start

### 1. Test a Strategy (No Trading)
```bash
# See what signals your strategy generates (safe)
stratequeue deploy --strategy examples/strategies/sma.py --symbols AAPL --no-trading
```

### 2. Paper Trading (Fake Money)
```bash
# Test with fake money on real market data (safe)
stratequeue deploy --strategy examples/strategies/sma.py --symbols AAPL --paper
```

### 3. Live Trading (Real Money)
```bash
# Trade with real money (requires broker setup)
stratequeue deploy --strategy examples/strategies/sma.py --symbols AAPL --live
```

## 🎯 Core Features

### **Automatic Strategy-Symbol Mapping**
Stratequeue automatically detects your intent based on the number of strategies vs symbols:

| Strategies | Symbols | Behavior | Example |
|------------|---------|----------|---------|
| 2 | 1 | **Traditional**: Both strategies trade the symbol | `sma.py,momentum.py` → `AAPL` |
| 2 | 2 | **1:1 Mapping**: Each strategy gets its own symbol | `sma.py,momentum.py` → `AAPL,MSFT` |
| 2 | 3+ | **Traditional**: Both strategies trade all symbols | `sma.py,momentum.py` → `AAPL,MSFT,GOOGL` |

```bash
# 🔄 Traditional Mode (all strategies on all symbols)
stratequeue --strategy sma.py,momentum.py --symbols AAPL,MSFT,GOOGL
# → sma trades AAPL,MSFT,GOOGL + momentum trades AAPL,MSFT,GOOGL

# 🎯 1:1 Mapping Mode (each strategy gets one symbol)  
stratequeue --strategy sma.py,momentum.py --symbols AAPL,MSFT
# → sma trades AAPL only + momentum trades MSFT only
```

### **Multiple Strategies at Once**
```bash
# Run 3 strategies simultaneously with different allocations
stratequeue --strategy sma.py,momentum.py,mean_revert.py --allocation 0.4,0.35,0.25 --symbols AAPL,MSFT
```

### **1:1 Strategy-Symbol Mapping**
```bash
# When strategy count = symbol count, each strategy gets its own symbol
stratequeue --strategy sma.py,random.py --allocation 0.5,0.5 --symbols ETH,AAPL
# ✅ sma.py trades ETH only, random.py trades AAPL only

# Perfect for specialized strategies
stratequeue --strategy stock_algo.py,crypto_algo.py --allocation 0.8,0.2 --symbols AAPL,BTC
# ✅ stock_algo.py → AAPL, crypto_algo.py → BTC
```

### **Any Time Frame**
```bash
# Different timeframes for different strategies
stratequeue --strategy sma.py,scalper.py --allocation 0.6,0.4 --granularity 1h,1m --symbols ETH
```

### **Multiple Brokers** 
```bash
# Use different brokers for different strategies
stratequeue --strategy stock_algo.py,crypto_algo.py --broker alpaca,kraken --symbols AAPL,BTC
```

### **Smart Strategy-Symbol Mapping**
```bash
# All strategies on one symbol (traditional mode)
stratequeue --strategy sma.py,momentum.py --allocation 0.5,0.5 --symbols AAPL --granularity 1m
# Both strategies trade AAPL on 1m timeframes

# 1:1 strategy-symbol mapping (when counts match)
stratequeue --strategy sma.py,momentum.py --allocation 0.6,0.4 --symbols AAPL,MSFT
# sma.py trades AAPL only, momentum.py trades MSFT only

# Traditional mode (when counts don't match)
stratequeue --strategy sma.py,momentum.py --allocation 0.5,0.5 --symbols AAPL,MSFT,GOOGL
# Both strategies trade all symbols (AAPL, MSFT, GOOGL)
```

## 🔥 One-Terminal Strategy Management

**No more terminal juggling!** The `deploy` command is now context-aware and automatically switches between blocking and hot swap modes.

### **🎯 Simple Unified Workflow**

```bash
# Option 1: Start in foreground (see output in terminal)
stratequeue deploy --strategy sma.py,momentum.py --allocation 0.6,0.4 --symbols AAPL

# Option 2: Start in background (daemon mode for hot swapping)
stratequeue deploy --strategy sma.py,momentum.py --allocation 0.6,0.4 --symbols AAPL --daemon

# Now use the SAME terminal for all management:
stratequeue deploy --strategy new_algo.py --allocation 0.2                 # Auto-hot-swap
stratequeue pause --strategy-id momentum                                   # Direct commands
stratequeue resume --strategy-id momentum
stratequeue undeploy --strategy-id old_strat
stratequeue list                                                           # Show live status
```

### **🤖 Context-Aware Intelligence**

The `deploy` command automatically detects your situation:

- **🆕 No system running** → Start fresh system (foreground or daemon based on `--daemon` flag)
- **🔄 System already running** → Hot swap new strategies into running system  
- **🧹 Dead system detected** → Clean up and restart fresh

### **📈 Your Exact Trading Timeline**
```bash
# t0: Deploy strategies A & B (daemon mode returns control immediately)
stratequeue deploy --strategy a.py,b.py --allocation 0.6,0.4 --daemon

# t1: Undeploy A (same terminal, system keeps running)
stratequeue undeploy --strategy-id a

# t2: Deploy A & C (context-aware - auto-hot-swaps into running system)
stratequeue deploy --strategy a_v2.py,c.py --allocation 0.3,0.3
```

### **🎛️ Direct Strategy Commands**

```bash
# Monitor running strategies  
stratequeue list                    # Smart: shows running strategies if system active

# Strategy lifecycle management
stratequeue pause --strategy-id momentum      # Pause strategy (stops signals, keeps positions)
stratequeue resume --strategy-id momentum     # Resume paused strategy
stratequeue undeploy --strategy-id old_algo   # Remove strategy completely

# Add more strategies (auto-detected as hot swap)
stratequeue deploy --strategy new.py --allocation 0.2
```

### **🔍 Status & Monitoring**

```bash
# Context-aware list command
stratequeue list                    # Shows running strategies (if daemon active) OR general options

# Example output when system is running:
# 📋 Current Strategy Status:
#    🟢 sma: 60.0% allocation, symbols: ['AAPL'] 
#    ⏸️ momentum: 40.0% allocation, symbols: ['AAPL']
#    💰 Total allocation: 100.0%
#    🔗 System PID: 12345

# Traditional hotswap commands still work
stratequeue hotswap list            # Explicit hotswap (legacy)
```

### **🎚️ Deployment Modes**

| Command | Behavior | Use Case |
|---------|----------|----------|
| `stratequeue deploy --strategy sma.py` | Context-aware, foreground mode | New users, want to see output |
| `stratequeue deploy --strategy sma.py --daemon` | Context-aware, background mode | Hot swapping, production |
| `stratequeue deploy --strategy new.py` *(when system running)* | Auto-hot-swap | Adding strategies at runtime |

> **💡 Pro Tip:** Start with `--daemon` for seamless strategy management. The terminal returns control immediately while the system runs in the background.

## 🏦 Supported Brokers

| Broker | Status | Paper Trading | Live Trading |
|--------|--------|---------------|--------------|
| **Alpaca** | ✅ Ready | ✅ | ✅ |
| **Interactive Brokers** | 🚧 Coming Soon | 🚧 | 🚧 |
| **Kraken** | 🚧 Coming Soon | 🚧 | 🚧 |

### Set Up Your Broker

```bash
# Check what brokers you have configured
stratequeue status

# Get setup instructions for a specific broker
stratequeue setup broker alpaca

# List all available brokers
stratequeue list brokers
```

## 📊 Data Sources

| Source | Best For | Free? | Timeframes |
|--------|----------|-------|------------|
| `demo` | Testing strategies | ✅ | 1s to 1d |
| `polygon` | US stocks, real data | 💰 | 1s to 1d |
| `coinmarketcap` | Crypto prices | 💰 | 1m to 1d |

```bash
# Use different data sources
stratequeue deploy --strategy crypto.py --symbols BTC,ETH --data-source coinmarketcap
stratequeue deploy --strategy stocks.py --symbols AAPL,MSFT --data-source polygon
```

## 🛡️ Safety Features

### **Paper Trading by Default**
- Everything starts in paper trading mode (fake money)
- Must explicitly use `--live` for real money
- Clear warnings when using real money

### **Risk Management**
- Each strategy gets its own allocated capital
- No strategy can exceed its allocation
- Automatic conflict resolution when strategies want the same stock

### **Easy Testing**
```bash
# Test strategy logic without any trading
stratequeue deploy --strategy my_new_idea.py --symbols AAPL --no-trading

# Test with fake money
stratequeue deploy --strategy my_new_idea.py --symbols AAPL --paper

# Only go live after thorough testing
stratequeue deploy --strategy my_tested_strategy.py --symbols AAPL --live
```

## 📋 Example Commands

### Single Strategy Examples
```bash
# Basic demo
stratequeue deploy --strategy sma.py --symbols AAPL

# Real data, paper trading
stratequeue deploy --strategy sma.py --symbols AAPL --data-source polygon --paper

# Crypto trading
stratequeue deploy --strategy crypto_momentum.py --symbols BTC,ETH --data-source coinmarketcap

# High frequency (1 second intervals)
stratequeue deploy --strategy scalper.py --symbols SPY --granularity 1s

# Long term (daily signals)
stratequeue deploy --strategy swing_trade.py --symbols AAPL,MSFT --granularity 1d
```

### Multi-Strategy Examples
```bash
# Traditional mode: both strategies trade AAPL
stratequeue deploy --strategy sma.py,momentum.py --allocation 0.6,0.4 --symbols AAPL

# Traditional mode: both strategies trade SPY  
stratequeue deploy --strategy day_trade.py,swing_trade.py --allocation 0.3,0.7 --granularity 1m,1d --symbols SPY

# 1:1 mapping: stock_algo.py→AAPL, crypto_algo.py→BTC
stratequeue deploy --strategy stock_algo.py,crypto_algo.py --allocation 0.8,0.2 --symbols AAPL,BTC --data-source polygon,coinmarketcap

# 1:1 mapping: each strategy gets its own symbol
stratequeue deploy \
  --strategy sma.py,momentum.py,mean_revert.py \
  --allocation 0.4,0.35,0.25 \
  --symbols AAPL,MSFT,GOOGL \
  --granularity 1h,15m,1d \
  --paper
```

## 🔧 Configuration

### Environment Variables (.env file)
```env
# Alpaca Trading (recommended for beginners)
PAPER_KEY=your_alpaca_paper_key
PAPER_SECRET=your_alpaca_paper_secret

# For live trading (after testing!)
ALPACA_API_KEY=your_alpaca_live_key  
ALPACA_SECRET_KEY=your_alpaca_live_secret

# Data Sources (optional)
POLYGON_API_KEY=your_polygon_key
CMC_API_KEY=your_coinmarketcap_key
```

### Create Your Strategy
```python
# my_strategy.py
LOOKBACK = 20  # How many historical bars you need

from backtesting import Strategy
from backtesting.lib import crossover
from backtesting.test import SMA

class MyStrategy(Strategy):
    def init(self):
        # Set up your indicators
        self.sma = self.I(SMA, self.data.Close, 20)
    
    def next(self):
        # Your trading logic
        if self.data.Close[-1] > self.sma[-1]:
            self.buy()
        else:
            self.sell()
```

```bash
# Test your strategy
stratequeue deploy --strategy my_strategy.py --symbols AAPL --no-trading
```

## 📈 Real-Time Output

```
🚀 LIVE TRADING SYSTEM STARTED
============================================================
Mode: MULTI-STRATEGY
Strategies: sma, momentum, mean_revert
Symbols: AAPL, MSFT, GOOGL
Data Source: polygon
Granularity: 1h, 15m, 1d
💰 Trading: PAPER MODE via Alpaca
============================================================

🎯 SIGNAL #1 - 2024-06-10 14:30:15 [sma]
Symbol: AAPL
Action: 📈 BUY
Price: $185.42
Confidence: 85.0%
Allocation: $2,000 (40% of strategy capital)

🎯 SIGNAL #2 - 2024-06-10 14:45:22 [momentum]  
Symbol: MSFT
Action: 📉 SELL
Price: $340.15
Confidence: 78.0%
Allocation: $1,750 (35% of strategy capital)
```

## 🆘 Common Issues

### "No broker detected"
```bash
# Check your setup
stratequeue --broker-status

# Get help setting up Alpaca (easiest broker)
stratequeue --broker-setup alpaca
```

### "Strategy file not found"
```bash
# Make sure your file exists
ls my_strategy.py

# Use full path if needed
stratequeue --strategy /full/path/to/my_strategy.py --symbols AAPL
```

### "Invalid allocation"
```bash
# Allocations must add up to 1.0 (100%) or less
stratequeue --strategy sma.py,momentum.py --allocation 0.6,0.4  # ✅ Good (100%)
stratequeue --strategy sma.py,momentum.py --allocation 0.6,0.3  # ✅ Good (90%)
stratequeue --strategy sma.py,momentum.py --allocation 0.6,0.6  # ❌ Bad (120%)
```

## 🎓 Learning Path

### 1. Start Simple
```bash
# Just see what signals your strategy generates
stratequeue deploy --strategy examples/strategies/sma.py --symbols AAPL --no-trading --duration 5
```

### 2. Add Paper Trading
```bash
# Test with fake money
stratequeue deploy --strategy examples/strategies/sma.py --symbols AAPL --paper --duration 30
```

### 3. Try Multiple Strategies
```bash
# Run a simple portfolio
stratequeue --strategy examples/strategies/sma.py,examples/strategies/momentum.py --allocation 0.6,0.4 --symbols AAPL --paper
```

### 4. Go Live (When Ready!)
```bash
# Real money trading (be careful!)
stratequeue --strategy my_tested_strategy.py --symbols AAPL --live
```

## 🔗 More Examples

### Get Help
```bash
stratequeue --help                    # Show all options
stratequeue --list-brokers           # See supported brokers  
stratequeue --list-granularities     # See supported timeframes
stratequeue --broker-status          # Check your broker setup
```

### Advanced Usage
```bash
# Custom runtime
stratequeue --strategy sma.py --symbols AAPL --duration 120  # Run for 2 hours

# Verbose logging (for debugging)
stratequeue --strategy sma.py --symbols AAPL --verbose

# Override strategy lookback period
stratequeue --strategy sma.py --symbols AAPL --lookback 50

# Multiple symbols, single strategy
stratequeue --strategy diversified.py --symbols AAPL,MSFT,GOOGL,TSLA --paper
```

---

**Ready to start?** Install Stratequeue and turn your backtesting strategies into live trading systems in minutes, not months. 