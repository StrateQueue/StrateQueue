#!/usr/bin/env python3

"""
Live Trading System Main Entry Point

This script orchestrates the entire live trading infrastructure:
1. Load strategy scripts dynamically
2. Calculate required lookback periods
3. Connect to data sources (real or demo)
4. Generate and display live trading signals
5. Execute trades (future feature)

Usage:
    python3 main.py --strategy sma.py --symbols AAPL,MSFT --data-source demo
    python3 main.py --strategy sma.py --symbols AAPL --data-source polygon --lookback 50
"""

import argparse
import asyncio
import importlib.util
import inspect
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Type, Any
import pandas as pd
import json

from data_ingestion import setup_data_ingestion, PolygonDataIngestion, TestDataIngestion
from signal_extractor import LiveSignalExtractor, SignalExtractorStrategy, TradingSignal, SignalType
from config import load_config, DataConfig, TradingConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('trading_system.log')
    ]
)
logger = logging.getLogger(__name__)

class StrategyLoader:
    """Dynamically load and analyze trading strategies"""
    
    @staticmethod
    def load_strategy_from_file(strategy_path: str) -> Type[SignalExtractorStrategy]:
        """
        Load a strategy class from a Python file
        
        Args:
            strategy_path: Path to the strategy file
            
        Returns:
            Strategy class that inherits from SignalExtractorStrategy
        """
        try:
            if not os.path.exists(strategy_path):
                raise FileNotFoundError(f"Strategy file not found: {strategy_path}")
            
            # Load the module
            spec = importlib.util.spec_from_file_location("strategy_module", strategy_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find strategy classes
            strategy_classes = []
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    hasattr(obj, 'init') and hasattr(obj, 'next') and 
                    name != 'Strategy' and name != 'SignalExtractorStrategy'):
                    strategy_classes.append(obj)
            
            if not strategy_classes:
                raise ValueError(f"No valid strategy class found in {strategy_path}")
            
            if len(strategy_classes) > 1:
                logger.warning(f"Multiple strategy classes found, using first one: {strategy_classes[0].__name__}")
            
            strategy_class = strategy_classes[0]
            logger.info(f"Loaded strategy: {strategy_class.__name__} from {strategy_path}")
            
            return strategy_class
            
        except Exception as e:
            logger.error(f"Error loading strategy from {strategy_path}: {e}")
            raise

    @staticmethod
    def convert_to_signal_strategy(original_strategy: Type) -> Type[SignalExtractorStrategy]:
        """
        Convert a regular backtesting.py strategy to a signal-extracting strategy
        
        Args:
            original_strategy: Original strategy class
            
        Returns:
            Modified strategy class that generates signals instead of trades
        """
        
        class ConvertedSignalStrategy(SignalExtractorStrategy):
            """Dynamically converted signal strategy"""
            
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                # Copy only safe class attributes from original strategy (parameters, not internal state)
                for attr_name in dir(original_strategy):
                    if (not attr_name.startswith('_') and 
                        not callable(getattr(original_strategy, attr_name)) and
                        not hasattr(self, attr_name) and  # Don't override existing attributes
                        attr_name not in ['closed_trades', 'trades', 'data', 'broker', 'position']):  # Skip backtesting internals
                        try:
                            setattr(self, attr_name, getattr(original_strategy, attr_name))
                        except (AttributeError, TypeError):
                            # Skip attributes that can't be set
                            pass
            
            def init(self):
                # Call original init method
                if hasattr(original_strategy, 'init'):
                    original_init = getattr(original_strategy, 'init')
                    original_init(self)
            
            def next(self):
                # Store original position methods
                original_buy = getattr(self, 'buy', None)
                original_sell = getattr(self, 'sell', None)
                original_close = getattr(self.position, 'close', None) if hasattr(self, 'position') else None
                
                buy_called = False
                sell_called = False
                close_called = False
                
                # Create mock methods that track calls
                def mock_buy(*args, **kwargs):
                    nonlocal buy_called
                    buy_called = True
                    return None
                
                def mock_sell(*args, **kwargs):
                    nonlocal sell_called  
                    sell_called = True
                    return None
                
                def mock_close(*args, **kwargs):
                    nonlocal close_called
                    close_called = True
                    return None
                
                # Replace methods temporarily
                self.buy = mock_buy
                self.sell = mock_sell
                if hasattr(self, 'position'):
                    self.position.close = mock_close
                
                # Call original next method
                if hasattr(original_strategy, 'next'):
                    original_next = getattr(original_strategy, 'next')
                    original_next(self)
                
                # Determine signal based on what was called
                if buy_called:
                    self.set_signal(SignalType.BUY, confidence=0.8)
                elif sell_called:
                    self.set_signal(SignalType.SELL, confidence=0.8)
                elif close_called:
                    self.set_signal(SignalType.CLOSE, confidence=0.6)
                else:
                    self.set_signal(SignalType.HOLD, confidence=0.1)
                
                # Store current indicators (try to extract common ones)
                self.indicators_values = {}
                if hasattr(self, 'data'):
                    self.indicators_values['price'] = self.data.Close[-1]
                    
                # Try to extract SMA values
                for attr_name in dir(self):
                    if 'sma' in attr_name.lower() and not attr_name.startswith('_'):
                        try:
                            sma_values = getattr(self, attr_name)
                            if hasattr(sma_values, '__getitem__'):
                                self.indicators_values[attr_name] = sma_values[-1]
                        except:
                            pass
                
                # Restore original methods
                if original_buy:
                    self.buy = original_buy
                if original_sell:
                    self.sell = original_sell
                if original_close and hasattr(self, 'position'):
                    self.position.close = original_close
        
        # Copy class attributes
        for attr_name in dir(original_strategy):
            if not attr_name.startswith('_') and not callable(getattr(original_strategy, attr_name)):
                setattr(ConvertedSignalStrategy, attr_name, getattr(original_strategy, attr_name))
        
        ConvertedSignalStrategy.__name__ = f"Signal{original_strategy.__name__}"
        return ConvertedSignalStrategy

    @staticmethod
    def calculate_lookback_period(strategy_class: Type, default_lookback: int = 100) -> int:
        """
        Calculate required lookback period for a strategy
        
        Args:
            strategy_class: Strategy class to analyze
            default_lookback: Default lookback if calculation fails
            
        Returns:
            Required lookback period in number of bars
        """
        try:
            # Look for common indicator periods in class attributes
            lookback_indicators = []
            
            for attr_name in dir(strategy_class):
                if not attr_name.startswith('_'):
                    attr_value = getattr(strategy_class, attr_name)
                    if isinstance(attr_value, int) and 1 <= attr_value <= 1000:
                        # Likely a period parameter
                        if any(keyword in attr_name.lower() for keyword in 
                              ['n', 'period', 'window', 'length', 'span']):
                            lookback_indicators.append(attr_value)
            
            if lookback_indicators:
                # Use maximum period + buffer
                calculated_lookback = max(lookback_indicators) * 2 + 50
                logger.info(f"Calculated lookback period: {calculated_lookback} bars")
                return calculated_lookback
            else:
                logger.info(f"Using default lookback period: {default_lookback} bars")
                return default_lookback
                
        except Exception as e:
            logger.warning(f"Error calculating lookback period: {e}, using default: {default_lookback}")
            return default_lookback

