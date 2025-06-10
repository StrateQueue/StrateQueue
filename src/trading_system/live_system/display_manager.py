"""
Display Manager

Handles all display and logging operations for the live trading system:
- Signal display formatting
- Trade logging
- Session summaries
- Progress reporting
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..core.signal_extractor import TradingSignal

logger = logging.getLogger(__name__)

class DisplayManager:
    """Manages display output and logging for live trading"""
    
    def __init__(self, is_multi_strategy: bool = False, statistics_manager=None):
        """
        Initialize DisplayManager
        
        Args:
            is_multi_strategy: Whether running in multi-strategy mode
            statistics_manager: Optional statistics manager for showing stats
        """
        self.is_multi_strategy = is_multi_strategy
        self.statistics_manager = statistics_manager
        self.trade_log = []
        
    def display_startup_banner(self, symbols: List[str], data_source: str, 
                             granularity: str, lookback_period: int,
                             duration_minutes: int, strategy_info: str,
                             enable_trading: bool, alpaca_executor=None):
        """Display system startup information"""
        print(f"\n{'='*60}")
        print(f"🚀 LIVE TRADING SYSTEM STARTED")
        print(f"{'='*60}")
        
        if self.is_multi_strategy:
            print(f"Mode: MULTI-STRATEGY")
        else:
            print(f"Mode: SINGLE-STRATEGY")
            
        print(f"Strategy: {strategy_info}")
        print(f"Symbols: {', '.join(symbols)}")
        print(f"Data Source: {data_source}")
        print(f"Granularity: {granularity}")
        print(f"Lookback: {lookback_period} bars")
        print(f"Duration: {duration_minutes} minutes")
        
        if enable_trading:
            print("💰 Trading: ENABLED via Alpaca")
            if alpaca_executor and alpaca_executor.config.paper_trading:
                print("📝 Mode: PAPER TRADING")
            else:
                print("🔴 Mode: LIVE TRADING")
        else:
            print("📊 Trading: SIGNALS ONLY (no execution)")
        
        print(f"{'='*60}\n")
    
    def display_signal(self, symbol: str, signal: TradingSignal, count: int, 
                      strategy_id: Optional[str] = None):
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
    
    def log_trade(self, symbol: str, signal: TradingSignal):
        """Log trade for later analysis"""
        self.trade_log.append({
            'timestamp': signal.timestamp,
            'symbol': symbol,
            'signal': signal.signal.value,
            'price': signal.price,
            'confidence': signal.confidence,
            'indicators': signal.indicators
        })
    
    def display_signals_summary(self, signals: Dict, count: int):
        """Display summary of current signals"""
        if self.is_multi_strategy:
            self._display_multi_strategy_signals(signals, count)
        else:
            self._display_single_strategy_signals(signals, count)
    
    def _display_single_strategy_signals(self, signals: Dict[str, TradingSignal], count: int):
        """Display signals for single-strategy mode"""
        if signals:
            for symbol, signal in signals.items():
                self.display_signal(symbol, signal, count)
                self.log_trade(symbol, signal)
    
    def _display_multi_strategy_signals(self, signals: Dict[str, Dict[str, TradingSignal]], count: int):
        """Display signals for multi-strategy mode"""
        signal_count = count
        for symbol, strategy_signals in signals.items():
            if isinstance(strategy_signals, dict):
                for strategy_id, signal in strategy_signals.items():
                    self.display_signal(symbol, signal, signal_count, strategy_id)
                    self.log_trade(symbol, signal)
                    signal_count += 1
    
    def display_session_summary(self, active_signals: Dict, alpaca_executor=None):
        """Display trading session summary"""
        print(f"\n{'='*60}")
        print(f"📊 SESSION SUMMARY")
        print(f"{'='*60}")
        
        print(f"Total Signals Generated: {len(self.trade_log)}")
        
        if self.trade_log:
            # Signal breakdown
            signal_counts = {}
            for trade in self.trade_log:
                signal_type = trade['signal']
                signal_counts[signal_type] = signal_counts.get(signal_type, 0) + 1
            
            print("\nSignal Breakdown:")
            for signal_type, count in signal_counts.items():
                print(f"  • {signal_type}: {count}")
            
            # Latest signals
            print(f"\nLatest Signals:")
            if self.is_multi_strategy:
                for symbol, signal_or_signals in active_signals.items():
                    if isinstance(signal_or_signals, dict):
                        for strategy_id, signal in signal_or_signals.items():
                            print(f"  • {symbol} [{strategy_id}]: {signal.signal.value} @ ${signal.price:.2f}")
                    else:
                        print(f"  • {symbol}: No signals")
            else:
                for symbol, signal in active_signals.items():
                    print(f"  • {symbol}: {signal.signal.value} @ ${signal.price:.2f}")
        
        # Show trading summary if enabled
        if alpaca_executor:
            self._display_trading_summary(alpaca_executor)
        
        # Show statistics summary if available
        if self.statistics_manager:
            print(f"\n{self.statistics_manager.display_summary()}")
        
        print(f"\nTrade log saved to trading_system.log")
        print(f"{'='*60}")
    
    def _display_trading_summary(self, alpaca_executor):
        """Display trading/portfolio summary"""
        try:
            account_info = alpaca_executor.get_account_info()
            positions = alpaca_executor.get_positions()
            
            print(f"\n📈 TRADING SUMMARY:")
            print(f"  Portfolio Value: ${account_info.get('portfolio_value', 0):,.2f}")
            print(f"  Cash: ${account_info.get('cash', 0):,.2f}")
            print(f"  Day Trades: {account_info.get('daytrade_count', 0)}")
            
            if positions:
                print(f"\n🎯 ACTIVE POSITIONS:")
                for symbol, pos in positions.items():
                    print(f"  • {symbol}: {pos['qty']} shares @ ${pos['avg_entry_price']:.2f} "
                          f"(P&L: ${pos['unrealized_pl']:.2f})")
            else:
                print(f"\n🎯 No active positions")
                
        except Exception as e:
            print(f"\n❌ Error getting trading summary: {e}")
    
    def get_trade_log(self) -> List[Dict]:
        """Get the current trade log"""
        return self.trade_log.copy()
    
    def get_trade_count(self) -> int:
        """Get total number of trades logged"""
        return len(self.trade_log) 