"""
Mock objects for strategy compatibility

This module provides mock implementations of objects that strategies might reference
but aren't needed in our live trading environment.
"""

import logging

logger = logging.getLogger(__name__)

class Order:
    """Mock Order class to provide compatibility with strategy examples that use Order.Stop, etc."""
    
    class Stop:
        """Mock Stop order type"""
        __name__ = "Stop"
        
    class Limit:
        """Mock Limit order type"""
        __name__ = "Limit"
        
    class StopLimit:
        """Mock StopLimit order type"""
        __name__ = "StopLimit"
        
    class Market:
        """Mock Market order type"""
        __name__ = "Market" 