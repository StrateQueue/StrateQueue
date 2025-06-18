"""
Engine Factory and Detection

Provides factory methods for creating trading engines and detecting which engine
a strategy file is designed for.
"""

import logging
from typing import Dict, List, Optional
from .engine_base import TradingEngine
from .engine_helpers import analyze_strategy_file, detect_engine_from_analysis

logger = logging.getLogger(__name__)


class EngineFactory:
    """Factory for creating trading engine instances"""
    
    _engines: Dict[str, type] = {}  # Only engines with available dependencies
    _all_known_engines: Dict[str, type] = {}  # All engines, regardless of availability
    _unavailable_engines: Dict[str, str] = {}  # Engines missing dependencies with reasons
    _initialized = False
    
    @classmethod
    def _initialize_engines(cls):
        """Initialize available engines (lazy loading)"""
        if cls._initialized:
            return
            
        # backtesting.py engine
        try:
            from .backtesting_engine import BacktestingEngine, is_available as bt_available
            cls._all_known_engines['backtesting'] = BacktestingEngine
            
            if bt_available():
                cls._engines['backtesting'] = BacktestingEngine
                logger.debug("Registered backtesting engine")
            else:
                cls._unavailable_engines['backtesting'] = "backtesting.py not installed. Run: pip install stratequeue[backtesting]"
                logger.debug("backtesting.py dependencies not available - engine skipped")
        except ImportError as e:
            logger.debug(f"Could not import backtesting engine module: {e}")
        
        # VectorBT engine
        try:
            from .vectorbt_engine import VectorBTEngine, is_available as vbt_available
            cls._all_known_engines['vectorbt'] = VectorBTEngine
            
            if vbt_available():
                cls._engines['vectorbt'] = VectorBTEngine
                logger.debug("Registered VectorBT engine")
            else:
                cls._unavailable_engines['vectorbt'] = "VectorBT not installed. Run: pip install stratequeue[vectorbt]"
                logger.debug("VectorBT dependencies not available - engine skipped")
        except ImportError as e:
            logger.debug(f"Could not import VectorBT engine module: {e}")
        
        # Future engines can be added here
        try:
            # from .zipline_engine import ZiplineEngine, is_available as zipline_available
            # cls._all_known_engines['zipline'] = ZiplineEngine
            # if zipline_available():
            #     cls._engines['zipline'] = ZiplineEngine
            #     logger.debug("Registered zipline engine")
            # else:
            #     cls._unavailable_engines['zipline'] = "Zipline not installed. Run: pip install stratequeue[zipline]"
            pass
        except ImportError:
            # Zipline engine not implemented yet
            pass
            
        cls._initialized = True
    
    @classmethod
    def create_engine(cls, engine_type: str) -> TradingEngine:
        """
        Create a trading engine instance
        
        Args:
            engine_type: Type of engine ('backtesting', 'zipline', etc.)
            
        Returns:
            TradingEngine instance
            
        Raises:
            ValueError: If engine type is not supported
        """
        cls._initialize_engines()
        
        if engine_type not in cls._engines:
            available = list(cls._engines.keys())
            raise ValueError(f"Unsupported engine type '{engine_type}'. Available: {available}")
        
        engine_class = cls._engines[engine_type]
        logger.info(f"Creating {engine_type} engine instance")
        
        return engine_class()
    
    @classmethod
    def get_supported_engines(cls) -> List[str]:
        """
        Get list of supported engine types (only engines with available dependencies)
        
        Returns:
            List of engine type names that can be instantiated
        """
        cls._initialize_engines()
        return list(cls._engines.keys())
    
    @classmethod
    def get_all_known_engines(cls) -> List[str]:
        """
        Get list of all known engine types (regardless of whether dependencies are available)
        
        Returns:
            List of all engine type names that StrateQueue knows about
        """
        cls._initialize_engines()
        return list(cls._all_known_engines.keys())
    
    @classmethod
    def get_unavailable_engines(cls) -> Dict[str, str]:
        """
        Get information about unavailable engines and why they're unavailable
        
        Returns:
            Dictionary mapping engine names to reason they're unavailable
        """
        cls._initialize_engines()
        return cls._unavailable_engines.copy()
    
    @classmethod
    def is_engine_supported(cls, engine_type: str) -> bool:
        """
        Check if an engine type is supported (has available dependencies)
        
        Args:
            engine_type: Engine type to check
            
        Returns:
            True if engine is supported and can be instantiated
        """
        cls._initialize_engines()
        return engine_type in cls._engines
    
    @classmethod
    def is_engine_known(cls, engine_type: str) -> bool:
        """
        Check if an engine type is known (regardless of dependency availability)
        
        Args:
            engine_type: Engine type to check
            
        Returns:
            True if engine is known to StrateQueue
        """
        cls._initialize_engines()
        return engine_type in cls._all_known_engines


