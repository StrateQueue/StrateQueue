# Live Trading Infrastructure

A comprehensive live trading system that converts backtesting.py strategies into real-time signal generators with support for multiple data sources and optional trading execution.

## System Overview

This system provides:
- **Strategy Conversion**: Automatically converts backtesting.py strategies to live signal generators
- **Multiple Data Sources**: Support for Polygon.io, CoinMarketCap, and demo data
- **Real-time Processing**: Live data ingestion and signal generation
- **Trading Execution**: Optional integration with Alpaca for actual trading
- **Flexible Granularity**: Support for various timeframes (1s, 1m, 5m, 1h, 1d, etc.)
- **Automatic Lookback**: Intelligent calculation of required historical data

## Quick Start

### 1. Installation

```bash
pip3.10 install -r requirements.txt
```

### 2. Basic Usage (Demo Mode)

```bash
# Run with SMA strategy on demo data
python3.10 main.py --strategy examples/strategies/sma.py --symbols AAPL,MSFT --data-source demo

# Run with custom duration and granularity
python3.10 main.py --strategy examples/strategies/random.py --symbols ETH --data-source coinmarketcap --granularity 5m --duration 30
```

### 3. Production Usage (Real Data)

```bash
# Using Polygon.io (requires API key in .env)
python3.10 main.py --strategy examples/strategies/sma.py --symbols AAPL,MSFT --data-source polygon --granularity 1m

# Using CoinMarketCap for crypto (requires API key in .env)
python3.10 main.py --strategy examples/strategies/sma.py --symbols BTC,ETH --data-source coinmarketcap --granularity 1h
```

## Configuration

### Environment Variables (.env file)

Create a `.env` file in the root directory:

```env
# Polygon.io API (for stock/forex data)
POLYGON_API_KEY=your_polygon_api_key

# CoinMarketCap API (for crypto data)
CMC_API_KEY=your_coinmarketcap_api_key

# Alpaca Trading API (for live trading execution)
ALPACA_API_KEY=your_alpaca_api_key
ALPACA_SECRET_KEY=your_alpaca_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Use paper trading by default

# Optional: Default symbols
TRADING_SYMBOLS=AAPL,MSFT,GOOGL
HISTORICAL_DAYS=30
```

### Data Sources

#### 1. Demo Data (`--data-source demo`)
- **Purpose**: Testing and development
- **Features**: Simulated market data with realistic price movements
- **Granularities**: All supported (1s, 30s, 1m, 5m, 15m, 30m, 1h, 4h, 1d)
- **No API key required**

#### 2. Polygon.io (`--data-source polygon`)
- **Purpose**: Real stock, forex, and crypto data
- **Features**: High-quality, real-time and historical data
- **Granularities**: Very flexible - supports most timeframes
- **Requires**: POLYGON_API_KEY in .env

#### 3. CoinMarketCap (`--data-source coinmarketcap`)
- **Purpose**: Cryptocurrency data
- **Features**: Comprehensive crypto market data
- **Granularities**: 1m, 5m, 15m, 30m, 1h, 2h, 6h, 12h, 1d
- **Requires**: CMC_API_KEY in .env

## Command Line Arguments

### Basic Usage
```bash
python3.10 main.py --strategy <path> --symbols <symbols> [options]
```

### Arguments

| Argument | Description | Example |
|----------|-------------|---------|
| `--strategy` | Path to strategy file | `examples/strategies/sma.py` |
| `--symbols` | Comma-separated symbols | `AAPL,MSFT,TSLA` |
| `--data-source` | Data source to use | `demo`, `polygon`, `coinmarketcap` |
| `--granularity` | Data timeframe | `1s`, `1m`, `5m`, `1h`, `1d` |
| `--lookback` | Override auto-calculated lookback | `50` |
| `--duration` | Runtime in minutes | `60` |
| `--enable-trading` | Enable live trading execution | (flag) |
| `--verbose` | Enable detailed logging | (flag) |
| `--list-granularities` | Show supported granularities | (flag) |

### Examples

```bash
# List supported granularities
python3.10 main.py --list-granularities

# Run SMA strategy on AAPL with 5-minute bars for 2 hours
python3.10 main.py --strategy examples/strategies/sma.py --symbols AAPL --granularity 5m --duration 120

# Run with live trading enabled (requires Alpaca setup)
python3.10 main.py --strategy examples/strategies/sma.py --symbols AAPL --data-source polygon --enable-trading

# Multiple symbols with custom lookback
python3.10 main.py --strategy examples/strategies/sma.py --symbols AAPL,MSFT,GOOGL --lookback 100
```

## Creating Strategies

### Strategy Format

Strategies should follow the backtesting.py format. The system automatically converts them to signal generators.

#### Example: SMA Crossover Strategy

