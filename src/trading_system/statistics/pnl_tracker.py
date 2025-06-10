"""
PnL Tracker

Tracks profit and loss for trading strategies:
- Realized PnL from completed trades
- Unrealized PnL from open positions
- Per-strategy and overall portfolio PnL
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass

from .base_tracker import BaseTracker, TradeEvent

logger = logging.getLogger(__name__)

@dataclass
class Position:
    """Tracks a position for PnL calculation"""
    symbol: str
    quantity: float
    total_cost: float
    avg_cost: float
    last_price: float = 0.0
    
    @property
    def market_value(self) -> float:
        return self.quantity * self.last_price
    
    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.total_cost

@dataclass
class Trade:
    """Completed trade for realized PnL calculation"""
    timestamp: datetime
    strategy_id: str
    symbol: str
    buy_quantity: float
    buy_price: float
    buy_cost: float
    sell_quantity: float
    sell_price: float
    sell_proceeds: float
    realized_pnl: float
    commission: float = 0.0

class PnLTracker(BaseTracker):
    """Tracks profit and loss across strategies and symbols"""
    
    def __init__(self):
        super().__init__()
        # Track positions by strategy and symbol
        self.positions: Dict[str, Dict[str, Position]] = defaultdict(dict)
        # Track completed trades
        self.completed_trades: List[Trade] = []
        # Track realized PnL by strategy
        self.realized_pnl: Dict[str, float] = defaultdict(float)
        # Track total commissions by strategy
        self.total_commissions: Dict[str, float] = defaultdict(float)
        
        logger.info("PnL Tracker initialized")
    
    def on_trade_executed(self, trade_event: TradeEvent):
        """Process a trade execution"""
        strategy_id = trade_event.strategy_id
        symbol = trade_event.symbol
        
        # Add commission to tracking
        self.total_commissions[strategy_id] += trade_event.commission
        
        if trade_event.action == 'buy':
            self._process_buy(trade_event)
        elif trade_event.action == 'sell':
            self._process_sell(trade_event)
        
        logger.debug(f"Processed {trade_event.action} trade: {strategy_id} {symbol} "
                    f"{trade_event.quantity} @ ${trade_event.price:.2f}")
    
    def _process_buy(self, trade_event: TradeEvent):
        """Process a buy trade"""
        strategy_id = trade_event.strategy_id
        symbol = trade_event.symbol
        
        total_cost = trade_event.quantity * trade_event.price + trade_event.commission
        
        if symbol in self.positions[strategy_id]:
            # Add to existing position
            position = self.positions[strategy_id][symbol]
            new_total_cost = position.total_cost + total_cost
            new_quantity = position.quantity + trade_event.quantity
            
            position.total_cost = new_total_cost
            position.quantity = new_quantity
            position.avg_cost = new_total_cost / new_quantity
        else:
            # Create new position
            self.positions[strategy_id][symbol] = Position(
                symbol=symbol,
                quantity=trade_event.quantity,
                total_cost=total_cost,
                avg_cost=trade_event.price + (trade_event.commission / trade_event.quantity)
            )
    
    def _process_sell(self, trade_event: TradeEvent):
        """Process a sell trade"""
        strategy_id = trade_event.strategy_id
        symbol = trade_event.symbol
        
        if symbol not in self.positions[strategy_id]:
            logger.warning(f"Sell trade for {symbol} but no position found for {strategy_id}")
            return
        
        position = self.positions[strategy_id][symbol]
        sell_proceeds = trade_event.quantity * trade_event.price - trade_event.commission
        
        if trade_event.quantity >= position.quantity:
            # Full position close
            cost_basis = position.total_cost
            realized_pnl = sell_proceeds - cost_basis
            
            # Record completed trade
            self._record_completed_trade(
                trade_event, position, 
                sell_proceeds, cost_basis, realized_pnl
            )
            
            # Update realized PnL
            self.realized_pnl[strategy_id] += realized_pnl
            
            # Remove position
            del self.positions[strategy_id][symbol]
            
        else:
            # Partial position close
            close_ratio = trade_event.quantity / position.quantity
            cost_basis = position.total_cost * close_ratio
            realized_pnl = sell_proceeds - cost_basis
            
            # Record completed trade
            self._record_completed_trade(
                trade_event, position,
                sell_proceeds, cost_basis, realized_pnl
            )
            
            # Update realized PnL
            self.realized_pnl[strategy_id] += realized_pnl
            
            # Update remaining position
            position.quantity -= trade_event.quantity
            position.total_cost -= cost_basis
    
    def _record_completed_trade(self, trade_event: TradeEvent, position: Position,
                               sell_proceeds: float, cost_basis: float, realized_pnl: float):
        """Record a completed trade"""
        trade = Trade(
            timestamp=trade_event.timestamp,
            strategy_id=trade_event.strategy_id,
            symbol=trade_event.symbol,
            buy_quantity=position.quantity,
            buy_price=position.avg_cost,
            buy_cost=cost_basis,
            sell_quantity=trade_event.quantity,
            sell_price=trade_event.price,
            sell_proceeds=sell_proceeds,
            realized_pnl=realized_pnl,
            commission=trade_event.commission
        )
        
        self.completed_trades.append(trade)
        logger.info(f"Completed trade: {trade_event.strategy_id} {trade_event.symbol} "
                   f"realized PnL: ${realized_pnl:.2f}")
    
    def on_portfolio_update(self, strategy_id: str, portfolio_value: float):
        """Update portfolio value for unrealized PnL calculations"""
        # This could be used for portfolio-level tracking
        # For now, we calculate unrealized PnL from individual positions
        pass
    
    def update_market_prices(self, prices: Dict[str, float]):
        """Update current market prices for unrealized PnL calculation"""
        updated_count = 0
        for strategy_id, strategy_positions in self.positions.items():
            for symbol, position in strategy_positions.items():
                if symbol in prices:
                    old_price = position.last_price
                    position.last_price = prices[symbol]
                    updated_count += 1
                    logger.info(f"📊 Updated {symbol} price for {strategy_id}: ${old_price:.2f} -> ${prices[symbol]:.2f}")
        
        if updated_count == 0 and prices:
            logger.warning(f"No positions matched for price update. Available prices: {list(prices.keys())}, Positions: {[(sid, list(pos.keys())) for sid, pos in self.positions.items()]}")
    
    def get_current_stats(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
        """Get current PnL statistics"""
        if strategy_id:
            return self._get_strategy_stats(strategy_id)
        else:
            return self._get_all_strategies_stats()
    
    def _get_strategy_stats(self, strategy_id: str) -> Dict[str, Any]:
        """Get PnL stats for a specific strategy"""
        realized_pnl = self.realized_pnl.get(strategy_id, 0.0)
        commissions = self.total_commissions.get(strategy_id, 0.0)
        
        # Calculate unrealized PnL from open positions
        unrealized_pnl = 0.0
        open_positions = []
        
        if strategy_id in self.positions:
            for symbol, position in self.positions[strategy_id].items():
                unrealized_pnl += position.unrealized_pnl
                open_positions.append({
                    'symbol': symbol,
                    'quantity': position.quantity,
                    'avg_cost': position.avg_cost,
                    'market_value': position.market_value,
                    'unrealized_pnl': position.unrealized_pnl
                })
        
        total_pnl = realized_pnl + unrealized_pnl
        net_pnl = total_pnl - commissions
        
        return {
            'strategy_id': strategy_id,
            'realized_pnl': realized_pnl,
            'unrealized_pnl': unrealized_pnl,
            'total_pnl': total_pnl,
            'commissions': commissions,
            'net_pnl': net_pnl,
            'open_positions': open_positions,
            'completed_trades_count': len([t for t in self.completed_trades if t.strategy_id == strategy_id])
        }
    
    def _get_all_strategies_stats(self) -> Dict[str, Any]:
        """Get PnL stats for all strategies"""
        all_strategies = set(self.realized_pnl.keys()) | set(self.positions.keys())
        
        strategy_stats = {}
        total_realized = 0.0
        total_unrealized = 0.0
        total_commissions = 0.0
        
        for strategy_id in all_strategies:
            stats = self._get_strategy_stats(strategy_id)
            strategy_stats[strategy_id] = stats
            total_realized += stats['realized_pnl']
            total_unrealized += stats['unrealized_pnl']
            total_commissions += stats['commissions']
        
        return {
            'strategies': strategy_stats,
            'portfolio_summary': {
                'total_realized_pnl': total_realized,
                'total_unrealized_pnl': total_unrealized,
                'total_pnl': total_realized + total_unrealized,
                'total_commissions': total_commissions,
                'net_pnl': total_realized + total_unrealized - total_commissions,
                'total_completed_trades': len(self.completed_trades)
            }
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of PnL tracking"""
        stats = self._get_all_strategies_stats()
        
        return {
            'tracker_type': 'PnL',
            'total_strategies': len(stats['strategies']),
            'portfolio_pnl': stats['portfolio_summary']['total_pnl'],
            'net_pnl': stats['portfolio_summary']['net_pnl'],
            'completed_trades': stats['portfolio_summary']['total_completed_trades'],
            'open_positions': sum(len(s['open_positions']) for s in stats['strategies'].values())
        }
    
    def get_trade_history(self, strategy_id: Optional[str] = None) -> List[Trade]:
        """Get completed trade history"""
        if strategy_id:
            return [t for t in self.completed_trades if t.strategy_id == strategy_id]
        return self.completed_trades.copy()
    
    def reset(self):
        """Reset all tracking data"""
        self.positions.clear()
        self.completed_trades.clear()
        self.realized_pnl.clear()
        self.total_commissions.clear()
        logger.info("PnL Tracker reset") 