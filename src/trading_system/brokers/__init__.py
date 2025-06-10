"""
Broker Abstraction Layer

This package provides a unified interface for different trading brokers (Alpaca, Interactive Brokers, etc.)
allowing different brokers to be used with the same live trading infrastructure.

Main Components:
- BaseBroker: Abstract base class for trading brokers
- BrokerConfig: Base configuration class for broker settings
- BrokerFactory: Factory for creating brokers and detecting broker types
"""

from .base import BaseBroker, BrokerConfig, BrokerInfo
from .broker_factory import BrokerFactory, detect_broker_type, get_supported_brokers, auto_create_broker, validate_broker_credentials


def list_broker_features():
    """List features of all supported brokers"""
    return {
        'alpaca': BrokerInfo(
            name="Alpaca",
            version="2.0.0",
            description="Commission-free stock and crypto trading", 
            supported_markets=['stocks', 'crypto'],
            paper_trading=True,
            supported_features={
                'market_orders': True,
                'limit_orders': True, 
                'stop_orders': True,
                'crypto_trading': True,
                'multi_strategy': True,
                'portfolio_management': True
            }
        ),
        'interactive_brokers': BrokerInfo(
            name="Interactive Brokers",
            version="1.0.0",
            description="Professional trading platform with global market access",
            supported_markets=['stocks', 'options', 'futures', 'forex', 'bonds'],
            paper_trading=True,
            supported_features={
                'market_orders': True,
                'limit_orders': True,
                'stop_orders': True,
                'options_trading': True,
                'futures_trading': True,
                'forex_trading': True,
                'multi_strategy': True,
                'portfolio_management': True
            }
        ),
        'td_ameritrade': BrokerInfo(
            name="TD Ameritrade",
            version="1.0.0", 
            description="Full-service brokerage with comprehensive trading tools",
            supported_markets=['stocks', 'options', 'futures'],
            paper_trading=True,
            supported_features={
                'market_orders': True,
                'limit_orders': True,
                'stop_orders': True,
                'options_trading': True,
                'futures_trading': True,
                'multi_strategy': True,
                'portfolio_management': True
            }
        )
    }

# Try importing Alpaca broker - if alpaca isn't installed, provide graceful fallback
try:
    from .alpaca_broker import AlpacaBroker
except ImportError:
    # Create dummy class if alpaca is not installed
    class AlpacaBroker:
        def __init__(self, *args, **kwargs):
            raise ImportError("alpaca-trade-api not installed. Install with: pip install stratequeue[trading]")

__all__ = [
    'BaseBroker',
    'BrokerConfig', 
    'BrokerInfo',
    'BrokerFactory',
    'detect_broker_type',
    'get_supported_brokers',
    'auto_create_broker',
    'validate_broker_credentials',
    'list_broker_features',
    'AlpacaBroker'
] 