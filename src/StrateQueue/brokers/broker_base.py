"""
Abstract Base Classes for Trading Brokers

Defines the common interface that all trading brokers must implement.
This allows different brokers (Alpaca, Interactive Brokers, etc.)
to be used interchangeably in the live trading system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from ..core.signal_extractor import TradingSignal
from ..core.position_sizer import PositionSizer, default_position_sizer


class OrderType(Enum):
    """Order type enumeration"""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"


class OrderSide(Enum):
    """Order side enumeration"""

    BUY = "BUY"
    SELL = "SELL"


@dataclass
class BrokerInfo:
    """Information about a trading broker"""

    name: str
    version: str
    supported_features: dict[str, bool]
    description: str
    supported_markets: list[str]  # e.g., ['stocks', 'crypto', 'options', 'futures']
    paper_trading: bool


@dataclass
class BrokerConfig:
    """Base configuration for broker connections"""

    broker_type: str
    paper_trading: bool = True
    credentials: dict[str, Any] = None
    timeout: int = 30
    additional_params: dict[str, Any] = None

    def __post_init__(self):
        if self.credentials is None:
            self.credentials = {}
        if self.additional_params is None:
            self.additional_params = {}


@dataclass
class AccountInfo:
    """Standardized account information structure"""

    account_id: str
    buying_power: float = 0.0
    total_value: float = 0.0
    cash: float = 0.0
    day_trade_count: int = 0
    pattern_day_trader: bool = False
    currency: str = "USD"
    additional_fields: dict[str, Any] = None

    def __post_init__(self):
        if self.additional_fields is None:
            self.additional_fields = {}


@dataclass
class Position:
    """Standardized position information structure"""

    symbol: str
    quantity: float
    market_value: float
    average_cost: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_percent: float = 0.0
    side: str = "long"  # 'long' or 'short'
    additional_fields: dict[str, Any] = None

    def __post_init__(self):
        if self.additional_fields is None:
            self.additional_fields = {}


@dataclass
class OrderResult:
    """Standardized order execution result"""

    success: bool
    order_id: str | None = None
    client_order_id: str | None = None
    message: str | None = None
    error_code: str | None = None
    timestamp: datetime | None = None
    broker_response: dict[str, Any] | None = None
    additional_fields: dict[str, Any] = None

    def __post_init__(self):
        if self.additional_fields is None:
            self.additional_fields = {}


class BaseBroker(ABC):
    """
    Abstract base class for trading brokers.
    Each broker (Alpaca, Interactive Brokers, etc.) will implement this interface.
    """

    def __init__(self, config: BrokerConfig, portfolio_manager=None, position_sizer: PositionSizer = None):
        self.config = config
        self.portfolio_manager = portfolio_manager
        self.position_sizer = position_sizer or default_position_sizer
        self.is_connected = False

    @abstractmethod
    def get_broker_info(self) -> BrokerInfo:
        """Get information about this broker"""
        pass

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the broker

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect from the broker"""
        pass

    @abstractmethod
    def validate_credentials(self) -> bool:
        """
        Validate broker credentials without establishing full connection

        Returns:
            True if credentials are valid
        """
        pass

    @abstractmethod
    def execute_signal(self, symbol: str, signal: TradingSignal) -> OrderResult:
        """
        Execute a trading signal

        Args:
            symbol: Symbol to trade
            signal: Trading signal to execute

        Returns:
            OrderResult with execution status and details
        """
        pass

    @abstractmethod
    def get_account_info(self) -> AccountInfo | None:
        """
        Get account information

        Returns:
            AccountInfo object or None if error
        """
        pass

    @abstractmethod
    def get_positions(self) -> dict[str, Position]:
        """
        Get current positions

        Returns:
            Dictionary mapping symbol to Position object
        """
        pass

    @abstractmethod
    def get_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """
        Get open orders

        Args:
            symbol: Optional symbol filter

        Returns:
            List of order dictionaries
        """
        pass

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        order_type: "OrderType",
        side: "OrderSide",
        quantity: float,
        price: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> OrderResult:
        """
        Place an order

        Args:
            symbol: Symbol to trade
            order_type: Type of order (MARKET, LIMIT, etc.)
            side: Order side (BUY, SELL)
            quantity: Quantity to trade
            price: Price for limit orders
            metadata: Additional order metadata

        Returns:
            OrderResult with execution status
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancellation successful
        """
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> dict[str, Any] | None:
        """
        Get order status

        Args:
            order_id: Order ID to check

        Returns:
            Order status dictionary or None if not found
        """
        pass

    @abstractmethod
    def cancel_all_orders(self) -> bool:
        """
        Cancel all open orders

        Returns:
            True if cancellation successful
        """
        pass

    @abstractmethod
    def replace_order(self, order_id: str, **updates) -> bool:
        """
        Replace/modify an existing order

        Args:
            order_id: Order ID to modify
            **updates: Fields to update (qty, limit_price, stop_price, etc.)

        Returns:
            True if modification successful
        """
        pass

    @abstractmethod
    def close_all_positions(self) -> bool:
        """
        Close all open positions

        Returns:
            True if successful
        """
        pass

    def supports_feature(self, feature: str) -> bool:
        """
        Check if broker supports a specific feature

        Args:
            feature: Feature name to check

        Returns:
            True if feature is supported
        """
        broker_info = self.get_broker_info()
        return broker_info.supported_features.get(feature, False)

    def supports_market(self, market: str) -> bool:
        """
        Check if broker supports a specific market

        Args:
            market: Market type ('stocks', 'crypto', 'options', 'futures')

        Returns:
            True if market is supported
        """
        broker_info = self.get_broker_info()
        return market.lower() in [m.lower() for m in broker_info.supported_markets]

    def get_status(self) -> dict[str, Any]:
        """
        Get broker connection status and basic info

        Returns:
            Status dictionary
        """
        return {
            "connected": self.is_connected,
            "broker_type": self.config.broker_type,
            "paper_trading": self.config.paper_trading,
            "broker_info": self.get_broker_info(),
        }