class LiveTradingSystem:
    """Main live trading system orchestrator"""
    
    def __init__(self, strategy_path: str, symbols: List[str], 
                 data_source: str = "demo", lookback_override: Optional[int] = None):
        """
        Initialize live trading system
        
        Args:
            strategy_path: Path to strategy file
            symbols: List of symbols to trade
            data_source: Data source ("demo" or "polygon") 
            lookback_override: Override calculated lookback period
        """
        self.strategy_path = strategy_path
        self.symbols = symbols
        self.data_source = data_source
        self.lookback_override = lookback_override
        
        # Load configuration
        self.data_config, self.trading_config = load_config()
        
        # Load and convert strategy
        original_strategy = StrategyLoader.load_strategy_from_file(strategy_path)
        self.strategy_class = StrategyLoader.convert_to_signal_strategy(original_strategy)
        
        # Calculate lookback
        self.lookback_period = (lookback_override or 
                               StrategyLoader.calculate_lookback_period(original_strategy))
        
        # Initialize data ingestion
        self.data_ingester = self._setup_data_ingestion()
        
        # For live data, start real-time feed and subscribe to symbols
        if self.data_source != "demo":
            for symbol in self.symbols:
                self.data_ingester.subscribe_to_symbol(symbol)
            # Start WebSocket in background (this would need threading in production)
            # For now, we'll rely on manual real-time data updates
        
        # Initialize signal extractors for each symbol
        self.signal_extractors = {}
        for symbol in symbols:
            self.signal_extractors[symbol] = LiveSignalExtractor(self.strategy_class)
        
        # Track active signals
        self.active_signals = {}
        self.trade_log = []
        
        # Track cumulative data for proper live simulation
        self.cumulative_data = {}
        
    def _setup_data_ingestion(self):
        """Setup data ingestion based on data source"""
        if self.data_source == "demo":
            # Use test data with realistic base prices
            base_prices = {symbol: 100.0 + hash(symbol) % 200 for symbol in self.symbols}
            return setup_data_ingestion(use_test_data=True, base_prices=base_prices)
        else:
            return setup_data_ingestion(use_test_data=False)
    
    async def run_live_system(self, duration_minutes: int = 60):
        """
        Run the live trading system
        
        Args:
            duration_minutes: How long to run the system
        """
        logger.info(f"Starting live trading system for {duration_minutes} minutes")
        logger.info(f"Strategy: {self.strategy_class.__name__}")
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Data Source: {self.data_source}")
        logger.info(f"Lookback Period: {self.lookback_period} bars")
        
        print(f"\n{'='*60}")
        print(f"🚀 LIVE TRADING SYSTEM STARTED")
        print(f"{'='*60}")
        print(f"Strategy: {self.strategy_class.__name__}")
        print(f"Symbols: {', '.join(self.symbols)}")
        print(f"Data Source: {self.data_source}")
        print(f"Lookback: {self.lookback_period} bars")
        print(f"Duration: {duration_minutes} minutes")
        print(f"{'='*60}\n")
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        try:
            # Get initial historical data
            await self._initialize_historical_data()
            
            # Main trading loop
            signal_count = 0
            while datetime.now() < end_time:
                # Get latest data and generate signals
                new_signals = await self._process_trading_cycle()
                
                for symbol, signal in new_signals.items():
                    if signal.signal != SignalType.HOLD:
                        signal_count += 1
                        self._display_signal(symbol, signal, signal_count)
                        self._log_trade(symbol, signal)
                
                # Wait before next cycle (simulate real-time processing)
                await asyncio.sleep(5)  # 5 second intervals
                
        except KeyboardInterrupt:
            logger.info("System stopped by user")
        except Exception as e:
            logger.error(f"System error: {e}")
        finally:
            print(f"\n{'='*60}")
            print(f"🛑 SYSTEM STOPPED")
            print(f"{'='*60}")
            self._display_summary()
    
    async def _initialize_historical_data(self):
        """Initialize historical data for all symbols"""
        logger.info("Fetching initial historical data...")
        
        for symbol in self.symbols:
            try:
                if self.data_source == "demo":
                    # For demo, generate initial historical data
                    historical_data = await self.data_ingester.fetch_historical_data(
                        symbol, days_back=max(5, self.lookback_period // 100)
                    )
                else:
                    # For real data, get actual historical data
                    historical_data = await self.data_ingester.fetch_historical_data(
                        symbol, days_back=max(5, self.lookback_period // 100)
                    )
                
                # Store the initial cumulative data
                self.cumulative_data[symbol] = historical_data.copy()
                
                logger.info(f"Loaded {len(historical_data)} initial historical bars for {symbol}")
                
            except Exception as e:
                logger.error(f"Error loading historical data for {symbol}: {e}")
    
    async def _process_trading_cycle(self) -> Dict[str, TradingSignal]:
        """Process one trading cycle for all symbols"""
        signals = {}
        
        for symbol in self.symbols:
            try:
                if self.data_source == "demo":
                    # Append one new bar to cumulative data (simulating live environment)
                    updated_data = self.data_ingester.append_new_bar(symbol)
                    if len(updated_data) > 0:
                        self.cumulative_data[symbol] = updated_data
                else:
                    # For real data, append current real-time bar to cumulative data
                    updated_data = self.data_ingester.append_current_bar(symbol)
                    if len(updated_data) > 0:
                        self.cumulative_data[symbol] = updated_data
                
                # Use cumulative data for signal extraction
                current_data = self.cumulative_data.get(symbol, pd.DataFrame())
                
                if len(current_data) >= self.lookback_period:
                    # Extract signal from cumulative data
                    signal = self.signal_extractors[symbol].extract_signal(current_data)
                    signals[symbol] = signal
                    self.active_signals[symbol] = signal
                    
                    # Log the data growth
                    logger.debug(f"Processing {symbol}: {len(current_data)} total bars, "
                               f"latest price: ${current_data['Close'].iloc[-1]:.2f}")
                    
                else:
                    logger.warning(f"Insufficient data for {symbol}: {len(current_data)} < {self.lookback_period}")
                    
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
        
        return signals
    
    def _display_signal(self, symbol: str, signal: TradingSignal, count: int):
        """Display a trading signal"""
        timestamp_str = signal.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        signal_emoji = {"BUY": "📈", "SELL": "📉", "CLOSE": "🔄", "HOLD": "⏸️"}
        
        print(f"\n🎯 SIGNAL #{count} - {timestamp_str}")
        print(f"Symbol: {symbol}")
        print(f"Action: {signal_emoji.get(signal.signal.value, '❓')} {signal.signal.value}")
        print(f"Price: ${signal.price:.2f}")
        print(f"Confidence: {signal.confidence:.1%}")
        
        if signal.indicators:
            print("Indicators:")
            for indicator, value in signal.indicators.items():
                if isinstance(value, (int, float)):
                    print(f"  • {indicator}: {value:.2f}")
                else:
                    print(f"  • {indicator}: {value}")
    
    def _log_trade(self, symbol: str, signal: TradingSignal):
        """Log trade for later analysis"""
        self.trade_log.append({
            'timestamp': signal.timestamp,
            'symbol': symbol,
            'signal': signal.signal.value,
            'price': signal.price,
            'confidence': signal.confidence,
            'indicators': signal.indicators
        })
    
    def _display_summary(self):
        """Display trading session summary"""
        print(f"Total Signals Generated: {len(self.trade_log)}")
        
        if self.trade_log:
            signal_counts = {}
            for trade in self.trade_log:
                signal_type = trade['signal']
                signal_counts[signal_type] = signal_counts.get(signal_type, 0) + 1
            
            print("\nSignal Breakdown:")
            for signal_type, count in signal_counts.items():
                print(f"  • {signal_type}: {count}")
            
            print(f"\nLatest Signals:")
            for symbol, signal in self.active_signals.items():
                print(f"  • {symbol}: {signal.signal.value} @ ${signal.price:.2f}")
        
        print(f"\nTrade log saved to trading_system.log")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Live Trading System')
    parser.add_argument('--strategy', required=True, help='Path to strategy file (e.g., sma.py)')
    parser.add_argument('--symbols', default='AAPL', help='Comma-separated list of symbols (e.g., AAPL,MSFT)')
    parser.add_argument('--data-source', choices=['demo', 'polygon'], default='demo', 
                       help='Data source to use')
    parser.add_argument('--lookback', type=int, help='Override calculated lookback period')
    parser.add_argument('--duration', type=int, default=60, help='Duration to run in minutes')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Parse symbols
    symbols = [s.strip().upper() for s in args.symbols.split(',')]
    
    # Create and run system
    try:
        system = LiveTradingSystem(
            strategy_path=args.strategy,
            symbols=symbols,
            data_source=args.data_source,
            lookback_override=args.lookback
        )
        
        # Run the system
        asyncio.run(system.run_live_system(duration_minutes=args.duration))
        
    except Exception as e:
        logger.error(f"Failed to start system: {e}")
        print(f"\n❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 