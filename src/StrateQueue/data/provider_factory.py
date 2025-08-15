"""
Data Provider Factory and Detection

Provides factory methods for creating data providers and detecting which provider
to use based on environment variables or explicit configuration.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

# Load environment variables from .env file
from dotenv import load_dotenv

# Prefer provider-driven validation; core wrapper remains for legacy
from ..core.granularity import validate_granularity
from .sources.data_source_base import BaseDataIngestion

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public convenience wrappers (backwards-compatibility helpers)
# ---------------------------------------------------------------------------

def create_provider(provider_type: str, config: "DataProviderConfig | None" = None):
    """Forward to DataProviderFactory.create_provider for backward compatibility."""
    return DataProviderFactory.create_provider(provider_type, config)


def is_provider_supported(provider_type: str) -> bool:
    """Return True if *provider_type* is among the registered providers."""
    return DataProviderFactory.is_provider_supported(provider_type)


@dataclass
class DataProviderInfo:
    """Information about a data provider"""
    name: str
    version: str
    supported_features: dict[str, bool]
    description: str
    supported_markets: list[str]  # e.g., ['stocks', 'crypto', 'forex', 'commodities']
    requires_api_key: bool
    supported_granularities: list[str]


@dataclass
class DataProviderConfig:
    """Base configuration for data provider connections"""
    provider_type: str
    api_key: str | None = None
    granularity: str = "1m"
    timeout: int = 30
    additional_params: dict[str, Any] = None

    def __post_init__(self):
        if self.additional_params is None:
            self.additional_params = {}


class DataProviderFactory:
    """Factory for creating data provider instances"""

    _providers: dict[str, type] = {}
    _initialized = False

    @classmethod
    def _initialize_providers(cls):
        """Initialize available data providers (lazy loading)"""
        if cls._initialized:
            return

        try:
            from .sources.polygon import PolygonDataIngestion
            cls._providers['polygon'] = PolygonDataIngestion
            logger.debug("Registered Polygon data provider")
        except ImportError as e:
            logger.warning(f"Could not load Polygon data provider: {e}")

        try:
            from .sources.coinmarketcap import CoinMarketCapDataIngestion
            cls._providers['coinmarketcap'] = CoinMarketCapDataIngestion
            logger.debug("Registered CoinMarketCap data provider")
        except ImportError as e:
            logger.warning(f"Could not load CoinMarketCap data provider: {e}")

        try:
            from .sources.demo import TestDataIngestion
            cls._providers['demo'] = TestDataIngestion
            logger.debug("Registered Demo/Test data provider")
        except ImportError as e:
            logger.warning(f"Could not load Demo data provider: {e}")

        try:
            from .sources.yfinance import YahooFinanceDataIngestion
            cls._providers['yfinance'] = YahooFinanceDataIngestion
            logger.debug("Registered Yahoo Finance data provider")
        except ImportError as e:
            logger.warning(f"Could not load Yahoo Finance data provider: {e}")

        # New: Alpaca provider (register even if SDK missing so error surfaces at creation time)
        try:
            from .sources.alpaca import AlpacaDataIngestion
            cls._providers['alpaca'] = AlpacaDataIngestion
            if AlpacaDataIngestion.dependencies_available():
                logger.debug("Registered Alpaca data provider")
            else:
                logger.debug("Alpaca provider registered but SDK not available; will raise at instantiation")
        except ImportError as e:
            logger.warning(f"Could not load Alpaca data provider: {e}")

        # Register IBKR data provider
        try:
            from .sources.ibkr import IBKRDataIngestion
            cls._providers['ibkr'] = IBKRDataIngestion
            logger.debug("Registered IBKR data provider")
        except ImportError as e:
            logger.warning(f"Could not load IBKR data provider: {e}")
            # Note: This will happen if ib_insync is not installed

        # Register CCXT data provider
        try:
            from .sources.ccxt_data import CCXTDataIngestion
            cls._providers['ccxt'] = CCXTDataIngestion
            
            # Register exchange-specific aliases for popular exchanges
            popular_exchanges = [
                'binance', 'coinbase', 'kraken', 'bitfinex', 'huobi', 'okx', 
                'bybit', 'kucoin', 'gate', 'bitget', 'mexc', 'coinex',
                'bitstamp', 'gemini', 'ftx', 'bitmex', 'deribit', 'bittrex'
            ]
            
            for exchange in popular_exchanges:
                cls._providers[f'ccxt.{exchange}'] = CCXTDataIngestion
            
            if CCXTDataIngestion.dependencies_available():
                logger.debug(f"Registered CCXT data provider with {len(popular_exchanges)} exchange aliases")
            else:
                logger.debug("CCXT provider registered but library not available; will raise at instantiation")
        except ImportError as e:
            logger.warning(f"Could not load CCXT data provider: {e}")

        cls._initialized = True

    @classmethod
    def create_provider(cls, provider_type: str, config: DataProviderConfig | None = None) -> BaseDataIngestion:
        """
        Create a data provider instance

        Args:
            provider_type: Type of provider ('polygon', 'coinmarketcap', 'demo', etc.)
            config: Optional provider configuration (will auto-detect from env if None)

        Returns:
            BaseDataIngestion instance

        Raises:
            ValueError: If provider type is not supported or configuration is invalid
        """
        cls._initialize_providers()

        if provider_type not in cls._providers:
            available = list(cls._providers.keys())
            raise ValueError(f"Unsupported data provider type '{provider_type}'. Available: {available}")

        provider_class = cls._providers[provider_type]
        logger.debug(f"Creating {provider_type} data provider instance")

        # Auto-generate config from environment if not provided
        if config is None:
            try:
                env_config = cls._get_provider_config_from_env(provider_type)
                config = DataProviderConfig(
                    provider_type=provider_type,
                    api_key=env_config.get('api_key'),
                    granularity=env_config.get('granularity', "1m"),
                    additional_params=env_config
                )
            except Exception as e:
                logger.error(f"Failed to create config from environment for {provider_type}: {e}")
                # For demo provider, we can continue without config
                if provider_type == 'demo':
                    config = DataProviderConfig(provider_type=provider_type)
                else:
                    raise ValueError(f"No config provided and failed to auto-detect from environment: {e}")

        # Validate granularity via provider capability first where available
        # Fallback to legacy core wrapper if capability is absent
        cls._initialize_providers()
        provider_class = cls._providers.get(provider_type)
        if provider_class and hasattr(provider_class, "accepts_granularity"):
            try:
                accepted = provider_class.accepts_granularity(config.granularity)  # type: ignore[attr-defined]
            except Exception:
                accepted = False
            if not accepted:
                supported = []
                if hasattr(provider_class, "get_supported_granularities"):
                    try:
                        supported = sorted(list(provider_class.get_supported_granularities()))  # type: ignore[attr-defined]
                    except Exception:
                        supported = []
                # Try resampling plan: if requested is a multiple of a supported base, allow
                try:
                    from ..core.resample import plan_base_granularity
                    if supported:
                        _ = plan_base_granularity(supported, config.granularity)
                        accepted = True
                except Exception:
                    pass
                if accepted:
                    # proceed
                    pass
                else:
                    if supported:
                        raise ValueError(
                            f"Granularity '{config.granularity}' not supported by {provider_type}. Supported: {', '.join(supported)}"
                        )
                    raise ValueError(
                        f"Granularity '{config.granularity}' not supported by {provider_type}."
                    )
        else:
            is_valid, error_msg = validate_granularity(config.granularity, provider_type)
            if not is_valid:
                raise ValueError(error_msg)

        # Create the appropriate data provider
        return cls._create_provider_instance(provider_class, provider_type, config)

    @classmethod
    def _create_provider_instance(cls, provider_class: type, provider_type: str, config: DataProviderConfig) -> BaseDataIngestion:
        """Create provider instance with proper configuration"""

        if provider_type == "polygon":
            if not config.api_key:
                raise ValueError("Polygon data provider requires an API key")
            return provider_class(config.api_key)

        elif provider_type == "coinmarketcap":
            if not config.api_key:
                config.api_key = os.getenv('CMC_API_KEY')
                if not config.api_key:
                    raise ValueError("CoinMarketCap data provider requires an API key. Set CMC_API_KEY environment variable.")
            return provider_class(config.api_key, config.granularity)

        elif provider_type == "demo":
            provider = provider_class()
            # Set update interval based on granularity for demo simulation
            provider.set_update_interval_from_granularity(config.granularity)
            return provider

        elif provider_type == "yfinance":
            return provider_class(config.granularity)

        # New: Alpaca provider creation
        elif provider_type == "alpaca":
            # Support multiple credential naming conventions (same as broker + new data-specific)
            api_key = config.api_key
            if not api_key:
                api_key = (
                    os.getenv("ALPACA_DATA_API_KEY") or  # New: data-specific credentials from broker setup
                    os.getenv("PAPER_KEY") or
                    os.getenv("PAPER_API_KEY") or
                    os.getenv("ALPACA_API_KEY")
                )
            
            secret_key = config.additional_params.get("secret_key") if config.additional_params else None
            if not secret_key:
                secret_key = (
                    os.getenv("ALPACA_DATA_SECRET_KEY") or  # New: data-specific credentials from broker setup
                    os.getenv("PAPER_SECRET") or
                    os.getenv("PAPER_SECRET_KEY") or
                    os.getenv("ALPACA_SECRET_KEY")
                )

            if not (api_key and secret_key):
                raise ValueError("Alpaca data provider requires credentials. Set PAPER_KEY/PAPER_SECRET or ALPACA_API_KEY/ALPACA_SECRET_KEY")

            paper = bool(os.getenv("ALPACA_PAPER", "1"))  # default to paper feed
            return provider_class(api_key, secret_key, paper=paper, granularity=config.granularity)

        elif provider_type == "ibkr":
            # IBKR provider uses IB Gateway for data - support data-specific credentials from broker setup
            host = os.getenv("IBKR_DATA_HOST") or os.getenv("IB_TWS_HOST", "localhost")
            port = int(os.getenv("IBKR_DATA_PORT") or os.getenv("IB_TWS_PORT", "4002"))
            client_id = int(os.getenv("IBKR_DATA_CLIENT_ID") or os.getenv("IB_CLIENT_ID", "1"))
            paper_trading = bool((os.getenv("IBKR_DATA_PAPER") or os.getenv("IB_PAPER", "true")).lower() == "true")
            
            return provider_class(
                granularity=config.granularity, 
                paper_trading=paper_trading,
                host=host,
                port=port,
                client_id=client_id
            )

        elif provider_type == "ccxt" or provider_type.startswith("ccxt."):
            # CCXT provider for cryptocurrency exchanges
            exchange_id = None
            
            # Parse exchange from provider_type if using ccxt.exchange format
            if provider_type.startswith("ccxt."):
                exchange_id = provider_type.split(".", 1)[1]
            else:
                # Generic ccxt provider - get exchange from config or environment
                exchange_id = config.additional_params.get("exchange_id") if config.additional_params else None
                if not exchange_id:
                    exchange_id = os.getenv('CCXT_EXCHANGE')
                    if not exchange_id:
                        raise ValueError("CCXT data provider requires exchange ID. Set CCXT_EXCHANGE environment variable.")
            
            # Get credentials using exchange-specific logic (same as broker)
            api_key = config.api_key
            secret_key = config.additional_params.get("secret_key") if config.additional_params else None
            passphrase = config.additional_params.get("passphrase") if config.additional_params else None
            
            # If credentials not provided in config, get from environment with exchange-specific fallback
            if not api_key or not secret_key:
                # Try exchange-specific environment variables first
                exchange_upper = exchange_id.upper()
                if not api_key:
                    api_key = os.getenv(f'CCXT_{exchange_upper}_API_KEY') or os.getenv('CCXT_API_KEY')
                if not secret_key:
                    secret_key = os.getenv(f'CCXT_{exchange_upper}_SECRET_KEY') or os.getenv('CCXT_SECRET_KEY')
                if not passphrase:
                    passphrase = os.getenv(f'CCXT_{exchange_upper}_PASSPHRASE') or os.getenv('CCXT_PASSPHRASE', '')
            
            sandbox = bool(os.getenv('CCXT_SANDBOX', 'true').lower() == 'true')
            
            return provider_class(
                exchange_id=exchange_id,
                api_key=api_key,
                secret_key=secret_key,
                passphrase=passphrase,
                granularity=config.granularity,
                sandbox=sandbox
            )

        else:
            # Generic provider creation for future providers
            return provider_class(config)

    @classmethod
    def _get_provider_config_from_env(cls, provider_type: str) -> dict[str, Any]:
        """Get provider configuration from environment variables"""
        config = {}

        if provider_type == "polygon":
            api_key = os.getenv('POLYGON_API_KEY')
            if api_key:
                config['api_key'] = api_key

        elif provider_type == "coinmarketcap":
            api_key = os.getenv('CMC_API_KEY')
            if api_key:
                config['api_key'] = api_key

        elif provider_type == "demo":
            # Demo doesn't need any environment configuration
            pass

        elif provider_type == "alpaca":
            # Support multiple credential naming conventions (same as broker)
            api_key = (
                os.getenv('PAPER_KEY') or
                os.getenv('PAPER_API_KEY') or
                os.getenv('ALPACA_API_KEY')
            )
            secret_key = (
                os.getenv('PAPER_SECRET') or
                os.getenv('PAPER_SECRET_KEY') or
                os.getenv('ALPACA_SECRET_KEY')
            )
            if api_key and secret_key:
                config['api_key'] = api_key
                config['secret_key'] = secret_key
                config['paper_trading'] = bool(os.getenv('ALPACA_PAPER', '1'))

        elif provider_type == "ibkr":
            # IBKR uses IB Gateway environment variables
            config['host'] = os.getenv('IB_TWS_HOST', 'localhost')
            config['port'] = int(os.getenv('IB_TWS_PORT', '4002'))
            config['client_id'] = int(os.getenv('IB_CLIENT_ID', '1'))
            config['paper_trading'] = bool(os.getenv('IB_PAPER', 'true').lower() == 'true')

        elif provider_type == "ccxt" or provider_type.startswith("ccxt."):
            # CCXT uses exchange-specific environment variables
            exchange_id = None
            
            # Parse exchange from provider_type if using ccxt.exchange format
            if provider_type.startswith("ccxt."):
                exchange_id = provider_type.split(".", 1)[1]
            else:
                exchange_id = os.getenv('CCXT_EXCHANGE')
            
            # Get credentials using exchange-specific logic with fallback
            api_key = None
            secret_key = None
            passphrase = ''
            
            if exchange_id:
                # Try exchange-specific environment variables first
                exchange_upper = exchange_id.upper()
                api_key = os.getenv(f'CCXT_{exchange_upper}_API_KEY') or os.getenv('CCXT_API_KEY')
                secret_key = os.getenv(f'CCXT_{exchange_upper}_SECRET_KEY') or os.getenv('CCXT_SECRET_KEY')
                passphrase = os.getenv(f'CCXT_{exchange_upper}_PASSPHRASE') or os.getenv('CCXT_PASSPHRASE', '')
            else:
                # Fallback to generic CCXT variables
                api_key = os.getenv('CCXT_API_KEY')
                secret_key = os.getenv('CCXT_SECRET_KEY')
                passphrase = os.getenv('CCXT_PASSPHRASE', '')
            
            sandbox = bool(os.getenv('CCXT_SANDBOX', 'true').lower() == 'true')
            
            if exchange_id:
                config['exchange_id'] = exchange_id
            if api_key:
                config['api_key'] = api_key
            if secret_key:
                config['secret_key'] = secret_key
            if passphrase:
                config['passphrase'] = passphrase
            config['sandbox'] = sandbox

        # Common granularity setting
        granularity = os.getenv('DATA_GRANULARITY', "1m")
        config['granularity'] = granularity

        return config

    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """
        Get list of supported data provider types

        Returns:
            List of provider type names
        """
        cls._initialize_providers()
        return list(cls._providers.keys())

    @classmethod
    def is_provider_supported(cls, provider_type: str) -> bool:
        """
        Check if a data provider type is supported

        Args:
            provider_type: Provider type to check

        Returns:
            True if provider is supported
        """
        cls._initialize_providers()
        return provider_type in cls._providers

    @classmethod
    def get_provider_info(cls, provider_type: str) -> DataProviderInfo | None:
        """
        Get information about a specific data provider without creating an instance

        Args:
            provider_type: Provider type to get info for

        Returns:
            DataProviderInfo object or None if provider not supported
        """
        cls._initialize_providers()

        if provider_type not in cls._providers:
            return None

        try:
            # Get info without creating full instance
            return cls._get_static_provider_info(provider_type)
        except Exception as e:
            logger.error(f"Error getting provider info for {provider_type}: {e}")
            return None

    @classmethod
    def _get_static_provider_info(cls, provider_type: str) -> DataProviderInfo:
        """Get static information about data providers"""

        if provider_type == "polygon":
            return DataProviderInfo(
                name="Polygon.io",
                version="1.0",
                supported_features={
                    "historical_data": True,
                    "real_time_data": True,
                    "multiple_granularities": True,
                    "stocks": True,
                    "crypto": True,
                    "forex": True
                },
                description="Professional market data from Polygon.io",
                supported_markets=["stocks", "crypto", "forex"],
                requires_api_key=True,
                supported_granularities=["1s", "5s", "10s", "30s", "1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]
            )

        elif provider_type == "coinmarketcap":
            return DataProviderInfo(
                name="CoinMarketCap",
                version="1.0",
                supported_features={
                    "historical_data": True,
                    "real_time_data": True,
                    "multiple_granularities": True,
                    "crypto": True
                },
                description="Cryptocurrency market data from CoinMarketCap",
                supported_markets=["crypto"],
                requires_api_key=True,
                supported_granularities=["1d", "1m", "5m", "15m", "30m", "1h"]
            )

        elif provider_type == "demo":
            return DataProviderInfo(
                name="Demo/Test Data",
                version="1.0",
                supported_features={
                    "historical_data": True,
                    "real_time_data": True,
                    "multiple_granularities": True,
                    "simulation": True
                },
                description="Simulated market data for testing and development",
                supported_markets=["stocks", "crypto", "any"],
                requires_api_key=False,
                supported_granularities=["1s", "5s", "10s", "30s", "1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1w"]
            )

        elif provider_type == "yfinance":
            return DataProviderInfo(
                name="Yahoo Finance",
                version="1.0",
                supported_features={
                    "historical_data": True,
                    "real_time_data": True,
                    "multiple_granularities": True,
                    "stocks": True,
                    "etfs": True,
                    "indices": True
                },
                description="Free stock market data from Yahoo Finance",
                supported_markets=["stocks", "etfs", "indices", "forex", "crypto"],
                requires_api_key=False,
                supported_granularities=["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"]
            )

        elif provider_type == "alpaca":
            return DataProviderInfo(
                name="Alpaca",
                version="1.0",
                supported_features={
                    "historical_data": True,
                    "real_time_data": True,
                    "multiple_granularities": True,
                    "stocks": True,
                    "crypto": True
                },
                description="Market data via Alpaca Market Data API",
                supported_markets=["stocks", "crypto"],
                requires_api_key=True,
                supported_granularities=["1m", "5m", "15m", "1h", "1d"]
            )

        elif provider_type == "ibkr":
            return DataProviderInfo(
                name="Interactive Brokers",
                version="1.0",
                supported_features={
                    "historical_data": True,
                    "real_time_data": True,
                    "multiple_granularities": True,
                    "stocks": True,
                    "crypto": True,
                    "options": True,
                    "futures": True,
                    "forex": True,
                    "streaming": True,
                    "level2_data": True
                },
                description="Professional market data via Interactive Brokers IB Gateway",
                supported_markets=["stocks", "crypto", "options", "futures", "forex"],
                requires_api_key=False,  # Uses TWS/Gateway connection instead
                supported_granularities=["1s", "5s", "10s", "15s", "30s", "1m", "2m", "3m", "5m", "10m", "15m", "20m", "30m", "1h", "2h", "3h", "4h", "8h", "1d", "1w", "1mo"]
            )

        elif provider_type == "ccxt":
            return DataProviderInfo(
                name="CCXT",
                version="1.0",
                supported_features={
                    "historical_data": True,
                    "real_time_data": True,
                    "multiple_granularities": True,
                    "crypto": True,
                    "multiple_exchanges": True,
                    "250_plus_exchanges": True
                },
                description="Cryptocurrency market data from 250+ exchanges via CCXT library",
                supported_markets=["crypto"],
                requires_api_key=True,
                supported_granularities=["1s", "5s", "10s", "30s", "1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1w"]
            )

        else:
            raise ValueError(f"Unknown provider type: {provider_type}")


def detect_provider_type() -> str:
    """
    Detect which data provider to use based on environment variables

    Returns:
        Provider type name ('polygon', 'coinmarketcap', 'demo') or 'unknown'
    """
    logger.debug("Detecting data provider type from environment")

    try:
        # Check for API keys to determine available providers
        if os.getenv('POLYGON_API_KEY'):
            logger.info("Detected Polygon API key, suggesting polygon provider")
            return 'polygon'

        if os.getenv('CMC_API_KEY'):
            logger.info("Detected CoinMarketCap API key, suggesting coinmarketcap provider")
            return 'coinmarketcap'

        # Check for Alpaca credentials (support multiple naming conventions)
        alpaca_key = (
            os.getenv('PAPER_KEY') or
            os.getenv('PAPER_API_KEY') or
            os.getenv('ALPACA_API_KEY')
        )
        alpaca_secret = (
            os.getenv('PAPER_SECRET') or
            os.getenv('PAPER_SECRET_KEY') or
            os.getenv('ALPACA_SECRET_KEY')
        )
        if alpaca_key and alpaca_secret:
            logger.info("Detected Alpaca credentials, suggesting alpaca provider")
            return 'alpaca'

        # Check for IBKR/IB Gateway credentials
        if os.getenv('IB_TWS_PORT') or os.getenv('IB_CLIENT_ID') or os.getenv('IB_TWS_HOST'):
            logger.info("Detected IB Gateway credentials, suggesting ibkr provider")
            return 'ibkr'

        # Check for CCXT credentials (generic or exchange-specific)
        ccxt_exchange = os.getenv('CCXT_EXCHANGE')
        ccxt_key = os.getenv('CCXT_API_KEY')
        ccxt_secret = os.getenv('CCXT_SECRET_KEY')
        if ccxt_exchange and ccxt_key and ccxt_secret:
            logger.info("Detected CCXT credentials, suggesting ccxt provider")
            return 'ccxt'
        
        # Check for exchange-specific CCXT credentials
        popular_exchanges = [
            'binance', 'coinbase', 'kraken', 'bitfinex', 'huobi', 'okx', 
            'bybit', 'kucoin', 'gate', 'bitget', 'mexc', 'coinex'
        ]
        for exchange in popular_exchanges:
            exchange_upper = exchange.upper()
            exchange_key = os.getenv(f'CCXT_{exchange_upper}_API_KEY')
            exchange_secret = os.getenv(f'CCXT_{exchange_upper}_SECRET_KEY')
            if exchange_key and exchange_secret:
                logger.info(f"Detected CCXT {exchange} credentials, suggesting ccxt provider")
                return 'ccxt'

        # Check for explicit provider setting
        explicit_provider = os.getenv('DATA_PROVIDER')
        if explicit_provider:
            if DataProviderFactory.is_provider_supported(explicit_provider):
                logger.info(f"Using explicitly configured provider: {explicit_provider}")
                return explicit_provider
            else:
                logger.warning(f"Explicitly configured provider '{explicit_provider}' is not supported")

        logger.info("No data provider detected from environment, defaulting to demo")
        return 'demo'

    except Exception as e:
        logger.error(f"Error detecting data provider type: {e}")
        return 'unknown'


def auto_create_provider(granularity: str = "1m") -> BaseDataIngestion:
    """
    Automatically detect provider type and create appropriate provider instance

    Args:
        granularity: Data granularity (e.g., '1s', '1m', '5m', '1h', '1d')

    Returns:
        BaseDataIngestion instance

    Raises:
        ValueError: If provider cannot be detected or created
    """
    provider_type = detect_provider_type()

    if provider_type == 'unknown':
        raise ValueError("Could not detect data provider type from environment")

    if not DataProviderFactory.is_provider_supported(provider_type):
        supported = DataProviderFactory.get_supported_providers()
        raise ValueError(f"Detected provider '{provider_type}' is not supported. Available: {supported}")

    # Create config with granularity and auto-detected environment settings
    try:
        env_config = DataProviderFactory._get_provider_config_from_env(provider_type)
        config = DataProviderConfig(
            provider_type=provider_type,
            api_key=env_config.get('api_key'),
            granularity=granularity,
            additional_params=env_config
        )
    except Exception as e:
        logger.error(f"Failed to create auto config for {provider_type}: {e}")
        # For demo provider, we can continue without config
        if provider_type == 'demo':
            config = DataProviderConfig(provider_type=provider_type, granularity=granularity)
        else:
            raise ValueError(f"Failed to auto-configure {provider_type}: {e}")

    return DataProviderFactory.create_provider(provider_type, config)


def get_supported_providers() -> list[str]:
    """
    Get list of supported data provider types

    Returns:
        List of provider type names
    """
    return DataProviderFactory.get_supported_providers()


def validate_provider_credentials(provider_type: str = None) -> bool:
    """
    Validate data provider credentials/configuration

    Args:
        provider_type: Provider type to validate (auto-detect if None)

    Returns:
        True if credentials are valid
    """
    try:
        if provider_type is None:
            provider_type = detect_provider_type()

        if provider_type == 'unknown':
            return False

        if not DataProviderFactory.is_provider_supported(provider_type):
            return False

        # Try to create provider to validate configuration
        provider = DataProviderFactory.create_provider(provider_type)

        # For providers that require API keys, validate them
        provider_info = DataProviderFactory.get_provider_info(provider_type)
        if provider_info and provider_info.requires_api_key:
            # This would be provider-specific validation
            # For now, just check if provider was created successfully
            return provider is not None

        return True

    except Exception as e:
        logger.error(f"Error validating provider credentials: {e}")
        return False


def list_provider_features() -> dict[str, DataProviderInfo]:
    """
    List features and capabilities of all supported data providers

    Returns:
        Dictionary mapping provider type to DataProviderInfo
    """
    DataProviderFactory._initialize_providers()

    features = {}
    for provider_type in DataProviderFactory.get_supported_providers():
        info = DataProviderFactory.get_provider_info(provider_type)
        if info:
            features[provider_type] = info

    return features


def create_data_source(data_source: str, api_key: str | None = None,
                      granularity: str = "1m") -> BaseDataIngestion:
    """
    Create a data source instance

    Args:
        data_source: Type of data source ('polygon', 'coinmarketcap', 'demo')
        api_key: API key for external data sources (not needed for demo)
        granularity: Data granularity (e.g., '1s', '1m', '5m', '1h', '1d')

    Returns:
        Configured data ingestion instance
    """
    config = DataProviderConfig(
        provider_type=data_source,
        api_key=api_key,
        granularity=granularity
    )

    return DataProviderFactory.create_provider(data_source, config)
