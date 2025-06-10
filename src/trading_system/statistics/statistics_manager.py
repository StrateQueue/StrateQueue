"""
Statistics Manager

Central coordinator for all statistics tracking.
Manages all stat trackers and provides a unified interface.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base_tracker import BaseTracker, TradeEvent
from .pnl_tracker import PnLTracker
from .win_loss_tracker import WinLossTracker

logger = logging.getLogger(__name__)

class StatisticsManager:
    """Manages all statistics trackers"""
    
    def __init__(self):
        """Initialize statistics manager with all available trackers"""
        self.trackers: List[BaseTracker] = []
        
        # Initialize all trackers (we always track everything we code)
        self._initialize_trackers()
        
        logger.info(f"Statistics Manager initialized with {len(self.trackers)} trackers")
        for tracker in self.trackers:
            logger.info(f"  • {tracker.name}")
    
    def _initialize_trackers(self):
        """Initialize all available stat trackers"""
        # Add PnL tracker
        self.pnl_tracker = PnLTracker()
        self.trackers.append(self.pnl_tracker)
        
        # Add Win/Loss tracker
        self.win_loss_tracker = WinLossTracker()
        self.trackers.append(self.win_loss_tracker)
        
        # Future trackers will be added here automatically
        # self.drawdown_tracker = DrawdownTracker()
        # self.trackers.append(self.drawdown_tracker)
    
    def record_trade(self, timestamp: datetime, strategy_id: str, symbol: str,
                    action: str, quantity: float, price: float, 
                    commission: float = 0.0, trade_id: Optional[str] = None):
        """
        Record a trade execution to all trackers
        
        Args:
            timestamp: When the trade occurred
            strategy_id: Strategy that executed the trade
            symbol: Symbol traded
            action: 'buy' or 'sell'
            quantity: Quantity traded
            price: Execution price
            commission: Commission paid
            trade_id: Optional trade identifier
        """
        trade_event = TradeEvent(
            timestamp=timestamp,
            strategy_id=strategy_id,
            symbol=symbol,
            action=action,
            quantity=quantity,
            price=price,
            commission=commission,
            trade_id=trade_id
        )
        
        # Send to all trackers
        for tracker in self.trackers:
            try:
                tracker.on_trade_executed(trade_event)
            except Exception as e:
                logger.error(f"Error in {tracker.name} processing trade: {e}")
        
        logger.debug(f"Recorded trade: {strategy_id} {action} {quantity} {symbol} @ ${price:.2f}")
    
    def record_hypothetical_trade(self, signal: Any, symbol: str, default_quantity: float = 100.0):
        """
        Record a hypothetical trade based on a signal (for signals-only mode)
        
        Args:
            signal: Trading signal object
            symbol: Symbol the signal is for
            default_quantity: Default quantity for hypothetical trades
        """
        from ..core.signal_extractor import SignalType
        
        # Skip HOLD signals
        if signal.signal == SignalType.HOLD:
            return
        
        # Determine action from signal type
        if signal.signal in [SignalType.BUY, SignalType.LIMIT_BUY, SignalType.STOP_BUY, SignalType.STOP_LIMIT_BUY]:
            action = "buy"
        elif signal.signal in [SignalType.SELL, SignalType.CLOSE, SignalType.LIMIT_SELL, 
                              SignalType.STOP_SELL, SignalType.STOP_LIMIT_SELL, SignalType.TRAILING_STOP_SELL]:
            action = "sell"
        else:
            return  # Unknown signal type
        
        # Create hypothetical trade event
        trade_event = TradeEvent(
            timestamp=signal.timestamp or datetime.now(),
            strategy_id=signal.strategy_id or "unknown",
            symbol=symbol,
            action=action,
            quantity=default_quantity,
            price=signal.price,
            commission=0.0,  # No commission for hypothetical trades
            trade_id=f"hyp_{signal.strategy_id}_{symbol}_{signal.timestamp}"
        )
        
        # Send to all trackers
        for tracker in self.trackers:
            try:
                tracker.on_trade_executed(trade_event)
            except Exception as e:
                logger.error(f"Error in {tracker.name} processing hypothetical trade: {e}")
        
        logger.debug(f"Recorded hypothetical trade: {signal.strategy_id} {action} {default_quantity} {symbol} @ ${signal.price:.2f}")
    
    def update_portfolio_value(self, strategy_id: str, portfolio_value: float):
        """Update portfolio value for all trackers"""
        for tracker in self.trackers:
            try:
                tracker.on_portfolio_update(strategy_id, portfolio_value)
            except Exception as e:
                logger.error(f"Error in {tracker.name} updating portfolio: {e}")
    
    def update_market_prices(self, prices: Dict[str, float]):
        """Update current market prices for unrealized PnL calculations"""
        # Only PnL tracker needs this for now
        if hasattr(self.pnl_tracker, 'update_market_prices'):
            self.pnl_tracker.update_market_prices(prices)
    
    def get_pnl_stats(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
        """Get PnL statistics"""
        return self.pnl_tracker.get_current_stats(strategy_id)
    
    def get_win_loss_stats(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
        """Get Win/Loss statistics"""
        return self.win_loss_tracker.get_current_stats(strategy_id)
    
    def get_all_stats(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics from all trackers"""
        all_stats = {}
        
        for tracker in self.trackers:
            try:
                stats = tracker.get_current_stats(strategy_id)
                all_stats[tracker.name] = stats
            except Exception as e:
                logger.error(f"Error getting stats from {tracker.name}: {e}")
                all_stats[tracker.name] = {"error": str(e)}
        
        return all_stats
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary from all trackers"""
        summary = {
            'tracker_count': len(self.trackers),
            'trackers': {}
        }
        
        for tracker in self.trackers:
            try:
                summary['trackers'][tracker.name] = tracker.get_summary()
            except Exception as e:
                logger.error(f"Error getting summary from {tracker.name}: {e}")
                summary['trackers'][tracker.name] = {"error": str(e)}
        
        return summary
    
    def get_trade_history(self, strategy_id: Optional[str] = None) -> List[Any]:
        """Get trade history from PnL tracker"""
        return self.pnl_tracker.get_trade_history(strategy_id)
    
    def reset_all(self):
        """Reset all trackers"""
        for tracker in self.trackers:
            try:
                tracker.reset()
            except Exception as e:
                logger.error(f"Error resetting {tracker.name}: {e}")
        
        logger.info("All statistics trackers reset")
    
    def display_summary(self) -> str:
        """Get a formatted display summary"""
        summary = self.get_summary()
        
        lines = []
        lines.append("=" * 50)
        lines.append("📊 STATISTICS SUMMARY")
        lines.append("=" * 50)
        
        for tracker_name, tracker_summary in summary['trackers'].items():
            if 'error' in tracker_summary:
                lines.append(f"{tracker_name}: ERROR - {tracker_summary['error']}")
                continue
                
            if tracker_name == 'PnLTracker':
                # Get detailed strategy breakdown
                detailed_stats = self.pnl_tracker.get_current_stats()
                
                # Portfolio summary
                portfolio = detailed_stats.get('portfolio_summary', {})
                lines.append(f"💰 PnL Tracker:")
                lines.append(f"  Portfolio P&L: ${portfolio.get('total_pnl', 0):.2f}")
                lines.append(f"  Net P&L: ${portfolio.get('net_pnl', 0):.2f}")
                lines.append(f"  Completed Trades: {portfolio.get('total_completed_trades', 0)}")
                
                # Individual strategy breakdown
                strategies = detailed_stats.get('strategies', {})
                if strategies:
                    lines.append(f"")
                    lines.append(f"📈 Strategy Breakdown:")
                    for strategy_id, strategy_stats in strategies.items():
                        lines.append(f"  • {strategy_id}:")
                        lines.append(f"    P&L: ${strategy_stats.get('total_pnl', 0):.2f}")
                        lines.append(f"    Net: ${strategy_stats.get('net_pnl', 0):.2f}")
                        lines.append(f"    Trades: {strategy_stats.get('completed_trades_count', 0)}")
                        lines.append(f"    Positions: {len(strategy_stats.get('open_positions', []))}")
                        
                        # Show open positions if any
                        open_positions = strategy_stats.get('open_positions', [])
                        if open_positions:
                            for pos in open_positions:
                                unrealized = pos.get('unrealized_pnl', 0)
                                qty = pos.get('quantity', 0)
                                symbol = pos.get('symbol', 'UNKNOWN')
                                lines.append(f"      {symbol}: {qty:.4f} (${unrealized:.2f})")
                
                # Overall totals
                total_open_positions = sum(len(s.get('open_positions', [])) for s in strategies.values())
                lines.append(f"")
                lines.append(f"  Total Open Positions: {total_open_positions}")
                
            elif tracker_name == 'WinLossTracker':
                # Get detailed strategy breakdown
                detailed_stats = self.win_loss_tracker.get_current_stats()
                
                # Portfolio summary
                portfolio = detailed_stats.get('portfolio_summary', {})
                lines.append(f"🎯 Win/Loss Tracker:")
                lines.append(f"  Portfolio Win Rate: {portfolio.get('portfolio_win_rate', 0)*100:.1f}%")
                lines.append(f"  Total Trades: {portfolio.get('total_trades', 0)}")
                lines.append(f"  Profit Factor: {portfolio.get('portfolio_profit_factor', 0):.2f}")
                
                # Individual strategy breakdown
                strategies = detailed_stats.get('strategies', {})
                if strategies:
                    lines.append(f"")
                    lines.append(f"📈 Strategy Breakdown:")
                    for strategy_id, strategy_stats in strategies.items():
                        win_rate = strategy_stats.get('win_rate', 0) * 100
                        wins = strategy_stats.get('wins', 0)
                        losses = strategy_stats.get('losses', 0)
                        profit_factor = strategy_stats.get('profit_factor', 0)
                        current_streak = strategy_stats.get('current_streak', 0)
                        
                        lines.append(f"  • {strategy_id}:")
                        lines.append(f"    Win Rate: {win_rate:.1f}%")
                        lines.append(f"    W/L: {wins}/{losses}")
                        lines.append(f"    Profit Factor: {profit_factor:.2f}")
                        if current_streak > 0:
                            lines.append(f"    Current Streak: {current_streak} wins")
                        elif current_streak < 0:
                            lines.append(f"    Current Streak: {abs(current_streak)} losses")
                        else:
                            lines.append(f"    Current Streak: 0")
                
                # Overall totals
                total_open_positions = portfolio.get('total_open_positions', 0)
                lines.append(f"")
                lines.append(f"  Total Open Positions: {total_open_positions}")
            else:
                lines.append(f"{tracker_name}: {tracker_summary}")
        
        lines.append("=" * 50)
        return "\n".join(lines) 