# Stratequeue

**Professional Multi-Strategy Live Trading Infrastructure**

Transform your backtesting.py strategies into a sophisticated multi-strategy live trading system with real-time signal generation, portfolio management, and multi-broker execution.

## 🚀 Key Features

### **Multi-Strategy Portfolio Management**
- **Run multiple strategies simultaneously** with intelligent capital allocation
- **Strategy isolation** - each strategy operates independently with dedicated capital
- **Conflict resolution** - automatic handling of overlapping symbol trades
- **Performance tracking** per strategy and overall portfolio

### **Multi-Broker Trading Infrastructure** 
- **Extensible broker factory** - easily add new trading platforms
- **Multiple broker support** - Alpaca (implemented), Interactive Brokers, TD Ameritrade (ready for implementation)
- **Unified trading interface** - consistent API across all brokers
- **Auto-detection** - automatically detects available broker credentials

### **Professional Trading Infrastructure** 
- **Real-time signal generation** from backtesting.py strategies
- **Multiple data sources**: Polygon.io, CoinMarketCap, and realistic demo data
- **Flexible timeframes**: 1s to 1d granularities
- **Paper & live trading** with explicit mode control
- **Risk management** with position sizing and portfolio controls

### **Easy Installation & Usage**
- **Professional packaging** - install via pip like any Python package
- **Intuitive CLI interface** with explicit trading mode controls
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
# Demo trading with one strategy (paper trading by default)
stratequeue --strategy examples/strategies/sma.py --symbols AAPL --data-source demo

# Paper trading with real data (safe)
stratequeue --strategy examples/strategies/sma.py --symbols AAPL --data-source polygon --paper

# Live trading with real money (use with caution!)
stratequeue --strategy examples/strategies/sma.py --symbols AAPL --data-source polygon --live

# Signals only (no trading execution)
stratequeue --strategy examples/strategies/sma.py --symbols AAPL --no-trading
```

### Multi-Strategy Portfolio
```bash
# Run multiple strategies simultaneously (paper trading)
stratequeue --strategies strategies.txt --symbols AAPL,MSFT,BTC --data-source demo --paper

# Multi-strategy with live trading
stratequeue --strategies strategies.txt --symbols AAPL,MSFT --live

# Multi-strategy signals only
stratequeue --strategies strategies.txt --symbols AAPL,MSFT --no-trading
```

### Broker-Specific Examples
```bash
# Specify broker explicitly (paper trading)
stratequeue --strategy sma.py --symbols AAPL --broker alpaca --paper

# Auto-detect broker from environment
stratequeue --strategy sma.py --symbols AAPL --live

# Check available brokers
stratequeue --list-brokers

# Check broker environment status
stratequeue --broker-status

# Get broker setup instructions
stratequeue --broker-setup alpaca
```

### Short Command Alias
```bash
# Use 'sq' for quick access
sq --strategy my_algo.py --symbols TSLA --paper --duration 30
```

## 🏦 Broker Factory Architecture

### Supported Brokers

| Broker | Status | Paper Trading | Live Trading | Asset Classes |
|--------|--------|---------------|--------------|---------------|
| **Alpaca** | ✅ Implemented | ✅ | ✅ | Stocks, ETFs, Crypto |
| **Interactive Brokers** | 📋 Documented | 📋 | 📋 | Stocks, Options, Futures, Forex |
| **TD Ameritrade** | 📋 Documented | 📋 | 📋 | Stocks, Options, ETFs |
| **Coinbase Pro** | 📋 Documented | 📋 | 📋 | Cryptocurrency |

### Adding New Brokers

The system uses an extensible broker factory pattern that makes adding new brokers straightforward:

```python
# Example: Adding a new broker
from stratequeue.brokers.base import BaseBroker, BrokerConfig

class MyBroker(BaseBroker):
    def connect(self) -> bool:
        # Implement connection logic
        pass
    
    def execute_order(self, signal, portfolio_manager):
        # Implement order execution
        pass
    
    def get_account_info(self):
        # Implement account information retrieval
        pass

# Register with factory
from stratequeue.brokers import BrokerFactory
BrokerFactory.register_broker('mybroker', MyBroker)
```

### Broker Auto-Detection

The system automatically detects available brokers from environment variables:

```bash
# Check what brokers are detected
stratequeue --broker-status

# Example output:
# ✅ Alpaca: Paper trading credentials detected
# ❌ Interactive Brokers: No credentials found
# ❌ TD Ameritrade: No credentials found
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
| `stratequeue[trading]` | + Broker APIs | Live/paper trading |
| `stratequeue[backtesting]` | + backtesting.py | Strategy development |
| `stratequeue[analytics]` | + scipy, ta-lib | Advanced analysis |
| `stratequeue[all]` | Everything | Full featured setup |

