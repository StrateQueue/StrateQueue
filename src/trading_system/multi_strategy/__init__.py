"""
Multi-Strategy Trading Package

A modular package for coordinating multiple trading strategies with:
- Strategy configuration and lifecycle management
- Signal coordination and validation
- Portfolio integration and capital allocation
- Performance monitoring and reporting

Public API:
    MultiStrategyRunner: Main strategy coordinator
    StrategyConfig: Configuration dataclass for strategies
    ConfigManager: Handles loading and parsing of strategy configurations
    SignalCoordinator: Manages signal generation and validation
    PortfolioIntegrator: Handles portfolio management integration
"""

from .runner import MultiStrategyRunner
from .config import StrategyConfig, ConfigManager
from .signal_coordinator import SignalCoordinator
from .portfolio_integrator import PortfolioIntegrator

__all__ = [
    'MultiStrategyRunner',
    'StrategyConfig',
    'ConfigManager',
    'SignalCoordinator',
    'PortfolioIntegrator'
] 