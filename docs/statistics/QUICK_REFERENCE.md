# Statistical Trackers Quick Reference

This is a condensed reference for quickly adding new statistical trackers. For detailed explanations, see [STATISTICAL_TRACKERS_GUIDE.md](STATISTICAL_TRACKERS_GUIDE.md).

## TL;DR Checklist

- [ ] Create `src/trading_system/statistics/your_tracker.py`
- [ ] Register in `StatisticsManager._initialize_trackers()`
- [ ] Add import to `statistics_manager.py`
- [ ] Export in `statistics/__init__.py`
- [ ] Export in main `__init__.py`
- [ ] Optional: Add display formatting

## Quick Template

```python
# src/trading_system/statistics/your_tracker.py
from .base_tracker import BaseTracker, TradeEvent
from typing import Dict, Any, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class YourTracker(BaseTracker):
    def __init__(self):
        super().__init__()
        self.your_data: Dict[str, YourType] = defaultdict(YourType)
        logger.info("Your Tracker initialized")
    
    def on_trade_executed(self, trade_event: TradeEvent):
        strategy_id = trade_event.strategy_id
        # Process trade_event and update self.your_data[strategy_id]
        
    def on_portfolio_update(self, strategy_id: str, portfolio_value: float):
        # Optional: handle portfolio updates
        pass
    
    def get_current_stats(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
        if strategy_id:
            return self._get_strategy_stats(strategy_id)
        else:
            return self._get_all_strategies_stats()
    
    def _get_strategy_stats(self, strategy_id: str) -> Dict[str, Any]:
        return {
            'strategy_id': strategy_id,
            'your_metric': self.your_data[strategy_id],
        }
    
    def _get_all_strategies_stats(self) -> Dict[str, Any]:
        all_strategies = set(self.your_data.keys())
        strategy_stats = {}
        portfolio_total = 0
        
        for strategy_id in all_strategies:
            stats = self._get_strategy_stats(strategy_id)
            strategy_stats[strategy_id] = stats
            portfolio_total += stats['your_metric']
        
        return {
            'strategies': strategy_stats,
            'portfolio_summary': {
                'total_your_metric': portfolio_total,
            }
        }
    
    def get_summary(self) -> Dict[str, Any]:
        stats = self._get_all_strategies_stats()
        return {
            'tracker_type': 'YourTracker',
            'total_strategies': len(stats['strategies']),
            'your_summary': stats['portfolio_summary']['total_your_metric'],
        }
    
    def reset(self):
        self.your_data.clear()
        logger.info("Your Tracker reset")
```

## Registration Code Snippets

### 1. StatisticsManager Registration

```python
# In src/trading_system/statistics/statistics_manager.py

# Add import
from .your_tracker import YourTracker

# In _initialize_trackers method
self.your_tracker = YourTracker()
self.trackers.append(self.your_tracker)

# Optional convenience method
def get_your_stats(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
    return self.your_tracker.get_current_stats(strategy_id)
```

### 2. Module Exports

```python
# In src/trading_system/statistics/__init__.py
from .your_tracker import YourTracker

__all__ = [
    'StatisticsManager',
    'PnLTracker',
    'WinLossTracker',
    'YourTracker',  # Add this
    'BaseTracker'
]
```

### 3. Main Module Exports

```python
# In src/trading_system/__init__.py
from .statistics import StatisticsManager, PnLTracker, WinLossTracker, YourTracker, BaseTracker

# In __all__ list
"YourTracker",
```

## Essential Patterns

### Strategy-Centric Data
```python
# ✅ Always organize by strategy_id
self.metrics: Dict[str, MetricType] = defaultdict(MetricType)

# ❌ Never use global metrics  
self.global_metric = 0
```

### Dual-Mode Stats
```python
def get_current_stats(self, strategy_id: Optional[str] = None):
    if strategy_id:
        return self._get_strategy_stats(strategy_id)    # Individual
    else:
        return self._get_all_strategies_stats()         # Portfolio
```

