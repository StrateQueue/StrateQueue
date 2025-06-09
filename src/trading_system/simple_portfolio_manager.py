"""
Simple Portfolio Manager for Multi-Strategy Trading

This module handles:
1. Capital allocation tracking per strategy
2. Symbol ownership registry (one symbol per strategy)
3. Order validation against capital limits and conflicts
4. Simple buy/sell permission checking
5. Trade tracking updates
"""

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class StrategyAllocation:
    """Strategy capital allocation configuration"""
    strategy_id: str
    allocation_percentage: float
    total_allocated: float = 0.0
    total_spent: float = 0.0
    
    @property
    def available_capital(self) -> float:
        """Calculate available capital for this strategy"""
        return self.total_allocated - self.total_spent

class SimplePortfolioManager:
    """
    Simple portfolio manager for multi-strategy trading.
    
    Handles capital allocation, symbol ownership, and conflict prevention
    with minimal complexity.
    """
    
    def __init__(self, strategy_allocations: Dict[str, float]):
        """
        Initialize portfolio manager with strategy allocations
        
        Args:
            strategy_allocations: Dict mapping strategy_id to allocation percentage
                                 Example: {"sma": 0.4, "momentum": 0.35, "random": 0.25}
        """
        self.strategy_allocations = {}
        for strategy_id, percentage in strategy_allocations.items():
            self.strategy_allocations[strategy_id] = StrategyAllocation(
                strategy_id=strategy_id,
                allocation_percentage=percentage
            )
        
        # Symbol ownership registry - one symbol per strategy
        self.symbol_owners: Dict[str, str] = {}
        
        # Track total account value for capital calculations
        self.total_account_value: float = 0.0
        
        logger.info(f"Initialized portfolio manager with {len(strategy_allocations)} strategies")
        for strategy_id, alloc in self.strategy_allocations.items():
            logger.info(f"  • {strategy_id}: {alloc.allocation_percentage:.1%} allocation")
    
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
            logger.debug(f"Strategy {strategy_id}: ${alloc.total_allocated:,.2f} allocated "
                        f"(${alloc.available_capital:,.2f} available)")
    
    def can_buy(self, strategy_id: str, symbol: str, amount: float) -> Tuple[bool, str]:
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
        
        # Check symbol ownership conflicts
        if symbol in self.symbol_owners:
            current_owner = self.symbol_owners[symbol]
            if current_owner != strategy_id:
                return False, f"Symbol {symbol} already owned by strategy {current_owner}"
        
        # Check capital availability
        strategy_alloc = self.strategy_allocations[strategy_id]
        if amount > strategy_alloc.available_capital:
            return False, (f"Insufficient capital for {strategy_id}: "
                          f"${amount:,.2f} requested, ${strategy_alloc.available_capital:,.2f} available")
        
        return True, "OK"
    
    def can_sell(self, strategy_id: str, symbol: str) -> Tuple[bool, str]:
        """
        Check if a strategy can sell a symbol
        
        Args:
            strategy_id: Strategy requesting the sell
            symbol: Symbol to sell
            
        Returns:
            Tuple of (can_sell: bool, reason: str)
        """
        # Check if strategy exists
        if strategy_id not in self.strategy_allocations:
            return False, f"Unknown strategy: {strategy_id}"
        
        # Check symbol ownership
        if symbol not in self.symbol_owners:
            return False, f"No position found for symbol {symbol}"
        
        current_owner = self.symbol_owners[symbol]
        if current_owner != strategy_id:
            return False, f"Symbol {symbol} owned by {current_owner}, not {strategy_id}"
        
        return True, "OK"
    
    def record_buy(self, strategy_id: str, symbol: str, amount: float):
        """
        Record a successful buy transaction
        
        Args:
            strategy_id: Strategy that executed the buy
            symbol: Symbol that was bought
            amount: Dollar amount spent
        """
        if strategy_id not in self.strategy_allocations:
            logger.error(f"Cannot record buy for unknown strategy: {strategy_id}")
            return
        
        # Update capital tracking
        self.strategy_allocations[strategy_id].total_spent += amount
        
        # Update symbol ownership
        self.symbol_owners[symbol] = strategy_id
        
        logger.info(f"Recorded buy: {strategy_id} bought {symbol} for ${amount:,.2f}")
        logger.debug(f"Strategy {strategy_id} capital: "
                    f"${self.strategy_allocations[strategy_id].available_capital:,.2f} remaining")
    
    def record_sell(self, strategy_id: str, symbol: str, amount: float):
        """
        Record a successful sell transaction
        
        Args:
            strategy_id: Strategy that executed the sell
            symbol: Symbol that was sold
            amount: Dollar amount received
        """
        if strategy_id not in self.strategy_allocations:
            logger.error(f"Cannot record sell for unknown strategy: {strategy_id}")
            return
        
        # Update capital tracking (add back proceeds)
        self.strategy_allocations[strategy_id].total_spent -= amount
        
        # Remove symbol ownership
        if symbol in self.symbol_owners:
            del self.symbol_owners[symbol]
        
        logger.info(f"Recorded sell: {strategy_id} sold {symbol} for ${amount:,.2f}")
        logger.debug(f"Strategy {strategy_id} capital: "
                    f"${self.strategy_allocations[strategy_id].available_capital:,.2f} available")
    
    def get_strategy_status(self, strategy_id: str) -> Dict:
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
        owned_symbols = [symbol for symbol, owner in self.symbol_owners.items() 
                        if owner == strategy_id]
        
        return {
            'strategy_id': strategy_id,
            'allocation_percentage': alloc.allocation_percentage,
            'total_allocated': alloc.total_allocated,
            'total_spent': alloc.total_spent,
            'available_capital': alloc.available_capital,
            'owned_symbols': owned_symbols,
            'position_count': len(owned_symbols)
        }
    
    def get_all_status(self) -> Dict:
        """
        Get status for all strategies
        
        Returns:
            Dictionary with overall portfolio status
        """
        strategy_status = {}
        for strategy_id in self.strategy_allocations.keys():
            strategy_status[strategy_id] = self.get_strategy_status(strategy_id)
        
        return {
            'total_account_value': self.total_account_value,
            'total_symbols_owned': len(self.symbol_owners),
            'symbol_owners': self.symbol_owners.copy(),
            'strategies': strategy_status
        }
    
    def validate_allocations(self) -> bool:
        """
        Validate that strategy allocations are reasonable
        
        Returns:
            True if allocations are valid, False otherwise
        """
        total_allocation = sum(alloc.allocation_percentage 
                             for alloc in self.strategy_allocations.values())
        
        # Check individual allocations
        for strategy_id, alloc in self.strategy_allocations.items():
            if alloc.allocation_percentage < 0 or alloc.allocation_percentage > 1:
                logger.error(f"Strategy {strategy_id} allocation {alloc.allocation_percentage:.2%} "
                           f"must be between 0% and 100%")
                return False
        
        # Check total doesn't exceed 100%
        if total_allocation > 1.01:  # Allow small floating point errors
            logger.error(f"Total strategy allocations ({total_allocation:.2%}) exceed 100%")
            return False
        
        # Warn if significantly under-allocated (but allow it)
        if total_allocation < 0.5:
            logger.warning(f"Total strategy allocations ({total_allocation:.2%}) are quite low. "
                         f"{(1.0 - total_allocation):.2%} of capital will remain in cash.")
        elif total_allocation < 1.0:
            logger.info(f"Total strategy allocations: {total_allocation:.2%}. "
                       f"{(1.0 - total_allocation):.2%} of capital will remain in cash.")
        
        return True 