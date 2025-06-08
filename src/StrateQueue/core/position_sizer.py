"""
Position Sizer

Broker-independent position sizing for trading signals.
Implements pluggable sizing algorithms following the strategy pattern.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from .signal_extractor import TradingSignal
from .portfolio_manager import SimplePortfolioManager

logger = logging.getLogger(__name__)


class PositionSizingStrategy(ABC):
    """Abstract base class for position sizing strategies"""

    @abstractmethod
    def calculate_size(
        self,
        strategy_id: str | None,
        symbol: str,
        signal: TradingSignal,
        price: float,
        portfolio_manager: SimplePortfolioManager | None = None,
        **kwargs
    ) -> float:
        """
        Calculate position size for a trading signal

        Args:
            strategy_id: Strategy identifier (None for single strategy)
            symbol: Trading symbol
            signal: Trading signal
            price: Current price
            portfolio_manager: Portfolio manager instance
            **kwargs: Additional parameters

        Returns:
            Position size in dollars
        """
        pass


class FixedDollarSizing(PositionSizingStrategy):
    """Fixed dollar amount per trade"""

    def __init__(self, amount: float = 100.0):
        """
        Initialize fixed dollar sizing

        Args:
            amount: Fixed dollar amount per trade
        """
        self.amount = amount

    def calculate_size(
        self,
        strategy_id: str | None,
        symbol: str,
        signal: TradingSignal,
        price: float,
        portfolio_manager: SimplePortfolioManager | None = None,
        **kwargs
    ) -> float:
        """Return fixed dollar amount"""
        return self.amount


class PercentOfCapitalSizing(PositionSizingStrategy):
    """Percentage of available capital per trade"""

    def __init__(self, percentage: float = 0.1, max_amount: float = 1000.0):
        """
        Initialize percent of capital sizing

        Args:
            percentage: Percentage of available capital (0.0 to 1.0)
            max_amount: Maximum dollar amount per trade
        """
        self.percentage = percentage
        self.max_amount = max_amount

    def calculate_size(
        self,
        strategy_id: str | None,
        symbol: str,
        signal: TradingSignal,
        price: float,
        portfolio_manager: SimplePortfolioManager | None = None,
        **kwargs
    ) -> float:
        """Calculate percentage of available capital"""
        if portfolio_manager and strategy_id:
            # Multi-strategy mode: get available capital for this strategy
            strategy_status = portfolio_manager.get_strategy_status(strategy_id)
            available_capital = strategy_status.get("available_capital", 100.0)
            position_size = available_capital * self.percentage
        else:
            # Single strategy mode: use default fallback
            # Could be enhanced to use account info if available
            available_capital = kwargs.get("account_value", 10000.0)
            position_size = available_capital * self.percentage

        # Apply maximum limit
        return min(position_size, self.max_amount)


class VolatilityBasedSizing(PositionSizingStrategy):
    """Position sizing based on volatility (ATR-based risk)"""

    def __init__(self, risk_per_trade: float = 0.02, fallback_sizing: PositionSizingStrategy = None):
        """
        Initialize volatility-based sizing

        Args:
            risk_per_trade: Risk percentage per trade (0.0 to 1.0)
            fallback_sizing: Fallback strategy if volatility data unavailable
        """
        self.risk_per_trade = risk_per_trade
        self.fallback_sizing = fallback_sizing or FixedDollarSizing(100.0)

    def calculate_size(
        self,
        strategy_id: str | None,
        symbol: str,
        signal: TradingSignal,
        price: float,
        portfolio_manager: SimplePortfolioManager | None = None,
        **kwargs
    ) -> float:
        """Calculate position size based on volatility"""
        # Check if ATR or volatility data is available in signal metadata
        atr = None
        if signal.metadata:
            atr = signal.metadata.get("atr") or signal.metadata.get("volatility")

        if atr and atr > 0:
            # Get available capital
            if portfolio_manager and strategy_id:
                strategy_status = portfolio_manager.get_strategy_status(strategy_id)
                available_capital = strategy_status.get("available_capital", 100.0)
            else:
                available_capital = kwargs.get("account_value", 10000.0)

            # Calculate position size based on risk
            # Risk per trade = position_size * (atr / price)
            # Therefore: position_size = (available_capital * risk_per_trade) / (atr / price)
            position_size = (available_capital * self.risk_per_trade * price) / atr
            return max(position_size, 10.0)  # Minimum $10 position
        else:
            # Fallback if no volatility data
            logger.debug(f"No volatility data for {symbol}, using fallback sizing")
            return self.fallback_sizing.calculate_size(
                strategy_id, symbol, signal, price, portfolio_manager, **kwargs
            )


class PositionSizer:
    """
    Main position sizing coordinator

    Uses pluggable strategies to determine position sizes for trading signals.
    """

    def __init__(self, strategy: PositionSizingStrategy = None):
        """
        Initialize position sizer

        Args:
            strategy: Position sizing strategy (defaults to PercentOfCapitalSizing)
        """
        self.strategy = strategy or PercentOfCapitalSizing()
        logger.info(f"Initialized position sizer with {self.strategy.__class__.__name__}")

    def get_position_size(
        self,
        strategy_id: str | None,
        symbol: str,
        signal: TradingSignal,
        price: float,
        portfolio_manager: SimplePortfolioManager | None = None,
        **kwargs
    ) -> float:
        """
        Get position size for a trading signal

        Args:
            strategy_id: Strategy identifier (None for single strategy)
            symbol: Trading symbol
            signal: Trading signal
            price: Current price
            portfolio_manager: Portfolio manager instance
            **kwargs: Additional parameters (e.g., account_value)

        Returns:
            Position size in dollars
        """
        try:
            # Check if signal already has a size specified
            if signal.size is not None and signal.size > 0:
                logger.debug(f"Using strategy-specified size for {symbol}: ${signal.size:.2f}")
                return signal.size

            # Calculate size using the configured strategy
            position_size = self.strategy.calculate_size(
                strategy_id, symbol, signal, price, portfolio_manager, **kwargs
            )

            logger.debug(
                f"Calculated position size for {symbol} using {self.strategy.__class__.__name__}: "
                f"${position_size:.2f}"
            )

            return max(position_size, 1.0)  # Ensure minimum $1 position

        except Exception as e:
            logger.error(f"Error calculating position size for {symbol}: {e}")
            # Emergency fallback
            return 100.0

    def set_strategy(self, strategy: PositionSizingStrategy):
        """
        Change the position sizing strategy

        Args:
            strategy: New position sizing strategy
        """
        old_strategy = self.strategy.__class__.__name__
        self.strategy = strategy
        logger.info(f"Changed position sizing strategy: {old_strategy} → {strategy.__class__.__name__}")


# Default instance for backward compatibility
default_position_sizer = PositionSizer() 