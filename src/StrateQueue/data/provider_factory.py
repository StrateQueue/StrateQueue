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

from ..core.granularity import validate_granularity
from .sources.data_source_base import BaseDataIngestion

load_dotenv()

logger = logging.getLogger(__name__)


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

        # Future data providers can be added here
        try:
            # from .sources.alpaca import AlpacaDataIngestion
            # cls._providers['alpaca'] = AlpacaDataIngestion
            # logger.debug("Registered Alpaca data provider")
            pass
        except ImportError:
            # Alpaca data provider not implemented yet
            pass

        try:
            # from .sources.binance import BinanceDataIngestion
            # cls._providers['binance'] = BinanceDataIngestion
            # logger.debug("Registered Binance data provider")
            pass
        except ImportError:
            # Binance data provider not implemented yet
            pass

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
        logger.info(f"Creating {provider_type} data provider instance")

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

        # Validate granularity for the specified data source
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