def detect_engine_type(strategy_path: str) -> str:
    """
    Detect which trading engine a strategy file is designed for
    
    Args:
        strategy_path: Path to the strategy file
        
    Returns:
        Engine type name ('backtesting', 'zipline', 'unknown')
        
    Raises:
        FileNotFoundError: If strategy file doesn't exist
    """
    logger.debug(f"Detecting engine type for {strategy_path}")
    
    try:
        analysis = analyze_strategy_file(strategy_path)
        engine_type = detect_engine_from_analysis(analysis)
        
        logger.info(f"Detected engine type '{engine_type}' for {strategy_path}")
        
        # Log detected indicators for debugging
        indicators = analysis['engine_indicators']
        if indicators.get('backtesting'):
            logger.debug(f"backtesting.py indicators: {indicators['backtesting']}")
        if indicators.get('zipline'):
            logger.debug(f"Zipline indicators: {indicators['zipline']}")
        if indicators.get('vectorbt'):
            logger.debug(f"VectorBT indicators: {indicators['vectorbt']}")
            
        return engine_type
        
    except Exception as e:
        logger.error(f"Error detecting engine type for {strategy_path}: {e}")
        return 'unknown'


def auto_create_engine(strategy_path: str) -> TradingEngine:
    """
    Automatically detect engine type and create appropriate engine instance
    
    Args:
        strategy_path: Path to the strategy file
        
    Returns:
        TradingEngine instance
        
    Raises:
        ValueError: If engine cannot be detected or created
        FileNotFoundError: If strategy file doesn't exist
    """
    engine_type = detect_engine_type(strategy_path)
    
    if engine_type == 'unknown':
        raise ValueError(f"Could not detect engine type for {strategy_path}")
    
    if not EngineFactory.is_engine_supported(engine_type):
        supported = EngineFactory.get_supported_engines()
        raise ValueError(f"Detected engine '{engine_type}' is not supported. Available: {supported}")
    
    return EngineFactory.create_engine(engine_type)


def get_supported_engines() -> List[str]:
    """
    Get list of supported engine types (only engines with available dependencies)
    
    Returns:
        List of engine type names that can be instantiated
    """
    return EngineFactory.get_supported_engines()


def get_all_known_engines() -> List[str]:
    """
    Get list of all known engine types (regardless of whether dependencies are available)
    
    Returns:
        List of all engine type names that StrateQueue knows about
    """
    return EngineFactory.get_all_known_engines()


def get_unavailable_engines() -> Dict[str, str]:
    """
    Get information about unavailable engines and why they're unavailable
    
    Returns:
        Dictionary mapping engine names to reason they're unavailable
    """
    return EngineFactory.get_unavailable_engines()


def validate_strategy_compatibility(strategy_path: str, engine_type: str = None) -> bool:
    """
    Validate that a strategy file is compatible with an engine
    
    Args:
        strategy_path: Path to the strategy file
        engine_type: Engine type to validate against (auto-detect if None)
        
    Returns:
        True if strategy is compatible
    """
    try:
        if engine_type is None:
            engine_type = detect_engine_type(strategy_path)
        
        if engine_type == 'unknown':
            return False
        
        if not EngineFactory.is_engine_supported(engine_type):
            return False
            
        # Create engine and validate strategy
        engine = EngineFactory.create_engine(engine_type)
        return engine.validate_strategy_file(strategy_path)
        
    except Exception as e:
        logger.error(f"Error validating strategy compatibility: {e}")
        return False 