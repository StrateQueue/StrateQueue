"""
Multi-Strategy Runner

Main coordinator for multi-strategy trading that orchestrates:
- Configuration management
- Signal coordination
- Portfolio integration
- System lifecycle management
"""

import logging
from typing import Dict, List, Optional

from .config import ConfigManager, StrategyConfig
from .signal_coordinator import SignalCoordinator
from .portfolio_integrator import PortfolioIntegrator
from ..core.signal_extractor import TradingSignal

logger = logging.getLogger(__name__)

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
        
        # Initialize configuration manager
        self.config_manager = ConfigManager(config_file_path, lookback_override)
        
        # Load strategy configurations
        strategy_configs = self.config_manager.load_configurations()
        
        # Calculate lookback periods
        self.max_lookback_period = self.config_manager.calculate_lookback_periods()
        
        # Initialize signal coordinator
        self.signal_coordinator = SignalCoordinator(strategy_configs)
        
        # Initialize portfolio integrator
        allocations = self.config_manager.get_allocations()
        self.portfolio_integrator = PortfolioIntegrator(allocations)
        
        logger.info(f"Initialized multi-strategy runner with {len(strategy_configs)} strategies")
        logger.info(f"Maximum lookback period required: {self.max_lookback_period} bars")
    
    def initialize_strategies(self):
        """Initialize all strategy classes and signal extractors"""
        self.signal_coordinator.initialize_strategies()
        logger.info("Multi-strategy runner fully initialized")
    
    def get_max_lookback_period(self) -> int:
        """Get the maximum lookback period required across all strategies"""
        return self.max_lookback_period
    
    async def generate_signals(self, symbol: str, historical_data) -> Dict[str, TradingSignal]:
        """
        Generate signals from all strategies for a given symbol
        
        Args:
            symbol: Symbol to generate signals for
            historical_data: Historical price data
            
        Returns:
            Dictionary mapping strategy_id to TradingSignal
        """
        return await self.signal_coordinator.generate_signals(symbol, historical_data)
    
    def validate_signal(self, signal: TradingSignal, symbol: str) -> tuple[bool, str]:
        """
        Validate a signal against portfolio constraints
        
        Args:
            signal: Trading signal to validate
            symbol: Symbol the signal is for
            
        Returns:
            Tuple of (is_valid: bool, reason: str)
        """
        return self.portfolio_integrator.can_execute_signal(signal, symbol)
    
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
        self.portfolio_integrator.record_execution(signal, symbol, execution_amount, execution_successful)
    
    def update_portfolio_value(self, account_value: float):
        """
        Update portfolio manager with current account value
        
        Args:
            account_value: Current total account value
        """
        self.portfolio_integrator.update_portfolio_value(account_value)
    
    def get_strategy_status_summary(self) -> str:
        """Get a formatted summary of all strategy statuses"""
        return self.portfolio_integrator.get_strategy_status_summary()
    
    def get_strategy_configs(self) -> Dict[str, StrategyConfig]:
        """Get all strategy configurations"""
        return self.config_manager.get_strategy_configs()
    
    def get_strategy_ids(self) -> List[str]:
        """Get list of all strategy IDs"""
        return self.config_manager.get_strategy_ids()
    
    def get_active_signals(self) -> Dict[str, Dict[str, TradingSignal]]:
        """Get all currently active signals"""
        return self.signal_coordinator.get_active_signals()
    
    def get_signals_for_symbol(self, symbol: str) -> Dict[str, TradingSignal]:
        """Get all active signals for a specific symbol"""
        return self.signal_coordinator.get_signals_for_symbol(symbol)
    
    def get_strategy_status(self, strategy_id: str) -> str:
        """Get status of a specific strategy"""
        return self.signal_coordinator.get_strategy_status(strategy_id)
    
    def get_all_strategy_statuses(self) -> Dict[str, str]:
        """Get status of all strategies"""
        return self.signal_coordinator.get_all_strategy_statuses()
    
    def get_portfolio_status(self) -> Dict:
        """Get the raw portfolio status data"""
        return self.portfolio_integrator.get_portfolio_status()
    
    def get_strategy_allocation(self, strategy_id: str) -> float:
        """Get the allocation percentage for a specific strategy"""
        return self.portfolio_integrator.get_strategy_allocation(strategy_id)
    
    def get_available_capital(self, strategy_id: str) -> float:
        """Get available capital for a specific strategy"""
        return self.portfolio_integrator.get_available_capital(strategy_id)
    
    def get_strategy_positions(self, strategy_id: str) -> Dict:
        """Get current positions for a specific strategy"""
        return self.portfolio_integrator.get_strategy_positions(strategy_id)
    
    def is_system_healthy(self) -> tuple[bool, str]:
        """
        Check if the multi-strategy system is healthy
        
        Returns:
            Tuple of (is_healthy: bool, status_message: str)
        """
        # Check portfolio health
        portfolio_healthy, portfolio_msg = self.portfolio_integrator.is_portfolio_healthy()
        if not portfolio_healthy:
            return False, f"Portfolio issue: {portfolio_msg}"
        
        # Check strategy statuses
        strategy_statuses = self.signal_coordinator.get_all_strategy_statuses()
        failed_strategies = []
        
        for strategy_id, status in strategy_statuses.items():
            if "error" in status.lower():
                failed_strategies.append(strategy_id)
        
        if failed_strategies:
            return False, f"Failed strategies: {', '.join(failed_strategies)}"
        
        return True, "Multi-strategy system is healthy"
    
    def get_system_summary(self) -> Dict:
        """
        Get a comprehensive system summary
        
        Returns:
            Dictionary with system status information
        """
        strategy_configs = self.config_manager.get_strategy_configs()
        strategy_statuses = self.signal_coordinator.get_all_strategy_statuses()
        portfolio_status = self.portfolio_integrator.get_portfolio_status()
        active_signals = self.signal_coordinator.get_active_signals()
        is_healthy, health_msg = self.is_system_healthy()
        
        return {
            'strategy_count': len(strategy_configs),
            'strategy_ids': list(strategy_configs.keys()),
            'max_lookback_period': self.max_lookback_period,
            'strategy_statuses': strategy_statuses,
            'portfolio_status': portfolio_status,
            'active_signals_count': sum(len(signals) for signals in active_signals.values()),
            'is_healthy': is_healthy,
            'health_message': health_msg,
            'symbols': self.symbols
        }
    
    @property
    def portfolio_manager(self):
        """Access to the underlying portfolio manager for backward compatibility"""
        return self.portfolio_integrator.portfolio_manager 