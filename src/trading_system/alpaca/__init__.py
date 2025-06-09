"""
Alpaca Trading Integration Package

A modular package for Alpaca trading execution with support for:
- Multiple order types (market, limit, stop, stop-limit, trailing stop)
- Position sizing strategies
- Multi-strategy portfolio management
- Paper and live trading modes

Public API:
    AlpacaExecutor: Main trading executor
    AlpacaConfig: Configuration for Alpaca connection
    PositionSizeConfig: Position sizing configuration
    create_alpaca_executor_from_env: Factory function from environment variables
"""

from .config import AlpacaConfig, PositionSizeConfig, PositionSizeMode

# Try importing executor - if alpaca isn't installed, provide graceful fallback
try:
    from .executor import AlpacaExecutor
    from .utils import normalize_crypto_symbol, create_alpaca_executor_from_env
except ImportError as e:
    # Create dummy classes that provide helpful error messages
    class AlpacaExecutor:
        def __init__(self, *args, **kwargs):
            raise ImportError("alpaca-trade-api not installed. Install with: pip install stratequeue[trading]")
    
    def normalize_crypto_symbol(*args, **kwargs):
        raise ImportError("alpaca-trade-api not installed. Install with: pip install stratequeue[trading]")
    
    def create_alpaca_executor_from_env(*args, **kwargs):
        raise ImportError("alpaca-trade-api not installed. Install with: pip install stratequeue[trading]")

__all__ = [
    'AlpacaExecutor',
    'AlpacaConfig', 
    'PositionSizeConfig',
    'PositionSizeMode',
    'normalize_crypto_symbol',
    'create_alpaca_executor_from_env'
] 