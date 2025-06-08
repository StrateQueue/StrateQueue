# Engine Factory Guide

## Overview

The Stratequeue trading system includes a flexible engine factory that makes it easy to add new trading engines and execution strategies. The factory pattern follows the same design as the broker and data provider factories, providing consistent interfaces and strategy-aware engine selection.

## Architecture

### Core Components

1. **BaseEngine** - Abstract base class defining the engine interface
2. **EngineFactory** - Factory class for creating engine instances
3. **Engine Utilities** - Strategy detection and configuration helpers
4. **Engine Implementations** - Specific engine implementations (Backtesting, Live Trading, Paper Trading)

### Key Features

- **Lazy Loading**: Engines are only loaded when requested
- **Strategy-Aware**: Automatically detects appropriate engine based on strategy requirements
- **Graceful Fallbacks**: Handles missing dependencies with appropriate fallbacks
- **Unified Interface**: Consistent API across all engine implementations
- **Configuration-Based**: Strategy configuration drives engine selection
- **Multi-Strategy Support**: Support for both single and multi-strategy execution

## Using the Engine Factory

### Basic Usage

```python
from StrateQueue.engines import (
    EngineFactory, 
    auto_create_engine,
    detect_engine_type,
    validate_strategy_compatibility
)

# Create a specific engine
engine = EngineFactory.create_engine('backtesting')

# Auto-detect and create engine based on strategy
engine = auto_create_engine('strategies/my_strategy.py')

# Check strategy compatibility
is_compatible = validate_strategy_compatibility('strategies/my_strategy.py', 'backtesting')

# Run strategy with engine
if engine.load_strategy_from_file('strategies/my_strategy.py'):
    results = engine.run(['AAPL', 'MSFT'])
    print(f"Total Return: {results.total_return:.2%}")
```

### CLI Integration

The engine factory is fully integrated with the CLI:

```bash
# List available engines
python3 main.py --list-engines

# Check engine compatibility with strategy
python3 main.py --check-compatibility strategies/sma.py

# Run with specific engine
python3 main.py --strategy sma.py --symbols AAPL --engine backtesting

# Auto-detect engine (default)
python3 main.py --strategy sma.py --symbols AAPL

# Enable live trading with appropriate engine
python3 main.py --strategy sma.py --symbols AAPL --enable-trading
```

### Strategy Detection

The system automatically detects appropriate engines based on strategy characteristics:

```python
from StrateQueue.engines import (
    detect_engine_type,
    get_supported_engines,
    analyze_strategy_requirements
)

# Detect engine from strategy file
engine_type = detect_engine_type('strategies/my_strategy.py')

# Get all supported engines
supported = get_supported_engines()

# Analyze strategy requirements
requirements = analyze_strategy_requirements('strategies/my_strategy.py')
print(f"Requires real-time data: {requirements.needs_realtime}")
print(f"Supports backtesting: {requirements.supports_backtesting}")
```

## Adding a New Engine

### Step 1: Create Engine Implementation

Create a new file `src/StrateQueue/engines/your_engine.py`:

