"""
Win/Loss Tracker

Tracks win/loss ratios and trade outcomes for trading strategies:
- Win rate and loss rate per strategy
- Average win/loss amounts
- Longest winning/losing streaks
- Portfolio-wide aggregated statistics
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass

from .base_tracker import BaseTracker, TradeEvent

logger = logging.getLogger(__name__)

@dataclass
class TradeOutcome:
    """Represents the outcome of a completed trade"""
    timestamp: datetime
    strategy_id: str
    symbol: str
    pnl: float
    is_win: bool
    trade_value: float

class WinLossTracker(BaseTracker):
    """Tracks win/loss statistics across strategies"""
    
    def __init__(self):
        super().__init__()
        # Track trade outcomes by strategy
        self.trade_outcomes: Dict[str, List[TradeOutcome]] = defaultdict(list)
        # Track current positions for PnL calculation
        self.open_positions: Dict[str, Dict[str, dict]] = defaultdict(dict)
        # Track win/loss counts
        self.wins_by_strategy: Dict[str, int] = defaultdict(int)
        self.losses_by_strategy: Dict[str, int] = defaultdict(int)
        # Track win/loss amounts
        self.total_win_amount: Dict[str, float] = defaultdict(float)
        self.total_loss_amount: Dict[str, float] = defaultdict(float)
        # Track current streaks
        self.current_streak: Dict[str, int] = defaultdict(int)  # Positive for wins, negative for losses
        self.max_win_streak: Dict[str, int] = defaultdict(int)
        self.max_loss_streak: Dict[str, int] = defaultdict(int)
        
        logger.info("Win/Loss Tracker initialized")
    
    def on_trade_executed(self, trade_event: TradeEvent):
        """Process a trade execution"""
        strategy_id = trade_event.strategy_id
        symbol = trade_event.symbol
        
        if trade_event.action == 'buy':
            self._process_buy(trade_event)
        elif trade_event.action == 'sell':
            self._process_sell(trade_event)
        
        logger.debug(f"Processed {trade_event.action} trade for win/loss tracking: "
                    f"{strategy_id} {symbol} {trade_event.quantity} @ ${trade_event.price:.2f}")
    
    def _process_buy(self, trade_event: TradeEvent):
        """Process a buy trade - open or add to position"""
        strategy_id = trade_event.strategy_id
        symbol = trade_event.symbol
        
        total_cost = trade_event.quantity * trade_event.price + trade_event.commission
        
        if symbol in self.open_positions[strategy_id]:
            # Add to existing position
            position = self.open_positions[strategy_id][symbol]
            new_total_cost = position['total_cost'] + total_cost
            new_quantity = position['quantity'] + trade_event.quantity
            
            position['total_cost'] = new_total_cost
            position['quantity'] = new_quantity
            position['avg_cost'] = new_total_cost / new_quantity
        else:
            # Create new position
            self.open_positions[strategy_id][symbol] = {
                'quantity': trade_event.quantity,
                'total_cost': total_cost,
                'avg_cost': trade_event.price + (trade_event.commission / trade_event.quantity),
                'first_buy_timestamp': trade_event.timestamp
            }
    
    def _process_sell(self, trade_event: TradeEvent):
        """Process a sell trade - calculate win/loss"""
        strategy_id = trade_event.strategy_id
        symbol = trade_event.symbol
        
        if symbol not in self.open_positions[strategy_id]:
            logger.warning(f"Sell trade for {symbol} but no position found for {strategy_id}")
            return
        
        position = self.open_positions[strategy_id][symbol]
        sell_proceeds = trade_event.quantity * trade_event.price - trade_event.commission
        
        if trade_event.quantity >= position['quantity']:
            # Full position close
            cost_basis = position['total_cost']
            pnl = sell_proceeds - cost_basis
            trade_value = sell_proceeds
            
            # Record trade outcome
            self._record_trade_outcome(trade_event, pnl, trade_value)
            
            # Remove position
            del self.open_positions[strategy_id][symbol]
            
        else:
            # Partial position close
            close_ratio = trade_event.quantity / position['quantity']
            cost_basis = position['total_cost'] * close_ratio
            pnl = sell_proceeds - cost_basis
            trade_value = sell_proceeds
            
            # Record trade outcome for the closed portion
            self._record_trade_outcome(trade_event, pnl, trade_value)
            
            # Update remaining position
            position['quantity'] -= trade_event.quantity
            position['total_cost'] -= cost_basis
    
    def _record_trade_outcome(self, trade_event: TradeEvent, pnl: float, trade_value: float):
        """Record the outcome of a completed trade"""
        strategy_id = trade_event.strategy_id
        is_win = pnl > 0
        
        # Create trade outcome record
        outcome = TradeOutcome(
            timestamp=trade_event.timestamp,
            strategy_id=strategy_id,
            symbol=trade_event.symbol,
            pnl=pnl,
            is_win=is_win,
            trade_value=trade_value
        )
        
        self.trade_outcomes[strategy_id].append(outcome)
        
        # Update win/loss counts and amounts
        if is_win:
            self.wins_by_strategy[strategy_id] += 1
            self.total_win_amount[strategy_id] += pnl
            
            # Update streak tracking
            if self.current_streak[strategy_id] >= 0:
                self.current_streak[strategy_id] += 1
            else:
                self.current_streak[strategy_id] = 1
            
            self.max_win_streak[strategy_id] = max(
                self.max_win_streak[strategy_id], 
                self.current_streak[strategy_id]
            )
        else:
            self.losses_by_strategy[strategy_id] += 1
            self.total_loss_amount[strategy_id] += abs(pnl)
            
            # Update streak tracking
            if self.current_streak[strategy_id] <= 0:
                self.current_streak[strategy_id] -= 1
            else:
                self.current_streak[strategy_id] = -1
            
            self.max_loss_streak[strategy_id] = max(
                self.max_loss_streak[strategy_id], 
                abs(self.current_streak[strategy_id])
            )
        
        logger.info(f"Recorded trade outcome: {strategy_id} {trade_event.symbol} "
                   f"{'WIN' if is_win else 'LOSS'} ${pnl:.2f}")
    
    def on_portfolio_update(self, strategy_id: str, portfolio_value: float):
        """Handle portfolio value updates (not used for win/loss tracking)"""
        pass
    
    def get_current_stats(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
        """Get current win/loss statistics"""
        if strategy_id:
            return self._get_strategy_stats(strategy_id)
        else:
            return self._get_all_strategies_stats()
    
    def _get_strategy_stats(self, strategy_id: str) -> Dict[str, Any]:
        """Get win/loss stats for a specific strategy"""
        wins = self.wins_by_strategy.get(strategy_id, 0)
        losses = self.losses_by_strategy.get(strategy_id, 0)
        total_trades = wins + losses
        
        # Calculate rates
        win_rate = wins / total_trades if total_trades > 0 else 0.0
        loss_rate = losses / total_trades if total_trades > 0 else 0.0
        
        # Calculate average amounts
        total_win_amount = self.total_win_amount.get(strategy_id, 0.0)
        total_loss_amount = self.total_loss_amount.get(strategy_id, 0.0)
        avg_win = total_win_amount / wins if wins > 0 else 0.0
        avg_loss = total_loss_amount / losses if losses > 0 else 0.0
        
        # Calculate profit factor (total wins / total losses)
        profit_factor = total_win_amount / total_loss_amount if total_loss_amount > 0 else float('inf') if total_win_amount > 0 else 0.0
        
        return {
            'strategy_id': strategy_id,
            'wins': wins,
            'losses': losses,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'loss_rate': loss_rate,
            'total_win_amount': total_win_amount,
            'total_loss_amount': total_loss_amount,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'current_streak': self.current_streak.get(strategy_id, 0),
            'max_win_streak': self.max_win_streak.get(strategy_id, 0),
            'max_loss_streak': self.max_loss_streak.get(strategy_id, 0),
            'open_positions': len(self.open_positions.get(strategy_id, {}))
        }
    
    def _get_all_strategies_stats(self) -> Dict[str, Any]:
        """Get win/loss stats for all strategies"""
        all_strategies = (set(self.wins_by_strategy.keys()) | 
                         set(self.losses_by_strategy.keys()) | 
                         set(self.open_positions.keys()))
        
        strategy_stats = {}
        total_wins = 0
        total_losses = 0
        total_win_amount = 0.0
        total_loss_amount = 0.0
        max_win_streak_overall = 0
        max_loss_streak_overall = 0
        
        for strategy_id in all_strategies:
            stats = self._get_strategy_stats(strategy_id)
            strategy_stats[strategy_id] = stats
            
            total_wins += stats['wins']
            total_losses += stats['losses']
            total_win_amount += stats['total_win_amount']
            total_loss_amount += stats['total_loss_amount']
            max_win_streak_overall = max(max_win_streak_overall, stats['max_win_streak'])
            max_loss_streak_overall = max(max_loss_streak_overall, stats['max_loss_streak'])
        
        total_trades = total_wins + total_losses
        portfolio_win_rate = total_wins / total_trades if total_trades > 0 else 0.0
        portfolio_loss_rate = total_losses / total_trades if total_trades > 0 else 0.0
        portfolio_avg_win = total_win_amount / total_wins if total_wins > 0 else 0.0
        portfolio_avg_loss = total_loss_amount / total_losses if total_losses > 0 else 0.0
        portfolio_profit_factor = total_win_amount / total_loss_amount if total_loss_amount > 0 else float('inf') if total_win_amount > 0 else 0.0
        
        return {
            'strategies': strategy_stats,
            'portfolio_summary': {
                'total_wins': total_wins,
                'total_losses': total_losses,
                'total_trades': total_trades,
                'portfolio_win_rate': portfolio_win_rate,
                'portfolio_loss_rate': portfolio_loss_rate,
                'total_win_amount': total_win_amount,
                'total_loss_amount': total_loss_amount,
                'portfolio_avg_win': portfolio_avg_win,
                'portfolio_avg_loss': portfolio_avg_loss,
                'portfolio_profit_factor': portfolio_profit_factor,
                'max_win_streak_overall': max_win_streak_overall,
                'max_loss_streak_overall': max_loss_streak_overall,
                'total_open_positions': sum(len(positions) for positions in self.open_positions.values())
            }
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of win/loss tracking"""
        stats = self._get_all_strategies_stats()
        portfolio = stats['portfolio_summary']
        
        return {
            'tracker_type': 'WinLoss',
            'total_strategies': len(stats['strategies']),
            'portfolio_win_rate': portfolio['portfolio_win_rate'],
            'total_trades': portfolio['total_trades'],
            'profit_factor': portfolio['portfolio_profit_factor'],
            'open_positions': portfolio['total_open_positions']
        }
    
    def get_trade_outcomes(self, strategy_id: Optional[str] = None) -> List[TradeOutcome]:
        """Get trade outcome history"""
        if strategy_id:
            return self.trade_outcomes.get(strategy_id, []).copy()
        
        # Return all trade outcomes across all strategies
        all_outcomes = []
        for strategy_outcomes in self.trade_outcomes.values():
            all_outcomes.extend(strategy_outcomes)
        
        # Sort by timestamp
        return sorted(all_outcomes, key=lambda x: x.timestamp)
    
    def reset(self):
        """Reset all tracking data"""
        self.trade_outcomes.clear()
        self.open_positions.clear()
        self.wins_by_strategy.clear()
        self.losses_by_strategy.clear()
        self.total_win_amount.clear()
        self.total_loss_amount.clear()
        self.current_streak.clear()
        self.max_win_streak.clear()
        self.max_loss_streak.clear()
        logger.info("Win/Loss Tracker reset") 