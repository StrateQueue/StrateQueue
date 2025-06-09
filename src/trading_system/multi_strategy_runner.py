"""
Multi-Strategy Runner for Live Trading

This module handles:
1. Loading multiple strategies from configuration file
2. Assigning strategy IDs and capital allocations
3. Coordinating parallel strategy execution
4. Routing signals from strategies to portfolio manager
5. Strategy lifecycle management (start/stop/restart)
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from .strategy_loader import StrategyLoader
from .signal_extractor import LiveSignalExtractor, TradingSignal, SignalType
from .simple_portfolio_manager import SimplePortfolioManager

logger = logging.getLogger(__name__)

@dataclass
class StrategyConfig:
    """Configuration for a single strategy"""
    strategy_id: str
    file_path: str
    allocation: float
    lookback_period: int = 20  # Add lookback_period field
    strategy_class: Optional[type] = None
    signal_extractor: Optional[LiveSignalExtractor] = None

class MultiStrategyRunner:
    """
    Coordinates multiple trading strategies running in parallel.
    
    Handles strategy loading, signal coordination, and portfolio management
    integration for multi-strategy live trading.
    """
    
    def __init__(self, config_file_path: str, symbols: List[str], 
                 lookback_override: Optional[int] = None):
        """
        Initialize multi-strategy runner
        
        Args:
            config_file_path: Path to strategy configuration file
            symbols: List of symbols to trade across all strategies
            lookback_override: Override all calculated lookback periods with this value
        """
        self.config_file_path = config_file_path
        self.symbols = symbols
        self.lookback_override = lookback_override
        
        # Strategy configurations and instances
        self.strategy_configs: Dict[str, StrategyConfig] = {}
        self.portfolio_manager: Optional[SimplePortfolioManager] = None
        
        # Calculate the maximum lookback needed across all strategies
        self.max_lookback_period = 20  # Default fallback
        
        # Track active signals and execution status
        self.active_signals: Dict[str, Dict[str, TradingSignal]] = {}  # strategy_id -> symbol -> signal
        self.strategy_status: Dict[str, str] = {}  # strategy_id -> status
        
        # Load strategy configurations
        self._load_strategy_configs()
        
        # Calculate lookback periods for each strategy
        self._calculate_strategy_lookbacks()
        
        # Initialize portfolio manager with allocations
        allocations = {config.strategy_id: config.allocation 
                      for config in self.strategy_configs.values()}
        self.portfolio_manager = SimplePortfolioManager(allocations)
        
        logger.info(f"Initialized multi-strategy runner with {len(self.strategy_configs)} strategies")
        logger.info(f"Maximum lookback period required: {self.max_lookback_period} bars")
    
    def _load_strategy_configs(self):
        """Load strategy configurations from file"""
        if not os.path.exists(self.config_file_path):
            raise FileNotFoundError(f"Strategy config file not found: {self.config_file_path}")
        
        logger.info(f"Loading strategy configurations from {self.config_file_path}")
        
        with open(self.config_file_path, 'r') as f:
            lines = f.readlines()
        
        total_allocation = 0.0
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Parse line: filename,strategy_id,allocation
            parts = [part.strip() for part in line.split(',')]
            if len(parts) != 3:
                raise ValueError(f"Invalid format in line {line_num}: {line}. "
                               f"Expected: filename,strategy_id,allocation")
            
            file_path, strategy_id, allocation_str = parts
            
            # Validate allocation
            try:
                allocation = float(allocation_str)
                if allocation <= 0 or allocation > 1:
                    raise ValueError(f"Allocation must be between 0 and 1, got {allocation}")
            except ValueError as e:
                raise ValueError(f"Invalid allocation in line {line_num}: {allocation_str}. {e}")
            
            # Resolve file path (support relative and absolute paths)
            if not os.path.isabs(file_path):
                # Try relative to config file directory first
                config_dir = os.path.dirname(self.config_file_path)
                resolved_path = os.path.join(config_dir, file_path)
                if not os.path.exists(resolved_path):
                    # Try relative to current working directory
                    resolved_path = file_path
            else:
                resolved_path = file_path
            
            if not os.path.exists(resolved_path):
                raise FileNotFoundError(f"Strategy file not found: {resolved_path}")
            
            # Check for duplicate strategy IDs
            if strategy_id in self.strategy_configs:
                raise ValueError(f"Duplicate strategy ID: {strategy_id}")
            
            # Create strategy config
            config = StrategyConfig(
                strategy_id=strategy_id,
                file_path=resolved_path,
                allocation=allocation
            )
            
            self.strategy_configs[strategy_id] = config
            total_allocation += allocation
            
            logger.info(f"Loaded strategy config: {strategy_id} ({file_path}, {allocation:.1%})")
        
        if not self.strategy_configs:
            raise ValueError("No strategies found in configuration file")
    
    def _calculate_strategy_lookbacks(self):
        """Calculate lookback period for each strategy and determine maximum"""
        max_lookback = 0
        
        for strategy_id, config in self.strategy_configs.items():
            try:
                # Load strategy class to calculate lookback
                original_strategy = StrategyLoader.load_strategy_from_file(config.file_path)
                
                # Calculate individual strategy lookback
                if self.lookback_override:
                    strategy_lookback = self.lookback_override
                    logger.info(f"Strategy {strategy_id}: Using override lookback = {strategy_lookback}")
                else:
                    strategy_lookback = StrategyLoader.calculate_lookback_period(
                        original_strategy, config.file_path
                    )
                    logger.info(f"Strategy {strategy_id}: Calculated lookback = {strategy_lookback}")
                
                # Update config with calculated lookback
                config.lookback_period = strategy_lookback
                
                # Track maximum
                max_lookback = max(max_lookback, strategy_lookback)
                
            except Exception as e:
                logger.error(f"Failed to calculate lookback for {strategy_id}: {e}")
                # Use default lookback for this strategy
                default_lookback = self.lookback_override or 20
                config.lookback_period = default_lookback
                max_lookback = max(max_lookback, default_lookback)
                logger.warning(f"Strategy {strategy_id}: Using default lookback = {default_lookback}")
        
        self.max_lookback_period = max_lookback
        logger.info(f"Maximum lookback across all strategies: {max_lookback} bars")
    
    def get_max_lookback_period(self) -> int:
        """Get the maximum lookback period required across all strategies"""
        return self.max_lookback_period
    
    def initialize_strategies(self):
        """Load and initialize all strategy classes"""
        logger.info("Initializing strategy classes...")
        
        for strategy_id, config in self.strategy_configs.items():
            try:
                # Load strategy class from file
                strategy_class = StrategyLoader.load_strategy_from_file(config.file_path)
                
                # Convert to signal-generating strategy
                signal_strategy_class = StrategyLoader.convert_to_signal_strategy(strategy_class)
                
                # Create signal extractor with individual strategy's lookback requirement
                signal_extractor = LiveSignalExtractor(
                    signal_strategy_class,
                    min_bars_required=config.lookback_period
                )
                
                # Update config
                config.strategy_class = signal_strategy_class
                config.signal_extractor = signal_extractor
                
                # Initialize strategy status
                self.strategy_status[strategy_id] = "initialized"
                
                logger.info(f"✅ Initialized strategy: {strategy_id} (lookback: {config.lookback_period})")
                
            except Exception as e:
                logger.error(f"❌ Failed to initialize strategy {strategy_id}: {e}")
                self.strategy_status[strategy_id] = f"error: {e}"
                raise
        
        logger.info(f"Successfully initialized {len(self.strategy_configs)} strategies")
    
    def update_portfolio_value(self, account_value: float):
        """Update portfolio manager with current account value"""
        if self.portfolio_manager:
            self.portfolio_manager.update_account_value(account_value)
            logger.debug(f"Updated portfolio value to ${account_value:,.2f}")
    
    async def generate_signals(self, symbol: str, historical_data) -> Dict[str, TradingSignal]:
        """
        Generate signals from all strategies for a given symbol
        
        Args:
            symbol: Symbol to generate signals for
            historical_data: Historical price data
            
        Returns:
            Dictionary mapping strategy_id to TradingSignal
        """
        signals = {}
        
        for strategy_id, config in self.strategy_configs.items():
            if not config.signal_extractor:
                continue
            
            try:
                # Extract signal from strategy
                signal = config.signal_extractor.extract_signal(historical_data)
                
                # Add strategy ID to signal
                signal.strategy_id = strategy_id
                
                signals[strategy_id] = signal
                
                # Update active signals tracking
                if strategy_id not in self.active_signals:
                    self.active_signals[strategy_id] = {}
                self.active_signals[strategy_id][symbol] = signal
                
                # Log non-hold signals
                if signal.signal != SignalType.HOLD:
                    logger.info(f"Signal from {strategy_id} for {symbol}: {signal.signal.value} "
                              f"@ ${signal.price:.2f}")
                
            except Exception as e:
                logger.error(f"Error generating signal from {strategy_id} for {symbol}: {e}")
                # Create error signal
                signals[strategy_id] = TradingSignal(
                    signal=SignalType.HOLD,
                    confidence=0.0,
                    price=0.0,
                    timestamp=historical_data.index[-1] if len(historical_data) > 0 else None,
                    indicators={},
                    strategy_id=strategy_id
                )
        
        return signals
    
    def validate_signal(self, signal: TradingSignal, symbol: str) -> Tuple[bool, str]:
        """
        Validate a signal against portfolio constraints
        
        Args:
            signal: Trading signal to validate
            symbol: Symbol the signal is for
            
        Returns:
            Tuple of (is_valid: bool, reason: str)
        """
        if not self.portfolio_manager:
            return False, "Portfolio manager not initialized"
        
        strategy_id = signal.strategy_id
        if not strategy_id:
            return False, "Signal missing strategy_id"
        
        # Validate buy signals
        if signal.signal in [SignalType.BUY, SignalType.LIMIT_BUY, SignalType.STOP_BUY, 
                           SignalType.STOP_LIMIT_BUY]:
            
            # Estimate order amount (simplified calculation)
            # In practice, this would need account value and signal size
            estimated_amount = 1000.0  # Placeholder - should be calculated properly
            if signal.size:
                estimated_amount *= signal.size
            
            return self.portfolio_manager.can_buy(strategy_id, symbol, estimated_amount)
        
        # Validate sell signals
        elif signal.signal in [SignalType.SELL, SignalType.CLOSE, SignalType.LIMIT_SELL,
                             SignalType.STOP_SELL, SignalType.STOP_LIMIT_SELL, 
                             SignalType.TRAILING_STOP_SELL]:
            
            return self.portfolio_manager.can_sell(strategy_id, symbol)
        
        # Hold signals are always valid
        elif signal.signal == SignalType.HOLD:
            return True, "OK"
        
        return False, f"Unknown signal type: {signal.signal}"
    
    def record_execution(self, signal: TradingSignal, symbol: str, execution_amount: float, 
                        execution_successful: bool):
        """
        Record the result of signal execution
        
        Args:
            signal: Signal that was executed
            symbol: Symbol that was traded
            execution_amount: Dollar amount of the trade
            execution_successful: Whether execution was successful
        """
        if not execution_successful or not self.portfolio_manager:
            return
        
        strategy_id = signal.strategy_id
        if not strategy_id:
            logger.error("Cannot record execution for signal without strategy_id")
            return
        
        # Record buy/sell in portfolio manager
        if signal.signal in [SignalType.BUY, SignalType.LIMIT_BUY, SignalType.STOP_BUY, 
                           SignalType.STOP_LIMIT_BUY]:
            self.portfolio_manager.record_buy(strategy_id, symbol, execution_amount)
            
        elif signal.signal in [SignalType.SELL, SignalType.CLOSE, SignalType.LIMIT_SELL,
                             SignalType.STOP_SELL, SignalType.STOP_LIMIT_SELL, 
                             SignalType.TRAILING_STOP_SELL]:
            self.portfolio_manager.record_sell(strategy_id, symbol, execution_amount)
    
    def get_strategy_status_summary(self) -> str:
        """Get a formatted summary of all strategy statuses"""
        if not self.portfolio_manager:
            return "Portfolio manager not initialized"
        
        status = self.portfolio_manager.get_all_status()
        
        lines = []
        lines.append("=" * 60)
        lines.append("MULTI-STRATEGY STATUS")
        lines.append("=" * 60)
        lines.append(f"Total Account Value: ${status['total_account_value']:,.2f}")
        lines.append(f"Active Positions: {status['total_symbols_owned']}")
        lines.append("")
        
        for strategy_id, strategy_info in status['strategies'].items():
            allocation_pct = strategy_info['allocation_percentage'] * 100
            lines.append(f"Strategy: {strategy_id} ({allocation_pct:.1f}%)")
            lines.append(f"  Allocated: ${strategy_info['total_allocated']:,.2f}")
            lines.append(f"  Available: ${strategy_info['available_capital']:,.2f}")
            lines.append(f"  Positions: {strategy_info['position_count']} ({', '.join(strategy_info['owned_symbols'])})")
            lines.append("")
        
        return "\n".join(lines)
    
    def get_strategy_configs(self) -> Dict[str, StrategyConfig]:
        """Get all strategy configurations"""
        return self.strategy_configs.copy()
    
    def get_strategy_ids(self) -> List[str]:
        """Get list of all strategy IDs"""
        return list(self.strategy_configs.keys()) 