## 📊 Trading Mode Controls

### Explicit Trading Mode Selection

The CLI uses explicit flags for trading mode control:

```bash
# Paper trading (default - safe for testing)
stratequeue --strategy sma.py --symbols AAPL --paper

# Live trading (real money - shows warnings)
stratequeue --strategy sma.py --symbols AAPL --live

# Signals only (no trading execution)
stratequeue --strategy sma.py --symbols AAPL --no-trading
```

### Trading Mode Examples

```bash
# Strategy Development - signals only
stratequeue --strategy my_new_algo.py --symbols AAPL --data-source demo --no-trading

# Testing - paper trading with real data
stratequeue --strategy tested_algo.py --symbols AAPL --data-source polygon --paper

# Production - live trading (after thorough testing)
stratequeue --strategy proven_algo.py --symbols AAPL --data-source polygon --live
```

### Safety Features

- **Paper trading by default** - safer for new users
- **Live trading warnings** - clear alerts when using real money
- **Broker credential validation** - ensures proper setup before trading
- **Mode-specific error messages** - clear guidance for credential issues

## 🔧 Configuration

### Environment Setup (.env)

#### Data Sources
```env
# Data Sources
POLYGON_API_KEY=your_polygon_key
CMC_API_KEY=your_coinmarketcap_key
```

#### Broker Credentials

**Alpaca Trading:**
```env
# Paper Trading Credentials (recommended for testing)
PAPER_KEY=your_alpaca_paper_key
PAPER_SECRET=your_alpaca_paper_secret
PAPER_ENDPOINT=https://paper-api.alpaca.markets

# Live Trading Credentials (use with caution)
ALPACA_API_KEY=your_alpaca_live_key
ALPACA_SECRET_KEY=your_alpaca_live_secret
ALPACA_BASE_URL=https://api.alpaca.markets
```

**Interactive Brokers (future implementation):**
```env
# IB Credentials
IB_HOST=127.0.0.1
IB_PORT=7497  # Paper: 7497, Live: 7496
IB_CLIENT_ID=1
IB_ACCOUNT=your_ib_account
```

**TD Ameritrade (future implementation):**
```env
# TD Ameritrade Credentials
TDA_CLIENT_ID=your_client_id
TDA_REFRESH_TOKEN=your_refresh_token
TDA_ACCOUNT_ID=your_account_id
```

### Credential Priority

The system intelligently selects credentials:

1. **Paper Trading Mode (`--paper`)**:
   - Prefers: `PAPER_KEY`, `PAPER_SECRET`, `PAPER_ENDPOINT`
   - Fallback: Live credentials with paper endpoint override

2. **Live Trading Mode (`--live`)**:
   - Requires: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_BASE_URL`
   - No fallback for safety

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
│ Signal Extractor│    │ Real-time Data   │    │ Broker Factory  │
│                 │    │ Processing       │    │                 │
│ • Convert Logic │    │                  │    │ • Alpaca        │
│ • Generate Sigs │    │ • Live Updates   │    │ • Inter. Brokers│
│ • Multi-Strategy│    │ • Historical     │    │ • TD Ameritrade │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Broker Factory Architecture

The system uses a **modular broker factory pattern** for extensible trading platform support:

```
🏭 BROKER FACTORY ARCHITECTURE

┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Unified Trading   │────▶│   Broker Factory    │────▶│   Broker Registry   │
│      Interface      │     │                     │     │                     │
│                     │     │ • Auto-detection    │     │ • Alpaca ✅         │
│ • execute_order()   │     │ • Credential Mgmt   │     │ • IB (planned)      │
│ • get_account()     │     │ • Config Creation   │     │ • TDA (planned)     │
│ • connect()         │     │ • Error Handling    │     │ • Coinbase (planned)│
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
         │                           │                           │
         ▼                           ▼                           ▼
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Signal Context    │     │   Config Context    │     │ Implementation Layer│
│                     │     │                     │     │                     │
│ • Strategy ID       │     │ • Paper/Live Mode   │     │ • Native APIs       │
│ • Portfolio Mgr     │     │ • Credentials       │     │ • Order Translation │
│ • Capital Limits    │     │ • Environment       │     │ • Error Mapping     │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

### Order Execution Architecture

The system uses a **context-aware order execution architecture** that follows trading industry standards:

