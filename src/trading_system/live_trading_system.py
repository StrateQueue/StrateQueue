"""
Live Trading System

This module handles:
1. Orchestrating the live trading system
2. Connecting to data sources
3. Processing trading cycles
4. Managing signals and executions
5. Real-time display and logging
"""

import asyncio
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from . import setup_data_ingestion, LiveSignalExtractor, SignalType, TradingSignal
from . import load_config, create_alpaca_executor_from_env
from .strategy_loader import StrategyLoader
from .multi_strategy_runner import MultiStrategyRunner
from .simple_portfolio_manager import SimplePortfolioManager

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
            data_source: Data source ("demo" or "polygon") 
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
        
        if self.is_multi_strategy:
            # Multi-strategy mode
            logger.info("Initializing in MULTI-STRATEGY mode")
            self.multi_strategy_runner = MultiStrategyRunner(
                multi_strategy_config, 
                self.symbols,
                lookback_override
            )
            self.multi_strategy_runner.initialize_strategies()
            
            # Use multi-strategy maximum lookback
            self.lookback_period = self.multi_strategy_runner.get_max_lookback_period()
            
            # Single strategy attributes set to None
            self.strategy_path = None
            self.strategy_class = None
            self.signal_extractors = {}
            
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
            self.lookback_period = (lookback_override or 
                                   StrategyLoader.calculate_lookback_period(original_strategy, strategy_path))
            
            # Initialize signal extractors for each symbol
            self.signal_extractors = {}
            for symbol in self.symbols:
                self.signal_extractors[symbol] = LiveSignalExtractor(
                    self.strategy_class, 
                    min_bars_required=self.lookback_period
                )
            
            # Multi-strategy attributes set to None
            self.multi_strategy_runner = None
        
        # Initialize data ingestion
        self.data_ingester = self._setup_data_ingestion()
        
        # For live data, start real-time feed and subscribe to symbols
        if self.data_source != "demo":
            for symbol in self.symbols:
                self.data_ingester.subscribe_to_symbol(symbol)
        
        # Track active signals and trade log
        self.active_signals = {}
        self.trade_log = []
        
        # Track cumulative data for proper live simulation
        self.cumulative_data = {}
        
        # Initialize Alpaca executor if trading is enabled
        self.alpaca_executor = None
        if self.enable_trading:
            try:
                # Get portfolio manager for multi-strategy mode
                portfolio_manager = None
                if self.is_multi_strategy:
                    portfolio_manager = self.multi_strategy_runner.portfolio_manager
                
                self.alpaca_executor = create_alpaca_executor_from_env(portfolio_manager)
                
                mode_info = "multi-strategy" if self.is_multi_strategy else "single-strategy"
                logger.info(f"✅ Alpaca trading enabled ({mode_info} mode)")
                
            except Exception as e:
                logger.error(f"Failed to initialize Alpaca executor: {e}")
                logger.warning("Trading disabled - running in signal-only mode")
                self.enable_trading = False
        
    def _setup_data_ingestion(self):
        """Setup data ingestion based on data source"""
        import os
        from .data_ingestion import create_data_source
        
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
        
        if self.is_multi_strategy:
            strategies_info = ', '.join(self.multi_strategy_runner.get_strategy_ids())
            logger.info(f"Strategies: {strategies_info}")
        else:
            logger.info(f"Strategy: {self.strategy_class.__name__}")
            
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Data Source: {self.data_source}")
        logger.info(f"Granularity: {self.granularity}")
        logger.info(f"Lookback Period: {self.lookback_period} bars")
        
        print(f"\n{'='*60}")
        print(f"🚀 LIVE TRADING SYSTEM STARTED")
        print(f"{'='*60}")
        
        if self.is_multi_strategy:
            strategies_info = ', '.join(self.multi_strategy_runner.get_strategy_ids())
            print(f"Mode: MULTI-STRATEGY ({len(self.multi_strategy_runner.get_strategy_ids())} strategies)")
            print(f"Strategies: {strategies_info}")
        else:
            print(f"Mode: SINGLE-STRATEGY")
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
                
                # Handle signals (could be single signal per symbol or multiple per symbol for multi-strategy)
                for symbol_or_key, signal_or_signals in new_signals.items():
                    if self.is_multi_strategy:
                        # Multi-strategy: signal_or_signals is dict of strategy_id -> signal
                        symbol = symbol_or_key
                        strategy_signals = signal_or_signals
                        
                        for strategy_id, signal in strategy_signals.items():
                            if signal.signal != SignalType.HOLD:
                                signal_count += 1
                                self._display_signal(symbol, signal, signal_count, strategy_id)
                                self._log_trade(symbol, signal)
                                
                                # Execute trade if trading is enabled
                                if self.enable_trading and self.alpaca_executor:
                                    success = self.alpaca_executor.execute_signal(symbol, signal)
                                    if success:
                                        logger.info(f"🎯 Trade executed successfully for {symbol} [{strategy_id}]")
                                    else:
                                        logger.error(f"❌ Trade execution failed for {symbol} [{strategy_id}]")
                    else:
                        # Single strategy: signal_or_signals is single signal
                        symbol = symbol_or_key
                        signal = signal_or_signals
                        
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
                from .granularity import parse_granularity
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
    
    async def _process_trading_cycle(self):
        """Process one trading cycle for all symbols"""
        if self.is_multi_strategy:
            return await self._process_multi_strategy_cycle()
        else:
            return await self._process_single_strategy_cycle()
    
    async def _process_single_strategy_cycle(self) -> Dict[str, TradingSignal]:
        """Process trading cycle for single strategy mode"""
        signals = {}
        
        for symbol in self.symbols:
            try:
                # Update data for this symbol
                await self._update_symbol_data(symbol)
                
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
                    # For simple strategies that don't need much historical data
                    if hasattr(self.strategy_class, '__name__') and 'random' in self.strategy_class.__name__.lower():
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
    
    async def _process_multi_strategy_cycle(self) -> Dict[str, Dict[str, TradingSignal]]:
        """Process trading cycle for multi-strategy mode"""
        all_signals = {}
        
        # Update portfolio value for all strategies
        if self.enable_trading and self.alpaca_executor:
            try:
                account = self.alpaca_executor.get_account_info()
                portfolio_value = account.get('portfolio_value', 100000)  # Default fallback
                self.multi_strategy_runner.update_portfolio_value(portfolio_value)
            except Exception as e:
                logger.warning(f"Could not update portfolio value: {e}")
        
        for symbol in self.symbols:
            try:
                # Update data for this symbol
                await self._update_symbol_data(symbol)
                
                # Use cumulative data for signal extraction
                current_data_df = self.cumulative_data.get(symbol, pd.DataFrame())
                
                if len(current_data_df) > 0:
                    # Always try to generate signals - let each strategy decide if it has enough data
                    strategy_signals = await self.multi_strategy_runner.generate_signals(symbol, current_data_df)
                    all_signals[symbol] = strategy_signals
                    
                    # Update active signals
                    self.active_signals[symbol] = strategy_signals
                    
                    # Log the data and signal info
                    logger.debug(f"Processing {symbol}: {len(current_data_df)} total bars, "
                               f"latest price: ${current_data_df['Close'].iloc[-1]:.2f}")
                    
                    # Show progress for strategies that might still be waiting for more data
                    max_lookback = self.lookback_period
                    if len(current_data_df) < max_lookback:
                        progress_pct = (len(current_data_df) / max_lookback) * 100
                        logger.info(f"Building {symbol} data: {len(current_data_df)}/{max_lookback} bars ({progress_pct:.1f}% complete)")
                        
                else:
                    logger.warning(f"No data available for {symbol}")
                    
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
        
        return all_signals
    
    async def _update_symbol_data(self, symbol: str):
        """Update data for a single symbol"""
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
    
    def _display_signal(self, symbol: str, signal: TradingSignal, count: int, strategy_id: Optional[str] = None):
        """Display a trading signal"""
        timestamp_str = signal.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        signal_emoji = {"BUY": "📈", "SELL": "📉", "CLOSE": "🔄", "HOLD": "⏸️"}
        
        strategy_info = f" [{strategy_id}]" if strategy_id else ""
        
        print(f"\n🎯 SIGNAL #{count} - {timestamp_str}{strategy_info}")
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
            for symbol, signal_or_signals in self.active_signals.items():
                if self.is_multi_strategy:
                    # Multi-strategy: signal_or_signals is dict of strategy_id -> signal
                    if isinstance(signal_or_signals, dict):
                        for strategy_id, signal in signal_or_signals.items():
                            print(f"  • {symbol} [{strategy_id}]: {signal.signal.value} @ ${signal.price:.2f}")
                    else:
                        print(f"  • {symbol}: No signals")
                else:
                    # Single strategy: signal_or_signals is single signal
                    signal = signal_or_signals
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