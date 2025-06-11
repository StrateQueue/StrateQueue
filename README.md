# StrateQueue

**🚀 Transform your backtesting strategies into live trading systems**

Turn your strategy backtests into a professional live trading system with comprehensive command-line tools. Deploy single or multi-strategy portfolios, manage them in real-time, and trade on real markets with enterprise-grade safety features.

## 🎯 What does this do?

**You have a trading strategy → StrateQueue makes it trade live**

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
# Deploy your strategy (safe by default - signals only)
stratequeue deploy --strategy sma.py --symbol AAPL --granularity 1m

# When ready, enable paper trading
stratequeue deploy --strategy sma.py --symbol AAPL --granularity 1m --paper

# When confident, go live
stratequeue deploy --strategy sma.py --symbol AAPL --granularity 1m --live
```

**That's it!** Your strategy is now running live with full real-time management capabilities.

## 📦 Installation

```bash
# Install the complete package
pip install stratequeue[all]

# Or just the core (for testing strategies)
pip install stratequeue
```

## ⚡ Quick Start

### 1. Test Strategy Logic (Default - Safe!)
```bash
# Generate signals without any trading (default behavior)
stratequeue deploy --strategy examples/strategies/sma.py --symbol AAPL --granularity 1m
```

### 2. Paper Trading (Fake Money)
```bash
# Test with fake money on real market data
stratequeue deploy --strategy examples/strategies/sma.py --symbol AAPL --granularity 1m --paper
```

### 3. Live Trading (Real Money)
```bash
# Trade with real money (requires broker setup)
stratequeue deploy --strategy examples/strategies/sma.py --symbol AAPL --granularity 1m --live
```

### 4. Real-Time Management
```bash
# Deploy in background for remote management
stratequeue deploy --strategy sma.py --symbol AAPL --granularity 1m --daemon

# Now manage from same terminal:
stratequeue pause sma          # Pause strategy (keeps positions)
stratequeue resume sma         # Resume strategy
stratequeue stop               # Stop entire system
```

## 🎮 Command Overview

StrateQueue provides a comprehensive CLI with 10 core commands for complete trading system management:

### **📚 Core Commands**

| Command | Description | Example |
|---------|-------------|---------|
| `deploy` | Start strategies with market data | `stratequeue deploy --strategy sma.py` |
| `pause` | Pause a running strategy | `stratequeue pause my_strategy` |
| `resume` | Resume a paused strategy | `stratequeue resume my_strategy` |
| `stop` | Shutdown the trading system | `stratequeue stop` |
| `remove` | Remove strategy from system | `stratequeue remove old_strategy` |
| `rebalance` | Adjust portfolio allocations | `stratequeue rebalance --allocations=0.6,0.4` |
| `list` | Discover available options | `stratequeue list brokers` |
| `status` | Check system health | `stratequeue status` |
| `setup` | Configure brokers/settings | `stratequeue setup broker alpaca` |
| `webui` | Launch web dashboard | `stratequeue webui` |

### **🎯 Get Help Anytime**
```bash
stratequeue --help              # Main help with colorful overview
stratequeue deploy --help       # Detailed help for any command
stratequeue pause --help        # Each command has focused, actionable help
```

## 🚀 Deploy Command (Core Functionality)

The `deploy` command is your main entry point for starting trading strategies.

### **🎯 Execution Modes**
- `--no-trading` - Generate signals only (default, safe for testing)
- `--paper` - Simulate trading with fake money  
- `--live` - Execute real trades with real money

### **📋 Single Strategy Deployment**
```bash
# Test strategy safely (default mode)
stratequeue deploy --strategy sma.py --symbol AAPL --granularity 1m

# Paper trading with custom timeframe
stratequeue deploy --strategy momentum.py --symbol MSFT --granularity 1h --paper

# Live trading with custom broker
stratequeue deploy --strategy sma.py --symbol AAPL --granularity 1m --broker alpaca --live

# Run in background for remote management
stratequeue deploy --strategy trend.py --symbol GOOGL --granularity 1m --daemon
```

### **📊 Multi-Strategy Portfolios**
```bash
# Deploy portfolio with custom allocations
stratequeue deploy --strategy sma.py,momentum.py --allocation 0.7,0.3 --symbol AAPL --granularity 1m

# 1:1 strategy-symbol mapping (when counts match)
stratequeue deploy --strategy stock_algo.py,crypto_algo.py --allocation 0.8,0.2 --symbol AAPL,BTC --granularity 1m

