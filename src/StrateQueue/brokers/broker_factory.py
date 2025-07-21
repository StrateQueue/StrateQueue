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
            'ib_gateway': 'ib_gateway',
            'ibkr_gateway': 'ib_gateway',
            'ib-gateway': 'ib_gateway',
            'gateway': 'ib_gateway',
            'ccxt': 'ccxt',
        }
        
        return alias_map.get(broker_type, broker_type)

    @classmethod
    def _initialize_brokers(cls):
        """Initialize available brokers (lazy loading)"""
        if cls._initialized:
            return

        # Use absolute imports to respect sys.modules stubs (for testing)
        try:
            import importlib
            alpaca_module = importlib.import_module('StrateQueue.brokers.Alpaca.alpaca_broker')
            AlpacaBroker = alpaca_module.AlpacaBroker
            cls._brokers['alpaca'] = AlpacaBroker
            logger.debug("Registered Alpaca broker")
        except ImportError as e:
            logger.warning(f"Could not load Alpaca broker: {e}")

        # Register Interactive Brokers with multiple aliases
        try:
            import importlib
            ibkr_module = importlib.import_module('StrateQueue.brokers.IBKR.ibkr_broker')
            IBKRBroker = ibkr_module.IBKRBroker
            
            # Register with multiple aliases for user convenience
            cls._brokers['ibkr'] = IBKRBroker
            cls._brokers['IBKR'] = IBKRBroker
            cls._brokers['interactive-brokers'] = IBKRBroker
            cls._brokers['interactive_brokers'] = IBKRBroker  # Keep existing name for compatibility
            logger.debug("Registered Interactive Brokers broker with aliases: ibkr, IBKR, interactive-brokers, interactive_brokers")
        except ImportError as e:
            logger.warning(f"Could not load Interactive Brokers broker: {e}")
            # Note: This will happen if ib_insync is not installed

        # Register IB Gateway broker with streaming capabilities
        try:
            from .IBKR.ib_gateway_broker import IBGatewayBroker
            cls._brokers['ib_gateway'] = IBGatewayBroker
            cls._brokers['ibkr_gateway'] = IBGatewayBroker
            cls._brokers['ib-gateway'] = IBGatewayBroker
            cls._brokers['gateway'] = IBGatewayBroker
            logger.debug("Registered IB Gateway broker with streaming capabilities")
        except ImportError as e:
            logger.warning(f"Could not load IB Gateway broker: {e}")
            # Note: This will happen if ib_insync is not installed

        # Register CCXT broker with exchange-specific aliases
        try:
            from .CCXT.ccxt_broker import CCXTBroker
            from .CCXT.exchange_config import ExchangeConfig
            
            # Register main CCXT broker
            cls._brokers['ccxt'] = CCXTBroker
            
            # Register exchange-specific aliases for deploy command (ccxt.binance, etc.)
            top_exchanges = ExchangeConfig.get_top_10_exchanges()
            for exchange in top_exchanges:
                cls._brokers[f'ccxt.{exchange.id}'] = CCXTBroker
            
            logger.debug(f"Registered CCXT broker with {len(top_exchanges)} exchange aliases")
        except ImportError as e:
            logger.warning(f"Could not load CCXT broker: {e}")
            # Note: This will happen if ccxt is not installed

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

        # Handle ccxt.exchange syntax by extracting exchange info FIRST
        original_broker_type = broker_type
        if broker_type.startswith('ccxt.'):
            exchange_id = broker_type.split('.', 1)[1]
            broker_type = 'ccxt'  # Normalize to base ccxt type
        else:
            exchange_id = None

        broker_class = cls._brokers[original_broker_type]
        logger.debug(f"Creating {original_broker_type} broker instance")

        # Auto-generate config from environment if not provided
        if config is None:
            try:
                env_config = get_broker_config_from_env(original_broker_type)
                config = BrokerConfig(
                    broker_type=broker_type,
                    paper_trading=env_config.get('paper_trading', True),
                    credentials=env_config,
                    additional_params=env_config
                )
            except Exception as e:
                logger.error(f"Failed to create config from environment for {original_broker_type}: {e}")
                raise ValueError(f"No config provided and failed to auto-detect from environment: {e}")

        # Set exchange info if this is a ccxt.exchange broker
        if exchange_id:
            config.additional_params = config.additional_params or {}
            config.additional_params['exchange'] = exchange_id

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

        # For IBKR and IB Gateway, get credentials from environment if not provided
        if normalized_broker_type in ['ibkr', 'ib_gateway'] and not config.credentials:
            try:
                from .broker_helpers import get_interactive_brokers_config_from_env
                ibkr_config = get_interactive_brokers_config_from_env()
                config.credentials = ibkr_config
            except Exception as e:
                logger.error(f"Failed to get IBKR credentials: {e}")
                raise ValueError(f"Failed to configure IBKR: {e}")

        # For CCXT, get credentials from environment if not provided
        if normalized_broker_type == 'ccxt' and not config.credentials:
            try:
                from .broker_helpers import get_ccxt_config_from_env
                ccxt_config = get_ccxt_config_from_env(config.additional_params.get('exchange'))
                config.credentials = ccxt_config
            except Exception as e:
                logger.error(f"Failed to get CCXT credentials: {e}")
                raise ValueError(f"Failed to configure CCXT: {e}")

        # Create broker instance with appropriate parameters
        if normalized_broker_type == 'alpaca':
            # AlpacaBroker has statistics_manager and position_sizer parameters
            return broker_class(config, portfolio_manager, statistics_manager, position_sizer)
        elif normalized_broker_type in ['ibkr', 'ib_gateway']:
            # IBKR brokers take config, portfolio_manager, and position_sizer
            return broker_class(config, portfolio_manager, position_sizer)
        else:
            # Other brokers have position_sizer parameter
            return broker_class(config, portfolio_manager, position_sizer)

    @classmethod
    def get_supported_brokers(cls) -> list[str]:
        """
        Get list of supported broker types

        Returns:
            List of canonical broker type names (deduplicated)
        """
        cls._initialize_brokers()
        # Deduplicate via canonical form so aliases (IBKR, interactive-brokers …)
        # only appear once.  Sorting gives deterministic order for tests.
        canonical = {cls._normalize_broker_type(name) for name in cls._brokers}
        return sorted(canonical)

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
            
            # Use the same logic as create_broker for constructor arguments
            normalized_broker_type = cls._normalize_broker_type(broker_type)
            if normalized_broker_type == 'alpaca':
                temp_broker = broker_class(temp_config, None, None, None)
            elif normalized_broker_type in ['ibkr', 'ib_gateway']:
                temp_broker = broker_class(temp_config, None, None)
            else:
                temp_broker = broker_class(temp_config, None, None)
            
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