```python
"""
Your Engine Implementation

Implementation of BaseEngine for Your Trading Strategy
"""

import logging
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio

from .base import BaseEngine, EngineResults, StrategyConfig
from ..portfolio.portfolio_manager import PortfolioManager
from ..data import auto_create_provider

logger = logging.getLogger(__name__)


class YourEngine(BaseEngine):
    """Your custom engine implementation"""
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        super().__init__(config)
        self.portfolio_manager = None
        self.data_provider = None
        self.running = False
        
    def initialize(self, symbols: List[str], initial_capital: float = 100000) -> bool:
        """Initialize the engine with symbols and capital"""
        try:
            # Initialize portfolio manager
            self.portfolio_manager = PortfolioManager(
                initial_capital=initial_capital,
                symbols=symbols
            )
            
            # Initialize data provider
            self.data_provider = auto_create_provider()
            
            # Subscribe to symbols if real-time
            if self.config and self.config.realtime:
                for symbol in symbols:
                    self.data_provider.subscribe_to_symbol(symbol)
                self.data_provider.start_realtime_feed()
            
            logger.info(f"Your Engine initialized with {len(symbols)} symbols")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Your Engine: {e}")
            return False
    
    async def run(self, symbols: List[str], **kwargs) -> EngineResults:
        """Run the strategy with your custom engine logic"""
        try:
            if not self.initialize(symbols, kwargs.get('initial_capital', 100000)):
                raise Exception("Engine initialization failed")
            
            # Start execution
            self.running = True
            start_time = datetime.now()
            
            if self.config and self.config.realtime:
                # Real-time execution
                results = await self._run_realtime(symbols, **kwargs)
            else:
                # Historical/backtest execution
                results = await self._run_historical(symbols, **kwargs)
            
            end_time = datetime.now()
            
            # Calculate final results
            final_portfolio_value = self.portfolio_manager.get_total_value()
            total_return = (final_portfolio_value - self.portfolio_manager.initial_capital) / self.portfolio_manager.initial_capital
            
            return EngineResults(
                total_return=total_return,
                final_portfolio_value=final_portfolio_value,
                trades=self.portfolio_manager.get_trade_history(),
                performance_metrics=self._calculate_performance_metrics(),
                execution_time=end_time - start_time,
                engine_type='your_engine'
            )
            
        except Exception as e:
            logger.error(f"Your Engine execution failed: {e}")
            return EngineResults(
                total_return=0.0,
                final_portfolio_value=0.0,
                trades=[],
                performance_metrics={},
                execution_time=datetime.now() - start_time,
                engine_type='your_engine',
                error=str(e)
            )
    
    async def _run_realtime(self, symbols: List[str], **kwargs) -> Dict:
        """Execute strategy in real-time mode"""
        logger.info("Starting real-time execution")
        
        # Set up real-time data callbacks
        self.data_provider.add_data_callback(self._handle_market_data)
        
        # Run until stopped
        while self.running:
            await asyncio.sleep(1)  # Check every second
            
            # Perform periodic tasks
            await self._periodic_tasks()
        
        return {}
    
    async def _run_historical(self, symbols: List[str], **kwargs) -> Dict:
        """Execute strategy on historical data"""
        logger.info("Starting historical execution")
        
        days_back = kwargs.get('days_back', 30)
        granularity = kwargs.get('granularity', '1m')
        
        # Fetch historical data for all symbols
        for symbol in symbols:
            historical_data = await self.data_provider.fetch_historical_data(
                symbol, days_back, granularity
            )
            
            if historical_data.empty:
                logger.warning(f"No historical data for {symbol}")
                continue
            
            # Process each bar
            for timestamp, bar in historical_data.iterrows():
                # Create market data object
                market_data = {
                    'symbol': symbol,
                    'timestamp': timestamp,
                    'open': bar['Open'],
                    'high': bar['High'],
                    'low': bar['Low'],
                    'close': bar['Close'],
                    'volume': bar['Volume']
                }
                
                # Handle the data
                await self._handle_market_data(market_data)
        
        return {}
    
    async def _handle_market_data(self, market_data: Dict):
        """Handle incoming market data"""
        if not self.strategy:
            return
        
        try:
            # Update portfolio with current prices
            self.portfolio_manager.update_prices({
                market_data['symbol']: market_data['close']
            })
            
            # Execute strategy logic
            signals = await self.strategy.generate_signals(market_data, self.portfolio_manager)
            
            # Process signals
            for signal in signals:
                await self._process_signal(signal)
                
        except Exception as e:
            logger.error(f"Error handling market data: {e}")
    
    async def _process_signal(self, signal: Dict):
        """Process trading signal"""
        try:
            symbol = signal['symbol']
            action = signal['action']  # 'buy', 'sell', 'hold'
            quantity = signal.get('quantity', 0)
            
            if action == 'buy' and quantity > 0:
                success = self.portfolio_manager.buy_stock(symbol, quantity)
                if success:
                    logger.info(f"Bought {quantity} shares of {symbol}")
            
            elif action == 'sell' and quantity > 0:
                success = self.portfolio_manager.sell_stock(symbol, quantity)
                if success:
                    logger.info(f"Sold {quantity} shares of {symbol}")
                    
        except Exception as e:
            logger.error(f"Error processing signal: {e}")
    
    async def _periodic_tasks(self):
        """Perform periodic maintenance tasks"""
        # Update portfolio metrics
        self.portfolio_manager.update_metrics()
        
        # Log portfolio status periodically
        if hasattr(self, '_last_status_log'):
            if (datetime.now() - self._last_status_log).seconds > 300:  # Every 5 minutes
                self._log_portfolio_status()
                self._last_status_log = datetime.now()
        else:
            self._last_status_log = datetime.now()
    
    def _log_portfolio_status(self):
        """Log current portfolio status"""
        total_value = self.portfolio_manager.get_total_value()
        positions = self.portfolio_manager.get_positions()
        
        logger.info(f"Portfolio Value: ${total_value:,.2f}")
        logger.info(f"Positions: {len(positions)} symbols")
    
    def _calculate_performance_metrics(self) -> Dict:
        """Calculate comprehensive performance metrics"""
        trades = self.portfolio_manager.get_trade_history()
        
        if not trades:
            return {}
        
        # Calculate basic metrics
        total_trades = len(trades)
        profitable_trades = len([t for t in trades if t.get('profit', 0) > 0])
        win_rate = profitable_trades / total_trades if total_trades > 0 else 0
        
        # Calculate returns
        returns = [t.get('return', 0) for t in trades]
        avg_return = sum(returns) / len(returns) if returns else 0
        
        return {
            'total_trades': total_trades,
            'profitable_trades': profitable_trades,
            'win_rate': win_rate,
            'average_return_per_trade': avg_return,
            'total_fees': sum(t.get('fees', 0) for t in trades)
        }
    
    def stop(self):
        """Stop the engine"""
        self.running = False
        if self.data_provider:
            self.data_provider.stop_realtime_feed()
        logger.info("Your Engine stopped")
```

