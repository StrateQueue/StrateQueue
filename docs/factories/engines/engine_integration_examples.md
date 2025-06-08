# Engine Integration Examples

This document provides practical examples of integrating different trading engines with the Stratequeue trading system.

## Backtesting Engine Integration

### Enhanced Backtesting Engine

```python
"""
Enhanced Backtesting Engine

Advanced backtesting with realistic market simulation
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio

from .base import BaseEngine, EngineResults, StrategyConfig
from ..portfolio.portfolio_manager import PortfolioManager
from ..data import auto_create_provider

logger = logging.getLogger(__name__)


class EnhancedBacktestingEngine(BaseEngine):
    """Enhanced backtesting engine with advanced features"""
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        super().__init__(config)
        self.portfolio_manager = None
        self.data_provider = None
        self.market_simulator = MarketSimulator()
        self.performance_tracker = PerformanceTracker()
        
    async def run(self, symbols: List[str], **kwargs) -> EngineResults:
        """Run backtest with comprehensive analysis"""
        try:
            # Initialize components
            initial_capital = kwargs.get('initial_capital', 100000)
            days_back = kwargs.get('days_back', 365)
            granularity = kwargs.get('granularity', '1d')
            
            self.portfolio_manager = PortfolioManager(
                initial_capital=initial_capital,
                symbols=symbols
            )
            
            self.data_provider = auto_create_provider()
            
            # Fetch historical data for all symbols
            market_data = {}
            for symbol in symbols:
                data = await self.data_provider.fetch_historical_data(
                    symbol, days_back, granularity
                )
                if not data.empty:
                    market_data[symbol] = data
                    logger.info(f"Loaded {len(data)} bars for {symbol}")
            
            if not market_data:
                raise Exception("No market data available for backtesting")
            
            # Run backtest simulation
            results = await self._run_backtest_simulation(market_data, **kwargs)
            
            return results
            
        except Exception as e:
            logger.error(f"Backtesting failed: {e}")
            return EngineResults(
                total_return=0.0,
                final_portfolio_value=initial_capital,
                trades=[],
                performance_metrics={},
                execution_time=timedelta(0),
                engine_type='enhanced_backtesting',
                error=str(e)
            )
    
    async def _run_backtest_simulation(self, market_data: Dict[str, pd.DataFrame], **kwargs) -> EngineResults:
        """Run the actual backtest simulation"""
        start_time = datetime.now()
        
        # Create unified timeline from all symbols
        timeline = self._create_unified_timeline(market_data)
        
        logger.info(f"Running backtest on {len(timeline)} time periods")
        
        # Execute strategy on each time step
        for timestamp in timeline:
            # Get current market state
            current_prices = {}
            current_bars = {}
            
            for symbol, data in market_data.items():
                if timestamp in data.index:
                    bar = data.loc[timestamp]
                    current_prices[symbol] = bar['Close']
                    current_bars[symbol] = {
                        'symbol': symbol,
                        'timestamp': timestamp,
                        'open': bar['Open'],
                        'high': bar['High'],
                        'low': bar['Low'],
                        'close': bar['Close'],
                        'volume': bar['Volume']
                    }
            
            if current_prices:
                # Update portfolio with current prices
                self.portfolio_manager.update_prices(current_prices)
                
                # Generate signals from strategy
                if self.strategy and current_bars:
                    for symbol, bar_data in current_bars.items():
                        signals = await self.strategy.generate_signals(
                            bar_data, self.portfolio_manager
                        )
                        
                        # Process signals with market simulation
                        for signal in signals:
                            await self._process_backtest_signal(signal, bar_data)
                
                # Track performance
                self.performance_tracker.record_snapshot(
                    timestamp, 
                    self.portfolio_manager.get_total_value(),
                    self.portfolio_manager.get_positions()
                )
        
        # Calculate final results
        end_time = datetime.now()
        final_value = self.portfolio_manager.get_total_value()
        total_return = (final_value - self.portfolio_manager.initial_capital) / self.portfolio_manager.initial_capital
        
        # Generate comprehensive performance metrics
        performance_metrics = self._calculate_backtest_metrics()
        
        return EngineResults(
            total_return=total_return,
            final_portfolio_value=final_value,
            trades=self.portfolio_manager.get_trade_history(),
            performance_metrics=performance_metrics,
            execution_time=end_time - start_time,
            engine_type='enhanced_backtesting'
        )
    
    def _create_unified_timeline(self, market_data: Dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
        """Create unified timeline from all symbols"""
        all_timestamps = set()
        
        for data in market_data.values():
            all_timestamps.update(data.index)
        
        return pd.DatetimeIndex(sorted(all_timestamps))
    
    async def _process_backtest_signal(self, signal: Dict, market_data: Dict):
        """Process signal with realistic execution simulation"""
        try:
            symbol = signal['symbol']
            action = signal['action']
            quantity = signal.get('quantity', 0)
            
            if quantity <= 0:
                return
            
            # Simulate order execution
            execution_result = self.market_simulator.execute_order(
                symbol=symbol,
                action=action,
                quantity=quantity,
                market_data=market_data,
                portfolio_manager=self.portfolio_manager
            )
            
            if execution_result['success']:
                logger.debug(f"Backtest order executed: {action} {quantity} {symbol} @ ${execution_result['price']:.2f}")
            else:
                logger.warning(f"Backtest order failed: {execution_result['reason']}")
                
        except Exception as e:
            logger.error(f"Error processing backtest signal: {e}")
    
    def _calculate_backtest_metrics(self) -> Dict:
        """Calculate comprehensive backtest performance metrics"""
        snapshots = self.performance_tracker.get_snapshots()
        trades = self.portfolio_manager.get_trade_history()
        
        if not snapshots:
            return {}
        
        # Calculate returns series
        values = [s['portfolio_value'] for s in snapshots]
        returns = pd.Series(values).pct_change().dropna()
        
        # Basic metrics
        total_return = (values[-1] - values[0]) / values[0]
        annualized_return = (1 + total_return) ** (252 / len(values)) - 1
        volatility = returns.std() * np.sqrt(252)
        sharpe_ratio = (annualized_return - 0.02) / volatility if volatility > 0 else 0  # Assume 2% risk-free rate
        
        # Drawdown analysis
        drawdowns = self._calculate_drawdowns(values)
        max_drawdown = min(drawdowns) if drawdowns else 0
        
        # Trade analysis
        if trades:
            profitable_trades = len([t for t in trades if t.get('profit', 0) > 0])
            win_rate = profitable_trades / len(trades)
            avg_profit = sum(t.get('profit', 0) for t in trades) / len(trades)
        else:
            win_rate = 0
            avg_profit = 0
        
        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'total_trades': len(trades),
            'win_rate': win_rate,
            'average_profit_per_trade': avg_profit,
            'calmar_ratio': annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0
        }
    
    def _calculate_drawdowns(self, values: List[float]) -> List[float]:
        """Calculate drawdown series"""
        drawdowns = []
        peak = values[0]
        
        for value in values:
            if value > peak:
                peak = value
            drawdown = (value - peak) / peak
            drawdowns.append(drawdown)
        
        return drawdowns


class MarketSimulator:
    """Simulate realistic market execution for backtesting"""
    
    def execute_order(self, symbol: str, action: str, quantity: int, 
                     market_data: Dict, portfolio_manager) -> Dict:
        """Simulate order execution with realistic constraints"""
        try:
            # Calculate execution price with slippage
            base_price = market_data['close']
            slippage = 0.0005 if action == 'buy' else -0.0005  # 0.05% slippage
            execution_price = base_price * (1 + slippage)
            
            # Execute the trade
            if action == 'buy':
                success = portfolio_manager.buy_stock(symbol, quantity, execution_price)
            else:
                success = portfolio_manager.sell_stock(symbol, quantity, execution_price)
            
            return {
                'success': success,
                'price': execution_price,
                'slippage': slippage
            }
            
        except Exception as e:
            return {'success': False, 'reason': str(e)}


class PerformanceTracker:
    """Track portfolio performance over time"""
    
    def __init__(self):
        self.snapshots = []
    
    def record_snapshot(self, timestamp: pd.Timestamp, portfolio_value: float, positions: Dict):
        """Record a performance snapshot"""
        self.snapshots.append({
            'timestamp': timestamp,
            'portfolio_value': portfolio_value,
            'positions': positions.copy()
        })
    
    def get_snapshots(self) -> List[Dict]:
        """Get all performance snapshots"""
        return self.snapshots
```