```python
# examples/strategies/sma.py

# Strategy Configuration
LOOKBACK = 20  # Required historical data

from backtesting import Strategy
from backtesting.lib import crossover
from backtesting.test import SMA

class SmaCross(Strategy):
    n1 = 10  # Short moving average
    n2 = 20  # Long moving average

    def init(self):
        close = self.data.Close
        self.sma1 = self.I(SMA, close, self.n1)
        self.sma2 = self.I(SMA, close, self.n2)

    def next(self):
        if crossover(self.sma1, self.sma2):
            self.position.close()
            self.buy(size=0.1)  # 10% of capital
        elif crossover(self.sma2, self.sma1):
            self.position.close()
            self.sell()
```

### Strategy Requirements

1. **LOOKBACK Variable**: Define the minimum required historical bars
2. **Strategy Class**: Inherit from backtesting.Strategy
3. **init() Method**: Initialize indicators
4. **next() Method**: Define trading logic

### Signal Conversion

The system automatically converts:
- `self.buy()` → BUY signal
- `self.sell()` → SELL signal  
- `self.position.close()` → CLOSE signal
- No action → HOLD signal

## System Architecture

### Core Components

1. **StrategyLoader**: Dynamically loads and converts strategies
2. **LiveTradingSystem**: Main orchestrator
3. **Data Ingestion**: Multi-source data pipeline
4. **Signal Extractor**: Converts strategies to signal generators
5. **Alpaca Executor**: Optional trading execution

### Data Flow

```
Strategy File → StrategyLoader → SignalExtractor → Live Signals → [Optional: Trading Execution]
     ↑                                ↑
Historical Data ← Data Ingestion ← Real-time Data
```

## Live Trading (Optional)

### Setup for Live Trading

1. **Configure Alpaca API** in `.env`:
   ```env
   ALPACA_API_KEY=your_api_key
   ALPACA_SECRET_KEY=your_secret_key
   ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Paper trading
   ```

2. **Enable trading** with `--enable-trading` flag:
   ```bash
   python3.10 main.py --strategy examples/strategies/sma.py --symbols AAPL --enable-trading
   ```

### Trading Features

- **Paper Trading**: Default mode for safe testing
- **Position Management**: Automatic position sizing and management
- **Account Monitoring**: Real-time portfolio tracking
- **Risk Controls**: Built-in safeguards and validation

## Monitoring and Logging

### Signal Display
```
🎯 SIGNAL #1 - 2024-01-15 10:30:00
Symbol: AAPL
Action: 📈 BUY
Price: $185.45
Confidence: 80.0%
Indicators:
  • sma1: 184.20
  • sma2: 183.15
```

### Trading Summary
```
📈 TRADING SUMMARY:
  Portfolio Value: $10,245.67
  Cash: $8,234.21
  Day Trades: 2

🎯 ACTIVE POSITIONS:
  • AAPL: 10 shares @ $185.45 (P&L: $12.34)
```

### Log Files
- **trading_system.log**: Detailed system logs
- **Console Output**: Real-time signals and status

## Troubleshooting

### Common Issues

1. **"Strategy file not found"**
   - Check the path to your strategy file
   - Use relative paths from project root

2. **"Invalid granularity"**
   - Run `python3.10 main.py --list-granularities`
   - Check data source compatibility

3. **"API key required"**
   - Add required API keys to `.env` file
   - Verify environment variable names

4. **"No data available"**
   - Check symbol names and market hours
   - Verify API key permissions

### Debug Mode

```bash
# Enable verbose logging
python3.10 main.py --strategy examples/strategies/sma.py --symbols AAPL --verbose
```

## Performance Notes

- **Demo Mode**: Instant startup, unlimited symbols
- **Real Data**: 1-2 second startup per symbol for historical data
- **Memory Usage**: ~10MB base + ~1MB per symbol per 1000 bars
- **CPU Usage**: Minimal during steady operation

## File Structure

```
Live-Trading-Infrastructure/
├── main.py                     # Main entry point
├── requirements.txt            # Dependencies
├── .env                        # Configuration (create this)
├── examples/
│   └── strategies/
│       ├── sma.py             # SMA crossover example
│       └── random.py          # Random strategy example
└── src/
    └── trading_system/
        ├── __init__.py        # Package exports
        ├── data_ingestion.py  # Data source factory
        ├── signal_extractor.py # Strategy → Signal conversion
        ├── alpaca_execution.py # Trading execution
        ├── config.py          # Configuration management
        ├── granularity.py     # Time granularity handling
        └── data_sources/      # Data source implementations
```

## Advanced Usage

### Custom Strategies
Place your strategy files anywhere and reference them:
```bash
python3.10 main.py --strategy /path/to/my_strategy.py --symbols AAPL
```

### Multiple Timeframes
Run multiple instances with different granularities:
```bash
# Terminal 1: Short-term signals
python3.10 main.py --strategy sma.py --symbols AAPL --granularity 1m

# Terminal 2: Long-term signals  
python3.10 main.py --strategy sma.py --symbols AAPL --granularity 1h
```

### Batch Processing
```bash
# Process multiple strategies
for strategy in examples/strategies/*.py; do
    python3.10 main.py --strategy "$strategy" --symbols AAPL --duration 10
done
```

---

**Note**: Always test with demo data first, then paper trading before enabling live trading with real money. 