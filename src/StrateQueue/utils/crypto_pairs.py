from typing import List

# List of individual cryptocurrency symbols supported by Alpaca (March 2025)
# NOTE: This list should be kept in sync with Alpaca documentation:
# https://alpaca.markets/support/what-cryptocurrencies-does-alpaca-currently-support
ALPACA_CRYPTO_SYMBOLS: List[str] = [
    "AAVE",
    "AVAX",
    "BAT",
    "BCH",
    "BTC",
    "CRV",
    "DOGE",
    "DOT",
    "ETH",
    "GRT",
    "LINK",
    "LTC",
    "MKR",
    "PEPE",
    "SHIB",
    "SOL",
    "SUSHI",
    "TRUMP",
    "UNI",
    "USDC",
    "USDT",
    "XRP",
    "XTZ",
    "YFI",
]

# Default base currency we quote against when normalising to Alpaca pair format
DEFAULT_BASE_CURRENCY = "USD"


def is_alpaca_crypto(symbol: str) -> bool:
    """Return True if the given symbol is recognised as an Alpaca-supported crypto symbol."""
    return symbol.upper() in ALPACA_CRYPTO_SYMBOLS


def to_alpaca_pair(symbol: str, base: str = DEFAULT_BASE_CURRENCY) -> str:
    """Convert a raw crypto symbol like ``ETH`` to Alpaca pair format (e.g. ``ETH/USD``).

    If the symbol already looks like a pair (contains ``/``) it will be returned upper-cased
    unchanged. For non-crypto symbols the original (upper-cased) string is returned so callers
    can still work with equities in the same code path without having to branch.
    """
    symbol_up = symbol.upper()

    # Already a pair – normalise case only
    if "/" in symbol_up:
        return symbol_up

    if is_alpaca_crypto(symbol_up):
        return f"{symbol_up}/{base.upper()}"

    # Not a supported crypto – return unchanged
    return symbol_up 