# Different timeframes per strategy
stratequeue deploy --strategy scalper.py,swing.py --allocation 0.4,0.6 --granularity 1m,1h --symbol ETH
```

### **⚙️ Configuration Options**
- `--symbol` - Trading symbol(s) (default: AAPL)
- `--data-source` - Data provider (default: demo)
- `--granularity` - Time intervals (1s, 1m, 5m, 1h, 1d)
- `--broker` - Trading broker (auto-detected from environment)
- `--duration` - Runtime in minutes (default: 60)
- `--daemon` - Background mode for remote management

## 🎛️ Real-Time Strategy Management

Once deployed in daemon mode, manage your strategies without stopping the system:

### **⏸️ Pause/Resume Strategies**
```bash
# Pause a strategy (stops signals, keeps positions)
stratequeue pause momentum_strategy

# Resume when ready
stratequeue resume momentum_strategy

# Preview actions with dry-run
stratequeue pause risky_strategy --dry-run
```

### **🛑 System Control**
```bash
# Graceful shutdown (preserves positions)
stratequeue stop

# Force immediate shutdown
stratequeue stop --force

# Liquidate all positions before stopping
stratequeue stop --liquidate
```

### **🗑️ Strategy Removal**
```bash
# Remove strategy and transfer positions to others
stratequeue remove old_strategy

# Remove strategy and liquidate its positions
stratequeue remove old_strategy --liquidate

# Remove and automatically rebalance remaining strategies
stratequeue remove old_strategy --rebalance
```

### **⚖️ Portfolio Rebalancing**
```bash
# Equal weight rebalancing
stratequeue rebalance --allocations=equal

# Custom allocations
stratequeue rebalance --allocations=0.5,0.3,0.2

# Specify strategy order
stratequeue rebalance --allocations=0.6,0.4 --strategy-ids=sma,momentum

# Rebalance positions only (keep allocation percentages)
stratequeue rebalance --allocations=equal --target=positions
```

## 🔍 Discovery and Setup Commands

### **📋 List Available Options**
```bash
# See all supported brokers
stratequeue list brokers

# See available time intervals
stratequeue list granularities

# Quick aliases
stratequeue ls brokers          # Short form
stratequeue show granularities  # Alternative
```

### **🔍 System Status**
```bash
# Check overall system health
stratequeue status

# Check specific broker
stratequeue status --broker alpaca

# Aliases
stratequeue check               # Alternative
stratequeue health              # Alternative
```

### **⚙️ Configuration Setup**
```bash
# Interactive setup wizard
stratequeue setup

# Setup specific broker
stratequeue setup broker alpaca

# Aliases
stratequeue config             # Alternative
stratequeue configure          # Alternative
```

### **🌐 Web Dashboard**
```bash
# Launch web interface (default port 8000)
stratequeue webui

# Custom port
stratequeue webui --port 9000

# Aliases
stratequeue web                # Alternative
stratequeue ui                 # Alternative
```

## 🎯 Strategy-Symbol Mapping Modes

StrateQueue uses **1:1 Strategy-Symbol Mapping** for optimal performance:

### **🎯 1:1 Mapping Mode** (Each strategy gets dedicated symbol)
```bash
# When strategy count = symbol count
stratequeue deploy --strategy sma.py,momentum.py --allocation 0.6,0.4 --symbol AAPL,MSFT --granularity 1m
# → sma trades AAPL only + momentum trades MSFT only

# Perfect for specialized strategies
stratequeue deploy --strategy stock_algo.py,crypto_algo.py --allocation 0.8,0.2 --symbol AAPL,BTC --granularity 1m
# → stock_algo.py → AAPL, crypto_algo.py → BTC
```

## 🏦 Supported Brokers

| Broker | Status | Paper Trading | Live Trading | Setup Command |
|--------|--------|---------------|--------------|---------------|
| **Alpaca** | ✅ Ready | ✅ | ✅ | `stratequeue setup broker alpaca` |
| **Interactive Brokers** | 🚧 Coming Soon | 🚧 | 🚧 | Coming Soon |
| **Kraken** | 🚧 Coming Soon | 🚧 | 🚧 | Coming Soon |

### **🔧 Broker Configuration**
```bash
# Check current broker status
stratequeue status

# Setup Alpaca (recommended for beginners)
stratequeue setup broker alpaca

# List all available brokers
stratequeue list brokers
```

## 📊 Data Sources

| Source | Best For | Free? | Timeframes | Setup |
|--------|----------|-------|------------|-------|
| `demo` | Testing strategies | ✅ | 1s to 1d | Built-in |
| `polygon` | US stocks, real data | 💰 | 1s to 1d | API key required |
| `coinmarketcap` | Crypto prices | 💰 | 1m to 1d | API key required |

```bash
# Use different data sources
stratequeue deploy --strategy crypto.py --symbol BTC,ETH --granularity 1m --data-source coinmarketcap
stratequeue deploy --strategy stocks.py --symbol AAPL,MSFT --granularity 1m --data-source polygon
```

## 🛡️ Safety Features

### **🔒 Safe by Default**
- **No-trading mode is default** - must explicitly enable trading
- **Paper trading for testing** - safe environment with fake money
- **Real money warnings** - clear confirmations for live trading
- **Dry-run support** - preview actions before execution

### **⚖️ Risk Management**
- **Allocation limits** - each strategy gets dedicated capital
- **Position isolation** - strategies cannot exceed their allocation
- **Conflict resolution** - automatic handling when strategies compete
- **Graceful shutdowns** - preserve positions during system stops

### **🧪 Testing Workflow**
```bash
# 1. Test strategy logic (no trading)
stratequeue deploy --strategy new_idea.py --symbol AAPL --granularity 1m

