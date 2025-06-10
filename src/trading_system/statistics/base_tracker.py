"""
Base Tracker

Abstract base class for all statistics trackers.
All stat trackers inherit from this and implement the required methods.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

@dataclass
class TradeEvent:
    """Represents a trade execution event"""
    timestamp: datetime
    strategy_id: str
    symbol: str
    action: str  # 'buy' or 'sell'
    quantity: float
    price: float
    commission: float = 0.0
    trade_id: Optional[str] = None

class BaseTracker(ABC):
    """Abstract base class for all statistics trackers"""
    
    def __init__(self):
        self.name = self.__class__.__name__
        
    @abstractmethod
    def on_trade_executed(self, trade_event: TradeEvent):
        """Called when a trade is executed"""
        pass
    
    @abstractmethod
    def on_portfolio_update(self, strategy_id: str, portfolio_value: float):
        """Called when portfolio value is updated"""
        pass
    
    @abstractmethod
    def get_current_stats(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
        """Get current statistics"""
        pass
    
    @abstractmethod
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all tracked statistics"""
        pass
    
    def reset(self):
        """Reset tracker state (optional to override)"""
        pass 