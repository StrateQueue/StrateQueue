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

from src.trading_system import setup_data_ingestion, PolygonDataIngestion, CoinMarketCapDataIngestion, TestDataIngestion
from src.trading_system import LiveSignalExtractor, SignalExtractorStrategy, TradingSignal, SignalType
from src.trading_system import load_config, DataConfig, TradingConfig
from src.trading_system import AlpacaExecutor, create_alpaca_executor_from_env

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
                trade_params = {}
                
                # Create mock methods that track calls and parameters
                def mock_buy(*args, **kwargs):
                    nonlocal buy_called, trade_params
                    buy_called = True
                    trade_params = kwargs
                    return None
                
                def mock_sell(*args, **kwargs):
                    nonlocal sell_called, trade_params
                    sell_called = True
                    trade_params = kwargs
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
                signal_size = trade_params.get('size')

                if buy_called:
                    self.set_signal(SignalType.BUY, confidence=0.8, size=signal_size)
                elif sell_called:
                    self.set_signal(SignalType.SELL, confidence=0.8, size=signal_size)
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
    def calculate_lookback_period(strategy_class: Type, strategy_path: str = None, default_lookback: int = 50) -> int:
        """
        Calculate required lookback period for a strategy
        
        Args:
            strategy_class: The strategy class
            strategy_path: Path to the strategy file (for parsing LOOKBACK config)
            default_lookback: Default lookback if none specified
            
        Returns:
            Required lookback period
        """
        
        # First, try to parse LOOKBACK configuration from the strategy file
        if strategy_path:
            try:
                lookback_from_file = StrategyLoader._parse_lookback_from_file(strategy_path)
                if lookback_from_file is not None:
                    logger.info(f"Using LOOKBACK={lookback_from_file} from strategy file")
                    return lookback_from_file
            except Exception as e:
                logger.warning(f"Could not parse LOOKBACK from strategy file: {e}")
        
        # Fallback to automatic detection from class attributes
        try:
            # Look for common indicator period attributes
            max_period = 0
            
            # Check for moving average periods
            for attr in ['n1', 'n2', 'n3', 'short_period', 'long_period', 'period', 'window']:
                if hasattr(strategy_class, attr):
                    value = getattr(strategy_class, attr)
                    if isinstance(value, int) and value > max_period:
                        max_period = value
            
            # Check for RSI periods (common default is 14)
            if hasattr(strategy_class, 'rsi_period'):
                rsi_period = getattr(strategy_class, 'rsi_period')
                if isinstance(rsi_period, int):
                    max_period = max(max_period, rsi_period)
            
            # Add buffer for indicator calculation
            if max_period > 0:
                calculated_lookback = max_period + 10  # Add 10 bar buffer
                logger.info(f"Calculated lookback period: {calculated_lookback} (based on max period {max_period})")
                return calculated_lookback
            
        except Exception as e:
            logger.warning(f"Error in automatic lookback calculation: {e}")
        
        # Final fallback
        logger.info(f"Using default lookback period: {default_lookback}")
        return default_lookback
    
    @staticmethod
    def _parse_lookback_from_file(strategy_path: str) -> Optional[int]:
        """
        Parse LOOKBACK configuration from strategy file
        
        Args:
            strategy_path: Path to strategy file
            
        Returns:
            LOOKBACK value if found, None otherwise
        """
        try:
            with open(strategy_path, 'r') as f:
                content = f.read()
            
            # Look for LOOKBACK = <number> pattern
            import re
            
            # Match patterns like "LOOKBACK = 20" or "LOOKBACK=20"
            pattern = r'^\s*LOOKBACK\s*=\s*(\d+)'
            
            for line in content.split('\n'):
                match = re.match(pattern, line.strip())
                if match:
                    lookback_value = int(match.group(1))
                    return lookback_value
            
            return None
            
        except Exception as e:
            logger.warning(f"Error parsing lookback from {strategy_path}: {e}")
            return None

