"""
Broker Factory and Detection

Provides factory methods for creating trading brokers and detecting which broker
to use based on environment variables or explicit configuration.
"""

import logging

from .broker_base import BaseBroker, BrokerConfig, BrokerInfo
from .broker_helpers import (
    detect_broker_from_environment,
    get_broker_config_from_env,
    validate_broker_environment,
)

logger = logging.getLogger(__name__)


class BrokerFactory:
    """Factory for creating trading broker instances"""

    _brokers: dict[str, type] = {}
    _initialized = False

    @classmethod
    def _normalize_broker_type(cls, broker_type: str) -> str:
        """
        Normalize broker type to canonical form
        
        Args:
            broker_type: Broker type (can be alias)
            
        Returns:
            Canonical broker type name
        """
        # Map aliases to canonical names
        alias_map = {
            'ibkr': 'ibkr',
            'IBKR': 'ibkr', 
            'interactive-brokers': 'ibkr',
            'interactive_brokers': 'ibkr',
            'alpaca': 'alpaca',
        }
        
        return alias_map.get(broker_type, broker_type)

    @classmethod
    def _initialize_brokers(cls):
        """Initialize available brokers (lazy loading)"""
        if cls._initialized:
            return

        try:
            from .Alpaca.alpaca_broker import AlpacaBroker
            cls._brokers['alpaca'] = AlpacaBroker
            logger.debug("Registered Alpaca broker")
        except ImportError as e:
            logger.warning(f"Could not load Alpaca broker: {e}")

        # Register Interactive Brokers with multiple aliases
        try:
            from .IBKR.ibkr_broker import IBKRBroker
            # Register with multiple aliases for user convenience
            cls._brokers['ibkr'] = IBKRBroker
            cls._brokers['IBKR'] = IBKRBroker
            cls._brokers['interactive-brokers'] = IBKRBroker
            cls._brokers['interactive_brokers'] = IBKRBroker  # Keep existing name for compatibility
            logger.debug("Registered Interactive Brokers broker with aliases: ibkr, IBKR, interactive-brokers, interactive_brokers")
        except ImportError as e:
            logger.warning(f"Could not load Interactive Brokers broker: {e}")
            # Note: This will happen if ib_insync is not installed

        try:
            # from .td_ameritrade_broker import TDAmeritradeBroker
            # cls._brokers['td_ameritrade'] = TDAmeritradeBroker
            # logger.debug("Registered TD Ameritrade broker")
            pass
        except ImportError:
            # TD Ameritrade broker not implemented yet
            pass

        cls._initialized = True

    @classmethod
    def create_broker(cls, broker_type: str, config: BrokerConfig | None = None,
                     portfolio_manager=None, statistics_manager=None, position_sizer=None) -> BaseBroker:
        """
        Create a trading broker instance

        Args:
            broker_type: Type of broker ('alpaca', 'interactive_brokers', etc.)
            config: Optional broker configuration (will auto-detect from env if None)
            portfolio_manager: Optional portfolio manager for multi-strategy support
            statistics_manager: Optional statistics manager for trade tracking
            position_sizer: Optional position sizer for calculating trade sizes

        Returns:
            BaseBroker instance

        Raises:
            ValueError: If broker type is not supported
        """
        cls._initialize_brokers()

        if broker_type not in cls._brokers:
            available = list(cls._brokers.keys())
            raise ValueError(f"Unsupported broker type '{broker_type}'. Available: {available}")

        broker_class = cls._brokers[broker_type]
        logger.info(f"Creating {broker_type} broker instance")

        # Auto-generate config from environment if not provided
        if config is None:
            try:
                env_config = get_broker_config_from_env(broker_type)
                config = BrokerConfig(
                    broker_type=broker_type,
                    paper_trading=env_config.get('paper_trading', True),
                    credentials=env_config,
                    additional_params=env_config
                )
            except Exception as e:
                logger.error(f"Failed to create config from environment for {broker_type}: {e}")
                raise ValueError(f"No config provided and failed to auto-detect from environment: {e}")

        # Normalize broker type for configuration
        normalized_broker_type = cls._normalize_broker_type(broker_type)
        
        # For Alpaca, get credentials appropriate for the trading mode
        if normalized_broker_type == 'alpaca' and not config.credentials:
            try:
                from .broker_helpers import get_alpaca_config_from_env
                alpaca_config = get_alpaca_config_from_env(config.paper_trading)
                config.credentials = alpaca_config
            except Exception as e:
                logger.error(f"Failed to get Alpaca credentials for {'paper' if config.paper_trading else 'live'} trading: {e}")
                raise ValueError(f"Failed to configure Alpaca for {'paper' if config.paper_trading else 'live'} trading: {e}")

        # For IBKR, get credentials from environment if not provided
        if normalized_broker_type == 'ibkr' and not config.credentials:
            try:
                from .broker_helpers import get_interactive_brokers_config_from_env
                ibkr_config = get_interactive_brokers_config_from_env()
                config.credentials = ibkr_config
            except Exception as e:
                logger.error(f"Failed to get IBKR credentials: {e}")
                raise ValueError(f"Failed to configure IBKR: {e}")

        # Create broker instance with appropriate parameters
        if normalized_broker_type == 'alpaca':
            # AlpacaBroker has statistics_manager and position_sizer parameters
            return broker_class(config, portfolio_manager, statistics_manager, position_sizer)
        elif normalized_broker_type == 'ibkr':
            # IBKRBroker takes config only
            return broker_class(config)
        else:
            # Other brokers have position_sizer parameter
            return broker_class(config, portfolio_manager, position_sizer)

    @classmethod
    def get_supported_brokers(cls) -> list[str]:
        """
        Get list of supported broker types

        Returns:
            List of broker type names
        """
        cls._initialize_brokers()
        return list(cls._brokers.keys())

    @classmethod
    def is_broker_supported(cls, broker_type: str) -> bool:
        """
        Check if a broker type is supported

        Args:
            broker_type: Broker type to check

        Returns:
            True if broker is supported
        """
        cls._initialize_brokers()
        return broker_type in cls._brokers

    @classmethod
    def get_broker_info(cls, broker_type: str) -> BrokerInfo | None:
        """
        Get information about a specific broker without creating an instance

        Args:
            broker_type: Broker type to get info for

        Returns:
            BrokerInfo object or None if broker not supported
        """
        cls._initialize_brokers()

        if broker_type not in cls._brokers:
            return None

        try:
            # Create a temporary instance to get info
            broker_class = cls._brokers[broker_type]
            # Create minimal config for info retrieval
            temp_config = BrokerConfig(broker_type=broker_type)
            temp_broker = broker_class(temp_config)
            return temp_broker.get_broker_info()
        except Exception as e:
            logger.error(f"Error getting broker info for {broker_type}: {e}")
            return None


