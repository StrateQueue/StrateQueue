"""
Multi-Strategy Runner

Main coordinator for multi-strategy trading that orchestrates:
- Configuration management
- Signal coordination
- Portfolio integration
- System lifecycle management
- Hot swapping strategies at runtime
"""

import logging

from ..core.signal_extractor import TradingSignal
from ..core.strategy_loader import StrategyLoader
from .portfolio_integrator import PortfolioIntegrator
from .signal_coordinator import SignalCoordinator
from .strategy_config import ConfigManager, StrategyConfig

logger = logging.getLogger(__name__)

class MultiStrategyRunner:
    """
    Coordinates multiple trading strategies running in parallel.

    Handles strategy loading, signal coordination, and portfolio management
    integration for multi-strategy live trading with hot swapping support.
    """

    def __init__(self, config_file_path: str, symbols: list[str],
                 lookback_override: int | None = None, statistics_manager=None):
        """
        Initialize multi-strategy runner

        Args:
            config_file_path: Path to strategy configuration file
            symbols: List of symbols to trade across all strategies
            lookback_override: Override default lookback period with this value
            statistics_manager: Statistics manager for portfolio integration
        """
        self.config_file_path = config_file_path
        self.symbols = symbols
        self.lookback_override = lookback_override
        self.statistics_manager = statistics_manager

        # Initialize configuration manager
        self.config_manager = ConfigManager(config_file_path, lookback_override)

        # Load strategy configurations
        strategy_configs = self.config_manager.load_configurations()

        # Set lookback periods
        from .strategy_config import DEFAULT_LOOKBACK_PERIOD
        self.max_lookback_period = self.config_manager.set_lookback_periods(self.lookback_override or DEFAULT_LOOKBACK_PERIOD)

        # Initialize signal coordinator
        self.signal_coordinator = SignalCoordinator(strategy_configs)

        # Initialize portfolio integrator
        strategy_allocations = self.config_manager.get_allocations()
        self.portfolio_integrator = PortfolioIntegrator(strategy_allocations, statistics_manager)

        logger.info(f"Initialized multi-strategy runner with {len(strategy_configs)} strategies")
        logger.info(f"Maximum lookback period required: {self.max_lookback_period} bars")

    def initialize_strategies(self):
        """Initialize all loaded strategies"""
        self.signal_coordinator.initialize_strategies()
        logger.info("Multi-strategy runner initialization complete")

    def get_max_lookback_period(self) -> int:
        """Get the maximum lookback period required across all strategies"""
        return self.max_lookback_period

    async def generate_signals(self, symbol: str, historical_data) -> dict[str, TradingSignal]:
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

    def get_strategy_configs(self) -> dict[str, StrategyConfig]:
        """Get all strategy configurations"""
        return self.config_manager.get_strategy_configs()

    def get_strategy_ids(self) -> list[str]:
        """Get list of all strategy IDs"""
        return self.config_manager.get_strategy_ids()

    def get_active_signals(self) -> dict[str, dict[str, TradingSignal]]:
        """Get all currently active signals"""
        return self.signal_coordinator.get_active_signals()

    def get_signals_for_symbol(self, symbol: str) -> dict[str, TradingSignal]:
        """Get all active signals for a specific symbol"""
        return self.signal_coordinator.get_signals_for_symbol(symbol)

    def get_strategy_status(self, strategy_id: str) -> str:
        """Get status of a specific strategy"""
        return self.signal_coordinator.get_strategy_status(strategy_id)

    def get_all_strategy_statuses(self) -> dict[str, str]:
        """Get status of all strategies"""
        return self.signal_coordinator.get_all_strategy_statuses()

    def get_portfolio_status(self) -> dict:
        """Get the raw portfolio status data"""
        return self.portfolio_integrator.get_portfolio_status()

    def get_strategy_allocation(self, strategy_id: str) -> float:
        """Get the allocation percentage for a specific strategy"""
        return self.portfolio_integrator.get_strategy_allocation(strategy_id)

    def get_available_capital(self, strategy_id: str) -> float:
        """Get available capital for a specific strategy"""
        return self.portfolio_integrator.get_available_capital(strategy_id)

    def get_strategy_positions(self, strategy_id: str) -> dict:
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

    def get_system_summary(self) -> dict:
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

    # HOT SWAP COORDINATION METHODS

    def deploy_strategy_runtime(self, strategy_path: str, strategy_id: str,
                              allocation_percentage: float, symbol: str | None = None) -> bool:
        """
        Deploy a new strategy at runtime

        Args:
            strategy_path: Path to the strategy file
            strategy_id: Unique identifier for the strategy
            allocation_percentage: Allocation percentage (0.0 to 1.0)
            symbol: Optional symbol for 1:1 mapping (None for all symbols)

        Returns:
            True if strategy was deployed successfully
        """
        try:
            logger.info(f"🚀 Deploying strategy {strategy_id} at runtime...")

            # Load and validate strategy file
            StrategyLoader.load_strategy_from_file(strategy_path)

            # Set lookback period
            from .strategy_config import DEFAULT_LOOKBACK_PERIOD
            lookback_period = self.lookback_override or DEFAULT_LOOKBACK_PERIOD

            # Create strategy configuration
            config = StrategyConfig(
                strategy_id=strategy_id,
                file_path=strategy_path,
                allocation=allocation_percentage,
                lookback_period=lookback_period,
                symbol=symbol
            )

            # Add to signal coordinator
            if not self.signal_coordinator.add_strategy_runtime(strategy_id, config):
                logger.error(f"Failed to add strategy {strategy_id} to signal coordinator")
                return False

            # Add to portfolio manager
            if not self.portfolio_integrator.portfolio_manager.add_strategy_runtime(strategy_id, allocation_percentage):
                logger.error(f"Failed to add strategy {strategy_id} to portfolio manager")
                # Rollback signal coordinator changes
                self.signal_coordinator.remove_strategy_runtime(strategy_id)
                return False

            # If strategy has a specific symbol, make sure data manager is tracking it
            if symbol and hasattr(self, 'data_manager_ref') and self.data_manager_ref:
                if not self.data_manager_ref.add_symbol_runtime(symbol):
                    logger.warning(f"Failed to add symbol {symbol} to data manager, strategy may not get data")

            # Update max lookback if necessary
            if lookback_period > self.max_lookback_period:
                self.max_lookback_period = lookback_period
                logger.info(f"Updated max lookback period to {lookback_period}")

            logger.info(f"✅ Successfully deployed strategy {strategy_id} at runtime "
                       f"({allocation_percentage:.1%} allocation, {lookback_period} lookback)")
            return True

        except Exception as e:
            logger.error(f"Failed to deploy strategy {strategy_id} at runtime: {e}")
            return False

    def undeploy_strategy_runtime(self, strategy_id: str, liquidate_positions: bool = True) -> bool:
        """
        Undeploy a strategy at runtime

        Args:
            strategy_id: Strategy to undeploy
            liquidate_positions: Whether to liquidate all positions for this strategy

        Returns:
            True if strategy was undeployed successfully
        """
        try:
            logger.info(f"🛑 Undeploying strategy {strategy_id} at runtime...")

            # Remove from signal coordinator first (stops new signals)
            if not self.signal_coordinator.remove_strategy_runtime(strategy_id):
                logger.warning(f"Strategy {strategy_id} not found in signal coordinator")

            # Remove from portfolio manager
            if not self.portfolio_integrator.portfolio_manager.remove_strategy_runtime(strategy_id, liquidate_positions):
                logger.warning(f"Strategy {strategy_id} not found in portfolio manager")

            logger.info(f"✅ Successfully undeployed strategy {strategy_id} at runtime")
            return True

        except Exception as e:
            logger.error(f"Failed to undeploy strategy {strategy_id} at runtime: {e}")
            return False

    def pause_strategy_runtime(self, strategy_id: str) -> bool:
        """
        Pause a strategy at runtime (stops signal generation but keeps positions)

        Args:
            strategy_id: Strategy to pause

        Returns:
            True if strategy was paused successfully
        """
        try:
            if self.signal_coordinator.pause_strategy(strategy_id):
                logger.info(f"✅ Successfully paused strategy {strategy_id}")
                return True
            else:
                logger.error(f"Failed to pause strategy {strategy_id}")
                return False
        except Exception as e:
            logger.error(f"Error pausing strategy {strategy_id}: {e}")
            return False

    def resume_strategy_runtime(self, strategy_id: str) -> bool:
        """
        Resume a paused strategy at runtime

        Args:
            strategy_id: Strategy to resume

        Returns:
            True if strategy was resumed successfully
        """
        try:
            if self.signal_coordinator.resume_strategy(strategy_id):
                logger.info(f"✅ Successfully resumed strategy {strategy_id}")
                return True
            else:
                logger.error(f"Failed to resume strategy {strategy_id}")
                return False
        except Exception as e:
            logger.error(f"Error resuming strategy {strategy_id}: {e}")
            return False

    def rebalance_portfolio_runtime(self, new_allocations: dict[str, float]) -> bool:
        """
        Rebalance portfolio allocations at runtime

        Args:
            new_allocations: New allocation percentages for strategies

        Returns:
            True if rebalancing was successful
        """
        try:
            logger.info("⚖️ Rebalancing portfolio at runtime...")

            if self.portfolio_integrator.portfolio_manager.rebalance_allocations(new_allocations):
                logger.info("✅ Successfully rebalanced portfolio")
                return True
            else:
                logger.error("Failed to rebalance portfolio")
                return False

        except Exception as e:
            logger.error(f"Error rebalancing portfolio: {e}")
            return False
