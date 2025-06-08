"""
Market Order Handler for IBKR

Handles market order creation and execution.
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


class MarketOrderHandler(BaseOrderHandler):
    """
    Handler for market orders.
    
    Market orders execute immediately at the current market price.
    """
    
    def get_order_type(self) -> OrderType:
        """Get the order type this handler supports"""
        return OrderType.MARKET
    
    def create_order(
        self, 
        side: OrderSide, 
        quantity: float, 
        price: float = None,  # Ignored for market orders
        security_type: str = "STK",
        **kwargs
    ) -> Order:
        """
        Create a market order
        
        Args:
            side: Order side (BUY/SELL)
            quantity: Order quantity
            price: Ignored for market orders
            **kwargs: Additional order parameters
            
        Returns:
            IB Order object configured for market execution
        """
        if not IB_INSYNC_AVAILABLE:
            raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
        
        # Validate parameters
        is_valid, error_msg = self.validate_order_params(side, quantity, price, **kwargs)
        if not is_valid:
            raise ValueError(f"Invalid market order parameters: {error_msg}")
        
        # Create market order - handle crypto vs stock differently
        if security_type == "CRYPTO":
            # For crypto: BUY uses cashQty (USD), SELL uses totalQuantity (coins)
            if side.value == "BUY":
                # BUY: Use cashQty (USD amount)
                order = Order(
                    action=side.value,
                    cashQty=quantity,   # USD amount for crypto buys
                    totalQuantity=0,    # Must be 0 for crypto cash orders
                    orderType='MKT',
                    tif='IOC'          # Immediate or Cancel for crypto
                )
                self.logger.debug(f"Created crypto BUY market order: ${quantity} USD")
            else:  # SELL
                # SELL: Use totalQuantity (number of coins) - quantity is USD, need to convert
                # For now, use a small default quantity until we implement position tracking
                coin_quantity = 1.0  # TODO: Calculate from current position
                order = Order(
                    action=side.value,
                    totalQuantity=coin_quantity,  # Number of coins to sell
                    orderType='MKT',
                    tif='IOC'          # Immediate or Cancel for crypto
                )
                self.logger.debug(f"Created crypto SELL market order: {coin_quantity} coins")
        else:
            # For stocks, use totalQuantity (number of shares)
            order = Order(
                action=side.value,  # "BUY" or "SELL"
                totalQuantity=int(round(quantity)),  # Ensure whole shares
                orderType='MKT',    # Market order type in IB
                outsideRth=True     # Allow orders outside regular trading hours
            )
            self.logger.debug(f"Created stock market order: {side.value} {int(round(quantity))} shares (outside RTH allowed)")
        
        # Add any additional parameters
        self._apply_additional_params(order, **kwargs)
        
        self.logger.debug(f"Created market order: {side.value} {quantity} shares")
        
        return order
    
    def _apply_additional_params(self, order: Order, **kwargs) -> None:
        """
        Apply additional parameters to the market order
        
        Args:
            order: IB Order object to modify
            **kwargs: Additional parameters
        """
        # Time in force (default is DAY for market orders)
        if 'time_in_force' in kwargs:
            tif = kwargs['time_in_force'].upper()
            if tif in ['DAY', 'GTC', 'IOC', 'FOK']:
                order.tif = tif
            else:
                self.logger.warning(f"Invalid time in force for market order: {tif}")
        
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
    
    def validate_order_params(
        self, 
        side: OrderSide, 
        quantity: float, 
        price: float = None,
        **kwargs
    ) -> tuple[bool, str]:
        """
        Validate market order parameters
        
        Args:
            side: Order side
            quantity: Order quantity
            price: Order price (ignored for market orders)
            **kwargs: Additional parameters
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Call base validation first
        is_valid, error_msg = super().validate_order_params(side, quantity, price, **kwargs)
        if not is_valid:
            return is_valid, error_msg
        
        # Market order specific validation
        
        # Check for fractional shares (some brokers don't support this)
        if quantity != int(quantity) and quantity < 1:
            # Allow fractional shares for small quantities
            pass
        
        # Validate time in force if provided
        if 'time_in_force' in kwargs:
            tif = kwargs['time_in_force'].upper()
            valid_tifs = ['DAY', 'GTC', 'IOC', 'FOK']
            if tif not in valid_tifs:
                return False, f"Invalid time in force: {tif}. Valid options: {valid_tifs}"
        
        # Market orders during extended hours need special handling
        if kwargs.get('outside_rth', False):
            self.logger.info("Market order will execute outside regular trading hours")
        
        return True, ""
    
    def get_order_description(self, side: OrderSide, quantity: float, **kwargs) -> str:
        """
        Get a human-readable description of the order
        
        Args:
            side: Order side
            quantity: Order quantity
            **kwargs: Additional parameters
            
        Returns:
            Order description string
        """
        desc = f"Market {side.value} {quantity} shares"
        
        if kwargs.get('outside_rth', False):
            desc += " (Extended Hours)"
        
        if 'time_in_force' in kwargs:
            desc += f" TIF:{kwargs['time_in_force']}"
        
        return desc 