"""
Broker Abstraction Layer

This package provides a unified interface for different trading brokers (Alpaca, Interactive Brokers, etc.)
allowing different brokers to be used with the same live trading infrastructure.

Main Components:
- BaseBroker: Abstract base class for trading brokers
- BrokerConfig: Base configuration class for broker settings
- BrokerFactory: Factory for creating brokers and detecting broker types
"""

from .broker_base import AccountInfo, BaseBroker, BrokerConfig, BrokerInfo, OrderResult, Position
from .broker_factory import (
    BrokerFactory,
    auto_create_broker,
    detect_broker_type,
    list_broker_features,
    validate_broker_credentials,
)

# Try importing Alpaca broker - if alpaca isn't installed, it won't be available
try:
    from .Alpaca.alpaca_broker import AlpacaBroker

    _ALPACA_AVAILABLE = True
except ImportError:
    _ALPACA_AVAILABLE = False

# Try importing IBKR broker - if ib_insync isn't installed, it won't be available
try:
    from .IBKR.ibkr_broker import IBKRBroker

    _IBKR_AVAILABLE = True
except ImportError:
    _IBKR_AVAILABLE = False


def get_supported_brokers():
    """
    Get list of supported broker types

    Returns:
        List of broker type names
    """
    return BrokerFactory.get_supported_brokers()


__all__ = [
    "BaseBroker",
    "BrokerConfig",
    "BrokerInfo",
    "AccountInfo",
    "Position",
    "OrderResult",
    "BrokerFactory",
    "detect_broker_type",
    "get_supported_brokers",
    "auto_create_broker",
    "validate_broker_credentials",
    "list_broker_features",
]

# Only add AlpacaBroker to __all__ if it's available
if _ALPACA_AVAILABLE:
    __all__.append("AlpacaBroker")

# Only add IBKRBroker to __all__ if it's available
if _IBKR_AVAILABLE:
    __all__.append("IBKRBroker")
