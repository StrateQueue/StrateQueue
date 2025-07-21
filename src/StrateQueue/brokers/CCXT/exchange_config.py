"""
Exchange Configuration System

Manages exchange-specific configurations, requirements, and metadata for CCXT brokers.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExchangeInfo:
    """Information about a specific exchange"""
    id: str
    name: str
    requires_passphrase: bool
    supports_sandbox: bool
    api_permissions: List[str]
    setup_instructions: str
    popular_rank: Optional[int] = None  # 1-10 for top exchanges, None for others


class ExchangeConfig:
    """Configuration and metadata for cryptocurrency exchanges"""
    
    # Top 10 most popular exchanges for the setup menu
    TOP_10_EXCHANGES = [
        ExchangeInfo(
            id="binance",
            name="Binance",
            requires_passphrase=False,
            supports_sandbox=True,
            api_permissions=["spot", "futures"],
            setup_instructions="Create API key with 'Enable Trading' permission. Testnet available.",
            popular_rank=1
        ),
        ExchangeInfo(
            id="coinbase",
            name="Coinbase Pro",
            requires_passphrase=True,
            supports_sandbox=True,
            api_permissions=["trade", "view"],
            setup_instructions="Create API key with 'trade' permission. Requires passphrase. Sandbox available.",
            popular_rank=2
        ),
        ExchangeInfo(
            id="kraken",
            name="Kraken",
            requires_passphrase=False,
            supports_sandbox=False,
            api_permissions=["trade", "query"],
            setup_instructions="Create API key with 'Create & modify orders' permission. No testnet available.",
            popular_rank=3
        ),
        ExchangeInfo(
            id="bybit",
            name="Bybit",
            requires_passphrase=False,
            supports_sandbox=True,
            api_permissions=["trade"],
            setup_instructions="Create API key with trading permissions. Testnet available.",
            popular_rank=4
        ),
        ExchangeInfo(
            id="okx",
            name="OKX",
            requires_passphrase=True,
            supports_sandbox=True,
            api_permissions=["trade"],
            setup_instructions="Create API key with trading permissions. Requires passphrase. Testnet available.",
            popular_rank=5
        ),
        ExchangeInfo(
            id="kucoin",
            name="KuCoin",
            requires_passphrase=True,
            supports_sandbox=True,
            api_permissions=["trade"],
            setup_instructions="Create API key with 'Trade' permission. Requires passphrase. Sandbox available.",
            popular_rank=6
        ),
        ExchangeInfo(
            id="huobi",
            name="Huobi",
            requires_passphrase=False,
            supports_sandbox=False,
            api_permissions=["trade"],
            setup_instructions="Create API key with trading permissions. No testnet available.",
            popular_rank=7
        ),
        ExchangeInfo(
            id="bitfinex",
            name="Bitfinex",
            requires_passphrase=False,
            supports_sandbox=False,
            api_permissions=["trading"],
            setup_instructions="Create API key with 'Orders' permission. No testnet available.",
            popular_rank=8
        ),
        ExchangeInfo(
            id="gateio",
            name="Gate.io",
            requires_passphrase=False,
            supports_sandbox=False,
            api_permissions=["spot"],
            setup_instructions="Create API key with 'Spot trading' permission. No testnet available.",
            popular_rank=9
        ),
        ExchangeInfo(
            id="mexc",
            name="MEXC",
            requires_passphrase=False,
            supports_sandbox=False,
            api_permissions=["spot"],
            setup_instructions="Create API key with trading permissions. No testnet available.",
            popular_rank=10
        )
    ]
    
    @classmethod
    def get_top_10_exchanges(cls) -> List[ExchangeInfo]:
        """Get the top 10 most popular exchanges for the setup menu"""
        return cls.TOP_10_EXCHANGES
    
    @classmethod
    def get_exchange_info(cls, exchange_id: str) -> Optional[ExchangeInfo]:
        """Get information for a specific exchange"""
        # Check top 10 first
        for exchange in cls.TOP_10_EXCHANGES:
            if exchange.id == exchange_id:
                return exchange
        
        # For other exchanges, return basic info
        try:
            import ccxt
            if hasattr(ccxt, exchange_id):
                return ExchangeInfo(
                    id=exchange_id,
                    name=exchange_id.title(),
                    requires_passphrase=False,  # Default assumption
                    supports_sandbox=False,     # Default assumption
                    api_permissions=["trade"],  # Default assumption
                    setup_instructions=f"Create API key for {exchange_id} with trading permissions.",
                    popular_rank=None
                )
        except ImportError:
            pass
        
        return None
    
    @classmethod
    def validate_exchange(cls, exchange_id: str) -> bool:
        """Validate if an exchange is supported by CCXT"""
        try:
            import ccxt
            return hasattr(ccxt, exchange_id)
        except ImportError:
            logger.warning("CCXT not installed, cannot validate exchange")
            return False
    
    @classmethod
    def get_all_supported_exchanges(cls) -> List[str]:
        """Get list of all exchanges supported by CCXT"""
        try:
            import ccxt
            return ccxt.exchanges
        except ImportError:
            logger.warning("CCXT not installed, returning empty exchange list")
            return []
    
    @classmethod
    def suggest_similar_exchanges(cls, partial_name: str, limit: int = 5) -> List[str]:
        """Suggest exchanges that match partial name"""
        all_exchanges = cls.get_all_supported_exchanges()
        partial_lower = partial_name.lower()
        
        # Find exchanges that start with or contain the partial name
        matches = []
        for exchange in all_exchanges:
            if exchange.lower().startswith(partial_lower):
                matches.append(exchange)
            elif partial_lower in exchange.lower():
                matches.append(exchange)
        
        return matches[:limit]