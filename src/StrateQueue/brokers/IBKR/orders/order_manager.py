"""
Order Manager for IBKR

Coordinates all order types and provides a unified interface for order management.
"""

import logging
from typing import Any, Dict, List, Optional

try:
    from ib_insync import IB, Trade
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False
    
    class IB:
        pass
    class Trade:
        pass

from .base_order import BaseOrderHandler
from .market_order import MarketOrderHandler
from .limit_order import LimitOrderHandler
from ...broker_base import OrderResult, OrderSide, OrderType

logger = logging.getLogger(__name__)


class OrderManager:
    """
    Manages all order types for IBKR broker.
    
    Provides a unified interface for creating and managing orders,
    delegating to specific order handlers based on order type.
    """
    
    def __init__(self, ib_client: IB):
        """
        Initialize the order manager
        
        Args:
            ib_client: Connected ib_insync IB client
        """
        if not IB_INSYNC_AVAILABLE:
            raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
        
        self.ib = ib_client
        self.logger = logging.getLogger(f"{__name__}.OrderManager")
        
        # Initialize order handlers
        self._handlers: Dict[OrderType, BaseOrderHandler] = {}
        self._initialize_handlers()
        
        # Track active orders
        self._active_orders: Dict[str, Trade] = {}
    
    def _initialize_handlers(self) -> None:
        """Initialize all available order handlers"""
        try:
            # Market orders
            self._handlers[OrderType.MARKET] = MarketOrderHandler(self.ib)
            self.logger.debug("Initialized market order handler")
            
            # Limit orders
            self._handlers[OrderType.LIMIT] = LimitOrderHandler(self.ib)
            self.logger.debug("Initialized limit order handler")
            
            # TODO: Add more order types as they're implemented
            # self._handlers[OrderType.STOP] = StopOrderHandler(self.ib)
            # self._handlers[OrderType.STOP_LIMIT] = StopLimitOrderHandler(self.ib)
            # self._handlers[OrderType.TRAILING_STOP] = TrailingStopOrderHandler(self.ib)
            
        except Exception as e:
            self.logger.error(f"Error initializing order handlers: {e}")
            raise
    
    def get_supported_order_types(self) -> List[OrderType]:
        """
        Get list of supported order types
        
        Returns:
            List of supported OrderType enums
        """
        return list(self._handlers.keys())
    
    def supports_order_type(self, order_type: OrderType) -> bool:
        """
        Check if an order type is supported
        
        Args:
            order_type: OrderType to check
            
        Returns:
            True if supported
        """
        return order_type in self._handlers
    
    def place_order(
        self,
        contract,
        order_type: OrderType,
        side: OrderSide,
        quantity: float,
        price: float = None,
        metadata: Dict[str, Any] = None,
        security_type: str = "STK",
        **kwargs
    ) -> OrderResult:
        """
        Place an order using the appropriate handler
        
        Args:
            contract: IB contract object
            order_type: Type of order to place
            side: Order side (BUY/SELL)
            quantity: Order quantity
            price: Order price (if applicable)
            metadata: Additional metadata
            **kwargs: Additional order parameters
            
        Returns:
            OrderResult with execution status
        """
        # Check if order type is supported
        if not self.supports_order_type(order_type):
            return OrderResult(
                success=False,
                message=f"Unsupported order type: {order_type}",
                timestamp=None
            )
        
        # Get the appropriate handler
        handler = self._handlers[order_type]
        
        try:
            # Place the order using the handler
            result = handler.place_order(
                contract=contract,
                side=side,
                quantity=quantity,
                price=price,
                metadata=metadata,
                security_type=security_type,
                **kwargs
            )
            
            # Track the order if successful
            if result.success and result.order_id:
                self._track_order(result.order_id)
            
            self.logger.info(
                f"Order placement result: {order_type.value} {side.value} "
                f"{quantity} {contract.symbol} - Success: {result.success}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error placing {order_type.value} order: {e}")
            return OrderResult(
                success=False,
                message=str(e),
                timestamp=None
            )
    
    def _track_order(self, order_id: str) -> None:
        """
        Track an active order
        
        Args:
            order_id: Order ID to track
        """
        try:
            # Find the trade object for this order
            for trade in self.ib.trades():
                if str(trade.order.orderId) == order_id:
                    self._active_orders[order_id] = trade
                    break
        except Exception as e:
            self.logger.warning(f"Could not track order {order_id}: {e}")
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific order
        
        Args:
            order_id: Order ID to check
            
        Returns:
            Order status dictionary or None if not found
        """
        try:
            # Check if we're tracking this order
            if order_id in self._active_orders:
                trade = self._active_orders[order_id]
                return self._extract_order_status(trade)
            
            # Search through all trades
            for trade in self.ib.trades():
                if str(trade.order.orderId) == order_id:
                    return self._extract_order_status(trade)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting order status for {order_id}: {e}")
            return None
    
    def _extract_order_status(self, trade: Trade) -> Dict[str, Any]:
        """
        Extract order status from trade object
        
        Args:
            trade: IB Trade object
            
        Returns:
            Order status dictionary
        """
        status = {}
        
        if trade.order:
            status.update({
                'order_id': str(trade.order.orderId),
                'order_type': trade.order.orderType,
                'action': trade.order.action,
                'total_quantity': trade.order.totalQuantity,
                'order_ref': getattr(trade.order, 'orderRef', None),
            })
        
        if trade.orderStatus:
            status.update({
                'status': trade.orderStatus.status,
                'filled': trade.orderStatus.filled,
                'remaining': trade.orderStatus.remaining,
                'avg_fill_price': trade.orderStatus.avgFillPrice,
                'last_fill_price': trade.orderStatus.lastFillPrice,
                'why_held': trade.orderStatus.whyHeld,
            })
        
        if trade.contract:
            status.update({
                'symbol': trade.contract.symbol,
                'exchange': trade.contract.exchange,
                'currency': trade.contract.currency,
            })
        
        return status
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a specific order
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancellation was initiated successfully
        """
        try:
            # Find the trade to cancel
            trade_to_cancel = None
            
            if order_id in self._active_orders:
                trade_to_cancel = self._active_orders[order_id]
            else:
                # Search through all trades
                for trade in self.ib.trades():
                    if str(trade.order.orderId) == order_id:
                        trade_to_cancel = trade
                        break
            
            if trade_to_cancel:
                self.ib.cancelOrder(trade_to_cancel.order)
                self.logger.info(f"Cancellation requested for order {order_id}")
                return True
            else:
                self.logger.warning(f"Order {order_id} not found for cancellation")
                return False
                
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    def cancel_all_orders(self) -> bool:
        """
        Cancel all open orders
        
        Returns:
            True if all cancellations were initiated successfully
        """
        try:
            open_trades = [trade for trade in self.ib.trades() 
                          if trade.orderStatus.status in ['Submitted', 'PreSubmitted']]
            
            if not open_trades:
                self.logger.info("No open orders to cancel")
                return True
            
            success_count = 0
            for trade in open_trades:
                try:
                    self.ib.cancelOrder(trade.order)
                    success_count += 1
                except Exception as e:
                    self.logger.error(f"Error cancelling order {trade.order.orderId}: {e}")
            
            self.logger.info(f"Requested cancellation for {success_count}/{len(open_trades)} orders")
            return success_count == len(open_trades)
            
        except Exception as e:
            self.logger.error(f"Error cancelling all orders: {e}")
            return False
    
    def get_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """
        Get all open orders
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of order status dictionaries
        """
        try:
            orders = []
            
            for trade in self.ib.openTrades():
                # Filter by symbol if specified
                if symbol and trade.contract.symbol != symbol:
                    continue
                
                orders.append(self._extract_order_status(trade))
            
            return orders
            
        except Exception as e:
            self.logger.error(f"Error getting open orders: {e}")
            return []
    
    def get_order_handler(self, order_type: OrderType) -> Optional[BaseOrderHandler]:
        """
        Get the handler for a specific order type
        
        Args:
            order_type: OrderType to get handler for
            
        Returns:
            Order handler or None if not supported
        """
        return self._handlers.get(order_type)
    
    def cleanup_completed_orders(self) -> None:
        """
        Clean up tracking for completed orders
        """
        try:
            completed_orders = []
            
            for order_id, trade in self._active_orders.items():
                if trade.orderStatus and trade.orderStatus.status in ['Filled', 'Cancelled']:
                    completed_orders.append(order_id)
            
            for order_id in completed_orders:
                del self._active_orders[order_id]
            
            if completed_orders:
                self.logger.debug(f"Cleaned up {len(completed_orders)} completed orders")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up completed orders: {e}")
    
    def get_handler_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all available handlers
        
        Returns:
            Dictionary with handler information
        """
        info = {}
        
        for order_type, handler in self._handlers.items():
            info[order_type.value] = {
                'order_type': order_type.value,
                'handler_class': handler.__class__.__name__,
                'supported': True,
            }
        
        return info 