## Live Trading Engine Integration

### Real-Time Trading Engine

```python
"""
Real-Time Trading Engine

Production-ready engine for live trading
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from .base import BaseEngine, EngineResults, StrategyConfig
from ..portfolio.portfolio_manager import PortfolioManager
from ..data import auto_create_provider
from ..brokers import auto_create_broker

logger = logging.getLogger(__name__)


@dataclass
class RiskParameters:
    """Risk management parameters"""
    max_position_size: float = 0.1  # 10% of portfolio
    max_daily_loss: float = 0.02   # 2% daily loss limit
    max_total_exposure: float = 0.8  # 80% max invested


class LiveTradingEngine(BaseEngine):
    """Production live trading engine"""
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        super().__init__(config)
        self.portfolio_manager = None
        self.data_provider = None
        self.broker = None
        self.risk_manager = RiskManager()
        self.running = False
        self.risk_params = RiskParameters()
        
    async def run(self, symbols: List[str], **kwargs) -> EngineResults:
        """Run live trading engine"""
        try:
            # Initialize all components
            if not await self._initialize_components(symbols, **kwargs):
                raise Exception("Failed to initialize trading components")
            
            # Start trading loop
            self.running = True
            start_time = datetime.now()
            
            # Start concurrent tasks
            tasks = [
                asyncio.create_task(self._market_data_loop()),
                asyncio.create_task(self._risk_monitoring_loop()),
                asyncio.create_task(self._performance_monitoring_loop())
            ]
            
            logger.info("Live trading engine started")
            
            try:
                # Run until stopped
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                logger.info("Live trading engine stopped")
            
            # Calculate final results
            end_time = datetime.now()
            final_value = self.portfolio_manager.get_total_value()
            total_return = (final_value - self.portfolio_manager.initial_capital) / self.portfolio_manager.initial_capital
            
            return EngineResults(
                total_return=total_return,
                final_portfolio_value=final_value,
                trades=self.portfolio_manager.get_trade_history(),
                performance_metrics=self._calculate_live_metrics(),
                execution_time=end_time - start_time,
                engine_type='live_trading'
            )
            
        except Exception as e:
            logger.error(f"Live trading engine failed: {e}")
            return EngineResults(
                total_return=0.0,
                final_portfolio_value=0.0,
                trades=[],
                performance_metrics={},
                execution_time=timedelta(0),
                engine_type='live_trading',
                error=str(e)
            )
    
    async def _initialize_components(self, symbols: List[str], **kwargs) -> bool:
        """Initialize all trading components"""
        try:
            # Initialize portfolio manager
            initial_capital = kwargs.get('initial_capital', 100000)
            self.portfolio_manager = PortfolioManager(
                initial_capital=initial_capital,
                symbols=symbols
            )
            
            # Initialize data provider
            self.data_provider = auto_create_provider()
            
            # Subscribe to real-time data
            for symbol in symbols:
                self.data_provider.subscribe_to_symbol(symbol)
            
            self.data_provider.start_realtime_feed()
            
            # Initialize broker
            self.broker = auto_create_broker()
            if not self.broker.connect():
                raise Exception("Failed to connect to broker")
            
            logger.info("All trading components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            return False
    
    async def _market_data_loop(self):
        """Process incoming market data"""
        def handle_market_data(market_data):
            asyncio.create_task(self._process_market_data(market_data))
        
        self.data_provider.add_data_callback(handle_market_data)
        
        while self.running:
            await asyncio.sleep(0.1)
    
    async def _process_market_data(self, market_data):
        """Process incoming market data and generate signals"""
        try:
            symbol = market_data.symbol
            
            # Update portfolio with current price
            self.portfolio_manager.update_prices({symbol: market_data.close})
            
            # Generate trading signals
            if self.strategy:
                signals = await self.strategy.generate_signals(
                    market_data.__dict__, self.portfolio_manager
                )
                
                # Process each signal through risk management
                for signal in signals:
                    await self._process_trading_signal(signal)
                    
        except Exception as e:
            logger.error(f"Error processing market data: {e}")
    
    async def _process_trading_signal(self, signal: Dict):
        """Process trading signal with risk management"""
        try:
            # Risk check
            if not self.risk_manager.validate_signal(signal, self.portfolio_manager, self.risk_params):
                logger.warning(f"Signal rejected by risk management: {signal}")
                return
            
            # Submit order to broker
            result = self.broker.place_order(
                symbol=signal['symbol'],
                order_type='market',
                side=signal['action'],
                quantity=signal['quantity']
            )
            
            if result.success:
                logger.info(f"Order submitted: {signal}")
            else:
                logger.error(f"Order failed: {result.message}")
            
        except Exception as e:
            logger.error(f"Error processing trading signal: {e}")
    
    async def _risk_monitoring_loop(self):
        """Monitor risk metrics continuously"""
        while self.running:
            try:
                # Check risk limits
                risk_status = self.risk_manager.check_risk_limits(
                    self.portfolio_manager, self.risk_params
                )
                
                if risk_status['violations']:
                    logger.warning(f"Risk violations detected: {risk_status['violations']}")
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in risk monitoring: {e}")
    
    async def _performance_monitoring_loop(self):
        """Monitor and log performance metrics"""
        while self.running:
            try:
                # Log portfolio status
                total_value = self.portfolio_manager.get_total_value()
                positions = self.portfolio_manager.get_positions()
                
                logger.info(f"Portfolio Value: ${total_value:,.2f}, Positions: {len(positions)}")
                
                await asyncio.sleep(300)  # Log every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")
    
    def stop(self):
        """Stop the live trading engine"""
        self.running = False
        
        if self.data_provider:
            self.data_provider.stop_realtime_feed()
        
        if self.broker:
            self.broker.disconnect()
        
        logger.info("Live trading engine stopped")
    
    def _calculate_live_metrics(self) -> Dict:
        """Calculate live trading metrics"""
        trades = self.portfolio_manager.get_trade_history()
        
        if not trades:
            return {}
        
        profitable_trades = len([t for t in trades if t.get('profit', 0) > 0])
        total_trades = len(trades)
        win_rate = profitable_trades / total_trades if total_trades > 0 else 0
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profitable_trades': profitable_trades
        }


class RiskManager:
    """Comprehensive risk management system"""
    
    def validate_signal(self, signal: Dict, portfolio_manager, risk_params: RiskParameters) -> bool:
        """Validate trading signal against risk parameters"""
        try:
            symbol = signal['symbol']
            quantity = signal['quantity']
            
            current_price = portfolio_manager.get_current_price(symbol)
            if not current_price:
                return False
            
            order_value = quantity * current_price
            total_portfolio_value = portfolio_manager.get_total_value()
            
            # Position size check
            position_percentage = order_value / total_portfolio_value
            if position_percentage > risk_params.max_position_size:
                logger.warning(f"Order rejected: position size {position_percentage:.2%} exceeds limit")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating signal: {e}")
            return False
    
    def check_risk_limits(self, portfolio_manager, risk_params: RiskParameters) -> Dict:
        """Check current portfolio against risk limits"""
        violations = []
        
        # Daily loss check
        daily_pnl = portfolio_manager.get_daily_pnl()
        daily_loss_percentage = daily_pnl / portfolio_manager.initial_capital
        
        if daily_loss_percentage < -risk_params.max_daily_loss:
            violations.append(f"Daily loss {daily_loss_percentage:.2%} exceeds limit")
        
        return {'violations': violations}
```

