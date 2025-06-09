"""
Alpaca Utility Functions

Contains helper functions for Alpaca trading operations.
"""

import os
import logging
from typing import Optional

from typing import TYPE_CHECKING

from .config import AlpacaConfig
from ..simple_portfolio_manager import SimplePortfolioManager

if TYPE_CHECKING:
    from .executor import AlpacaExecutor

logger = logging.getLogger(__name__)

def normalize_crypto_symbol(symbol: str) -> str:
    """
    Normalize crypto symbols for Alpaca format.
    
    Args:
        symbol: Original symbol (e.g., 'ETH', 'BTC')
        
    Returns:
        Alpaca-formatted symbol (e.g., 'ETH/USD', 'BTC/USD')
    """
    # If already has a slash, assume it's properly formatted
    if '/' in symbol:
        return symbol
    
    # Add /USD for crypto symbols
    crypto_symbols = ['BTC', 'ETH', 'LTC', 'BCH', 'DOGE', 'SHIB', 'AVAX', 'UNI']
    if symbol.upper() in crypto_symbols:
        return f"{symbol.upper()}/USD"
    
    # For other symbols, return as-is (stocks, etc.)
    return symbol.upper()

def create_alpaca_executor_from_env(portfolio_manager: Optional[SimplePortfolioManager] = None) -> 'AlpacaExecutor':
    """
    Create AlpacaExecutor from environment variables
    
    Expected environment variables:
    - PAPER_KEY: Alpaca API key for paper trading
    - PAPER_SECRET: Alpaca secret key for paper trading  
    - PAPER_ENDPOINT: Alpaca base URL for paper trading
    
    Args:
        portfolio_manager: Optional portfolio manager for multi-strategy support
    
    Returns:
        Configured AlpacaExecutor instance
    """
    # Get environment variables
    api_key = os.getenv('PAPER_KEY')
    secret_key = os.getenv('PAPER_SECRET')
    base_url = os.getenv('PAPER_ENDPOINT')
    
    if not api_key or not secret_key:
        raise ValueError("Missing required environment variables: PAPER_KEY and PAPER_SECRET")
    
    # Remove /v2 suffix if present in base_url since TradingClient adds it automatically
    if base_url and base_url.endswith('/v2'):
        base_url = base_url[:-3]
        logger.info(f"Removed /v2 suffix from base_url: {base_url}")
    
    config = AlpacaConfig(
        api_key=api_key,
        secret_key=secret_key, 
        base_url=base_url,
        paper=True  # Always use paper trading for safety
    )
    
    # Import here to avoid circular import
    from .executor import AlpacaExecutor
    return AlpacaExecutor(config, portfolio_manager=portfolio_manager) 