# 2. Test with fake money
stratequeue deploy --strategy new_idea.py --symbol AAPL --granularity 1m --paper

# 3. Small live test
stratequeue deploy --strategy tested_strategy.py --symbol AAPL --granularity 1m --live --duration 30

# 4. Full deployment
stratequeue deploy --strategy proven_strategy.py --symbol AAPL --granularity 1m --live --daemon
```

## 📋 Complete Command Examples

### **🚀 Deployment Examples**
```bash
# Basic strategy testing (default mode)
stratequeue deploy --strategy sma.py --symbol AAPL --granularity 1m

# Paper trading with real data
stratequeue deploy --strategy momentum.py --symbol MSFT --granularity 1m --data-source polygon --paper

# High-frequency crypto trading
stratequeue deploy --strategy scalper.py --symbol BTC --granularity 1s --data-source coinmarketcap --paper

# Multi-strategy portfolio
stratequeue deploy --strategy sma.py,momentum.py,mean_revert.py --allocation 0.4,0.35,0.25 --symbol AAPL,MSFT --granularity 1m

# Background deployment for remote management
stratequeue deploy --strategy trend.py --symbol GOOGL --granularity 1m --daemon --duration 480
```

### **🎛️ Management Examples**
```bash
# Deploy in background
stratequeue deploy --strategy sma.py,momentum.py --allocation 0.6,0.4 --granularity 1m --daemon

# Pause risky strategy during volatility
stratequeue pause momentum

# Add new strategy to running system
stratequeue deploy --strategy new_algo.py --granularity 1m --daemon

# Rebalance portfolio
stratequeue rebalance --allocations=0.5,0.3,0.2

# Remove underperforming strategy
stratequeue remove poor_performer --liquidate

# Stop everything gracefully
stratequeue stop
```

### **🔍 Discovery Examples**
```bash
# Explore available options
stratequeue list brokers
stratequeue list granularities

# Check system health
stratequeue status
stratequeue status --broker alpaca

# Setup and configuration
stratequeue setup broker alpaca
stratequeue webui --port 8080
```

## 🔧 Configuration

### **Environment Variables (.env file)**
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

### **Strategy Development**
```python
# my_strategy.py
LOOKBACK = 20  # Historical bars needed

from backtesting import Strategy
from backtesting.lib import crossover
from backtesting.test import SMA

class MyStrategy(Strategy):
    def init(self):
        # Set up indicators
        self.sma = self.I(SMA, self.data.Close, 20)
    
    def next(self):
        # Trading logic
        if self.data.Close[-1] > self.sma[-1]:
            self.buy()
        else:
            self.sell()
```

```bash
# Test your strategy
stratequeue deploy --strategy my_strategy.py --symbol AAPL --granularity 1m
```

## 📈 Real-Time Output

```
🚀 StrateQueue - Live Trading System Started
════════════════════════════════════════════════════════════════════════════════
📊 Mode: MULTI-STRATEGY PORTFOLIO
🎯 Strategies: sma (60%), momentum (40%)
📈 Symbol: AAPL, MSFT
🔌 Data Source: polygon (1h intervals)
💰 Trading: PAPER MODE via Alpaca
🕐 Duration: 240 minutes
════════════════════════════════════════════════════════════════════════════════

🎯 SIGNAL #1 - 2024-06-10 14:30:15 [sma]
📈 BUY AAPL @ $185.42
💰 Allocation: $3,000 (60% of portfolio)
🎯 Confidence: 85%

⏸️  STRATEGY PAUSED - 2024-06-10 14:45:00 [momentum]
📝 Reason: User command via CLI
🔄 Status: Signals stopped, positions maintained

🎯 SIGNAL #2 - 2024-06-10 15:00:22 [sma]  
📉 SELL AAPL @ $186.15
💰 P&L: +$73 (+0.39%)
📊 Portfolio Value: $10,073

▶️  STRATEGY RESUMED - 2024-06-10 15:15:00 [momentum]
📝 Reason: User command via CLI
🔄 Status: Signal generation resumed

