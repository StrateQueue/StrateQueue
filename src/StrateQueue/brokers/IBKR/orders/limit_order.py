"""
Limit Order Handler for IBKR

Handles limit order creation and execution.
"""

import logging
from typing import Any

try:
    from ib_insync import Order
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False
    class Order:
        pass

from .base_order import BaseOrderHandler
from ...broker_base import OrderSide, OrderType

logger = logging.getLogger(__name__)


class LimitOrderHandler(BaseOrderHandler):
    """
    Handler for limit orders.
    
    Limit orders execute only at the specified price or better.
    """
    
    def get_order_type(self) -> OrderType:
        """Get the order type this handler supports"""
        return OrderType.LIMIT
    
    def create_order(
        self, 
        side: OrderSide, 
        quantity: float, 
        price: float,
        security_type: str = "STK",
        **kwargs
    ) -> Order:
        """
        Create a limit order
        
        Args:
            side: Order side (BUY/SELL)
            quantity: Order quantity
            price: Limit price
            **kwargs: Additional order parameters
            
        Returns:
            IB Order object configured for limit execution
        """
        if not IB_INSYNC_AVAILABLE:
            raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
        
        # Validate parameters
        is_valid, error_msg = self.validate_order_params(side, quantity, price, **kwargs)
        if not is_valid:
            raise ValueError(f"Invalid limit order parameters: {error_msg}")
        
        # Create limit order - handle crypto vs stock differently
        if security_type == "CRYPTO":
            # For crypto: BUY uses cashQty (USD), SELL uses totalQuantity (coins)
            if side.value == "BUY":
                # BUY: Use cashQty (USD amount)
                order = Order(
                    action=side.value,
                    cashQty=quantity,   # USD amount for crypto buys
                    totalQuantity=0,    # Must be 0 for crypto cash orders
                    orderType='LMT',
                    lmtPrice=price,
                    tif='IOC'          # Immediate or Cancel for crypto
                )
                self.logger.debug(f"Created crypto BUY limit order: ${quantity} USD @ ${price}")
            else:  # SELL
                # SELL: Use totalQuantity (number of coins) - quantity is USD, need to convert
                # For now, use a small default quantity until we implement position tracking
                coin_quantity = 1.0  # TODO: Calculate from current position
                order = Order(
                    action=side.value,
                    totalQuantity=coin_quantity,  # Number of coins to sell
                    orderType='LMT',
                    lmtPrice=price,
                    tif='IOC'          # Immediate or Cancel for crypto
                )
                self.logger.debug(f"Created crypto SELL limit order: {coin_quantity} coins @ ${price}")
        else:
            # For stocks, use totalQuantity (number of shares)
            order = Order(
                action=side.value,  # "BUY" or "SELL"
                totalQuantity=int(round(quantity)),  # Ensure whole shares
                orderType='LMT',    # Limit order type in IB
                lmtPrice=price,     # Limit price
                outsideRth=True     # Allow orders outside regular trading hours
            )
            self.logger.debug(f"Created stock limit order: {side.value} {int(round(quantity))} shares @ ${price} (outside RTH allowed)")
        
        # Add any additional parameters
        self._apply_additional_params(order, **kwargs)
        
        self.logger.debug(f"Created limit order: {side.value} {quantity} shares @ ${price}")
        
        return order
    
    def _apply_additional_params(self, order: Order, **kwargs) -> None:
        """
        Apply additional parameters to the limit order
        
        Args:
            order: IB Order object to modify
            **kwargs: Additional parameters
        """
        # Time in force (default is DAY for limit orders)
        if 'time_in_force' in kwargs:
            tif = kwargs['time_in_force'].upper()
            if tif in ['DAY', 'GTC', 'IOC', 'FOK']:
                order.tif = tif
            else:
                self.logger.warning(f"Invalid time in force for limit order: {tif}")
        
        # Outside regular trading hours
        if 'outside_rth' in kwargs:
            order.outsideRth = bool(kwargs['outside_rth'])
        
        # Good after time
        if 'good_after_time' in kwargs:
            order.goodAfterTime = kwargs['good_after_time']
        
        # Good till date
        if 'good_till_date' in kwargs:
            order.goodTillDate = kwargs['good_till_date']
        
        # Order reference
        if 'order_ref' in kwargs:
            order.orderRef = str(kwargs['order_ref'])[:50]  # IB has length limits
        
        # Client ID
        if 'client_id' in kwargs:
            order.clientId = int(kwargs['client_id'])
        
        # Hidden order (iceberg)
        if 'hidden' in kwargs and kwargs['hidden']:
            order.hidden = True
        
        # Display size for iceberg orders
        if 'display_size' in kwargs:
            order.displaySize = int(kwargs['display_size'])
        
        # Minimum quantity
        if 'min_qty' in kwargs:
            order.minQty = int(kwargs['min_qty'])
        
        # All or none
        if 'all_or_none' in kwargs:
            order.allOrNone = bool(kwargs['all_or_none'])
    
    def validate_order_params(
        self, 
        side: OrderSide, 
        quantity: float, 
        price: float = None,
        **kwargs
    ) -> tuple[bool, str]:
        """
        Validate limit order parameters
        
        Args:
            side: Order side
            quantity: Order quantity
            price: Limit price
            **kwargs: Additional parameters
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Call base validation first
        is_valid, error_msg = super().validate_order_params(side, quantity, price, **kwargs)
        if not is_valid:
            return is_valid, error_msg
        
        # Limit order specific validation
        
        # Price is required for limit orders
        if price is None or price <= 0:
            return False, "Limit price must be positive"
        
        # Validate time in force if provided
        if 'time_in_force' in kwargs:
            tif = kwargs['time_in_force'].upper()
            valid_tifs = ['DAY', 'GTC', 'IOC', 'FOK']
            if tif not in valid_tifs:
                return False, f"Invalid time in force: {tif}. Valid options: {valid_tifs}"
        
        # Validate display size for iceberg orders
        if 'display_size' in kwargs:
            display_size = kwargs['display_size']
            if display_size <= 0 or display_size > quantity:
                return False, f"Display size must be positive and <= total quantity"
        
        # Validate minimum quantity
        if 'min_qty' in kwargs:
            min_qty = kwargs['min_qty']
            if min_qty <= 0 or min_qty > quantity:
                return False, f"Minimum quantity must be positive and <= total quantity"
        
        # Check for reasonable price (basic sanity check)
        if price > 1000000:  # $1M per share seems unreasonable
            self.logger.warning(f"Very high limit price: ${price}")
        
        return True, ""
    
    def get_order_description(self, side: OrderSide, quantity: float, price: float = None, **kwargs) -> str:
        """
        Get a human-readable description of the order
        
        Args:
            side: Order side
            quantity: Order quantity
            price: Limit price
            **kwargs: Additional parameters
            
        Returns:
            Order description string
        """
        desc = f"Limit {side.value} {quantity} shares @ ${price:.2f}"
        
        if kwargs.get('outside_rth', False):
            desc += " (Extended Hours)"
        
        if 'time_in_force' in kwargs:
            desc += f" TIF:{kwargs['time_in_force']}"
        
        if kwargs.get('hidden', False):
            desc += " (Hidden)"
        
        if 'display_size' in kwargs:
            desc += f" Display:{kwargs['display_size']}"
        
        if kwargs.get('all_or_none', False):
            desc += " (AON)"
        
        return desc
    
    def calculate_estimated_cost(self, side: OrderSide, quantity: float, price: float) -> float:
        """
        Calculate estimated cost/proceeds for the limit order
        
        Args:
            side: Order side
            quantity: Order quantity
            price: Limit price
            
        Returns:
            Estimated cost (positive) or proceeds (negative)
        """
        base_amount = quantity * price
        
        if side == OrderSide.BUY:
            return base_amount  # Cost to buy
        else:
            return -base_amount  # Proceeds from selling (negative cost)
    
    def is_price_improvement(self, side: OrderSide, limit_price: float, market_price: float) -> bool:
        """
        Check if the limit price offers price improvement over market price
        
        Args:
            side: Order side
            limit_price: Proposed limit price
            market_price: Current market price
            
        Returns:
            True if limit price is better than market price
        """
        if side == OrderSide.BUY:
            # For buy orders, lower price is better
            return limit_price < market_price
        else:
            # For sell orders, higher price is better
            return limit_price > market_price 