```
📊 TRADING SIGNAL               🧠 PORTFOLIO CONTEXT                💰 ORDER EXECUTION
┌─────────────────┐            ┌─────────────────┐               ┌─────────────────┐
│   Pure Signal   │            │ Portfolio Mgr   │               │ Context-Aware   │
│                 │            │                 │               │ Broker Executor │
│ • Signal Type   │            │ • Strategy      │               │                 │
│ • Price/Size    │──────────▶ │   Allocations   │──────────────▶│ • Market Buy    │
│ • Strategy ID   │            │ • Capital Limits│               │ • Market Sell   │
│ • Pure Intent   │            │ • Position      │               │ • Limit Orders  │
│                 │            │   Tracking      │               │ • Stop Orders   │
└─────────────────┘            └─────────────────┘               └─────────────────┘
```

**Key Architecture Principles:**

1. **Clean Separation**: Signals remain pure trading intent, execution handles allocation
2. **Context-Aware Executors**: Order executors have portfolio manager access for proper capital allocation
3. **Strategy-Specific Allocation**: Each strategy uses only its allocated capital, not full account value
4. **Broker Abstraction**: Unified interface across all trading platforms
5. **Industry Standard**: Matches Bloomberg EMSX, FIX Protocol patterns where execution engines have risk context

**Example Capital Allocation:**
```python
# Account Value: $100,000
# Strategy Allocations:
#   - sma_cross: 40% = $40,000
#   - momentum: 35% = $35,000  
#   - mean_revert: 25% = $25,000

# Signal: sma_cross BUY with size=0.5 (50% of strategy allocation)
# Order Amount: $40,000 × 0.5 = $20,000 (NOT $100,000 × 0.5 = $50,000)
```

This architecture ensures:
- ✅ **Proper Capital Allocation**: Each strategy respects its limits
- ✅ **Multi-Strategy Safety**: No strategy can exceed its allocation
- ✅ **Broker Flexibility**: Easy to add new trading platforms
- ✅ **Scalable Design**: Easy to add new order types and risk controls
- ✅ **Production Ready**: Follows institutional trading system patterns

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
| `--paper` | Paper trading (default) | `--paper` |
| `--live` | Live trading | `--live` |
| `--no-trading` | Signals only | `--no-trading` |
| `--broker` | Specify broker | `--broker alpaca` |
| `--duration` | Runtime in minutes | `--duration 120` |
| `--verbose` | Detailed logging | `--verbose` |

### Trading Mode Examples
```bash
# Development - signals only
stratequeue --strategy algo.py --symbols AAPL --no-trading

# Testing - paper trading  
stratequeue --strategy algo.py --symbols AAPL --paper

# Production - live trading (with warnings)
stratequeue --strategy algo.py --symbols AAPL --live
```

### Broker Management
```bash
# List supported brokers and features
stratequeue --list-brokers

# Check broker environment status
stratequeue --broker-status

# Get setup instructions
stratequeue --broker-setup alpaca
stratequeue --broker-setup all

# Specify broker explicitly
stratequeue --strategy algo.py --symbols AAPL --broker alpaca --paper
```

### Advanced Examples
```bash
# List available granularities
stratequeue --list-granularities

# Custom granularity and lookback
stratequeue --strategy algo.py --symbols AAPL --granularity 5m --lookback 100 --paper

# Multi-strategy with specific duration
stratequeue --strategies portfolio.txt --symbols AAPL,MSFT --duration 480 --live  # 8 hours

# Verbose logging for debugging
stratequeue --strategy debug_algo.py --symbols TSLA --verbose --paper
```

## 🎯 Use Cases

### **Quantitative Research**
```bash
# Quick strategy validation (signals only)
stratequeue --strategy research_idea.py --symbols SPY --data-source demo --no-trading --duration 10
```

### **Strategy Testing**
```bash
# Paper trading with real data
stratequeue --strategy new_algo.py --symbols AAPL --data-source polygon --paper --duration 60
```

### **Portfolio Management**
```bash
# Multi-strategy portfolio with paper trading
stratequeue --strategies diversified_portfolio.txt --symbols AAPL,MSFT,GOOGL,TSLA --paper

# Live multi-strategy trading (production)
stratequeue --strategies tested_portfolio.txt --symbols AAPL,MSFT --live
```

### **Crypto Trading**
```bash
# Crypto strategy with CoinMarketCap data (paper trading)
stratequeue --strategy crypto_momentum.py --symbols BTC,ETH --data-source coinmarketcap --paper

# Live crypto trading
stratequeue --strategy proven_crypto.py --symbols BTC,ETH --data-source coinmarketcap --live
```

