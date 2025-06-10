# Statistics Documentation

This directory contains documentation for the Statistical Tracking System in the Live Trading Infrastructure.

## 📊 Overview

The statistics system provides real-time tracking and analysis of trading performance across multiple strategies and portfolios. It uses a modular, plugin-based architecture that makes adding new metrics straightforward.

## 📚 Documentation

### [📖 Statistical Trackers Guide](STATISTICAL_TRACKERS_GUIDE.md)
**Comprehensive guide** for implementing new statistical trackers.

- Complete step-by-step implementation guide
- Architecture explanation and design patterns
- Real-world examples (Volume, Drawdown, Win/Loss)
- Best practices and testing templates
- Advanced features and integration points

### [⚡ Quick Reference](QUICK_REFERENCE.md)
**Condensed reference** for experienced developers.

- TL;DR checklist for adding new trackers
- Code templates and snippets
- Essential patterns and common examples
- Gotchas and troubleshooting tips

## 🎯 Current Implementations

### Built-in Trackers

| Tracker | Purpose | Key Metrics |
|---------|---------|------------|
| **PnLTracker** | Profit & Loss tracking | Realized/Unrealized P&L, Commissions, Net P&L |
| **WinLossTracker** | Win/Loss analysis | Win rates, Profit factors, Streak tracking |

### Available Statistics

#### Portfolio-Level
- Total P&L across all strategies
- Portfolio win rate and profit factor
- Total trading volume and trade count
- Maximum drawdowns and recoveries

#### Strategy-Level  
- Individual strategy performance
- Per-strategy P&L breakdown
- Strategy-specific win/loss metrics
- Open positions by strategy

## 🏗️ Architecture

```
StatisticsManager
├── PnLTracker (realized/unrealized P&L)
├── WinLossTracker (win rates, streaks)
└── YourTracker (your custom metrics)
```

**Key Features:**
- **Event-driven**: Automatic processing of all trade events
- **Multi-strategy**: Built-in support for portfolio management
- **Error isolation**: Trackers can't affect each other
- **Unified API**: Consistent interface across all trackers
- **Real-time**: Live updates during trading

## 🚀 Quick Start

1. **View existing trackers** for reference:
   - `src/trading_system/statistics/pnl_tracker.py`
   - `src/trading_system/statistics/win_loss_tracker.py`

2. **Create your tracker** following the [Quick Reference](QUICK_REFERENCE.md)

3. **Test integration** with the StatisticsManager

4. **Verify output** in live system displays

## 💡 Use Cases

### Performance Analysis
- Track strategy effectiveness over time
- Compare performance across different strategies
- Identify best/worst performing periods

### Risk Management  
- Monitor drawdowns and recovery patterns
- Track position sizes and exposure
- Analyze win/loss patterns for risk assessment

### Portfolio Optimization
- Compare strategy allocations
- Rebalance based on performance metrics
- Optimize position sizing based on historical data

### Compliance & Reporting
- Generate performance reports
- Track commission costs
- Maintain trade history for auditing

## 🔧 Integration

The statistics system integrates automatically with:

- **Live Trading System**: Real-time processing of trades
- **Multi-Strategy Runner**: Portfolio-level aggregation  
- **Backtesting Engine**: Historical performance analysis
- **Display Manager**: Formatted output for monitoring
- **API Endpoints**: Programmatic access to statistics

## 📈 Example Output

```
📊 STATISTICS SUMMARY
==================================================
💰 PnL Tracker:
  Portfolio P&L: $1,250.00
  Net P&L: $1,225.00
  Completed Trades: 15

🎯 Win/Loss Tracker:
  Portfolio Win Rate: 66.7%
  Total Trades: 15
  Profit Factor: 2.45

📈 Strategy Breakdown:
  • momentum_strategy:
    P&L: $850.00
    Win Rate: 70.0%
    Trades: 10
  • mean_reversion:
    P&L: $400.00  
    Win Rate: 60.0%
    Trades: 5
==================================================
```

## 🤝 Contributing

When adding new trackers:

1. Follow the established patterns in existing implementations
2. Include comprehensive logging for debugging
3. Add unit tests for your tracker
4. Update documentation with your new metrics
5. Consider both portfolio and strategy-level analytics

## 📧 Support

For questions about the statistics system:
- Review existing implementations for patterns
- Check the [troubleshooting section](STATISTICAL_TRACKERS_GUIDE.md#common-gotchas) in the guide
- Ensure your tracker follows the BaseTracker interface
- Verify registration in StatisticsManager

---

**Next Steps:** Start with the [Quick Reference](QUICK_REFERENCE.md) for immediate implementation, or dive into the [complete guide](STATISTICAL_TRACKERS_GUIDE.md) for comprehensive understanding. 