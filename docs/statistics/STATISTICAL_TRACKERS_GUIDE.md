# Statistical Trackers Guide

This guide explains how to add new statistical trackers to the Live Trading Infrastructure. The statistics system uses a modular, plugin-based architecture that makes adding new metrics straightforward and automatic.

## Overview

The statistical tracking system provides:

- **Modular Design**: Each tracker is an independent module
- **Automatic Integration**: New trackers automatically receive all trade events
- **Multi-Strategy Support**: Built-in support for portfolio-wide and per-strategy statistics
- **Event-Driven Processing**: Real-time processing of trading events
- **Unified API**: Consistent interface for all trackers
- **Error Isolation**: Trackers can't affect each other

## Architecture Components

### Core Components

#### 1. BaseTracker (Abstract Base Class)
**Location**: `src/trading_system/statistics/base_tracker.py`

Defines the interface that all statistical trackers must implement:

```python
class BaseTracker(ABC):
    @abstractmethod
    def on_trade_executed(self, trade_event: TradeEvent):
        """Called when a trade is executed"""
        pass
    
    @abstractmethod
    def on_portfolio_update(self, strategy_id: str, portfolio_value: float):
        """Called when portfolio value is updated"""
        pass
    
    @abstractmethod
    def get_current_stats(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
        """Get current statistics"""
        pass
    
    @abstractmethod
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all tracked statistics"""
        pass
```

#### 2. StatisticsManager
**Location**: `src/trading_system/statistics/statistics_manager.py`

Central coordinator that:
- Manages all registered trackers
- Broadcasts events to all trackers
- Provides unified API for querying statistics
- Handles error isolation and logging

#### 3. TradeEvent Data Structure
**Location**: `src/trading_system/statistics/base_tracker.py`

Standardized event object containing:
- Timestamp and strategy identification
- Trade details (symbol, action, quantity, price)
- Commission and optional trade ID

## Step-by-Step Guide: Adding a New Tracker

### Step 1: Create Your Tracker Class

Create a new file `src/trading_system/statistics/your_tracker.py`:

```python
"""
Your Tracker

Description of what your tracker measures and provides.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import defaultdict

from .base_tracker import BaseTracker, TradeEvent

logger = logging.getLogger(__name__)

class YourTracker(BaseTracker):
    """Tracks your specific metrics across strategies"""
    
    def __init__(self):
        super().__init__()
        # Initialize your data structures
        # Always organize by strategy_id for multi-strategy support
        self.your_metrics: Dict[str, YourMetricType] = defaultdict(YourMetricType)
        
        logger.info("Your Tracker initialized")
    
    def on_trade_executed(self, trade_event: TradeEvent):
        """Process a trade execution"""
        strategy_id = trade_event.strategy_id
        
        # Process the trade event and update your metrics
        # Example:
        # self.your_metrics[strategy_id].process_trade(trade_event)
        
        logger.debug(f"Processed trade for your tracker: {strategy_id}")
    
    def on_portfolio_update(self, strategy_id: str, portfolio_value: float):
        """Handle portfolio value updates"""
        # Update portfolio-level metrics if needed
        pass
    
    def get_current_stats(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
        """Get current statistics - portfolio or individual strategy"""
        if strategy_id:
            return self._get_strategy_stats(strategy_id)
        else:
            return self._get_all_strategies_stats()
    
    def _get_strategy_stats(self, strategy_id: str) -> Dict[str, Any]:
        """Get stats for a specific strategy"""
        # Return strategy-specific metrics
        return {
            'strategy_id': strategy_id,
            'your_metric': self.your_metrics[strategy_id].value,
            # ... other strategy-specific metrics
        }
    
    def _get_all_strategies_stats(self) -> Dict[str, Any]:
        """Get stats for all strategies + portfolio summary"""
        all_strategies = set(self.your_metrics.keys())
        
        strategy_stats = {}
        portfolio_total = 0.0
        
        # Get individual strategy stats
        for strategy_id in all_strategies:
            stats = self._get_strategy_stats(strategy_id)
            strategy_stats[strategy_id] = stats
            portfolio_total += stats['your_metric']  # Aggregate as needed
        
        return {
            'strategies': strategy_stats,           # Individual breakdown
            'portfolio_summary': {                  # Portfolio totals
                'total_your_metric': portfolio_total,
                # ... other portfolio-level aggregations
            }
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of your tracking"""
        stats = self._get_all_strategies_stats()
        portfolio = stats['portfolio_summary']
        
        return {
            'tracker_type': 'YourTracker',
            'total_strategies': len(stats['strategies']),
            'your_summary_metric': portfolio['total_your_metric'],
            # ... other summary metrics
        }
    
    def reset(self):
        """Reset all tracking data"""
        self.your_metrics.clear()
        logger.info("Your Tracker reset")
```

### Step 2: Register in StatisticsManager

Add your tracker to `src/trading_system/statistics/statistics_manager.py`:

