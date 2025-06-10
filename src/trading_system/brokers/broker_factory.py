"""
Broker Factory and Detection

Provides factory methods for creating trading brokers and detecting which broker
to use based on environment variables or explicit configuration.
"""

import logging
from typing import Dict, List, Optional

from .base import BaseBroker, BrokerConfig, BrokerInfo
from .utils import detect_broker_from_environment, validate_broker_environment, get_broker_config_from_env, get_alpaca_config_from_env

logger = logging.getLogger(__name__)


class BrokerFactory:
    """Factory for creating trading broker instances"""
    
    _brokers: Dict[str, type] = {}
    _initialized = False
    
    @classmethod
    def _initialize_brokers(cls):
        """Initialize available brokers (lazy loading)"""
        if cls._initialized:
            return
            
        try:
            from .alpaca_broker import AlpacaBroker
            cls._brokers['alpaca'] = AlpacaBroker
            logger.debug("Registered Alpaca broker")
        except ImportError as e:
            logger.warning(f"Could not load Alpaca broker: {e}")
        
        # Future brokers can be added here
        try:
            # from .interactive_brokers_broker import InteractiveBrokersBroker
            # cls._brokers['interactive_brokers'] = InteractiveBrokersBroker
            # logger.debug("Registered Interactive Brokers broker")
            pass
        except ImportError:
            # Interactive Brokers broker not implemented yet
            pass
        
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
    def create_broker(cls, broker_type: str, config: Optional[BrokerConfig] = None, 
                     portfolio_manager=None, statistics_manager=None) -> BaseBroker:
        """
        Create a trading broker instance
        
        Args:
            broker_type: Type of broker ('alpaca', 'interactive_brokers', etc.)
            config: Optional broker configuration (will auto-detect from env if None)
            portfolio_manager: Optional portfolio manager for multi-strategy support
            statistics_manager: Optional statistics manager for trade tracking
            
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
        
        # For Alpaca, get credentials appropriate for the trading mode
        if broker_type == 'alpaca' and not config.credentials:
            try:
                from .utils import get_alpaca_config_from_env
                alpaca_config = get_alpaca_config_from_env(config.paper_trading)
                config.credentials = alpaca_config
            except Exception as e:
                logger.error(f"Failed to get Alpaca credentials for {'paper' if config.paper_trading else 'live'} trading: {e}")
                raise ValueError(f"Failed to configure Alpaca for {'paper' if config.paper_trading else 'live'} trading: {e}")
        
        return broker_class(config, portfolio_manager, statistics_manager)
    
    @classmethod
    def get_supported_brokers(cls) -> List[str]:
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
    def get_broker_info(cls, broker_type: str) -> Optional[BrokerInfo]:
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


def auto_create_broker(portfolio_manager=None, statistics_manager=None) -> BaseBroker:
    """
    Automatically detect broker type and create appropriate broker instance
    
    Args:
        portfolio_manager: Optional portfolio manager for multi-strategy support
        statistics_manager: Optional statistics manager for trade tracking
        
    Returns:
        BaseBroker instance
        
    Raises:
        ValueError: If broker cannot be detected or created
    """
    broker_type = detect_broker_type()
    
    if broker_type == 'unknown':
        raise ValueError("Could not detect broker type from environment variables")
    
    if not BrokerFactory.is_broker_supported(broker_type):
        supported = BrokerFactory.get_supported_brokers()
        raise ValueError(f"Detected broker '{broker_type}' is not supported. Available: {supported}")
    
    return BrokerFactory.create_broker(broker_type, portfolio_manager=portfolio_manager, statistics_manager=statistics_manager)


def get_supported_brokers() -> List[str]:
    """
    Get list of supported broker types
    
    Returns:
        List of broker type names
    """
    return BrokerFactory.get_supported_brokers()


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
            
        # Create broker and validate credentials
        broker = BrokerFactory.create_broker(broker_type)
        return broker.validate_credentials()
        
    except Exception as e:
        logger.error(f"Error validating broker credentials: {e}")
        return False


def list_broker_features() -> Dict[str, BrokerInfo]:
    """
    Get information about all supported brokers
    
    Returns:
        Dictionary mapping broker type to BrokerInfo
    """
    supported_brokers = get_supported_brokers()
    broker_features = {}
    
    for broker_type in supported_brokers:
        info = BrokerFactory.get_broker_info(broker_type)
        if info:
            broker_features[broker_type] = info
    
    return broker_features 