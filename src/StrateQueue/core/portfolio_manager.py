"""
Simple Portfolio Manager for Multi-Strategy Trading

This module handles:
1. Capital allocation tracking per strategy
2. Position tracking per strategy per symbol (multiple strategies can own same symbol)
3. Order validation against capital limits and strategy positions
4. Simple buy/sell permission checking based on strategy-specific holdings
5. Trade tracking updates
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StrategyPosition:
    """Track position data for a strategy in a specific symbol"""

    symbol: str
    quantity: float = 0.0
    total_cost: float = 0.0

    @property
    def avg_cost(self) -> float:
        """Calculate average cost per unit"""
        return self.total_cost / self.quantity if self.quantity > 0 else 0.0


@dataclass
class StrategyAllocation:
    """Strategy capital allocation configuration with position tracking"""

    strategy_id: str
    allocation_percentage: float
    total_allocated: float = 0.0
    total_spent: float = 0.0
    positions: dict[str, StrategyPosition] = field(default_factory=dict)

    @property
    def available_capital(self) -> float:
        """Calculate available capital for this strategy"""
        return self.total_allocated - self.total_spent

    def get_position(self, symbol: str) -> StrategyPosition | None:
        """Get position for a symbol, or None if no position"""
        return self.positions.get(symbol)

    def has_position(self, symbol: str) -> bool:
        """Check if strategy has any position in symbol"""
        position = self.positions.get(symbol)
        # Consider it a position if we have quantity OR if we have cost basis (for unknown quantities)
        return position is not None and (position.quantity > 0 or position.total_cost > 0)


class SimplePortfolioManager:
    """
    Simple portfolio manager for multi-strategy trading.

    Handles capital allocation, per-strategy position tracking, and allows
    multiple strategies to hold positions in the same symbol simultaneously.
    """

    def __init__(self, strategy_allocations: dict[str, float]):
        """
        Initialize portfolio manager with strategy allocations

        Args:
            strategy_allocations: Dict mapping strategy_id to allocation percentage
                                 Example: {"sma": 0.4, "momentum": 0.35, "random": 0.25}
        """
        self.strategy_allocations = {}
        for strategy_id, percentage in strategy_allocations.items():
            self.strategy_allocations[strategy_id] = StrategyAllocation(
                strategy_id=strategy_id, allocation_percentage=percentage
            )

        # Track total account value for capital calculations
        self.total_account_value: float = 0.0

        logger.info(f"Initialized portfolio manager with {len(strategy_allocations)} strategies")
        for strategy_id, alloc in self.strategy_allocations.items():
            logger.info(f"  • {strategy_id}: {alloc.allocation_percentage:.1%} allocation")

    def add_strategy(self, strategy_id: str, allocation_percentage: float):
        """
        Add a new strategy allocation (convenience method for testing)

        Args:
            strategy_id: Strategy identifier
            allocation_percentage: Allocation percentage (0.0 to 1.0)
        """
        self.strategy_allocations[strategy_id] = StrategyAllocation(
            strategy_id=strategy_id, allocation_percentage=allocation_percentage
        )

        # Update allocations if account value is set
        if self.total_account_value > 0:
            self.strategy_allocations[strategy_id].total_allocated = (
                self.total_account_value * allocation_percentage
            )

        logger.info(f"Added strategy {strategy_id}: {allocation_percentage:.1%} allocation")

    # HOT SWAP METHODS

    def add_strategy_runtime(self, strategy_id: str, allocation_percentage: float) -> bool:
        """
        Add a new strategy allocation at runtime with automatic rebalancing

        Args:
            strategy_id: Strategy identifier
            allocation_percentage: Allocation percentage (0.0 to 1.0)

        Returns:
            True if strategy was added successfully
        """
        try:
            if strategy_id in self.strategy_allocations:
                logger.warning(f"Strategy {strategy_id} already exists in portfolio, skipping add")
                return False

            # Check if new allocation would exceed 100%
            current_total = sum(
                alloc.allocation_percentage for alloc in self.strategy_allocations.values()
            )
            if current_total + allocation_percentage > 1.01:  # Allow small rounding error
                logger.error(
                    f"Cannot add strategy {strategy_id}: would exceed 100% allocation "
                    f"(current: {current_total:.1%}, adding: {allocation_percentage:.1%})"
                )
                return False

            # Add the strategy
            self.add_strategy(strategy_id, allocation_percentage)

            logger.info(
                f"🔥 Hot-added strategy to portfolio: {strategy_id} ({allocation_percentage:.1%})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to hot-add strategy {strategy_id} to portfolio: {e}")
            return False

    def remove_strategy_runtime(self, strategy_id: str, liquidate_positions: bool = True) -> bool:
        """
        Remove a strategy allocation at runtime

        Args:
            strategy_id: Strategy to remove
            liquidate_positions: Whether to liquidate all positions for this strategy

        Returns:
            True if strategy was removed successfully
        """
        try:
            if strategy_id not in self.strategy_allocations:
                logger.warning(f"Strategy {strategy_id} not found in portfolio, cannot remove")
                return False

            # Log positions that will be affected
            positions = self.strategy_allocations[strategy_id].positions
            if positions and liquidate_positions:
                logger.warning(
                    f"Strategy {strategy_id} has {len(positions)} positions that will be orphaned"
                )
                for symbol, position in positions.items():
                    if position.quantity > 0:
                        logger.warning(
                            f"  • {symbol}: {position.quantity} shares, ${position.total_cost:.2f} cost basis"
                        )

            # Remove from portfolio
            removed_allocation = self.strategy_allocations[strategy_id].allocation_percentage
            del self.strategy_allocations[strategy_id]

            logger.info(
                f"🔥 Hot-removed strategy from portfolio: {strategy_id} "
                f"(freed {removed_allocation:.1%} allocation)"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to hot-remove strategy {strategy_id} from portfolio: {e}")
            return False

    def rebalance_allocations(self, new_allocations: dict[str, float]) -> bool:
        """
        Rebalance strategy allocations at runtime

        Args:
            new_allocations: New allocation percentages for strategies

        Returns:
            True if rebalancing was successful
        """
        try:
            # Validate new allocations (allow ≤ 100% for cash reserves)
            total_allocation = sum(new_allocations.values())
            if total_allocation > 1.0:
                logger.error(f"New allocations sum to {total_allocation:.1%}, which exceeds 100%")
                return False
            elif total_allocation <= 0.0:
                logger.error(
                    f"New allocations sum to {total_allocation:.1%}, which must be positive"
                )
                return False
            elif total_allocation < 1.0:
                cash_reserve = 1.0 - total_allocation
                logger.info(
                    f"New allocations sum to {total_allocation:.1%}. "
                    f"Keeping {cash_reserve:.1%} in cash reserves."
                )

            # Check if all strategies exist
            for strategy_id in new_allocations:
                if strategy_id not in self.strategy_allocations:
                    logger.error(f"Strategy {strategy_id} not found in portfolio")
                    return False

            # Apply new allocations
            old_allocations = {}
            for strategy_id, new_percentage in new_allocations.items():
                old_percentage = self.strategy_allocations[strategy_id].allocation_percentage
                old_allocations[strategy_id] = old_percentage

                self.strategy_allocations[strategy_id].allocation_percentage = new_percentage

                # Update allocated amounts if account value is set
                if self.total_account_value > 0:
                    self.strategy_allocations[strategy_id].total_allocated = (
                        self.total_account_value * new_percentage
                    )

                logger.info(f"Strategy {strategy_id}: {old_percentage:.1%} → {new_percentage:.1%}")

            logger.info("🔥 Portfolio rebalanced successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to rebalance portfolio: {e}")
            # Restore old allocations on failure
            for strategy_id, old_percentage in old_allocations.items():
                if strategy_id in self.strategy_allocations:
                    self.strategy_allocations[strategy_id].allocation_percentage = old_percentage
                    if self.total_account_value > 0:
                        self.strategy_allocations[strategy_id].total_allocated = (
                            self.total_account_value * old_percentage
                        )
            return False

    def update_account_value(self, account_value: float):
        """
        Update total account value and recalculate strategy allocations

        Args:
            account_value: Current total account value
        """
        self.total_account_value = account_value

        # Update allocated amounts for each strategy
        for strategy_id, alloc in self.strategy_allocations.items():
            alloc.total_allocated = account_value * alloc.allocation_percentage
            logger.debug(
                f"Strategy {strategy_id}: ${alloc.total_allocated:,.2f} allocated "
                f"(${alloc.available_capital:,.2f} available)"
            )

    def can_buy(self, strategy_id: str, symbol: str, amount: float) -> tuple[bool, str]:
        """
        Check if a strategy can buy a symbol

        Args:
            strategy_id: Strategy requesting the buy
            symbol: Symbol to buy
            amount: Dollar amount to spend

        Returns:
            Tuple of (can_buy: bool, reason: str)
        """
        # Check if strategy exists
        if strategy_id not in self.strategy_allocations:
            return False, f"Unknown strategy: {strategy_id}"

        # Multiple strategies can now buy the same symbol - no ownership conflict checking

        # Check capital availability
        strategy_alloc = self.strategy_allocations[strategy_id]
        if amount > strategy_alloc.available_capital:
            return False, (
                f"Insufficient capital for {strategy_id}: "
                f"${amount:,.2f} requested, ${strategy_alloc.available_capital:,.2f} available"
            )

        return True, "OK"

    def can_sell(
        self, strategy_id: str, symbol: str, quantity: float | None = None
    ) -> tuple[bool, str]:
        """
        Check if a strategy can sell a symbol

        Args:
            strategy_id: Strategy requesting the sell
            symbol: Symbol to sell
            quantity: Optional quantity to sell (if None, assumes full position)

        Returns:
            Tuple of (can_sell: bool, reason: str)
        """
        # Check if strategy exists
        if strategy_id not in self.strategy_allocations:
            return False, f"Unknown strategy: {strategy_id}"

        # Check if strategy has position in this symbol
        strategy_alloc = self.strategy_allocations[strategy_id]
        if not strategy_alloc.has_position(symbol):
            return False, f"Strategy {strategy_id} has no position in {symbol}"

        # Check if strategy has enough quantity to sell
        if quantity is not None:
            position = strategy_alloc.get_position(symbol)
            if position and quantity > position.quantity:
                return False, (
                    f"Strategy {strategy_id} cannot sell {quantity} of {symbol}: "
                    f"only owns {position.quantity}"
                )

        return True, "OK"

    def record_buy(
        self, strategy_id: str, symbol: str, amount: float, quantity: float | None = None
    ):
        """
        Record a successful buy transaction

        Args:
            strategy_id: Strategy that executed the buy
            symbol: Symbol that was bought
            amount: Dollar amount spent
            quantity: Optional quantity bought (if known)
        """
        if strategy_id not in self.strategy_allocations:
            logger.error(f"Cannot record buy for unknown strategy: {strategy_id}")
            return

        strategy_alloc = self.strategy_allocations[strategy_id]

        # Update capital tracking
        strategy_alloc.total_spent += amount

        # Update position tracking
        if symbol not in strategy_alloc.positions:
            strategy_alloc.positions[symbol] = StrategyPosition(symbol=symbol)

        position = strategy_alloc.positions[symbol]
        position.total_cost += amount

        if quantity is not None:
            position.quantity += quantity

        logger.info(f"Recorded buy: {strategy_id} bought {symbol} for ${amount:,.2f}")
        if quantity:
            logger.debug(
                f"  Position: {position.quantity} shares @ ${position.avg_cost:.2f} avg cost"
            )
        logger.debug(
            f"Strategy {strategy_id} capital: "
            f"${strategy_alloc.available_capital:,.2f} remaining"
        )

    def record_sell(
        self, strategy_id: str, symbol: str, amount: float, quantity: float | None = None
    ):
        """
        Record a successful sell transaction

        Args:
            strategy_id: Strategy that executed the sell
            symbol: Symbol that was sold
            amount: Dollar amount received
            quantity: Optional quantity sold (if known)
        """
        if strategy_id not in self.strategy_allocations:
            logger.error(f"Cannot record sell for unknown strategy: {strategy_id}")
            return

        strategy_alloc = self.strategy_allocations[strategy_id]

        # Update capital tracking (add back proceeds)
        strategy_alloc.total_spent -= amount

        # Update position tracking
        if symbol in strategy_alloc.positions:
            position = strategy_alloc.positions[symbol]

            if quantity is not None:
                # Partial sell - reduce quantity proportionally
                if quantity >= position.quantity:
                    # Selling full position
                    del strategy_alloc.positions[symbol]
                else:
                    # Partial sell - reduce position
                    cost_ratio = quantity / position.quantity
                    position.total_cost *= 1 - cost_ratio
                    position.quantity -= quantity
            else:
                # Full position sell
                del strategy_alloc.positions[symbol]

        logger.info(f"Recorded sell: {strategy_id} sold {symbol} for ${amount:,.2f}")
        if quantity:
            logger.debug(f"  Sold quantity: {quantity}")
        logger.debug(
            f"Strategy {strategy_id} capital: "
            f"${strategy_alloc.available_capital:,.2f} available"
        )

    def get_strategy_positions(self, strategy_id: str) -> dict[str, StrategyPosition]:
        """
        Get all positions for a strategy

        Args:
            strategy_id: Strategy to get positions for

        Returns:
            Dictionary mapping symbol to StrategyPosition
        """
        if strategy_id not in self.strategy_allocations:
            return {}

        return self.strategy_allocations[strategy_id].positions.copy()

    def get_all_symbol_holders(self, symbol: str) -> set[str]:
        """
        Get all strategies that hold positions in a symbol

        Args:
            symbol: Symbol to check

        Returns:
            Set of strategy IDs that hold positions in the symbol
        """
        holders = set()
        for strategy_id, alloc in self.strategy_allocations.items():
            if alloc.has_position(symbol):
                holders.add(strategy_id)
        return holders

    def get_strategy_status(self, strategy_id: str) -> dict:
        """
        Get current status for a strategy

        Args:
            strategy_id: Strategy to get status for

        Returns:
            Dictionary with strategy status information
        """
        if strategy_id not in self.strategy_allocations:
            return {}

        alloc = self.strategy_allocations[strategy_id]
        position_symbols = list(alloc.positions.keys())

        # Calculate total position value
        total_position_value = sum(pos.total_cost for pos in alloc.positions.values())

        return {
            "strategy_id": strategy_id,
            "allocation_percentage": alloc.allocation_percentage,
            "total_allocated": alloc.total_allocated,
            "total_spent": alloc.total_spent,
            "available_capital": alloc.available_capital,
            "held_symbols": position_symbols,
            "position_count": len(position_symbols),
            "total_position_value": total_position_value,
            "positions": {
                sym: {
                    "quantity": pos.quantity,
                    "total_cost": pos.total_cost,
                    "avg_cost": pos.avg_cost,
                }
                for sym, pos in alloc.positions.items()
            },
        }

    def get_all_status(self) -> dict:
        """
        Get status for all strategies

        Returns:
            Dictionary with overall portfolio status
        """
        strategy_status = {}
        for strategy_id in self.strategy_allocations:
            strategy_status[strategy_id] = self.get_strategy_status(strategy_id)

        # Get symbol overlap analysis
        all_symbols = set()
        symbol_holders = {}
        for strategy_id, alloc in self.strategy_allocations.items():
            for symbol in alloc.positions:
                all_symbols.add(symbol)
                if symbol not in symbol_holders:
                    symbol_holders[symbol] = []
                symbol_holders[symbol].append(strategy_id)

        return {
            "total_account_value": self.total_account_value,
            "total_unique_symbols": len(all_symbols),
            "symbol_holders": symbol_holders,
            "strategies": strategy_status,
        }

    def validate_allocations(self) -> bool:
        """
        Validate that strategy allocations are reasonable

        Returns:
            True if allocations are valid, False otherwise
        """
        total_allocation = sum(
            alloc.allocation_percentage for alloc in self.strategy_allocations.values()
        )

        # Check individual allocations
        for strategy_id, alloc in self.strategy_allocations.items():
            if alloc.allocation_percentage < 0 or alloc.allocation_percentage > 1:
                logger.error(
                    f"Strategy {strategy_id} allocation {alloc.allocation_percentage:.2%} "
                    f"must be between 0% and 100%"
                )
                return False

        # Check total doesn't exceed 100%
        if total_allocation > 1.01:  # Allow small floating point errors
            logger.error(f"Total strategy allocations ({total_allocation:.2%}) exceed 100%")
            return False

        # Warn if significantly under-allocated (but allow it)
        if total_allocation < 0.5:
            logger.warning(
                f"Total strategy allocations ({total_allocation:.2%}) are quite low. "
                f"{(1.0 - total_allocation):.2%} of capital will remain in cash."
            )
        elif total_allocation < 1.0:
            logger.info(
                f"Total strategy allocations: {total_allocation:.2%}. "
                f"{(1.0 - total_allocation):.2%} of capital will remain in cash."
            )

        return True