⚖️  PORTFOLIO REBALANCED - 2024-06-10 15:30:00
📊 New Allocations: sma (50%), momentum (30%), new_algo (20%)
🔄 Positions redistributed automatically
```

## 🆘 Troubleshooting

### **❌ "No broker detected"**
```bash
# Check your broker configuration
stratequeue status

# Setup Alpaca (easiest broker)
stratequeue setup broker alpaca

# List available brokers
stratequeue list brokers
```

### **❌ "Strategy file not found"**
```bash
# Verify file exists
ls my_strategy.py

# Use absolute path if needed
stratequeue deploy --strategy /full/path/to/my_strategy.py --symbol AAPL --granularity 1m

# Check working directory
pwd
```

### **❌ "Invalid allocation"**
```bash
# Allocations must sum to ≤ 1.0 (100%)
stratequeue deploy --strategy sma.py,momentum.py --allocation 0.6,0.4  # ✅ Good (100%)
stratequeue deploy --strategy sma.py,momentum.py --allocation 0.6,0.3  # ✅ Good (90%)
stratequeue deploy --strategy sma.py,momentum.py --allocation 0.6,0.6  # ❌ Bad (120%)
```

### **❌ "Command not found"**
```bash
# Verify installation
pip show stratequeue

# Reinstall if needed
pip install --upgrade stratequeue[all]

# Check CLI accessibility
which stratequeue
```

## 🎓 Learning Path

### **1. 🧪 Start with Signal Testing**
```bash
# See what signals your strategy generates (safe!)
stratequeue deploy --strategy examples/strategies/sma.py --symbol AAPL --granularity 1m --duration 5
```

### **2. 📄 Add Paper Trading**
```bash
# Test with fake money
stratequeue deploy --strategy examples/strategies/sma.py --symbol AAPL --granularity 1m --paper --duration 30
```

### **3. 📊 Try Multi-Strategy**
```bash
# Run a simple portfolio
stratequeue deploy --strategy examples/strategies/sma.py,examples/strategies/momentum.py --allocation 0.6,0.4 --symbol AAPL --granularity 1m --paper
```

### **4. 🎛️ Learn Real-Time Management**
```bash
# Deploy in background and practice management
stratequeue deploy --strategy sma.py,momentum.py --allocation 0.6,0.4 --daemon

# Practice commands
stratequeue pause momentum
stratequeue resume momentum
stratequeue rebalance --allocations=0.5,0.5
stratequeue stop
```

### **5. 💰 Go Live (When Ready!)**
```bash
# Real money trading (be very careful!)
stratequeue deploy --strategy my_tested_strategy.py --symbol AAPL --granularity 1m --live
```

## 🔗 Advanced Usage

### **📊 System Monitoring**
```bash
# Comprehensive system status
stratequeue status --verbose

# Web dashboard for visual monitoring
stratequeue webui

# Check specific broker health
stratequeue status --broker alpaca
```

### **⚙️ Advanced Configuration**
```bash
# Custom runtime duration
stratequeue deploy --strategy sma.py --symbol AAPL --granularity 1m --duration 480  # 8 hours

# Override strategy lookback period
stratequeue deploy --strategy sma.py --symbol AAPL --granularity 1m --lookback 100

# Verbose logging for debugging
stratequeue deploy --strategy sma.py --symbol AAPL --granularity 1m --verbose

# Custom PID file location for daemon mode
stratequeue deploy --strategy sma.py --daemon --pid-file /custom/path/stratequeue.pid
```

### **🎯 Specialized Deployments**
```bash
# Multi-symbol, single strategy
stratequeue deploy --strategy diversified.py --symbol AAPL,MSFT,GOOGL,TSLA --granularity 1m --paper

# Cross-asset strategies
stratequeue deploy --strategy multi_asset.py --symbol AAPL,BTC,EUR_USD --granularity 1m --data-source polygon,coinmarketcap,forex

# Time-based strategies
stratequeue deploy --strategy market_open.py --symbol SPY --granularity 1m --duration 390  # Full trading day
```

---

## 🌟 Why StrateQueue?

**✅ Production-Ready**: Enterprise-grade CLI with comprehensive command suite  
**✅ Safe by Default**: No-trading mode prevents accidental losses  
**✅ Real-Time Management**: Pause, resume, rebalance without system restarts  
**✅ Multi-Strategy**: Portfolio management with automatic allocation handling  
**✅ Professional UX**: Colorful, intuitive help system and clear error messages  
**✅ Flexible Architecture**: Single strategies to complex multi-asset portfolios  

**Ready to transform your backtesting strategies into live trading systems?** 

```bash
pip install stratequeue[all]
stratequeue deploy --strategy your_strategy.py --symbol AAPL --granularity 1m
```

**Start safe, scale smart, trade professionally.** 🚀📈 