### Step 2: Register in Factory

Add your engine to `src/StrateQueue/engines/engine_factory.py`:

```python
# In EngineFactory._initialize_engines()
try:
    from .your_engine import YourEngine
    cls._engines['your_engine'] = YourEngine
    logger.debug("Registered Your Engine")
except ImportError as e:
    logger.warning(f"Could not load Your Engine: {e}")
```

### Step 3: Add Engine Information

```python
# In EngineFactory.get_engine_info()
elif engine_type == "your_engine":
    return {
        'name': 'Your Custom Engine',
        'description': 'Your custom trading engine implementation',
        'supports_realtime': True,
        'supports_backtesting': True,
        'supports_paper_trading': True,
        'required_dependencies': ['your_custom_lib'],
        'strategy_requirements': ['signals', 'portfolio_management']
    }
```

### Step 4: Add Strategy Detection Logic

```python
# In detect_engine_type()
def detect_engine_type(strategy_path: str = None) -> str:
    """Detect appropriate engine based on strategy characteristics"""
    if not strategy_path:
        return 'backtesting'  # Default
    
    # Analyze strategy file
    requirements = analyze_strategy_requirements(strategy_path)
    
    # Your custom detection logic
    if requirements.needs_custom_features:
        if 'your_engine' in cls._engines:
            return 'your_engine'
    
    # Fallback to standard detection
    # ... existing logic
```

## Advanced Engine Patterns

### Multi-Strategy Engine

```python
class MultiStrategyEngine(BaseEngine):
    """Engine that can run multiple strategies simultaneously"""
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        super().__init__(config)
        self.strategies = {}
        self.strategy_allocations = {}
        
    def load_strategies(self, strategy_configs: List[Dict]) -> bool:
        """Load multiple strategies with allocations"""
        total_allocation = 0
        
        for config in strategy_configs:
            strategy_path = config['path']
            allocation = config['allocation']  # Percentage of capital
            
            if self.load_strategy_from_file(strategy_path):
                strategy_name = config.get('name', strategy_path)
                self.strategies[strategy_name] = self.strategy
                self.strategy_allocations[strategy_name] = allocation
                total_allocation += allocation
        
        if abs(total_allocation - 1.0) > 0.01:  # Should sum to 100%
            logger.warning(f"Strategy allocations sum to {total_allocation:.1%}, not 100%")
        
        return len(self.strategies) > 0
    
    async def _handle_market_data(self, market_data: Dict):
        """Handle market data for all strategies"""
        for strategy_name, strategy in self.strategies.items():
            try:
                # Create isolated portfolio view for this strategy
                strategy_capital = self.portfolio_manager.initial_capital * self.strategy_allocations[strategy_name]
                
                # Execute strategy
                signals = await strategy.generate_signals(market_data, self.portfolio_manager)
                
                # Scale signals by allocation
                for signal in signals:
                    if 'quantity' in signal:
                        signal['quantity'] *= self.strategy_allocations[strategy_name]
                    
                    await self._process_signal(signal)
                    
            except Exception as e:
                logger.error(f"Error in strategy {strategy_name}: {e}")
```