### **Multi-Broker Setup**
```bash
# Test with different brokers
stratequeue --strategy algo.py --symbols AAPL --broker alpaca --paper
stratequeue --strategy algo.py --symbols AAPL --broker ib --paper  # Future

# Auto-detect best available broker
stratequeue --strategy algo.py --symbols AAPL --paper  # Uses detected broker
```

## 🔍 Monitoring & Output

### Real-time Signal Display
```
🎯 MULTI-STRATEGY SIGNALS - 2024-06-09 14:30:00

📈 sma_short → AAPL: BUY @ $185.45 (Conf: 85%)
  └─ Allocation: $2,500 (25% of strategy capital)
  └─ Broker: Alpaca (Paper Trading)
  
📉 momentum_1h → MSFT: SELL @ $340.12 (Conf: 78%)
  └─ Allocation: $1,800 (18% of strategy capital)
  └─ Broker: Alpaca (Paper Trading)

📊 PORTFOLIO STATUS:
  • Total Value: $12,450.67
  • Active Strategies: 3/3
  • Open Positions: 5
  • Available Cash: $3,234.21
  • Trading Mode: PAPER
```

### Broker Status Display
```bash
$ stratequeue --broker-status

🏦 BROKER ENVIRONMENT STATUS:
┌─────────────────────┬─────────────┬─────────────┬─────────────────┐
│ Broker              │ Paper Creds │ Live Creds  │ Status          │
├─────────────────────┼─────────────┼─────────────┼─────────────────┤
│ Alpaca              │ ✅ Valid    │ ❌ Missing  │ Paper Ready     │
│ Interactive Brokers │ ❌ Missing  │ ❌ Missing  │ Not Configured  │
│ TD Ameritrade       │ ❌ Missing  │ ❌ Missing  │ Not Configured  │
└─────────────────────┴─────────────┴─────────────┴─────────────────┘

💡 Run 'stratequeue --broker-setup <broker>' for setup instructions
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
💰 Trading Mode: PAPER via Alpaca
```

## 🚨 Important Notes

### **Trading Mode Safety**
- **Paper trading by default** - system defaults to paper trading for safety
- **Explicit live trading** - must use `--live` flag for real money trading
- **Live trading warnings** - clear alerts when using real money
- **Credential validation** - ensures proper setup before trading

### **Risk Management**
- **Always test with `--no-trading` first** - validate strategy logic
- **Use paper trading extensively** - test with `--paper` before going live
- **Start with small position sizes** - use conservative allocations initially
- **Monitor multi-strategy interactions** - watch for unexpected correlations

### **Best Practices**
- **Strategy isolation**: Each strategy should be independent
- **Capital allocation**: Don't over-allocate to any single strategy
- **Regular monitoring**: Watch for unexpected correlations
- **Gradual scaling**: Increase allocation as strategies prove themselves
- **Broker diversification**: Consider using multiple brokers for redundancy

### **Broker-Specific Notes**
- **Alpaca**: Supports both paper and live trading, good for US stocks/ETFs
- **Interactive Brokers**: Planned support for global markets, options, futures
- **TD Ameritrade**: Planned support for US markets with good options support

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
stratequeue --strategy test.py --symbols AAPL --verbose --no-trading
```

### Trading Issues
```bash
# Check broker status
stratequeue --broker-status

# Get setup instructions
stratequeue --broker-setup alpaca

# Test with paper trading first
stratequeue --strategy test.py --symbols AAPL --paper --verbose

# Test signals only
stratequeue --strategy test.py --symbols AAPL --no-trading
```

### Multi-Strategy Issues
- **Capital conflicts**: Check strategy allocations sum to ≤ 1.0
- **Symbol conflicts**: Monitor which strategies trade overlapping symbols
- **Performance attribution**: Use `--verbose` to track per-strategy signals
- **Broker limitations**: Ensure your broker supports all required symbols

### Broker-Specific Troubleshooting

**Alpaca Issues:**
```bash
# Validate credentials
stratequeue --broker-setup alpaca

# Check API key permissions
# Ensure keys have trading permissions (not just market data)

# Paper vs Live confusion
# Use PAPER_KEY/PAPER_SECRET for paper trading
# Use ALPACA_API_KEY/ALPACA_SECRET_KEY for live trading
```

## 🔗 Additional Resources

- **Strategy Examples**: See `examples/strategies/` directory
- **Configuration Templates**: Sample multi-strategy configs included
- **Broker Integration Guide**: Detailed guide for adding new brokers
- **API Documentation**: Auto-generated docs from docstrings
- **Community**: GitHub issues for support and feature requests

---

**Stratequeue** - Professional multi-strategy trading infrastructure with extensible broker support for Python developers. 