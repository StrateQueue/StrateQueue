"""
Signal Coordination

Handles signal generation and validation across multiple strategies:
- Strategy initialization and lifecycle management
- Multi-strategy signal generation
- Signal validation against portfolio constraints
- Strategy status tracking
"""

import logging
from typing import Dict, List, Tuple, Optional

from ..core.strategy_loader import StrategyLoader
from ..core.signal_extractor import LiveSignalExtractor, TradingSignal, SignalType
from .config import StrategyConfig

logger = logging.getLogger(__name__)

class SignalCoordinator:
    """Coordinates signal generation across multiple strategies"""
    
    def __init__(self, strategy_configs: Dict[str, StrategyConfig]):
        """
        Initialize SignalCoordinator
        
        Args:
            strategy_configs: Dictionary of strategy configurations
        """
        self.strategy_configs = strategy_configs
        self.strategy_status: Dict[str, str] = {}
        self.active_signals: Dict[str, Dict[str, TradingSignal]] = {}  # strategy_id -> symbol -> signal
        
    def initialize_strategies(self):
        """Load and initialize all strategy classes"""
        logger.info("Initializing strategy classes...")
        
        for strategy_id, config in self.strategy_configs.items():
            try:
                # Use cached strategy class or load from file if not cached
                if config.strategy_class is not None:
                    strategy_class = config.strategy_class
                else:
                    # Load strategy class from file (fallback if not cached)
                    strategy_class = StrategyLoader.load_strategy_from_file(config.file_path)
                    config.strategy_class = strategy_class
                
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
    
    def validate_signal(self, signal: TradingSignal, symbol: str, portfolio_manager) -> Tuple[bool, str]:
        """
        Validate a signal against portfolio constraints
        
        Args:
            signal: Trading signal to validate
            symbol: Symbol the signal is for
            portfolio_manager: Portfolio manager instance for validation
            
        Returns:
            Tuple of (is_valid: bool, reason: str)
        """
        if not portfolio_manager:
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
            if hasattr(signal, 'size') and signal.size:
                estimated_amount *= signal.size
            
            return portfolio_manager.can_buy(strategy_id, symbol, estimated_amount)
        
        # Validate sell signals
        elif signal.signal in [SignalType.SELL, SignalType.CLOSE, SignalType.LIMIT_SELL,
                             SignalType.STOP_SELL, SignalType.STOP_LIMIT_SELL, 
                             SignalType.TRAILING_STOP_SELL]:
            
            # Use None for quantity to check full position sell capability
            return portfolio_manager.can_sell(strategy_id, symbol, None)
        
        # Hold signals are always valid
        elif signal.signal == SignalType.HOLD:
            return True, "OK"
        
        return False, f"Unknown signal type: {signal.signal}"
    
    def get_strategy_status(self, strategy_id: str) -> str:
        """Get status of a specific strategy"""
        return self.strategy_status.get(strategy_id, "unknown")
    
    def get_all_strategy_statuses(self) -> Dict[str, str]:
        """Get status of all strategies"""
        return self.strategy_status.copy()
    
    def get_active_signals(self) -> Dict[str, Dict[str, TradingSignal]]:
        """Get all currently active signals"""
        return self.active_signals.copy()
    
    def get_signals_for_symbol(self, symbol: str) -> Dict[str, TradingSignal]:
        """Get all active signals for a specific symbol"""
        signals = {}
        for strategy_id, symbol_signals in self.active_signals.items():
            if symbol in symbol_signals:
                signals[strategy_id] = symbol_signals[symbol]
        return signals
    
    def clear_signals_for_symbol(self, symbol: str):
        """Clear all signals for a specific symbol"""
        for strategy_id in self.active_signals:
            if symbol in self.active_signals[strategy_id]:
                del self.active_signals[strategy_id][symbol]
    
    def get_strategy_count(self) -> int:
        """Get total number of strategies"""
        return len(self.strategy_configs)
    
    def is_strategy_active(self, strategy_id: str) -> bool:
        """Check if a strategy is active and working"""
        status = self.strategy_status.get(strategy_id, "unknown")
        return status == "initialized" or status == "running" 