### Paper Trading Engine

```python
class PaperTradingEngine(BaseEngine):
    """Engine for paper trading with realistic order execution simulation"""
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        super().__init__(config)
        self.order_book = []
        self.slippage_model = SlippageModel()
        self.commission_model = CommissionModel()
        
    async def _process_signal(self, signal: Dict):
        """Process signal with simulated order execution"""
        try:
            # Create simulated order
            order = {
                'id': self._generate_order_id(),
                'symbol': signal['symbol'],
                'action': signal['action'],
                'quantity': signal['quantity'],
                'order_type': signal.get('order_type', 'market'),
                'timestamp': datetime.now(),
                'status': 'pending'
            }
            
            # Add to order book
            self.order_book.append(order)
            
            # Simulate execution delay
            await asyncio.sleep(0.1)  # 100ms delay
            
            # Execute with slippage and commission
            if order['order_type'] == 'market':
                execution_price = self._calculate_execution_price(order)
                commission = self.commission_model.calculate(order)
                
                # Update portfolio
                if order['action'] == 'buy':
                    total_cost = execution_price * order['quantity'] + commission
                    success = self.portfolio_manager.buy_stock(
                        order['symbol'], 
                        order['quantity'], 
                        execution_price
                    )
                else:
                    total_proceeds = execution_price * order['quantity'] - commission
                    success = self.portfolio_manager.sell_stock(
                        order['symbol'], 
                        order['quantity'], 
                        execution_price
                    )
                
                # Update order status
                order['status'] = 'filled' if success else 'rejected'
                order['execution_price'] = execution_price
                order['commission'] = commission
                
                logger.info(f"Paper trade executed: {order['action']} {order['quantity']} {order['symbol']} @ ${execution_price:.2f}")
            
        except Exception as e:
            logger.error(f"Error in paper trading execution: {e}")
    
    def _calculate_execution_price(self, order: Dict) -> float:
        """Calculate execution price with slippage"""
        current_price = self.portfolio_manager.get_current_price(order['symbol'])
        slippage = self.slippage_model.calculate(order)
        
        if order['action'] == 'buy':
            return current_price * (1 + slippage)
        else:
            return current_price * (1 - slippage)


class SlippageModel:
    """Model for calculating realistic slippage"""
    
    def calculate(self, order: Dict) -> float:
        """Calculate slippage based on order characteristics"""
        base_slippage = 0.001  # 0.1% base slippage
        
        # Increase slippage for larger orders
        quantity_factor = min(order['quantity'] / 1000, 0.01)  # Up to 1% for large orders
        
        # Add random component
        import random
        random_factor = random.uniform(-0.0005, 0.0005)
        
        return base_slippage + quantity_factor + random_factor


class CommissionModel:
    """Model for calculating commissions"""
    
    def calculate(self, order: Dict) -> float:
        """Calculate commission for order"""
        # Flat rate commission (like many modern brokers)
        return 0.0  # Many brokers are commission-free now
        
        # Or percentage-based
        # return order['quantity'] * price * 0.001  # 0.1%
```

### Real-Time Engine with WebSocket