def detect_broker_type() -> str:
    """
    Detect which broker to use based on environment variables

    Returns:
        Broker type name ('alpaca', 'interactive_brokers', etc.) or 'unknown'
    """
    logger.debug("Detecting broker type from environment")

    try:
        broker_type = detect_broker_from_environment()

        if broker_type:
            logger.info(f"Detected broker type '{broker_type}' from environment")

            # Validate that the detected broker is supported
            if not BrokerFactory.is_broker_supported(broker_type):
                logger.warning(f"Detected broker '{broker_type}' is not supported")
                return 'unknown'

            # Validate environment variables
            is_valid, message = validate_broker_environment(broker_type)
            if not is_valid:
                logger.warning(f"Environment validation failed for {broker_type}: {message}")
                return 'unknown'

            return broker_type
        else:
            logger.info("No broker detected from environment variables")
            return 'unknown'

    except Exception as e:
        logger.error(f"Error detecting broker type: {e}")
        return 'unknown'


def auto_create_broker(portfolio_manager=None, statistics_manager=None, position_sizer=None) -> BaseBroker:
    """
    Automatically create a broker based on environment detection

    Args:
        portfolio_manager: Optional portfolio manager for multi-strategy support
        statistics_manager: Optional statistics manager for trade tracking
        position_sizer: Optional position sizer for calculating trade sizes

    Returns:
        BaseBroker instance

    Raises:
        ValueError: If no broker can be auto-detected or created
    """
    broker_type = detect_broker_type()

    if broker_type == 'unknown':
        raise ValueError(
            "Could not auto-detect broker type from environment. "
            "Please set appropriate environment variables or specify broker explicitly."
        )

    return BrokerFactory.create_broker(broker_type, portfolio_manager=portfolio_manager, statistics_manager=statistics_manager, position_sizer=position_sizer)


def validate_broker_credentials(broker_type: str = None) -> bool:
    """
    Validate broker credentials

    Args:
        broker_type: Broker type to validate (auto-detect if None)

    Returns:
        True if credentials are valid
    """
    try:
        if broker_type is None:
            broker_type = detect_broker_type()

        if broker_type == 'unknown':
            return False

        if not BrokerFactory.is_broker_supported(broker_type):
            return False

        # Use lightweight credential testing for IBKR to avoid interfering with live connections
        if broker_type == 'ibkr':
            try:
                from .broker_helpers import get_interactive_brokers_config_from_env
                from .IBKR.credential_check import test_ibkr_credentials
                
                ibkr_config = get_interactive_brokers_config_from_env()
                return test_ibkr_credentials(
                    host=ibkr_config.get("host", "127.0.0.1"),
                    port=int(ibkr_config.get("port", 7497)),
                    client_id=int(ibkr_config.get("client_id", 1)),
                    timeout=5
                )
            except Exception as e:
                logger.error(f"Error validating IBKR credentials: {e}")
                return False
        else:
            # For other brokers, create broker and validate credentials
            broker = BrokerFactory.create_broker(broker_type)
            return broker.validate_credentials()

    except Exception as e:
        logger.error(f"Error validating broker credentials: {e}")
        return False


def list_broker_features() -> dict[str, BrokerInfo]:
    """
    Get information about all supported brokers

    Returns:
        Dictionary mapping broker type to BrokerInfo (deduplicated by broker class)
    """
    BrokerFactory._initialize_brokers()
    broker_features = {}
    seen_classes = set()

    # Use canonical names to avoid duplicates
    canonical_brokers = {
        'alpaca': 'alpaca',
        'ibkr': 'ibkr',  # Use 'ibkr' as canonical name for IBKR
        'td_ameritrade': 'td_ameritrade'
    }

    for canonical_name in canonical_brokers.values():
        if canonical_name in BrokerFactory._brokers:
            broker_class = BrokerFactory._brokers[canonical_name]
            
            # Skip if we've already processed this broker class
            if broker_class in seen_classes:
                continue
                
            seen_classes.add(broker_class)
            
            info = BrokerFactory.get_broker_info(canonical_name)
            if info:
                broker_features[canonical_name.upper()] = info

    return broker_features