class LiveTradingSystem:
    """Main live trading system orchestrator"""
    
    def __init__(self, strategy_path: str, symbols: List[str], 
                 data_source: str = "demo", granularity: str = "1m", lookback_override: Optional[int] = None,
                 enable_trading: bool = False):
        """
        Initialize live trading system
        
        Args:
            strategy_path: Path to strategy file
            symbols: List of symbols to trade
            data_source: Data source ("demo" or "polygon") 
            lookback_override: Override calculated lookback period
            enable_trading: Enable actual trading execution via Alpaca
        """
        self.strategy_path = strategy_path
        self.symbols = symbols
        self.data_source = data_source
        self.granularity = granularity
        self.lookback_override = lookback_override
        self.enable_trading = enable_trading
        
        # Load configuration
        self.data_config, self.trading_config = load_config()
        
        # Load and convert strategy
        original_strategy = StrategyLoader.load_strategy_from_file(strategy_path)
        self.strategy_class = StrategyLoader.convert_to_signal_strategy(original_strategy)
        
        # Calculate lookback
        self.lookback_period = (lookback_override or 
                               StrategyLoader.calculate_lookback_period(original_strategy, strategy_path))
        
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
            self.signal_extractors[symbol] = LiveSignalExtractor(
                self.strategy_class, 
                min_bars_required=self.lookback_period
            )
        
        # Track active signals
        self.active_signals = {}
        self.trade_log = []
        
        # Track cumulative data for proper live simulation
        self.cumulative_data = {}
        
        # Initialize Alpaca executor if trading is enabled
        self.alpaca_executor = None
        if self.enable_trading:
            try:
                self.alpaca_executor = create_alpaca_executor_from_env()
                logger.info("✅ Alpaca trading enabled. Trade size is determined by the strategy.")
            except Exception as e:
                logger.error(f"Failed to initialize Alpaca executor: {e}")
                logger.warning("Trading disabled - running in signal-only mode")
                self.enable_trading = False
        
    def _setup_data_ingestion(self):
        """Setup data ingestion based on data source"""
        import os
        from src.trading_system.data_ingestion import create_data_source
        
        # Get API key if needed
        api_key = None
        if self.data_source == "polygon":
            api_key = os.getenv('POLYGON_API_KEY')
        elif self.data_source == "coinmarketcap":
            api_key = os.getenv('CMC_API_KEY')
        
        # Create data source with granularity support
        return create_data_source(self.data_source, api_key, self.granularity)
    
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
        logger.info(f"Granularity: {self.granularity}")
        logger.info(f"Lookback Period: {self.lookback_period} bars")
        
        print(f"\n{'='*60}")
        print(f"🚀 LIVE TRADING SYSTEM STARTED")
        print(f"{'='*60}")
        print(f"Strategy: {self.strategy_class.__name__}")
        print(f"Symbols: {', '.join(self.symbols)}")
        print(f"Data Source: {self.data_source}")
        print(f"Granularity: {self.granularity}")
        print(f"Lookback: {self.lookback_period} bars")
        print(f"Duration: {duration_minutes} minutes")
        
        if self.enable_trading:
            print("💰 Trading: ENABLED via Alpaca")
            if self.alpaca_executor and self.alpaca_executor.config.paper:
                print("📝 Mode: PAPER TRADING")
            else:
                print("🔴 Mode: LIVE TRADING")
        else:
            print("📊 Trading: SIGNALS ONLY (no execution)")
        
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
                        
                        # Execute trade if trading is enabled
                        if self.enable_trading and self.alpaca_executor:
                            success = self.alpaca_executor.execute_signal(symbol, signal)
                            if success:
                                logger.info(f"🎯 Trade executed successfully for {symbol}")
                            else:
                                logger.error(f"❌ Trade execution failed for {symbol}")
                
                # Wait before next cycle - use granularity-based interval
                from src.trading_system.granularity import parse_granularity
                try:
                    parsed_granularity = parse_granularity(self.granularity)
                    sleep_interval = parsed_granularity.to_seconds()
                    # For very short intervals (< 1 second), use 1 second minimum for UI responsiveness
                    sleep_interval = max(sleep_interval, 1.0)
                    await asyncio.sleep(sleep_interval)
                except Exception:
                    # Fallback to 5 seconds if granularity parsing fails
                    await asyncio.sleep(5)
                
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
        
        # Start real-time feed first so we can get live data even if historical fails
        self.data_ingester.start_realtime_feed()
        
        for symbol in self.symbols:
            try:
                # Subscribe to real-time data for this symbol
                self.data_ingester.subscribe_to_symbol(symbol)
                
                # Try to fetch historical data with granularity
                historical_data = await self.data_ingester.fetch_historical_data(
                    symbol, 
                    days_back=max(5, self.lookback_period // 100),
                    granularity=self.granularity
                )
                
                # Store the initial cumulative data
                self.cumulative_data[symbol] = historical_data.copy()
                
                logger.info(f"✅ Loaded {len(historical_data)} initial historical bars for {symbol}")
                
            except Exception as e:
                logger.error(f"Error loading historical data for {symbol}: {e}")
                
                # If historical data fails, start with empty DataFrame - we'll build from real-time
                self.cumulative_data[symbol] = pd.DataFrame()
                logger.info(f"📊 Will build {symbol} data from real-time feeds only (no historical data available)")
        
        # Give real-time feed a moment to get initial data
        await asyncio.sleep(2)
        
        # Check if we got any initial real-time data
        for symbol in self.symbols:
            current_data = self.data_ingester.get_current_data(symbol)
            if current_data and len(self.cumulative_data[symbol]) == 0:
                # Add the first real-time bar to start building data
                first_bar = pd.DataFrame({
                    'Open': [current_data.open],
                    'High': [current_data.high],
                    'Low': [current_data.low],
                    'Close': [current_data.close],
                    'Volume': [current_data.volume]
                }, index=[current_data.timestamp])
                
                self.cumulative_data[symbol] = first_bar
                logger.info(f"🚀 Started building {symbol} data from first real-time bar: ${current_data.close:.2f}")
    
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
                    # For real data sources (like CoinMarketCap), get current real-time data
                    current_data = self.data_ingester.get_current_data(symbol)
                    
                    if current_data:
                        # Add current real-time bar to cumulative data
                        new_bar = pd.DataFrame({
                            'Open': [current_data.open],
                            'High': [current_data.high],
                            'Low': [current_data.low],
                            'Close': [current_data.close],
                            'Volume': [current_data.volume]
                        }, index=[current_data.timestamp])
                        
                        if symbol in self.cumulative_data and len(self.cumulative_data[symbol]) > 0:
                            # Check if this is a new timestamp (avoid duplicates)
                            last_timestamp = self.cumulative_data[symbol].index[-1]
                            time_diff = (current_data.timestamp - last_timestamp).total_seconds()
                            
                            # For CoinMarketCap, be more flexible with timestamps since they cache for 60s
                            # Add new bar if: significant time difference OR price changed OR first few bars
                            last_price = self.cumulative_data[symbol]['Close'].iloc[-1]
                            price_changed = abs(current_data.close - last_price) > 0.01  # Price changed by more than 1 cent
                            need_more_bars = len(self.cumulative_data[symbol]) < self.lookback_period
                            
                            if time_diff >= 30 or price_changed or need_more_bars:
                                self.cumulative_data[symbol] = pd.concat([self.cumulative_data[symbol], new_bar])
                                logger.debug(f"📊 Added new bar for {symbol}: ${current_data.close:.2f} (time_diff: {time_diff}s, price_changed: {price_changed}, need_more: {need_more_bars})")
                            else:
                                logger.debug(f"⏭️  Skipping duplicate bar for {symbol}: same timestamp and price")
                        else:
                            # First bar
                            self.cumulative_data[symbol] = new_bar
                            logger.info(f"🎬 First bar for {symbol}: ${current_data.close:.2f}")
                
                # Use cumulative data for signal extraction
                current_data_df = self.cumulative_data.get(symbol, pd.DataFrame())
                
                if len(current_data_df) >= self.lookback_period:
                    # Extract signal from cumulative data
                    signal = self.signal_extractors[symbol].extract_signal(current_data_df)
                    signals[symbol] = signal
                    self.active_signals[symbol] = signal
                    
                    # Log the data growth
                    logger.debug(f"Processing {symbol}: {len(current_data_df)} total bars, "
                               f"latest price: ${current_data_df['Close'].iloc[-1]:.2f}")
                    
                elif len(current_data_df) > 0:
                    # For simple strategies that don't need much historical data, generate signals
                    if len(current_data_df) >= self.lookback_period:
                        # We have enough data - generate signals
                        logger.info(f"Processing {symbol} with sufficient data: {len(current_data_df)} >= {self.lookback_period} bars")
                        signal = self.signal_extractors[symbol].extract_signal(current_data_df)
                        signals[symbol] = signal
                        self.active_signals[symbol] = signal
                    elif 'random' in self.strategy_class.__name__.lower():
                        # Random strategy can work with any amount of data
                        logger.info(f"Processing {symbol} with random strategy: {len(current_data_df)} bars available")
                        signal = self.signal_extractors[symbol].extract_signal(current_data_df)
                        signals[symbol] = signal
                        self.active_signals[symbol] = signal
                    else:
                        # Show progress towards having enough data
                        progress_pct = (len(current_data_df) / self.lookback_period) * 100
                        logger.info(f"Building {symbol} data: {len(current_data_df)}/{self.lookback_period} bars ({progress_pct:.1f}% complete)")
                else:
                    logger.warning(f"No data available for {symbol}")
                    
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
        
        # Show trading summary if enabled
        if self.enable_trading and self.alpaca_executor:
            try:
                account_info = self.alpaca_executor.get_account_info()
                positions = self.alpaca_executor.get_positions()
                
                print(f"\n📈 TRADING SUMMARY:")
                print(f"  Portfolio Value: ${account_info.get('portfolio_value', 0):,.2f}")
                print(f"  Cash: ${account_info.get('cash', 0):,.2f}")
                print(f"  Day Trades: {account_info.get('day_trade_count', 0)}")
                
                if positions:
                    print(f"\n🎯 ACTIVE POSITIONS:")
                    for symbol, pos in positions.items():
                        print(f"  • {symbol}: {pos['qty']} shares @ ${pos['avg_entry_price']:.2f} "
                              f"(P&L: ${pos['unrealized_pl']:.2f})")
                else:
                    print(f"\n🎯 No active positions")
                    
            except Exception as e:
                print(f"\n❌ Error getting trading summary: {e}")
        
        print(f"\nTrade log saved to trading_system.log")

def print_granularity_info():
    """Print information about supported granularities"""
    from src.trading_system.granularity import GranularityParser
    
    print("\nSupported granularities by data source:")
    print("=" * 50)
    
    for source in ["polygon", "coinmarketcap", "demo"]:
        granularities = GranularityParser.get_supported_granularities(source)
        print(f"\n{source.upper()}:")
        print(f"  Supported: {', '.join(granularities)}")
        if source == "polygon":
            print(f"  Default: 1m (very flexible with most timeframes)")
        elif source == "coinmarketcap":
            print(f"  Default: 1d (historical), supports intraday real-time simulation")
        elif source == "demo":
            print(f"  Default: 1m (can generate any granularity)")
    
    print("\nExample granularity formats:")
    print("  1s   = 1 second")
    print("  30s  = 30 seconds") 
    print("  1m   = 1 minute")
    print("  5m   = 5 minutes")
    print("  1h   = 1 hour")
    print("  1d   = 1 day")
    print()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Live Trading System')
    parser.add_argument('--strategy', help='Path to strategy file (e.g., sma.py)')
    parser.add_argument('--symbols', default='AAPL', help='Comma-separated list of symbols (e.g., AAPL,MSFT)')
    parser.add_argument('--data-source', choices=['demo', 'polygon', 'coinmarketcap'], default='demo', 
                       help='Data source to use')
    parser.add_argument('--granularity', type=str, 
                       help='Data granularity (e.g., 1s, 1m, 5m, 1h, 1d)')
    parser.add_argument('--lookback', type=int, help='Override calculated lookback period')
    parser.add_argument('--duration', type=int, default=60, help='Duration to run in minutes')
    parser.add_argument('--list-granularities', action='store_true',
                       help='List supported granularities for each data source')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    parser.add_argument('--enable-trading', action='store_true', 
                       help='Enable actual trading execution via Alpaca (requires .env setup)')
    
    args = parser.parse_args()
    
    # Handle granularity info request
    if args.list_granularities:
        print_granularity_info()
        return 0
    
    # Strategy is required for normal operation
    if not args.strategy:
        parser.error("--strategy is required when not using --list-granularities")
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine granularity
    granularity = args.granularity
    if not granularity:
        defaults = {
            "polygon": "1m",
            "coinmarketcap": "1d",
            "demo": "1m"
        }
        granularity = defaults.get(args.data_source, "1m")
        logger.info(f"Using default granularity {granularity} for {args.data_source}")
    
    # Validate granularity for the chosen data source
    from src.trading_system.granularity import validate_granularity
    is_valid, error_msg = validate_granularity(granularity, args.data_source)
    if not is_valid:
        logger.error(f"Invalid granularity: {error_msg}")
        print(f"\nError: {error_msg}")
        print(f"Use --list-granularities to see supported options.")
        return 1
    
    # Parse symbols
    symbols = [s.strip().upper() for s in args.symbols.split(',')]
    
    # Create and run system
    try:
        system = LiveTradingSystem(
            strategy_path=args.strategy,
            symbols=symbols,
            data_source=args.data_source,
            granularity=granularity,
            lookback_override=args.lookback,
            enable_trading=args.enable_trading
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