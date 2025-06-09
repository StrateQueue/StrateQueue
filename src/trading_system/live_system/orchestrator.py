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

from ..config import load_config
from ..alpaca import create_alpaca_executor_from_env
from ..signal_extractor import SignalType
from ..strategy_loader import StrategyLoader
from ..multi_strategy import MultiStrategyRunner
from ..granularity import parse_granularity
from .data_manager import DataManager
from .trading_processor import TradingProcessor
from .display_manager import DisplayManager

logger = logging.getLogger(__name__)

class LiveTradingSystem:
    """Main live trading system orchestrator"""
    
    def __init__(self, strategy_path: Optional[str] = None, symbols: List[str] = None, 
                 data_source: str = "demo", granularity: str = "1m", lookback_override: Optional[int] = None,
                 enable_trading: bool = False, multi_strategy_config: Optional[str] = None):
        """
        Initialize live trading system
        
        Args:
            strategy_path: Path to single strategy file (single-strategy mode)
            symbols: List of symbols to trade
            data_source: Data source ("demo", "polygon", "coinmarketcap") 
            granularity: Data granularity (e.g., "1m", "5m", "1h")
            lookback_override: Override calculated lookback period
            enable_trading: Enable actual trading execution via Alpaca
            multi_strategy_config: Path to multi-strategy config file (multi-strategy mode)
        """
        self.symbols = symbols or []
        self.data_source = data_source
        self.granularity = granularity
        self.lookback_override = lookback_override
        self.enable_trading = enable_trading
        
        # Determine mode
        self.is_multi_strategy = multi_strategy_config is not None
        
        # Load configuration
        self.data_config, self.trading_config = load_config()
        
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
        
        self.display_manager = DisplayManager(self.is_multi_strategy)
        
        # Initialize data ingestion
        self.data_ingester = self.data_manager.setup_data_ingestion()
        
        # Initialize Alpaca executor if trading is enabled
        self.alpaca_executor = self._initialize_trading()
        
    def _initialize_strategies(self, strategy_path: str, multi_strategy_config: str):
        """Initialize strategy components based on mode"""
        if self.is_multi_strategy:
            # Multi-strategy mode
            logger.info("Initializing in MULTI-STRATEGY mode")
            self.multi_strategy_runner = MultiStrategyRunner(
                multi_strategy_config, 
                self.symbols,
                self.lookback_override
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
        """Initialize Alpaca trading executor if enabled"""
        if not self.enable_trading:
            return None
            
        try:
            # Get portfolio manager for multi-strategy mode
            portfolio_manager = None
            if self.is_multi_strategy:
                portfolio_manager = self.multi_strategy_runner.portfolio_manager
            
            alpaca_executor = create_alpaca_executor_from_env(portfolio_manager)
            
            mode_info = "multi-strategy" if self.is_multi_strategy else "single-strategy"
            logger.info(f"✅ Alpaca trading enabled with {mode_info} portfolio management")
            
            return alpaca_executor
            
        except Exception as e:
            logger.error(f"Failed to initialize Alpaca executor: {e}")
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
            self.alpaca_executor
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
                    self.alpaca_executor
                )
                
                # Display and log signals
                if signals:
                    signal_count += 1
                    self.display_manager.display_signals_summary(signals, signal_count)
                    
                    # Execute trades if enabled
                    if self.enable_trading and self.alpaca_executor:
                        await self._execute_signals(signals)
                
                # Wait before next cycle (respecting granularity)
                await asyncio.sleep(cycle_interval)
                
        except KeyboardInterrupt:
            logger.info("Received interrupt signal - shutting down gracefully...")
        except Exception as e:
            logger.error(f"Error in main trading loop: {e}")
        finally:
            # Display final summary
            active_signals = self.trading_processor.get_active_signals()
            self.display_manager.display_session_summary(active_signals, self.alpaca_executor)
    
    async def _execute_signals(self, signals):
        """Execute trading signals via Alpaca"""
        if self.is_multi_strategy:
            # Multi-strategy signals: Dict[symbol, Dict[strategy_id, signal]]
            for symbol, strategy_signals in signals.items():
                if isinstance(strategy_signals, dict):
                    for strategy_id, signal in strategy_signals.items():
                        if signal.signal != SignalType.HOLD:
                            success = self.alpaca_executor.execute_signal(symbol, signal)
                            if success:
                                logger.info(f"✅ Executed {signal.signal.value} for {symbol} [{strategy_id}]")
                            else:
                                logger.warning(f"❌ Failed to execute {signal.signal.value} for {symbol} [{strategy_id}]")
        else:
            # Single strategy signals: Dict[symbol, signal]
            for symbol, signal in signals.items():
                if signal.signal != SignalType.HOLD:
                    success = self.alpaca_executor.execute_signal(symbol, signal)
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