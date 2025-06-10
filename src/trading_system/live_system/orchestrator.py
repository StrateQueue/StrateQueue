"""
Live Trading System Orchestrator

Main orchestrator that coordinates all components of the live trading system:
- Initializes and manages all subsystems
- Coordinates the main trading loop
- Handles system lifecycle
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from ..utils.config import load_config
from ..core.signal_extractor import SignalType
from ..core.strategy_loader import StrategyLoader
from ..multi_strategy import MultiStrategyRunner
from ..core.granularity import parse_granularity
from .data_manager import DataManager
from .trading_processor import TradingProcessor
from .display_manager import DisplayManager
from ..statistics import StatisticsManager

logger = logging.getLogger(__name__)

class LiveTradingSystem:
    """Main live trading system orchestrator"""
    
    def __init__(self, strategy_path: Optional[str] = None, symbols: List[str] = None, 
                 data_source: str = "demo", granularity: str = "1m", lookback_override: Optional[int] = None,
                 enable_trading: bool = False, multi_strategy_config: Optional[str] = None,
                 broker_type: Optional[str] = None, paper_trading: bool = True):
        """
        Initialize live trading system
        
        Args:
            strategy_path: Path to single strategy file (single-strategy mode)
            symbols: List of symbols to trade
            data_source: Data source ("demo", "polygon", "coinmarketcap") 
            granularity: Data granularity (e.g., "1m", "5m", "1h")
            lookback_override: Override calculated lookback period
            enable_trading: Enable actual trading execution
            multi_strategy_config: Path to multi-strategy config file (multi-strategy mode)
            broker_type: Broker type to use for trading (auto-detected if None)
            paper_trading: Use paper trading (True) or live trading (False)
        """
        self.symbols = symbols or []
        self.data_source = data_source
        self.granularity = granularity
        self.lookback_override = lookback_override
        self.enable_trading = enable_trading
        self.broker_type = broker_type
        self.paper_trading = paper_trading
        
        # Determine mode
        self.is_multi_strategy = multi_strategy_config is not None
        
        # Load configuration
        self.data_config, self.trading_config = load_config()
        
        # Initialize statistics manager
        self.statistics_manager = StatisticsManager()
        
        # Initialize strategy components
        self._initialize_strategies(strategy_path, multi_strategy_config)
        
        # Initialize modular components
        self.data_manager = DataManager(
            self.symbols, 
            self.data_source, 
            self.granularity, 
            self.lookback_period
        )
        
        self.trading_processor = TradingProcessor(
            self.symbols,
            self.lookback_period,
            self.is_multi_strategy,
            getattr(self, 'strategy_class', None),
            getattr(self, 'multi_strategy_runner', None)
        )
        
        self.display_manager = DisplayManager(self.is_multi_strategy, self.statistics_manager)
        
        # Initialize data ingestion
        self.data_ingester = self.data_manager.setup_data_ingestion()
        
        # Initialize broker executor if trading is enabled
        self.broker_executor = self._initialize_trading()
        
    def _initialize_strategies(self, strategy_path: str, multi_strategy_config: str):
        """Initialize strategy components based on mode"""
        if self.is_multi_strategy:
            # Multi-strategy mode
            logger.info("Initializing in MULTI-STRATEGY mode")
            self.multi_strategy_runner = MultiStrategyRunner(
                multi_strategy_config, 
                self.symbols,
                self.lookback_override,
                self.statistics_manager
            )
            self.multi_strategy_runner.initialize_strategies()
            
            # Use multi-strategy maximum lookback
            self.lookback_period = self.multi_strategy_runner.get_max_lookback_period()
            
            # Single strategy attributes set to None
            self.strategy_path = None
            self.strategy_class = None
            
        else:
            # Single strategy mode
            if not strategy_path:
                raise ValueError("strategy_path required for single-strategy mode")
                
            logger.info("Initializing in SINGLE-STRATEGY mode")
            self.strategy_path = strategy_path
            
            # Load and convert strategy
            original_strategy = StrategyLoader.load_strategy_from_file(strategy_path)
            self.strategy_class = StrategyLoader.convert_to_signal_strategy(original_strategy)
            
            # Calculate lookback
            self.lookback_period = (self.lookback_override or 
                                   StrategyLoader.calculate_lookback_period(original_strategy, strategy_path))
            
            # Multi-strategy attributes set to None
            self.multi_strategy_runner = None
    
    def _initialize_trading(self):
        """Initialize broker trading executor if enabled"""
        if not self.enable_trading:
            return None
            
        try:
            # Get portfolio manager for multi-strategy mode
            portfolio_manager = None
            if self.is_multi_strategy:
                portfolio_manager = self.multi_strategy_runner.portfolio_manager
            
            # Try new broker factory first
            try:
                from ..brokers import auto_create_broker, BrokerFactory
                from ..brokers.base import BrokerConfig
                
                if self.broker_type:
                    # Use specified broker
                    config = BrokerConfig(
                        broker_type=self.broker_type,
                        paper_trading=self.paper_trading
                    )
                    broker_executor = BrokerFactory.create_broker(self.broker_type, config=config, portfolio_manager=portfolio_manager, statistics_manager=self.statistics_manager)
                    trading_mode = "paper" if self.paper_trading else "live"
                    logger.info(f"✅ Using specified broker: {self.broker_type} ({trading_mode} trading)")
                else:
                    # Auto-detect broker
                    broker_executor = auto_create_broker(portfolio_manager=portfolio_manager, statistics_manager=self.statistics_manager)
                    # Update the auto-created broker's paper trading setting
                    broker_executor.config.paper_trading = self.paper_trading
                    trading_mode = "paper" if self.paper_trading else "live"
                    logger.info(f"✅ Auto-detected broker: {broker_executor.config.broker_type} ({trading_mode} trading)")
                
                # Connect to broker
                if broker_executor.connect():
                    mode_info = "multi-strategy" if self.is_multi_strategy else "single-strategy"
                    trading_mode = "paper" if self.paper_trading else "live"
                    logger.info(f"✅ Broker trading enabled with {mode_info} portfolio management ({trading_mode} mode)")
                    return broker_executor
                else:
                    logger.error("Failed to connect to broker")
                    return None
                
            except ImportError:
                # Broker factory not available
                logger.error("Broker factory not available - no broker dependencies installed")
                logger.warning("Install broker dependencies with: pip install stratequeue[trading]")
                return None
                
        except Exception as e:
            logger.error(f"Failed to initialize trading executor: {e}")
            logger.warning("Trading disabled - running in signal-only mode")
            self.enable_trading = False
            return None
    
    async def run_live_system(self, duration_minutes: int = 60):
        """
        Run the live trading system
        
        Args:
            duration_minutes: How long to run the system
        """
        logger.info(f"Starting live trading system for {duration_minutes} minutes")
        
        # Log system configuration
        strategy_info = self.trading_processor.get_strategy_info()
        logger.info(f"Strategy: {strategy_info}")
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Data Source: {self.data_source}")
        logger.info(f"Granularity: {self.granularity}")
        logger.info(f"Lookback Period: {self.lookback_period} bars")
        
        # Display startup banner
        self.display_manager.display_startup_banner(
            self.symbols, 
            self.data_source, 
            self.granularity, 
            self.lookback_period,
            duration_minutes, 
            strategy_info,
            self.enable_trading, 
            self.broker_executor
        )
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        # Initialize historical data
        await self.data_manager.initialize_historical_data()
        
        # Calculate cycle interval based on granularity
        try:
            granularity_obj = parse_granularity(self.granularity)
            cycle_interval = granularity_obj.to_seconds()
            logger.info(f"Trading cycle interval set to {cycle_interval} seconds based on granularity {self.granularity}")
        except Exception as e:
            logger.warning(f"Could not parse granularity {self.granularity}: {e}. Using default 5-second interval")
            cycle_interval = 5
        
        # Main trading loop
        signal_count = 0
        try:
            while datetime.now() < end_time:
                # Process trading cycle
                signals = await self.trading_processor.process_trading_cycle(
                    self.data_manager, 
                    self.broker_executor
                )
                
                # Display and log signals
                if signals:
                    signal_count += 1
                    self.display_manager.display_signals_summary(signals, signal_count)
                    
                    # Execute trades if enabled, otherwise record hypothetical trades
                    if self.enable_trading and self.broker_executor:
                        await self._execute_signals(signals)
                    else:
                        # Record hypothetical trades for statistics tracking in signals-only mode
                        self._record_hypothetical_signals(signals)
                
                # Wait before next cycle (respecting granularity)
                await asyncio.sleep(cycle_interval)
                
        except KeyboardInterrupt:
            logger.info("Received interrupt signal - shutting down gracefully...")
        except Exception as e:
            logger.error(f"Error in main trading loop: {e}")
        finally:
            # Display final summary
            active_signals = self.trading_processor.get_active_signals()
            self.display_manager.display_session_summary(active_signals, self.broker_executor)
    
    def _record_hypothetical_signals(self, signals):
        """Record hypothetical trades from signals for statistics tracking"""
        if self.is_multi_strategy:
            # Multi-strategy signals: Dict[symbol, Dict[strategy_id, signal]]
            for symbol, strategy_signals in signals.items():
                if isinstance(strategy_signals, dict):
                    for strategy_id, signal in strategy_signals.items():
                        self.statistics_manager.record_hypothetical_trade(signal, symbol)
        else:
            # Single strategy signals: Dict[symbol, signal]
            for symbol, signal in signals.items():
                self.statistics_manager.record_hypothetical_trade(signal, symbol)

    async def _execute_signals(self, signals):
        """Execute trading signals via broker"""
        if self.is_multi_strategy:
            # Multi-strategy signals: Dict[symbol, Dict[strategy_id, signal]]
            for symbol, strategy_signals in signals.items():
                if isinstance(strategy_signals, dict):
                    for strategy_id, signal in strategy_signals.items():
                        if signal.signal != SignalType.HOLD:
                            # Handle both new broker interface and legacy Alpaca executor
                            if hasattr(self.broker_executor, 'execute_signal'):
                                result = self.broker_executor.execute_signal(symbol, signal)
                                if hasattr(result, 'success'):  # New broker interface returns OrderResult
                                    success = result.success
                                else:  # Legacy interface returns boolean
                                    success = result
                            else:
                                success = False
                            
                            if success:
                                logger.info(f"✅ Executed {signal.signal.value} for {symbol} [{strategy_id}]")
                            else:
                                logger.warning(f"❌ Failed to execute {signal.signal.value} for {symbol} [{strategy_id}]")
        else:
            # Single strategy signals: Dict[symbol, signal]
            for symbol, signal in signals.items():
                if signal.signal != SignalType.HOLD:
                    # Handle both new broker interface and legacy Alpaca executor
                    if hasattr(self.broker_executor, 'execute_signal'):
                        result = self.broker_executor.execute_signal(symbol, signal)
                        if hasattr(result, 'success'):  # New broker interface returns OrderResult
                            success = result.success
                        else:  # Legacy interface returns boolean
                            success = result
                    else:
                        success = False
                    
                    if success:
                        logger.info(f"✅ Executed {signal.signal.value} for {symbol}")
                    else:
                        logger.warning(f"❌ Failed to execute {signal.signal.value} for {symbol}")
    
    def get_system_status(self) -> dict:
        """Get current system status"""
        return {
            'mode': 'multi-strategy' if self.is_multi_strategy else 'single-strategy',
            'symbols': self.symbols,
            'data_source': self.data_source,
            'granularity': self.granularity,
            'lookback_period': self.lookback_period,
            'trading_enabled': self.enable_trading,
            'trade_count': self.display_manager.get_trade_count(),
            'active_signals': self.trading_processor.get_active_signals()
        } 