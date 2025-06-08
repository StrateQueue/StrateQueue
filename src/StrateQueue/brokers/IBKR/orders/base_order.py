"""
Base Order Handler for IBKR

Provides common functionality for all order types.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict

try:
    from ib_insync import IB, Order, Trade
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False
    
    class IB:
        pass
    class Order:
        pass
    class Trade:
        pass

from ...broker_base import OrderResult, OrderSide, OrderType

logger = logging.getLogger(__name__)


class BaseOrderHandler(ABC):
    """
    Abstract base class for order handlers.
    
    Each order type (market, limit, stop, etc.) should inherit from this class
    and implement the specific order creation and management logic.
    """
    
    def __init__(self, ib_client: IB):
        """
        Initialize the order handler
        
        Args:
            ib_client: Connected ib_insync IB client
        """
        if not IB_INSYNC_AVAILABLE:
            raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
            
        self.ib = ib_client
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def create_order(
        self, 
        side: OrderSide, 
        quantity: float, 
        price: float = None,
        security_type: str = "STK",
        **kwargs
    ) -> Order:
        """
        Create an IB order object for this order type
        
        Args:
            side: Order side (BUY/SELL)
            quantity: Order quantity
            price: Order price (if applicable)
            **kwargs: Additional order parameters
            
        Returns:
            IB Order object
        """
        pass
    
    @abstractmethod
    def get_order_type(self) -> OrderType:
        """
        Get the StrateQueue OrderType this handler supports
        
        Returns:
            OrderType enum value
        """
        pass
    
    def place_order(
        self, 
        contract, 
        side: OrderSide, 
        quantity: float, 
        price: float = None,
        metadata: Dict[str, Any] = None,
        security_type: str = "STK",
        **kwargs
    ) -> OrderResult:
        """
        Place an order using this handler
        
        Args:
            contract: IB contract object
            side: Order side (BUY/SELL)
            quantity: Order quantity
            price: Order price (if applicable)
            metadata: Additional metadata
            **kwargs: Additional order parameters
            
        Returns:
            OrderResult with execution status
        """
        try:
            # Create the order with security type context
            ib_order = self.create_order(side, quantity, price, security_type=security_type, **kwargs)
            
            # Add metadata as order reference if provided
            if metadata:
                # Convert metadata to string for IB order reference
                ref_parts = []
                for key, value in metadata.items():
                    ref_parts.append(f"{key}:{value}")
                if ref_parts:
                    ib_order.orderRef = ";".join(ref_parts)[:50]  # IB has length limits
            
            # Place the order
            trade = self.ib.placeOrder(contract, ib_order)
            
            # Check order status (order status is immediately available after placeOrder)
            success = self._is_order_accepted(trade)
            
            result = OrderResult(
                success=success,
                order_id=str(trade.order.orderId) if trade.order.orderId else None,
                client_order_id=trade.order.orderRef if hasattr(trade.order, 'orderRef') else None,
                message=trade.orderStatus.status if trade.orderStatus else "Unknown",
                timestamp=datetime.utcnow(),
                broker_response=self._extract_broker_response(trade)
            )
            
            self.logger.info(
                f"Order placed: {self.get_order_type().value} {side.value} "
                f"{quantity} {contract.symbol} - Status: {result.message}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error placing {self.get_order_type().value} order: {e}")
            return OrderResult(
                success=False,
                message=str(e),
                timestamp=datetime.utcnow()
            )
    
    def _is_order_accepted(self, trade: Trade) -> bool:
        """
        Check if an order was accepted by the broker
        
        Args:
            trade: IB Trade object
            
        Returns:
            True if order was accepted
        """
        if not trade.orderStatus:
            return False
            
        accepted_statuses = {
            'PendingSubmit', 'Submitted', 'PreSubmitted', 'Filled', 'PartiallyFilled'
        }
        
        return trade.orderStatus.status in accepted_statuses
    
    def _extract_broker_response(self, trade: Trade) -> Dict[str, Any]:
        """
        Extract relevant information from IB trade object
        
        Args:
            trade: IB Trade object
            
        Returns:
            Dictionary with broker response data
        """
        response = {}
        
        if trade.orderStatus:
            response.update({
                'status': trade.orderStatus.status,
                'filled': trade.orderStatus.filled,
                'remaining': trade.orderStatus.remaining,
                'avg_fill_price': trade.orderStatus.avgFillPrice,
                'last_fill_price': trade.orderStatus.lastFillPrice,
            })
        
        if trade.order:
            response.update({
                'order_id': trade.order.orderId,
                'order_type': trade.order.orderType,
                'total_quantity': trade.order.totalQuantity,
                'order_ref': getattr(trade.order, 'orderRef', None),
            })
        
        return response
    
    def supports_order_type(self, order_type: OrderType) -> bool:
        """
        Check if this handler supports a specific order type
        
        Args:
            order_type: OrderType to check
            
        Returns:
            True if supported
        """
        return order_type == self.get_order_type()
    
    def validate_order_params(
        self, 
        side: OrderSide, 
        quantity: float, 
        price: float = None,
        **kwargs
    ) -> tuple[bool, str]:
        """
        Validate order parameters before placing order
        
        Args:
            side: Order side
            quantity: Order quantity
            price: Order price
            **kwargs: Additional parameters
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Basic validation
        if quantity <= 0:
            return False, "Quantity must be positive"
        
        if side not in [OrderSide.BUY, OrderSide.SELL]:
            return False, f"Invalid order side: {side}"
        
        return True, "" 