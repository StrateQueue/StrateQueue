"""
Interactive Brokers Contract Helpers

Helper functions to create IB contracts for different asset types.
"""

import logging
from typing import Optional, Tuple

try:
    from ib_insync import Stock, Crypto, Contract, IB
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False
    
    # Create dummy classes for graceful fallback
    class Stock:
        def __init__(self, *args, **kwargs):
            raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
    
    class Crypto:
        def __init__(self, *args, **kwargs):
            raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
    
    class Contract:
        def __init__(self, *args, **kwargs):
            raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
    
    class IB:
        def __init__(self, *args, **kwargs):
            raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")

logger = logging.getLogger(__name__)


def detect_security_type_from_ibkr(ib_client: IB, symbol: str) -> Tuple[str, Optional[dict]]:
    """
    Use IBKR's API to detect the security type of a symbol
    
    Args:
        ib_client: Connected IB client
        symbol: Symbol to analyze
        
    Returns:
        Tuple of (security_type, contract_details) where:
        - security_type: 'STK', 'CRYPTO', 'FUT', 'OPT', etc.
        - contract_details: Dictionary with exchange, currency, etc.
    """
    if not IB_INSYNC_AVAILABLE:
        raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
    
    try:
        # Use reqMatchingSymbols to find all matching contracts
        matching_symbols = ib_client.reqMatchingSymbols(symbol)
        
        if not matching_symbols:
            logger.warning(f"No matching symbols found for {symbol}")
            return "UNKNOWN", None
        
        # Look for the best match - prefer exact symbol matches
        best_match = None
        for contract_desc in matching_symbols:
            contract = contract_desc.contract
            
            # Exact symbol match gets priority
            if contract.symbol.upper() == symbol.upper():
                best_match = contract_desc
                break
            
            # Otherwise, take the first reasonable match
            if best_match is None:
                best_match = contract_desc
        
        if best_match:
            contract = best_match.contract
            details = {
                'symbol': contract.symbol,
                'secType': contract.secType,
                'exchange': contract.exchange,
                'currency': contract.currency,
                'primaryExchange': getattr(contract, 'primaryExchange', ''),
                'localSymbol': getattr(contract, 'localSymbol', ''),
                'description': getattr(best_match, 'derivativeSecTypes', [])
            }
            
            logger.info(f"Detected {symbol} as {contract.secType} on {contract.exchange}")
            return contract.secType, details
        
    except Exception as e:
        logger.error(f"Error detecting security type for {symbol}: {e}")
    
    # Fallback to heuristic detection
    return detect_asset_type_heuristic(symbol), None


def detect_asset_type_heuristic(symbol: str) -> str:
    """
    Heuristic-based asset type detection (fallback)
    
    Args:
        symbol: Trading symbol
        
    Returns:
        Asset type: "STK", "CRYPTO", or "UNKNOWN"
    """
    symbol_upper = symbol.upper()
    
    # Common crypto patterns
    crypto_indicators = [
        'BTC', 'ETH', 'ADA', 'DOT', 'LINK', 'AAVE', 'UNI', 'COMP',
        'SOL', 'AVAX', 'MATIC', 'LTC', 'XRP', 'DOGE'
    ]
    
    # Check if it's a crypto pair (like BTCUSD, ETHUSD)
    for crypto in crypto_indicators:
        if symbol_upper.startswith(crypto) and len(symbol_upper) >= 6:
            return "CRYPTO"
    
    # Check for -USD suffix (like AAVE-USD)
    if '-USD' in symbol_upper or '-EUR' in symbol_upper:
        return "CRYPTO"
    
    # Default to stock for typical stock symbols
    if len(symbol_upper) <= 5 and symbol_upper.isalpha():
        return "STK"
    
    return "UNKNOWN"


def stock_contract(ticker: str, currency: str = "USD", exchange: str = "SMART") -> Contract:
    """
    Create a stock contract for Interactive Brokers
    
    Args:
        ticker: Stock symbol (e.g., "AAPL")
        currency: Currency (default: "USD")
        exchange: Exchange (default: "SMART" for IB's smart routing)
    
    Returns:
        IB Stock contract
    """
    if not IB_INSYNC_AVAILABLE:
        raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
    
    return Stock(ticker.upper(), exchange, currency)


def crypto_contract(symbol: str, currency: str = "USD", exchange: str = "PAXOS") -> Contract:
    """
    Create a crypto contract for Interactive Brokers
    
    Args:
        symbol: Crypto symbol (e.g., "BTC", "AAVE-USD", or "BTCUSD")
        currency: Quote currency (default: "USD")
        exchange: Crypto exchange (default: "PAXOS")
    
    Returns:
        IB Crypto contract
    """
    if not IB_INSYNC_AVAILABLE:
        raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
    
    # Handle different crypto symbol formats
    if '-' in symbol:
        # Format: AAVE-USD
        parts = symbol.split('-')
        base = parts[0].upper()
        quote = parts[1].upper() if len(parts) > 1 else currency.upper()
    elif len(symbol) >= 6 and symbol.upper().endswith('USD'):
        # Format: BTCUSD
        base = symbol[:-3].upper()
        quote = symbol[-3:].upper()
    else:
        # Simple format: BTC
        base = symbol.upper()
        quote = currency.upper()
    
    logger.info(f"Creating crypto contract: {base}/{quote} on {exchange}")
    return Crypto(base, exchange, quote)


def create_contract_with_detection(ib_client: IB, symbol: str) -> Tuple[Contract, str]:
    """
    Create appropriate contract with automatic security type detection
    
    Args:
        ib_client: Connected IB client
        symbol: Trading symbol
        
    Returns:
        Tuple of (contract, security_type)
    """
    if not IB_INSYNC_AVAILABLE:
        raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
    
    # Detect security type using IBKR API
    sec_type, details = detect_security_type_from_ibkr(ib_client, symbol)
    
    if sec_type == "CRYPTO":
        # Use details from IBKR if available
        if details:
            exchange = details.get('exchange', 'PAXOS')
            currency = details.get('currency', 'USD')
            return crypto_contract(symbol, currency, exchange), sec_type
        else:
            return crypto_contract(symbol), sec_type
    
    elif sec_type == "STK":
        # Use details from IBKR if available
        if details:
            exchange = details.get('exchange', 'SMART')
            currency = details.get('currency', 'USD')
            return stock_contract(symbol, currency, exchange), sec_type
        else:
            return stock_contract(symbol), sec_type
    
    else:
        # Unknown or unsupported security type - default to stock
        logger.warning(f"Unknown security type {sec_type} for {symbol}, defaulting to stock")
        return stock_contract(symbol), "STK"


def create_contract(symbol: str, asset_type: str = None) -> Contract:
    """
    Create appropriate contract based on symbol and asset type (legacy method)
    
    Args:
        symbol: Trading symbol
        asset_type: Optional asset type override ("stock", "crypto")
        
    Returns:
        Appropriate IB contract
    """
    if asset_type is None:
        asset_type = detect_asset_type_heuristic(symbol)
        # Convert to legacy format
        if asset_type == "CRYPTO":
            asset_type = "crypto"
        else:
            asset_type = "stock"
    
    if asset_type == "crypto":
        return crypto_contract(symbol)
    else:
        return stock_contract(symbol) 