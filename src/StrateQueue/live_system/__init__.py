"""
Live Trading System Package

A modular package for live trading system orchestration with support for:
- Single and multi-strategy trading
- Real-time data processing
- Signal extraction and execution
- Performance monitoring and logging

Public API:
    LiveTradingSystem: Main system orchestrator
    DataManager: Handles data loading and updates
    TradingProcessor: Processes trading cycles
    DisplayManager: Handles output formatting and logging
"""

from .data_manager import DataManager
from .display_manager import DisplayManager
from .orchestrator import LiveTradingSystem
from .trading_processor import TradingProcessor

__all__ = ["LiveTradingSystem", "DataManager", "TradingProcessor", "DisplayManager"]
