"""
IBKR Order Management Package

This package contains modular order management components for Interactive Brokers.
Each order type has its own implementation for better maintainability.
"""

from .order_manager import OrderManager
from .market_order import MarketOrderHandler
from .limit_order import LimitOrderHandler

try:
    from .stop_order import StopOrderHandler
    STOP_ORDERS_AVAILABLE = True
except ImportError:
    STOP_ORDERS_AVAILABLE = False
    class StopOrderHandler:
        def __init__(self, *args, **kwargs):
            raise NotImplementedError("Stop orders not yet implemented")

__all__ = [
    "OrderManager",
    "MarketOrderHandler", 
    "LimitOrderHandler",
    "StopOrderHandler",
    "STOP_ORDERS_AVAILABLE"
] 