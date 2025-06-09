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
from .executor import AlpacaExecutor
from .utils import normalize_crypto_symbol, create_alpaca_executor_from_env

__all__ = [
    'AlpacaExecutor',
    'AlpacaConfig', 
    'PositionSizeConfig',
    'PositionSizeMode',
    'normalize_crypto_symbol',
    'create_alpaca_executor_from_env'
] 