## Paper Trading Engine Integration

### Paper Trading with Broker Simulation

```python
"""
Paper Trading Engine

Realistic paper trading with broker simulation
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import uuid

from .base import BaseEngine, EngineResults, StrategyConfig
from ..portfolio.portfolio_manager import PortfolioManager
from ..data import auto_create_provider

logger = logging.getLogger(__name__)


class PaperTradingEngine(BaseEngine):
    """Paper trading engine with realistic broker simulation"""
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        super().__init__(config)
        self.portfolio_manager = None
        self.data_provider = None
        self.paper_broker = PaperBroker()
        self.running = False
        
    async def run(self, symbols: List[str], **kwargs) -> EngineResults:
        """Run paper trading simulation"""
        try:
            # Initialize components
            initial_capital = kwargs.get('initial_capital', 100000)
            self.portfolio_manager = PortfolioManager(
                initial_capital=initial_capital,
                symbols=symbols
            )
            
            self.data_provider = auto_create_provider()
            
            # Subscribe to real-time data
            for symbol in symbols:
                self.data_provider.subscribe_to_symbol(symbol)
            
            self.data_provider.start_realtime_feed()
            self.data_provider.add_data_callback(self._handle_market_data)
            
            # Start paper trading
            self.running = True
            start_time = datetime.now()
            
            logger.info("Paper trading started")
            
            # Run trading loop
            while self.running:
                # Process paper broker orders
                await self.paper_broker.process_orders(self.portfolio_manager)
                await asyncio.sleep(1)
            
            # Calculate results
            end_time = datetime.now()
            final_value = self.portfolio_manager.get_total_value()
            total_return = (final_value - initial_capital) / initial_capital
            
            return EngineResults(
                total_return=total_return,
                final_portfolio_value=final_value,
                trades=self.portfolio_manager.get_trade_history(),
                performance_metrics=self._calculate_paper_metrics(),
                execution_time=end_time - start_time,
                engine_type='paper_trading'
            )
            
        except Exception as e:
            logger.error(f"Paper trading failed: {e}")
            return EngineResults(
                total_return=0.0,
                final_portfolio_value=0.0,
                trades=[],
                performance_metrics={},
                execution_time=timedelta(0),
                engine_type='paper_trading',
                error=str(e)
            )
    
    async def _handle_market_data(self, market_data):
        """Handle incoming market data"""
        try:
            symbol = market_data.symbol
            
            # Update portfolio with current price
            self.portfolio_manager.update_prices({symbol: market_data.close})
            
            # Update paper broker with market data
            self.paper_broker.update_market_data(symbol, market_data)
            
            # Generate signals
            if self.strategy:
                signals = await self.strategy.generate_signals(
                    market_data.__dict__, self.portfolio_manager
                )
                
                # Submit signals to paper broker
                for signal in signals:
                    await self._submit_paper_order(signal)
                    
        except Exception as e:
            logger.error(f"Error handling market data: {e}")
    
    async def _submit_paper_order(self, signal: Dict):
        """Submit order to paper broker"""
        try:
            order = {
                'id': str(uuid.uuid4()),
                'symbol': signal['symbol'],
                'action': signal['action'],
                'quantity': signal['quantity'],
                'order_type': signal.get('order_type', 'market'),
                'timestamp': datetime.now(),
                'status': 'pending'
            }
            
            self.paper_broker.submit_order(order)
            
        except Exception as e:
            logger.error(f"Error submitting paper order: {e}")
    
    def _calculate_paper_metrics(self) -> Dict:
        """Calculate paper trading metrics"""
        trades = self.portfolio_manager.get_trade_history()
        
        if not trades:
            return {}
        
        return {
            'total_trades': len(trades),
            'paper_trading': True
        }


class PaperBroker:
    """Simulated broker for paper trading"""
    
    def __init__(self):
        self.pending_orders = []
        self.market_data = {}
        self.execution_delay = 0.1  # 100ms execution delay
        
    def submit_order(self, order: Dict):
        """Submit order for execution"""
        self.pending_orders.append(order)
        logger.info(f"Paper order submitted: {order['action']} {order['quantity']} {order['symbol']}")
    
    def update_market_data(self, symbol: str, market_data):
        """Update market data for execution"""
        self.market_data[symbol] = market_data
    
    async def process_orders(self, portfolio_manager):
        """Process pending orders"""
        for order in list(self.pending_orders):
            if await self._should_execute_order(order):
                await self._execute_order(order, portfolio_manager)
                self.pending_orders.remove(order)
    
    async def _should_execute_order(self, order: Dict) -> bool:
        """Determine if order should be executed"""
        # Check if we have market data
        if order['symbol'] not in self.market_data:
            return False
        
        # Check execution delay
        time_since_submission = (datetime.now() - order['timestamp']).total_seconds()
        return time_since_submission >= self.execution_delay
    
    async def _execute_order(self, order: Dict, portfolio_manager):
        """Execute paper order"""
        try:
            symbol = order['symbol']
            market_data = self.market_data[symbol]
            execution_price = market_data.close
            
            # Execute trade
            if order['action'] == 'buy':
                success = portfolio_manager.buy_stock(symbol, order['quantity'], execution_price)
            else:
                success = portfolio_manager.sell_stock(symbol, order['quantity'], execution_price)
            
            if success:
                logger.info(f"Paper order executed: {order['action']} {order['quantity']} {symbol} @ ${execution_price:.2f}")
            else:
                logger.warning(f"Paper order failed: insufficient funds/shares")
                
        except Exception as e:
            logger.error(f"Error executing paper order: {e}")
```

## Best Practices

### 1. Engine Architecture
- Separate data processing from execution logic
- Use async/await for I/O operations
- Implement proper error handling and recovery
- Design for extensibility and modularity

### 2. Risk Management
- Always validate signals before execution
- Implement position size limits
- Monitor total portfolio exposure
- Have emergency stop mechanisms

### 3. Order Management
- Track order lifecycle carefully
- Handle partial fills appropriately
- Implement retry logic for failed orders
- Log all order activities

### 4. Performance Monitoring
- Track latency and execution times
- Monitor portfolio metrics in real-time
- Log important events and errors
- Calculate comprehensive performance metrics

### 5. Testing and Validation
- Test engines with mock data first
- Validate against historical performance
- Use paper trading before live deployment
- Monitor for unexpected behavior 