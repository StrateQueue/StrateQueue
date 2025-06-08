"""
Interactive Brokers (IBKR) Broker Implementation

This package provides Interactive Brokers TWS/IB Gateway integration for StrateQueue.
Requires ib_insync to be installed: pip install stratequeue[ibkr]
"""

try:
    from .ibkr_broker import IBKRBroker
    IBKR_AVAILABLE = True
except ImportError:
    IBKR_AVAILABLE = False
    
    class IBKRBroker:
        def __init__(self, *args, **kwargs):
            raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")

__all__ = ["IBKRBroker", "IBKR_AVAILABLE"] 