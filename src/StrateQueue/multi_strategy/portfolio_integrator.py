"""
Portfolio Integration

Handles portfolio management integration for multi-strategy trading:
- Portfolio manager initialization and coordination
- Trade execution recording
- Portfolio value updates
- Status reporting and monitoring
"""

import logging

from ..core.portfolio_manager import SimplePortfolioManager
from ..core.signal_extractor import SignalType, TradingSignal

logger = logging.getLogger(__name__)


class PortfolioIntegrator:
    """Integrates multi-strategy trading with portfolio management"""

    def __init__(self, strategy_allocations: dict[str, float], statistics_manager=None):
        """
        Initialize PortfolioIntegrator

        Args:
            strategy_allocations: Dictionary mapping strategy_id to allocation percentage
            statistics_manager: Optional statistics manager for trade tracking
        """
        self.strategy_allocations = strategy_allocations
        self.statistics_manager = statistics_manager
        self.portfolio_manager: SimplePortfolioManager | None = None

        # Initialize portfolio manager with allocations
        self._initialize_portfolio_manager()

    def _initialize_portfolio_manager(self):
        """Initialize the portfolio manager with strategy allocations"""
        try:
            self.portfolio_manager = SimplePortfolioManager(self.strategy_allocations)
            logger.info(
                f"Initialized portfolio manager with {len(self.strategy_allocations)} strategy allocations"
            )
        except Exception as e:
            logger.error(f"Failed to initialize portfolio manager: {e}")
            raise

    def update_portfolio_value(self, account_value: float):
        """
        Update portfolio manager with current account value

        Args:
            account_value: Current total account value
        """
        if self.portfolio_manager:
            self.portfolio_manager.update_account_value(account_value)
            logger.debug(f"Updated portfolio value to ${account_value:,.2f}")
        else:
            logger.warning("Portfolio manager not initialized - cannot update value")

    def can_execute_signal(self, signal: TradingSignal, symbol: str) -> tuple[bool, str]:
        """
        Check if a signal can be executed based on portfolio constraints

        Args:
            signal: Trading signal to check
            symbol: Symbol the signal is for

        Returns:
            Tuple of (can_execute: bool, reason: str)
        """
        if not self.portfolio_manager:
            return False, "Portfolio manager not initialized"

        strategy_id = signal.strategy_id
        if not strategy_id:
            return False, "Signal missing strategy_id"

        # Check buy signals
        if signal.signal in [
            SignalType.BUY,
            SignalType.LIMIT_BUY,
            SignalType.STOP_BUY,
            SignalType.STOP_LIMIT_BUY,
        ]:

            # Estimate order amount (simplified calculation)
            estimated_amount = 1000.0  # Placeholder - should be calculated properly
            if hasattr(signal, "size") and signal.size:
                estimated_amount *= signal.size

            return self.portfolio_manager.can_buy(strategy_id, symbol, estimated_amount)

        # Check sell signals
        elif signal.signal in [
            SignalType.SELL,
            SignalType.CLOSE,
            SignalType.LIMIT_SELL,
            SignalType.STOP_SELL,
            SignalType.STOP_LIMIT_SELL,
            SignalType.TRAILING_STOP_SELL,
        ]:

            # Use None for quantity to check full position sell capability
            return self.portfolio_manager.can_sell(strategy_id, symbol, None)

        # Hold signals are always valid
        elif signal.signal == SignalType.HOLD:
            return True, "OK"

        return False, f"Unknown signal type: {signal.signal}"

    def record_execution(
        self,
        signal: TradingSignal,
        symbol: str,
        execution_amount: float,
        execution_successful: bool,
    ):
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
        if signal.signal in [
            SignalType.BUY,
            SignalType.LIMIT_BUY,
            SignalType.STOP_BUY,
            SignalType.STOP_LIMIT_BUY,
        ]:
            self.portfolio_manager.record_buy(strategy_id, symbol, execution_amount)
            logger.info(f"Recorded buy execution: {strategy_id} {symbol} ${execution_amount:.2f}")

            # Record in statistics manager
            if self.statistics_manager:
                # Estimate quantity from execution amount and signal price
                estimated_quantity = execution_amount / signal.price if signal.price else 0
                self.statistics_manager.record_trade(
                    timestamp=signal.timestamp,
                    strategy_id=strategy_id,
                    symbol=symbol,
                    action="buy",
                    quantity=estimated_quantity,
                    price=signal.price,
                    commission=0.0,
                )

        elif signal.signal in [
            SignalType.SELL,
            SignalType.CLOSE,
            SignalType.LIMIT_SELL,
            SignalType.STOP_SELL,
            SignalType.STOP_LIMIT_SELL,
            SignalType.TRAILING_STOP_SELL,
        ]:
            self.portfolio_manager.record_sell(strategy_id, symbol, execution_amount)
            logger.info(f"Recorded sell execution: {strategy_id} {symbol} ${execution_amount:.2f}")

            # Record in statistics manager
            if self.statistics_manager:
                # Estimate quantity from execution amount and signal price
                estimated_quantity = execution_amount / signal.price if signal.price else 0
                self.statistics_manager.record_trade(
                    timestamp=signal.timestamp,
                    strategy_id=strategy_id,
                    symbol=symbol,
                    action="sell",
                    quantity=estimated_quantity,
                    price=signal.price,
                    commission=0.0,
                )

    def get_strategy_status_summary(self) -> str:
        """
        Get a formatted summary of all strategy statuses

        Returns:
            Formatted string with portfolio status
        """
        if not self.portfolio_manager:
            return "Portfolio manager not initialized"

        status = self.portfolio_manager.get_all_status()

        lines = []
        lines.append("=" * 60)
        lines.append("MULTI-STRATEGY PORTFOLIO STATUS")
        lines.append("=" * 60)
        lines.append(f"Total Account Value: ${status['total_account_value']:,.2f}")
        lines.append(f"Active Positions: {status['total_unique_symbols']}")
        lines.append("")

        for strategy_id, strategy_info in status["strategies"].items():
            allocation_pct = strategy_info["allocation_percentage"] * 100
            lines.append(f"Strategy: {strategy_id} ({allocation_pct:.1f}%)")
            lines.append(f"  Allocated: ${strategy_info['total_allocated']:,.2f}")
            lines.append(f"  Available: ${strategy_info['available_capital']:,.2f}")
            lines.append(
                f"  Positions: {strategy_info['position_count']} ({', '.join(strategy_info['held_symbols'])})"
            )
            lines.append("")

        return "\n".join(lines)

    def get_portfolio_status(self) -> dict:
        """
        Get the raw portfolio status data

        Returns:
            Dictionary with portfolio status information
        """
        if not self.portfolio_manager:
            return {"error": "Portfolio manager not initialized"}

        return self.portfolio_manager.get_all_status()

    def get_strategy_allocation(self, strategy_id: str) -> float:
        """
        Get the allocation percentage for a specific strategy

        Args:
            strategy_id: Strategy identifier

        Returns:
            Allocation percentage (0.0 to 1.0)
        """
        # First try the portfolio manager (handles runtime additions)
        if self.portfolio_manager and strategy_id in self.portfolio_manager.strategy_allocations:
            allocation = self.portfolio_manager.strategy_allocations[
                strategy_id
            ].allocation_percentage
            # Sync our local dictionary for consistency
            if strategy_id not in self.strategy_allocations:
                self.strategy_allocations[strategy_id] = allocation
                logger.info(f"Synced strategy allocation: {strategy_id} = {allocation:.1%}")
            return allocation

        # Fallback to initial allocations (for backward compatibility)
        return self.strategy_allocations.get(strategy_id, 0.0)

    def get_available_capital(self, strategy_id: str) -> float:
        """
        Get available capital for a specific strategy

        Args:
            strategy_id: Strategy identifier

        Returns:
            Available capital amount
        """
        if not self.portfolio_manager:
            return 0.0

        try:
            status = self.portfolio_manager.get_strategy_status(strategy_id)
            return status.get("available_capital", 0.0)
        except Exception as e:
            logger.error(f"Error getting available capital for {strategy_id}: {e}")
            return 0.0

    def get_strategy_positions(self, strategy_id: str) -> dict:
        """
        Get current positions for a specific strategy

        Args:
            strategy_id: Strategy identifier

        Returns:
            Dictionary with position information
        """
        if not self.portfolio_manager:
            return {}

        try:
            status = self.portfolio_manager.get_strategy_status(strategy_id)
            return {
                "owned_symbols": status.get("held_symbols", []),
                "position_count": status.get("position_count", 0),
            }
        except Exception as e:
            logger.error(f"Error getting positions for {strategy_id}: {e}")
            return {"owned_symbols": [], "position_count": 0}

    def is_portfolio_healthy(self) -> tuple[bool, str]:
        """
        Check if the portfolio is in a healthy state

        Returns:
            Tuple of (is_healthy: bool, status_message: str)
        """
        if not self.portfolio_manager:
            return False, "Portfolio manager not initialized"

        try:
            status = self.portfolio_manager.get_all_status()
            total_value = status.get("total_account_value", 0)

            if total_value <= 0:
                return False, "Account value is zero or negative"

            # Check if any strategy has excessive allocation
            for strategy_id, strategy_info in status.get("strategies", {}).items():
                allocation = strategy_info.get("allocation_percentage", 0)
                if allocation > 0.5:  # More than 50% to one strategy
                    return (
                        False,
                        f"Strategy {strategy_id} has excessive allocation: {allocation:.1%}",
                    )

            return True, "Portfolio is healthy"

        except Exception as e:
            return False, f"Error checking portfolio health: {e}"
