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

logger = logging.getLogger(__name__)

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