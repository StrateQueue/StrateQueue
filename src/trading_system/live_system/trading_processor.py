"""
Trading Processor

Handles the core trading cycle processing for both single-strategy and multi-strategy modes:
- Signal extraction and processing
- Strategy coordination
- Portfolio value updates
- Trading logic execution
"""

import logging
from typing import Dict, List, Optional
import pandas as pd

from ..core.signal_extractor import LiveSignalExtractor, TradingSignal

logger = logging.getLogger(__name__)

class TradingProcessor:
    """Processes trading cycles for single and multi-strategy modes"""
    
    def __init__(self, symbols: List[str], lookback_period: int, 
                 is_multi_strategy: bool = False,
                 strategy_class = None,
                 multi_strategy_runner = None,
                 statistics_manager = None):
        """
        Initialize TradingProcessor
        
        Args:
            symbols: List of symbols to process
            lookback_period: Required lookback period for strategies
            is_multi_strategy: Whether running in multi-strategy mode
            strategy_class: Strategy class for single-strategy mode
            multi_strategy_runner: MultiStrategyRunner for multi-strategy mode
            statistics_manager: Statistics manager for price updates
        """
        self.symbols = symbols
        self.lookback_period = lookback_period
        self.is_multi_strategy = is_multi_strategy
        self.strategy_class = strategy_class
        self.multi_strategy_runner = multi_strategy_runner
        self.statistics_manager = statistics_manager
        
        # Initialize signal extractors for single-strategy mode
        if not is_multi_strategy and strategy_class:
            self.signal_extractors = {}
            for symbol in self.symbols:
                self.signal_extractors[symbol] = LiveSignalExtractor(
                    strategy_class, 
                    min_bars_required=lookback_period
                )
        else:
            self.signal_extractors = None
        
        # Track active signals
        self.active_signals = {}
    
    async def process_trading_cycle(self, data_manager, alpaca_executor=None):
        """Process one trading cycle for all symbols"""
        if self.is_multi_strategy:
            return await self._process_multi_strategy_cycle(data_manager, alpaca_executor)
        else:
            return await self._process_single_strategy_cycle(data_manager)
    
    async def _process_single_strategy_cycle(self, data_manager) -> Dict[str, TradingSignal]:
        """Process trading cycle for single strategy mode"""
        signals = {}
        current_prices = {}
        
        for symbol in self.symbols:
            try:
                # Update data for this symbol
                await data_manager.update_symbol_data(symbol)
                
                # Use cumulative data for signal extraction
                current_data_df = data_manager.get_symbol_data(symbol)
                
                if len(current_data_df) >= self.lookback_period:
                    # Get current price for statistics update
                    current_price = current_data_df['Close'].iloc[-1]
                    
                    # For statistics tracking, we need to match the symbol format used in trades
                    current_prices[symbol] = current_price
                    
                    # Also store crypto pair format for Alpaca compatibility  
                    if symbol in ['BTC', 'ETH', 'LTC', 'BCH', 'DOGE', 'SHIB', 'AVAX', 'UNI', 'LINK', 'MATIC']:
                        crypto_pair = f"{symbol}/USD"
                        current_prices[crypto_pair] = current_price
                    
                    # Extract signal from cumulative data
                    signal = self.signal_extractors[symbol].extract_signal(current_data_df)
                    signals[symbol] = signal
                    self.active_signals[symbol] = signal
                    
                    # Log the data growth
                    logger.debug(f"Processing {symbol}: {len(current_data_df)} total bars, "
                               f"latest price: ${current_data_df['Close'].iloc[-1]:.2f}")
                    
                elif len(current_data_df) > 0:
                    # For simple strategies that don't need much historical data
                    if (hasattr(self.strategy_class, '__name__') and 
                        'random' in self.strategy_class.__name__.lower()):
                        # Random strategy can work with any amount of data
                        logger.info(f"Processing {symbol} with random strategy: {len(current_data_df)} bars available")
                        signal = self.signal_extractors[symbol].extract_signal(current_data_df)
                        signals[symbol] = signal
                        self.active_signals[symbol] = signal
                    else:
                        # Show progress towards having enough data
                        current_bars, required_bars, progress_pct = data_manager.get_data_progress(symbol)
                        logger.info(f"Building {symbol} data: {current_bars}/{required_bars} bars ({progress_pct:.1f}% complete)")
                elif len(current_data_df) > 0:
                    # Even if we don't have enough data for signals, update prices for statistics
                    current_price = current_data_df['Close'].iloc[-1]
                    current_prices[symbol] = current_price
                    
                    # Also store crypto pair format for Alpaca compatibility
                    if symbol in ['BTC', 'ETH', 'LTC', 'BCH', 'DOGE', 'SHIB', 'AVAX', 'UNI', 'LINK', 'MATIC']:
                        crypto_pair = f"{symbol}/USD"
                        current_prices[crypto_pair] = current_price
                else:
                    logger.warning(f"No data available for {symbol}")
                    
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
        
        # Update statistics manager with current market prices for unrealized P&L calculations
        if current_prices and self.statistics_manager:
            self.statistics_manager.update_market_prices(current_prices)
        
        return signals
    
    async def _process_multi_strategy_cycle(self, data_manager, alpaca_executor=None) -> Dict[str, Dict[str, TradingSignal]]:
        """Process trading cycle for multi-strategy mode"""
        all_signals = {}
        current_prices = {}
        
        # Update portfolio value for all strategies
        if alpaca_executor:
            try:
                account = alpaca_executor.get_account_info()
                portfolio_value = account.get('portfolio_value', 100000)  # Default fallback
                self.multi_strategy_runner.update_portfolio_value(portfolio_value)
            except Exception as e:
                logger.warning(f"Could not update portfolio value: {e}")
        
        for symbol in self.symbols:
            try:
                # Update data for this symbol
                await data_manager.update_symbol_data(symbol)
                
                # Use cumulative data for signal extraction
                current_data_df = data_manager.get_symbol_data(symbol)
                
                if len(current_data_df) > 0:
                    # Get current price for statistics update
                    current_price = current_data_df['Close'].iloc[-1]
                    
                    # For statistics tracking, we need to match the symbol format used in trades
                    # Alpaca normalizes symbols to crypto pairs (e.g., ETH -> ETH/USD)
                    # so we need to store prices for both formats to ensure matching
                    current_prices[symbol] = current_price
                    
                    # Also store crypto pair format for Alpaca compatibility
                    if symbol in ['BTC', 'ETH', 'LTC', 'BCH', 'DOGE', 'SHIB', 'AVAX', 'UNI', 'LINK', 'MATIC']:
                        crypto_pair = f"{symbol}/USD"
                        current_prices[crypto_pair] = current_price
                    
                    # Always try to generate signals - let each strategy decide if it has enough data
                    strategy_signals = await self.multi_strategy_runner.generate_signals(symbol, current_data_df)
                    all_signals[symbol] = strategy_signals
                    
                    # Update active signals
                    self.active_signals[symbol] = strategy_signals
                    
                    # Log the data and signal info
                    logger.debug(f"Processing {symbol}: {len(current_data_df)} total bars, "
                               f"latest price: ${current_data_df['Close'].iloc[-1]:.2f}")
                    
                    # Show progress for strategies that might still be waiting for more data
                    if not data_manager.has_sufficient_data(symbol):
                        current_bars, required_bars, progress_pct = data_manager.get_data_progress(symbol)
                        logger.info(f"Building {symbol} data: {current_bars}/{required_bars} bars ({progress_pct:.1f}% complete)")
                        
                else:
                    logger.warning(f"No data available for {symbol}")
                    
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
        
        # Update statistics manager with current market prices for unrealized P&L calculations
        if current_prices and hasattr(self.multi_strategy_runner, 'statistics_manager') and self.multi_strategy_runner.statistics_manager:
            self.multi_strategy_runner.statistics_manager.update_market_prices(current_prices)
        
        return all_signals
    
    def get_active_signals(self) -> Dict:
        """Get currently active signals"""
        return self.active_signals.copy()
    
    def get_strategy_info(self) -> str:
        """Get string representation of current strategy configuration"""
        if self.is_multi_strategy:
            strategy_ids = self.multi_strategy_runner.get_strategy_ids()
            return f"Multi-strategy: {', '.join(strategy_ids)}"
        else:
            return f"Single-strategy: {self.strategy_class.__name__}" 