"""
Display Manager

Handles all display and logging operations for the live trading system:
- Signal display formatting
- Trade logging
- Session summaries
- Progress reporting
"""

import logging

from ..core.signal_extractor import TradingSignal
from ..utils.price_formatter import PriceFormatter

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

    def display_startup_banner(
        self,
        symbols: list[str],
        data_source: str,
        granularity: str,
        lookback_period: int,
        duration_minutes: int,
        strategy_info: str,
        enable_trading: bool,
        broker_executor=None,
    ):
        """Display system startup information"""
        print(f"\n{'='*60}")
        print("🚀 LIVE TRADING SYSTEM STARTED")
        print(f"{'='*60}")

        if self.is_multi_strategy:
            print("Mode: MULTI-STRATEGY")
        else:
            print("Mode: SINGLE-STRATEGY")

        print(f"Strategy: {strategy_info}")
        print(f"Symbols: {', '.join(symbols)}")
        print(f"Data Source: {data_source}")
        print(f"Granularity: {granularity}")
        print(f"Lookback: {lookback_period} bars")
        print(f"Duration: {duration_minutes} minutes")

        if enable_trading:
            broker_name = self._get_broker_display_name(broker_executor)
            print(f"💰 Trading: ENABLED via {broker_name}")
            if broker_executor and broker_executor.config.paper_trading:
                print("📝 Mode: PAPER TRADING")
            else:
                print("🔴 Mode: LIVE TRADING")
        else:
            print("📊 Trading: SIGNALS ONLY (no execution)")

        print(f"{'='*60}\n")

    def _get_broker_display_name(self, broker_executor) -> str:
        """Get a user-friendly display name for the broker"""
        if not broker_executor:
            return "Unknown"
        
        try:
            # Try to get broker type from config
            if hasattr(broker_executor, 'config') and hasattr(broker_executor.config, 'broker_type'):
                broker_type = broker_executor.config.broker_type
                
                # Map broker types to display names
                display_names = {
                    'alpaca': 'Alpaca',
                    'ibkr': 'Interactive Brokers',
                    'ib_gateway': 'Interactive Brokers Gateway',
                    'ccxt': 'CCXT',
                }
                
                # Handle CCXT exchange-specific brokers
                if broker_type == 'ccxt' and hasattr(broker_executor.config, 'additional_params'):
                    exchange = broker_executor.config.additional_params.get('exchange')
                    if exchange:
                        return f"CCXT ({exchange.title()})"
                
                # Handle ccxt.exchange format
                if broker_type.startswith('ccxt.'):
                    exchange = broker_type.split('.', 1)[1]
                    return f"CCXT ({exchange.title()})"
                
                return display_names.get(broker_type, broker_type.title())
            
            # Fallback: try to get broker info
            if hasattr(broker_executor, 'get_broker_info'):
                broker_info = broker_executor.get_broker_info()
                if broker_info and hasattr(broker_info, 'name'):
                    return broker_info.name
            
            # Last resort: use class name
            return broker_executor.__class__.__name__.replace('Broker', '')
            
        except Exception as e:
            logger.debug(f"Error getting broker display name: {e}")
            return "Unknown"

    def display_signal(
        self, symbol: str, signal: TradingSignal, count: int, strategy_id: str | None = None
    ):
        """Display a trading signal"""
        timestamp_str = signal.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        signal_emoji = {"BUY": "📈", "SELL": "📉", "CLOSE": "🔄", "HOLD": "⏸️"}

        strategy_info = f" [{strategy_id}]" if strategy_id else ""

        print(f"\n🎯 SIGNAL #{count} - {timestamp_str}{strategy_info}")
        print(f"Symbol: {symbol}")
        print(f"Action: {signal_emoji.get(signal.signal.value, '❓')} {signal.signal.value}")
        # Print full OHLCV if available in metadata for easier debugging
        ohlcv = signal.metadata.get("bar") if hasattr(signal, "metadata") and signal.metadata else None
        if isinstance(ohlcv, dict) and all(k in ohlcv for k in ("Open","High","Low","Close","Volume")):
            print(
                f"OHLCV: O={PriceFormatter.format_price_for_display(ohlcv['Open'])}, "
                f"H={PriceFormatter.format_price_for_display(ohlcv['High'])}, "
                f"L={PriceFormatter.format_price_for_display(ohlcv['Low'])}, "
                f"C={PriceFormatter.format_price_for_display(ohlcv['Close'])}, "
                f"V={ohlcv['Volume']}"
            )
        else:
            print(f"Price: {PriceFormatter.format_price_for_display(signal.price)}")

        # Removed verbose indicator output to keep the console log concise

    def log_trade(self, symbol: str, signal: TradingSignal):
        """Log trade for later analysis"""
        self.trade_log.append(
            {
                "timestamp": signal.timestamp,
                "symbol": symbol,
                "signal": signal.signal.value,
                "price": signal.price,
                "indicators": signal.indicators,
            }
        )
        
        # Remove this duplicate recording - orchestrator handles it
        # if self.statistics_manager:
        #     self.statistics_manager.record_signal(...)

    def display_signals_summary(self, signals: dict, count: int):
        """Display summary of current signals"""
        if self.is_multi_strategy:
            self._display_multi_strategy_signals(signals, count)
        else:
            self._display_single_strategy_signals(signals, count)

    def _display_single_strategy_signals(self, signals: dict[str, TradingSignal], count: int):
        """Display signals for single-strategy mode"""
        if signals:
            for symbol, signal in signals.items():
                self.display_signal(symbol, signal, count)
                self.log_trade(symbol, signal)

    def _display_multi_strategy_signals(
        self, signals: dict[str, dict[str, TradingSignal]], count: int
    ):
        """Display signals for multi-strategy mode"""
        signal_count = count
        for symbol, strategy_signals in signals.items():
            if isinstance(strategy_signals, dict):
                for strategy_id, signal in strategy_signals.items():
                    self.display_signal(symbol, signal, signal_count, strategy_id)
                    self.log_trade(symbol, signal)
                    signal_count += 1

    def display_session_summary(self, active_signals: dict, broker_executor=None):
        """Display trading session summary"""
        print(f"\n{'='*60}")
        print("📊 SESSION SUMMARY")
        print(f"{'='*60}")

        print(f"Total Signals Generated: {len(self.trade_log)}")

        if self.trade_log:
            # Signal breakdown
            signal_counts = {}
            for trade in self.trade_log:
                signal_type = trade["signal"]
                signal_counts[signal_type] = signal_counts.get(signal_type, 0) + 1

            print("\nSignal Breakdown:")
            for signal_type, count in signal_counts.items():
                print(f"  • {signal_type}: {count}")

            # Latest signals
            print("\nLatest Signals:")
            if self.is_multi_strategy:
                for symbol, signal_or_signals in active_signals.items():
                    if isinstance(signal_or_signals, dict):
                        for strategy_id, signal in signal_or_signals.items():
                            print(
                                f"  • {symbol} [{strategy_id}]: {signal.signal.value} @ {PriceFormatter.format_price_for_display(signal.price)}"
                            )
                    else:
                        print(f"  • {symbol}: No signals")
            else:
                for symbol, signal in active_signals.items():
                    print(f"  • {symbol}: {signal.signal.value} @ {PriceFormatter.format_price_for_display(signal.price)}")

        # Show trading summary if enabled
        if broker_executor:
            self._display_trading_summary(broker_executor)

        # Show statistics summary if available
        if self.statistics_manager:
            print()  # Add some spacing before the enhanced display
            self.statistics_manager.display_enhanced_summary()

        print("\nTrade log saved to stratequeue.log")
        print(f"{'='*60}")

    def _display_trading_summary(self, broker_executor):
        """Display trading/portfolio summary"""
        try:
            account_info = broker_executor.get_account_info()
            positions = broker_executor.get_positions()

            print("\n📈 TRADING SUMMARY:")
            print(f"  Portfolio Value: ${account_info.get('portfolio_value', 0):,.2f}")
            print(f"  Cash: ${account_info.get('cash', 0):,.2f}")
            print(f"  Day Trades: {account_info.get('daytrade_count', 0)}")

            if positions:
                print("\n🎯 ACTIVE POSITIONS:")
                for symbol, pos in positions.items():
                    print(
                        f"  • {symbol}: {PriceFormatter.format_quantity(pos['qty'])} shares @ {PriceFormatter.format_price_for_display(pos['avg_entry_price'])} "
                        f"(P&L: {PriceFormatter.format_price_for_display(pos['unrealized_pl'])})"
                    )
            else:
                print("\n🎯 No active positions")

        except Exception as e:
            print(f"\n❌ Error getting trading summary: {e}")

    def get_trade_log(self) -> list[dict]:
        """Get the current trade log"""
        return self.trade_log.copy()

    def get_trade_count(self) -> int:
        """Get total number of trades logged"""
        return len(self.trade_log)