```python
# 1. Add import at the top
from .your_tracker import YourTracker

# 2. Add to _initialize_trackers method
def _initialize_trackers(self):
    """Initialize all available stat trackers"""
    # Existing trackers...
    
    # Add your tracker
    self.your_tracker = YourTracker()
    self.trackers.append(self.your_tracker)

# 3. Add convenience method (optional)
def get_your_stats(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
    """Get your tracker statistics"""
    return self.your_tracker.get_current_stats(strategy_id)
```

### Step 3: Update Module Exports

Add to `src/trading_system/statistics/__init__.py`:

```python
from .your_tracker import YourTracker

__all__ = [
    'StatisticsManager',
    'PnLTracker',
    'WinLossTracker',
    'YourTracker',  # Add this
    'BaseTracker'
]
```

### Step 4: Update Main Module Exports

Add to `src/trading_system/__init__.py`:

```python
# In the imports section
from .statistics import StatisticsManager, PnLTracker, WinLossTracker, YourTracker, BaseTracker

# In the __all__ list
__all__ = [
    # ... existing exports
    "YourTracker",
    # ... rest of exports
]
```

### Step 5: Add Display Integration (Optional)

To include your tracker in the formatted display summary, add to the `display_summary()` method in `StatisticsManager`:

```python
elif tracker_name == 'YourTracker':
    # Get detailed strategy breakdown
    detailed_stats = self.your_tracker.get_current_stats()
    
    # Portfolio summary
    portfolio = detailed_stats.get('portfolio_summary', {})
    lines.append(f"📊 Your Tracker:")
    lines.append(f"  Your Metric: {portfolio.get('total_your_metric', 0):.2f}")
    
    # Individual strategy breakdown
    strategies = detailed_stats.get('strategies', {})
    if strategies:
        lines.append(f"")
        lines.append(f"📈 Strategy Breakdown:")
        for strategy_id, strategy_stats in strategies.items():
            lines.append(f"  • {strategy_id}:")
            lines.append(f"    Your Metric: {strategy_stats.get('your_metric', 0):.2f}")
```

## Implementation Examples

### Example 1: Volume Tracker

Tracks trading volume across strategies:

```python
class VolumeTracker(BaseTracker):
    def __init__(self):
        super().__init__()
        self.volume_by_strategy: Dict[str, float] = defaultdict(float)
        self.trade_count_by_strategy: Dict[str, int] = defaultdict(int)
    
    def on_trade_executed(self, trade_event: TradeEvent):
        strategy_id = trade_event.strategy_id
        volume = trade_event.quantity * trade_event.price
        
        self.volume_by_strategy[strategy_id] += volume
        self.trade_count_by_strategy[strategy_id] += 1
    
    def _get_strategy_stats(self, strategy_id: str) -> Dict[str, Any]:
        volume = self.volume_by_strategy[strategy_id]
        count = self.trade_count_by_strategy[strategy_id]
        avg_trade_size = volume / count if count > 0 else 0
        
        return {
            'strategy_id': strategy_id,
            'total_volume': volume,
            'trade_count': count,
            'avg_trade_size': avg_trade_size
        }
```

### Example 2: Drawdown Tracker

Tracks maximum drawdown from peak portfolio value:

```python
class DrawdownTracker(BaseTracker):
    def __init__(self):
        super().__init__()
        self.peak_value: Dict[str, float] = defaultdict(float)
        self.current_value: Dict[str, float] = defaultdict(float)
        self.max_drawdown: Dict[str, float] = defaultdict(float)
        self.current_drawdown: Dict[str, float] = defaultdict(float)
    
    def on_portfolio_update(self, strategy_id: str, portfolio_value: float):
        # Update peak value
        if portfolio_value > self.peak_value[strategy_id]:
            self.peak_value[strategy_id] = portfolio_value
        
        self.current_value[strategy_id] = portfolio_value
        
        # Calculate current drawdown
        if self.peak_value[strategy_id] > 0:
            drawdown = (self.peak_value[strategy_id] - portfolio_value) / self.peak_value[strategy_id]
            self.current_drawdown[strategy_id] = drawdown
            
            # Update max drawdown
            if drawdown > self.max_drawdown[strategy_id]:
                self.max_drawdown[strategy_id] = drawdown
```

## Key Design Patterns

### 1. Strategy-Centric Data Organization

Always organize your data by `strategy_id` to support multi-strategy portfolios:

```python
# ✅ Good - organized by strategy
self.metrics: Dict[str, MetricType] = defaultdict(MetricType)

# ❌ Bad - single global metric
self.global_metric: MetricType = MetricType()
```

### 2. Dual-Mode Statistics

Implement the dual-mode pattern for both portfolio and strategy-level statistics:

```python
def get_current_stats(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
    if strategy_id:
        return self._get_strategy_stats(strategy_id)    # Individual
    else:
        return self._get_all_strategies_stats()         # Portfolio
```

### 3. Aggregation in Portfolio Stats

When implementing `_get_all_strategies_stats()`, aggregate individual strategy metrics:

```python
def _get_all_strategies_stats(self) -> Dict[str, Any]:
    strategy_stats = {}
    portfolio_total = 0.0
    
    for strategy_id in all_strategies:
        stats = self._get_strategy_stats(strategy_id)
        strategy_stats[strategy_id] = stats
        portfolio_total += stats['metric']  # Aggregate
    
    return {
        'strategies': strategy_stats,        # Individual breakdown
        'portfolio_summary': {               # Portfolio aggregation
            'total_metric': portfolio_total
        }
    }
```

## Integration Points

### Automatic Event Delivery

Once registered, your tracker automatically receives:

1. **Trade Events**: Every `on_trade_executed()` call
2. **Portfolio Updates**: Every `on_portfolio_update()` call
3. **Market Price Updates**: Via custom methods if needed

### API Access

Your tracker becomes available through:

```python
# Via StatisticsManager
stats_manager = StatisticsManager()
your_stats = stats_manager.get_all_stats()['YourTracker']

# Via convenience method (if added)
your_stats = stats_manager.get_your_stats()

# Direct access
your_stats = stats_manager.your_tracker.get_current_stats()
```

### Display Integration

Your tracker appears in:
- Live system status displays
- Statistics summaries
- CLI output
- API responses

## Best Practices

### 1. Error Handling

Always wrap calculations in try-catch blocks to prevent affecting other trackers:

```python
def on_trade_executed(self, trade_event: TradeEvent):
    try:
        # Your processing logic
        pass
    except Exception as e:
        logger.error(f"Error in {self.name}: {e}")
```

### 2. Logging

Use structured logging for debugging and monitoring:

```python
logger.debug(f"Processed {trade_event.action}: {strategy_id} {symbol}")
logger.info(f"Updated metric: {strategy_id} -> {new_value}")
logger.warning(f"Unusual condition detected: {condition}")
```

### 3. Performance Considerations

- Use efficient data structures (`defaultdict`, `deque`)
- Avoid expensive calculations in event handlers
- Pre-calculate aggregations when possible
- Consider memory usage for long-running systems

### 4. Data Validation

Validate input data to prevent errors:

```python
def on_trade_executed(self, trade_event: TradeEvent):
    if trade_event.quantity <= 0:
        logger.warning(f"Invalid quantity: {trade_event.quantity}")
        return
    
    if trade_event.price <= 0:
        logger.warning(f"Invalid price: {trade_event.price}")
        return
```

## Testing Your Tracker

### Unit Testing Template

```python
import unittest
from datetime import datetime
from src.trading_system.statistics.base_tracker import TradeEvent
from src.trading_system.statistics.your_tracker import YourTracker

class TestYourTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = YourTracker()
    
    def test_trade_processing(self):
        trade_event = TradeEvent(
            timestamp=datetime.now(),
            strategy_id="test_strategy",
            symbol="AAPL",
            action="buy",
            quantity=100,
            price=150.0,
            commission=1.0
        )
        
        self.tracker.on_trade_executed(trade_event)
        
        stats = self.tracker.get_current_stats("test_strategy")
        self.assertEqual(stats['strategy_id'], "test_strategy")
        # Add your specific assertions
    
    def test_portfolio_stats(self):
        # Test portfolio-wide statistics
        pass
```

### Integration Testing

Test your tracker within the full StatisticsManager:

```python
from src.trading_system.statistics import StatisticsManager

def test_integration():
    stats_manager = StatisticsManager()
    
    # Verify your tracker is registered
    tracker_names = [t.name for t in stats_manager.trackers]
    assert 'YourTracker' in tracker_names
    
    # Test event delivery
    stats_manager.record_trade(
        timestamp=datetime.now(),
        strategy_id="test",
        symbol="AAPL",
        action="buy",
        quantity=100,
        price=150.0
    )
    
    # Verify your tracker received the event
    your_stats = stats_manager.get_your_stats()
    assert your_stats is not None
```

## Advanced Features

### Custom Event Types

You can extend the tracker to handle custom events:

```python
def update_custom_metric(self, strategy_id: str, custom_data: Any):
    """Handle custom metric updates"""
    # Your custom processing
    pass
```

### Real-Time Market Data Integration

For trackers that need current market prices:

```python
def update_market_prices(self, prices: Dict[str, float]):
    """Update current market prices for calculations"""
    # Similar to PnLTracker.update_market_prices()
    pass
```

### Historical Data Access

Access historical trade data for complex calculations:

```python
def get_historical_data(self, strategy_id: str, lookback_days: int) -> List[Any]:
    """Get historical data for analysis"""
    # Return historical data for the strategy
    pass
```

## Conclusion

The statistical tracking system is designed to make adding new metrics straightforward while providing powerful multi-strategy support and automatic integration. By following this guide and the established patterns, you can quickly add sophisticated statistical tracking to the trading system.

Key benefits of this approach:
- **Zero integration effort** - automatic event delivery
- **Consistent API** - uniform interface across all trackers  
- **Error isolation** - trackers can't break each other
- **Multi-strategy ready** - built-in portfolio and strategy-level support
- **Extensible** - easy to add new functionality without breaking existing code

For additional examples, refer to the existing implementations:
- `PnLTracker` - Comprehensive P&L tracking with position management
- `WinLossTracker` - Win/loss ratios with streak tracking 