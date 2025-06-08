"""
Position Manager for IBKR

Handles position information retrieval and management.
"""

import logging
from typing import Any, Dict, List, Optional

try:
    from ib_insync import IB
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False
    
    class IB:
        pass

from ...broker_base import Position

logger = logging.getLogger(__name__)


class PositionManager:
    """
    Manages position information for IBKR broker.
    
    Handles retrieval and management of current positions,
    including real-time P&L calculations.
    """
    
    def __init__(self, ib_client: IB):
        """
        Initialize the position manager
        
        Args:
            ib_client: Connected ib_insync IB client
        """
        if not IB_INSYNC_AVAILABLE:
            raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
        
        self.ib = ib_client
        self.logger = logging.getLogger(f"{__name__}.PositionManager")
        
        # Cache for position data
        self._position_cache: Dict[str, Position] = {}
        self._cache_valid = False
    
    def get_positions(self, force_refresh: bool = False) -> Dict[str, Position]:
        """
        Get all current positions
        
        Args:
            force_refresh: Force refresh of cached data
            
        Returns:
            Dictionary mapping symbol to Position object
        """
        try:
            # Refresh cache if needed
            if force_refresh or not self._cache_valid:
                self._refresh_position_cache()
            
            return self._position_cache.copy()
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return {}
    
    def get_position(self, symbol: str, force_refresh: bool = False) -> Optional[Position]:
        """
        Get position for a specific symbol
        
        Args:
            symbol: Symbol to get position for
            force_refresh: Force refresh of cached data
            
        Returns:
            Position object or None if no position
        """
        positions = self.get_positions(force_refresh)
        return positions.get(symbol)
    
    def _refresh_position_cache(self) -> None:
        """Refresh the position data cache"""
        try:
            positions = {}
            
            # Get positions from IB
            ib_positions = self.ib.positions()
            
            for ib_pos in ib_positions:
                if ib_pos.position == 0:
                    continue  # Skip zero positions
                
                symbol = ib_pos.contract.symbol
                
                # Calculate market value and P&L
                market_value = 0.0
                unrealized_pnl = 0.0
                unrealized_pnl_percent = 0.0
                
                if ib_pos.marketPrice and ib_pos.marketPrice > 0:
                    market_value = ib_pos.position * ib_pos.marketPrice
                    
                    if ib_pos.unrealizedPNL:
                        unrealized_pnl = ib_pos.unrealizedPNL
                        
                        # Calculate percentage P&L
                        if ib_pos.avgCost and ib_pos.avgCost > 0:
                            cost_basis = abs(ib_pos.position) * ib_pos.avgCost
                            if cost_basis > 0:
                                unrealized_pnl_percent = (unrealized_pnl / cost_basis) * 100
                
                # Determine position side
                side = "long" if ib_pos.position > 0 else "short"
                
                position = Position(
                    symbol=symbol,
                    quantity=ib_pos.position,
                    market_value=market_value,
                    average_cost=ib_pos.avgCost or 0.0,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_percent=unrealized_pnl_percent,
                    side=side,
                    additional_fields=self._extract_additional_fields(ib_pos)
                )
                
                positions[symbol] = position
            
            self._position_cache = positions
            self._cache_valid = True
            
            self.logger.debug(f"Refreshed position cache with {len(positions)} positions")
            
        except Exception as e:
            self.logger.error(f"Error refreshing position cache: {e}")
            self._cache_valid = False
    
    def _extract_additional_fields(self, ib_position) -> Dict[str, Any]:
        """
        Extract additional fields from IB position
        
        Args:
            ib_position: IB position object
            
        Returns:
            Dictionary with additional fields
        """
        additional = {}
        
        try:
            # Contract information
            if ib_position.contract:
                additional.update({
                    'contract_id': getattr(ib_position.contract, 'conId', None),
                    'exchange': getattr(ib_position.contract, 'exchange', None),
                    'currency': getattr(ib_position.contract, 'currency', None),
                    'security_type': getattr(ib_position.contract, 'secType', None),
                })
            
            # Market data
            additional.update({
                'market_price': getattr(ib_position, 'marketPrice', None),
                'market_value': getattr(ib_position, 'marketValue', None),
            })
            
            # Account information
            additional.update({
                'account': getattr(ib_position, 'account', None),
            })
            
        except Exception as e:
            self.logger.warning(f"Error extracting additional fields: {e}")
        
        return additional
    
    def get_total_portfolio_value(self) -> float:
        """
        Get total portfolio market value
        
        Returns:
            Total market value of all positions
        """
        try:
            positions = self.get_positions()
            return sum(pos.market_value for pos in positions.values())
            
        except Exception as e:
            self.logger.error(f"Error calculating total portfolio value: {e}")
            return 0.0
    
    def get_total_unrealized_pnl(self) -> float:
        """
        Get total unrealized P&L across all positions
        
        Returns:
            Total unrealized P&L
        """
        try:
            positions = self.get_positions()
            return sum(pos.unrealized_pnl for pos in positions.values())
            
        except Exception as e:
            self.logger.error(f"Error calculating total unrealized P&L: {e}")
            return 0.0
    
    def get_positions_by_side(self, side: str) -> Dict[str, Position]:
        """
        Get positions filtered by side (long/short)
        
        Args:
            side: Position side ("long" or "short")
            
        Returns:
            Dictionary of positions for the specified side
        """
        try:
            positions = self.get_positions()
            return {symbol: pos for symbol, pos in positions.items() 
                   if pos.side == side}
            
        except Exception as e:
            self.logger.error(f"Error getting positions by side {side}: {e}")
            return {}
    
    def get_long_positions(self) -> Dict[str, Position]:
        """Get all long positions"""
        return self.get_positions_by_side("long")
    
    def get_short_positions(self) -> Dict[str, Position]:
        """Get all short positions"""
        return self.get_positions_by_side("short")
    
    def has_position(self, symbol: str) -> bool:
        """
        Check if there's a position in the specified symbol
        
        Args:
            symbol: Symbol to check
            
        Returns:
            True if position exists
        """
        position = self.get_position(symbol)
        return position is not None and position.quantity != 0
    
    def get_position_quantity(self, symbol: str) -> float:
        """
        Get position quantity for a symbol
        
        Args:
            symbol: Symbol to check
            
        Returns:
            Position quantity (0 if no position)
        """
        position = self.get_position(symbol)
        return position.quantity if position else 0.0
    
    def close_position(self, symbol: str) -> bool:
        """
        Close a position by placing a market order
        
        Args:
            symbol: Symbol to close position for
            
        Returns:
            True if close order was placed successfully
        """
        try:
            position = self.get_position(symbol)
            if not position or position.quantity == 0:
                self.logger.warning(f"No position to close for {symbol}")
                return False
            
            # Import here to avoid circular dependency
            from ..contracts import create_contract
            from ...broker_base import OrderSide, OrderType
            
            # Create contract
            contract = create_contract(symbol)
            
            # Determine order side (opposite of position)
            side = OrderSide.SELL if position.quantity > 0 else OrderSide.BUY
            quantity = abs(position.quantity)
            
            # Place market order to close
            from ib_insync import Order
            close_order = Order(
                action=side.value,
                totalQuantity=quantity,
                orderType='MKT'
            )
            
            trade = self.ib.placeOrder(contract, close_order)
            
            # Wait for order to be submitted
            self.ib.waitOnUpdate()
            
            success = trade.orderStatus.status in ['Submitted', 'PreSubmitted', 'Filled']
            
            if success:
                self.logger.info(f"Close order placed for {symbol}: {side.value} {quantity}")
                # Invalidate cache since position will change
                self.invalidate_cache()
            else:
                self.logger.error(f"Failed to place close order for {symbol}: {trade.orderStatus.status}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error closing position for {symbol}: {e}")
            return False
    
    def close_all_positions(self) -> bool:
        """
        Close all open positions
        
        Returns:
            True if all close orders were placed successfully
        """
        try:
            positions = self.get_positions()
            
            if not positions:
                self.logger.info("No positions to close")
                return True
            
            success_count = 0
            for symbol in positions.keys():
                if self.close_position(symbol):
                    success_count += 1
            
            self.logger.info(f"Requested close for {success_count}/{len(positions)} positions")
            return success_count == len(positions)
            
        except Exception as e:
            self.logger.error(f"Error closing all positions: {e}")
            return False
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get portfolio summary statistics
        
        Returns:
            Dictionary with portfolio summary
        """
        try:
            positions = self.get_positions()
            
            summary = {
                'total_positions': len(positions),
                'long_positions': len(self.get_long_positions()),
                'short_positions': len(self.get_short_positions()),
                'total_market_value': self.get_total_portfolio_value(),
                'total_unrealized_pnl': self.get_total_unrealized_pnl(),
                'symbols': list(positions.keys())
            }
            
            # Calculate average P&L percentage
            if positions:
                pnl_percentages = [pos.unrealized_pnl_percent for pos in positions.values() 
                                 if pos.unrealized_pnl_percent != 0]
                if pnl_percentages:
                    summary['avg_unrealized_pnl_percent'] = sum(pnl_percentages) / len(pnl_percentages)
                else:
                    summary['avg_unrealized_pnl_percent'] = 0.0
            else:
                summary['avg_unrealized_pnl_percent'] = 0.0
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting portfolio summary: {e}")
            return {}
    
    def invalidate_cache(self) -> None:
        """Invalidate the position cache to force refresh on next access"""
        self._cache_valid = False
        self.logger.debug("Position cache invalidated") 