```python
class RealTimeEngine(BaseEngine):
    """Engine optimized for real-time trading with low latency"""
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        super().__init__(config)
        self.message_queue = asyncio.Queue()
        self.order_queue = asyncio.Queue()
        self.latency_tracker = LatencyTracker()
        
    async def _run_realtime(self, symbols: List[str], **kwargs) -> Dict:
        """Optimized real-time execution"""
        # Start parallel processing tasks
        tasks = [
            asyncio.create_task(self._process_market_data()),
            asyncio.create_task(self._process_orders()),
            asyncio.create_task(self._monitor_performance())
        ]
        
        # Set up data feed
        self.data_provider.add_data_callback(self._queue_market_data)
        
        try:
            # Wait for tasks to complete
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Real-time engine error: {e}")
        
        return {}
    
    async def _queue_market_data(self, market_data: Dict):
        """Queue market data for processing"""
        await self.message_queue.put(market_data)
    
    async def _process_market_data(self):
        """Process market data from queue"""
        while self.running:
            try:
                # Get data with timeout
                market_data = await asyncio.wait_for(
                    self.message_queue.get(), 
                    timeout=1.0
                )
                
                start_time = time.perf_counter()
                
                # Process the data
                await self._handle_market_data(market_data)
                
                # Track latency
                processing_time = time.perf_counter() - start_time
                self.latency_tracker.record(processing_time)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing market data: {e}")
    
    async def _process_orders(self):
        """Process order queue"""
        while self.running:
            try:
                order = await asyncio.wait_for(
                    self.order_queue.get(),
                    timeout=1.0
                )
                
                # Execute order immediately
                await self._execute_order(order)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing order: {e}")
    
    async def _execute_order(self, order: Dict):
        """Execute order with broker"""
        # Implementation depends on broker integration
        pass


class LatencyTracker:
    """Track and monitor processing latency"""
    
    def __init__(self, window_size: int = 1000):
        self.latencies = []
        self.window_size = window_size
    
    def record(self, latency: float):
        """Record processing latency"""
        self.latencies.append(latency)
        
        if len(self.latencies) > self.window_size:
            self.latencies = self.latencies[-self.window_size:]
    
    def get_stats(self) -> Dict:
        """Get latency statistics"""
        if not self.latencies:
            return {}
        
        import statistics
        return {
            'avg_latency_ms': statistics.mean(self.latencies) * 1000,
            'p95_latency_ms': statistics.quantiles(self.latencies, n=20)[18] * 1000,
            'p99_latency_ms': statistics.quantiles(self.latencies, n=100)[98] * 1000,
            'max_latency_ms': max(self.latencies) * 1000
        }
```

## Testing Engines

### Engine Test Framework

```python
import pytest
import asyncio
from unittest.mock import Mock, patch

class TestEngineFramework:
    """Comprehensive test framework for engines"""
    
    @pytest.fixture
    def mock_strategy(self):
        """Create mock strategy"""
        strategy = Mock()
        strategy.generate_signals = Mock(return_value=[])
        return strategy
    
    @pytest.fixture
    def test_engine(self):
        """Create test engine instance"""
        return YourEngine()
    
    @pytest.mark.asyncio
    async def test_engine_initialization(self, test_engine):
        """Test engine initialization"""
        symbols = ['AAPL', 'MSFT']
        success = test_engine.initialize(symbols, initial_capital=10000)
        
        assert success
        assert test_engine.portfolio_manager is not None
        assert test_engine.data_provider is not None
    
    @pytest.mark.asyncio
    async def test_strategy_execution(self, test_engine, mock_strategy):
        """Test strategy execution"""
        test_engine.strategy = mock_strategy
        
        # Mock market data
        market_data = {
            'symbol': 'AAPL',
            'timestamp': datetime.now(),
            'close': 150.0
        }
        
        await test_engine._handle_market_data(market_data)
        
        # Verify strategy was called
        mock_strategy.generate_signals.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_performance_calculation(self, test_engine):
        """Test performance metrics calculation"""
        # Set up test portfolio
        test_engine.portfolio_manager = Mock()
        test_engine.portfolio_manager.get_trade_history.return_value = [
            {'profit': 100, 'return': 0.05, 'fees': 1},
            {'profit': -50, 'return': -0.02, 'fees': 1},
            {'profit': 200, 'return': 0.08, 'fees': 1}
        ]
        
        metrics = test_engine._calculate_performance_metrics()
        
        assert metrics['total_trades'] == 3
        assert metrics['profitable_trades'] == 2
        assert metrics['win_rate'] == 2/3
```

## Best Practices

### 1. Engine Design
- Keep engines focused on execution logic
- Separate strategy logic from engine logic
- Use async/await for I/O operations
- Implement proper error handling and recovery

### 2. Performance
- Use message queues for real-time processing
- Track latency and processing times
- Optimize hot paths in the execution loop
- Consider memory usage for long-running engines

### 3. Configuration
- Make engines configurable via StrategyConfig
- Support both real-time and historical modes
- Allow for different execution models
- Validate configurations on startup

### 4. Testing
- Unit test engine components separately
- Use mock data providers and brokers
- Test error conditions and edge cases
- Validate performance under load

### 5. Monitoring
- Log engine operations and metrics
- Track portfolio performance in real-time
- Monitor latency and execution quality
- Alert on engine failures or issues 