### Portfolio Aggregation
```python
def _get_all_strategies_stats(self):
    strategy_stats = {}
    portfolio_total = 0
    
    for strategy_id in all_strategies:
        stats = self._get_strategy_stats(strategy_id)
        strategy_stats[strategy_id] = stats
        portfolio_total += stats['metric']  # Aggregate here
    
    return {
        'strategies': strategy_stats,       # Individual breakdown
        'portfolio_summary': {              # Portfolio totals
            'total_metric': portfolio_total
        }
    }
```

## Display Integration (Optional)

```python
# In StatisticsManager.display_summary() method
elif tracker_name == 'YourTracker':
    detailed_stats = self.your_tracker.get_current_stats()
    portfolio = detailed_stats.get('portfolio_summary', {})
    
    lines.append(f"📊 Your Tracker:")
    lines.append(f"  Your Metric: {portfolio.get('total_your_metric', 0):.2f}")
    
    strategies = detailed_stats.get('strategies', {})
    if strategies:
        lines.append(f"📈 Strategy Breakdown:")
        for strategy_id, stats in strategies.items():
            lines.append(f"  • {strategy_id}: {stats.get('your_metric', 0):.2f}")
```

## Common Examples

### Volume Tracker
```python
def on_trade_executed(self, trade_event: TradeEvent):
    volume = trade_event.quantity * trade_event.price
    self.volume_by_strategy[trade_event.strategy_id] += volume
```

### Count Tracker
```python
def on_trade_executed(self, trade_event: TradeEvent):
    self.trade_count[trade_event.strategy_id] += 1
```

### Win Rate Tracker
```python
def _record_trade_outcome(self, strategy_id: str, pnl: float):
    if pnl > 0:
        self.wins[strategy_id] += 1
    else:
        self.losses[strategy_id] += 1
```

## Testing Template

```python
import unittest
from datetime import datetime
from src.trading_system.statistics.base_tracker import TradeEvent
from src.trading_system.statistics.your_tracker import YourTracker

class TestYourTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = YourTracker()
    
    def test_basic_functionality(self):
        trade_event = TradeEvent(
            timestamp=datetime.now(),
            strategy_id="test",
            symbol="AAPL", 
            action="buy",
            quantity=100,
            price=150.0
        )
        
        self.tracker.on_trade_executed(trade_event)
        stats = self.tracker.get_current_stats("test")
        
        self.assertEqual(stats['strategy_id'], "test")
        # Add your assertions here
```

## Key Trade Event Fields

```python
trade_event.timestamp      # datetime
trade_event.strategy_id    # str - ALWAYS organize by this
trade_event.symbol         # str - e.g., "AAPL"
trade_event.action         # str - "buy" or "sell"
trade_event.quantity       # float
trade_event.price          # float
trade_event.commission     # float
trade_event.trade_id       # Optional[str]
```

## Output Structure

Your tracker will produce:
```json
{
  "strategies": {
    "strategy1": {"strategy_id": "strategy1", "your_metric": 100},
    "strategy2": {"strategy_id": "strategy2", "your_metric": 200}
  },
  "portfolio_summary": {
    "total_your_metric": 300
  }
}
```

## Common Gotchas

- ❌ Don't forget `super().__init__()` in constructor
- ❌ Don't use global variables - always organize by `strategy_id`
- ❌ Don't modify trade_event - it's shared across trackers
- ❌ Don't raise exceptions - use try/catch and logging
- ✅ Always validate input data (quantity > 0, price > 0)
- ✅ Use `defaultdict` for automatic initialization
- ✅ Log important events for debugging

## File Locations Summary

```
src/trading_system/statistics/
├── base_tracker.py           # Abstract base class
├── statistics_manager.py     # Central coordinator  
├── pnl_tracker.py           # Example: P&L tracking
├── win_loss_tracker.py      # Example: Win/loss ratios
├── your_tracker.py          # Your new tracker
└── __init__.py              # Module exports
```

For complete implementation details and advanced features, see [STATISTICAL_TRACKERS_GUIDE.md](STATISTICAL_TRACKERS_GUIDE.md). 