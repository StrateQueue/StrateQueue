"""
Alpaca Broker Implementation

Alpaca broker implementation that conforms to the BaseBroker interface.
This refactors the existing AlpacaExecutor to fit the new broker factory pattern.
"""

import logging
import sys
from datetime import datetime
from typing import Any

try:
    # Filter out the bin directory from sys.path during import to avoid conflicts
    # This prevents conflicts with unrelated alpaca.py files in system bin directories
    original_path = sys.path[:]
    sys.path = [p for p in sys.path if "/bin" not in p]

    from alpaca.common.exceptions import APIError
    from alpaca.trading.client import TradingClient

    # Restore original path
    sys.path = original_path

    ALPACA_AVAILABLE = True
except ImportError:
    # Restore original path in case of error
    sys.path = original_path if "original_path" in locals() else sys.path
    ALPACA_AVAILABLE = False

    # Create dummy classes for graceful fallback
    class TradingClient:
        def __init__(self, *args, **kwargs):
            raise ImportError("alpaca-trade-api not installed")

    class APIError(Exception):
        pass


from ...core.signal_extractor import SignalType, TradingSignal
from ..broker_base import (
    AccountInfo,
    BaseBroker,
    BrokerConfig,
    BrokerInfo,
    OrderResult,
    OrderSide,
    OrderType,
    Position,
)
from ...utils.crypto_pairs import ALPACA_CRYPTO_SYMBOLS, to_alpaca_pair

# Define Alpaca-specific components inline since legacy code was removed
if ALPACA_AVAILABLE:
    # Inline AlpacaConfig and PositionSizeConfig since legacy code removed
    class AlpacaConfig:
        def __init__(
            self, api_key: str, secret_key: str, base_url: str | None = None, paper: bool = True
        ):
            self.api_key = api_key
            self.secret_key = secret_key
            self.base_url = base_url
            self.paper = paper

    class PositionSizeConfig:
        def __init__(
            self, default_position_size: float = 100.0, max_position_size: float = 10000.0
        ):
            self.default_position_size = default_position_size
            self.max_position_size = max_position_size

    # Simple crypto symbol normalization function
    def normalize_crypto_symbol(symbol: str) -> str:
        """Normalize crypto symbols for Alpaca format"""
        # Reuse centralised helper to avoid symbol drift
        symbol_upper = symbol.upper()

        # Already pair – just normalise case via helper
        if "/" in symbol_upper:
            return to_alpaca_pair(symbol_upper)

        # Crypto symbol – convert using helper
        if symbol_upper in ALPACA_CRYPTO_SYMBOLS:
            return to_alpaca_pair(symbol_upper)

        # Non-crypto instruments (e.g., equities)
        return symbol_upper


logger = logging.getLogger(__name__)


class AlpacaBroker(BaseBroker):
    """
    Alpaca broker implementation for live trading.

    Handles the actual execution of trading signals through the Alpaca API using
    a modular order execution system. Supports multi-strategy trading with portfolio
    management and conflict prevention.
    """

    def __init__(self, config: BrokerConfig, portfolio_manager=None, statistics_manager=None, position_sizer=None):
        """
        Initialize Alpaca broker

        Args:
            config: Broker configuration
            portfolio_manager: Optional portfolio manager for multi-strategy support
            statistics_manager: Optional statistics manager for trade tracking
            position_sizer: Optional position sizer for calculating trade sizes
        """
        if not ALPACA_AVAILABLE:
            raise ImportError(
                "alpaca-trade-api not installed. Please reinstall the package: pip install stratequeue"
            )

        super().__init__(config, portfolio_manager, position_sizer)

        # Store statistics manager
        self.statistics_manager = statistics_manager

        # Create Alpaca-specific config from broker config
        self.alpaca_config = self._create_alpaca_config(config)
        self.position_config = PositionSizeConfig()  # Default position sizing

        # Initialize Alpaca trading client (will be set in connect())
        self.trading_client = None

        # Order executors (will be initialized in connect())
        self.order_executors = {}

        # Track pending orders and order counter for unique IDs
        self.pending_orders = {}
        self.order_counter = 0

    def _create_alpaca_config(self, config: BrokerConfig) -> "AlpacaConfig":
        """Convert BrokerConfig to AlpacaConfig"""
        return AlpacaConfig(
            api_key=config.credentials.get("api_key"),
            secret_key=config.credentials.get("secret_key"),
            base_url=config.credentials.get("base_url"),
            paper=config.paper_trading,
        )

    def get_broker_info(self) -> BrokerInfo:
        """Get information about the Alpaca broker"""
        return BrokerInfo(
            name="Alpaca",
            version="2.0.0",
            supported_features={
                "market_orders": True,
                "limit_orders": True,
                "stop_orders": True,
                "stop_limit_orders": True,
                "trailing_stop_orders": True,
                "bracket_orders": True,
                "oco_orders": True,
                "oto_orders": True,
                "cancel_all_orders": True,
                "replace_orders": True,
                "close_all_positions": True,
                "ioc_orders": True,
                "fok_orders": True,
                "opg_orders": True,
                "cls_orders": True,
                "extended_hours": True,
                "fractional_shares": True,
                "crypto_trading": True,
                "options_trading": False,
                "futures_trading": False,
                "multi_strategy": True,
                "paper_trading": True,
            },
            description="Commission-free stock and crypto trading",
            supported_markets=["stocks", "crypto"],
            paper_trading=self.config.paper_trading,
        )

    def connect(self) -> bool:
        """
        Establish connection to Alpaca API

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Initialize Alpaca trading client
            self.trading_client = TradingClient(
                api_key=self.alpaca_config.api_key,
                secret_key=self.alpaca_config.secret_key,
                paper=self.config.paper_trading,
                url_override=self.alpaca_config.base_url if self.alpaca_config.base_url else None,
            )

            # Initialize order executors
            self._init_order_executors()

            # Validate connection
            return self._validate_connection()

        except Exception as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        """Disconnect from Alpaca API"""
        self.trading_client = None
        self.order_executors = {}
        self.is_connected = False
        logger.info("Disconnected from Alpaca")

    def validate_credentials(self) -> bool:
        """
        Validate Alpaca credentials without establishing full connection

        Returns:
            True if credentials are valid
        """
        try:
            # Create temporary client to test credentials
            temp_client = TradingClient(
                api_key=self.alpaca_config.api_key,
                secret_key=self.alpaca_config.secret_key,
                paper=self.config.paper_trading,
                url_override=self.alpaca_config.base_url if self.alpaca_config.base_url else None,
            )

            # Try to get account info as credential validation
            account = temp_client.get_account()
            logger.info(f"Alpaca credentials validated for account: {account.id}")
            return True

        except APIError as e:
            logger.error(f"Alpaca credential validation failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Error validating Alpaca credentials: {e}")
            return False

    def execute_signal(self, symbol: str, signal: TradingSignal) -> OrderResult:
        """
        Execute a trading signal

        Args:
            symbol: Symbol to trade
            signal: Trading signal to execute

        Returns:
            OrderResult with execution status and details
        """
        if not self.is_connected:
            return OrderResult(success=False, message="Not connected to Alpaca")

        try:
            # Normalize symbol for Alpaca format
            alpaca_symbol = normalize_crypto_symbol(symbol)

            strategy_id = getattr(signal, "strategy_id", None)
            strategy_info = f" [{strategy_id}]" if strategy_id else ""

            logger.info(
                f"Executing signal{strategy_info} for {symbol} ({alpaca_symbol}): "
                f"{signal.signal.value} @ ${signal.price:.2f}"
            )

            # Validate portfolio constraints if in multi-strategy mode
            is_valid, reason = self._validate_portfolio_constraints(alpaca_symbol, signal)
            if not is_valid:
                logger.warning(f"❌ Signal blocked{strategy_info} for {symbol}: {reason}")
                return OrderResult(
                    success=False, message=f"Portfolio constraint violation: {reason}"
                )

                # Handle HOLD signals
            if signal.signal == SignalType.HOLD:
                logger.debug(f"HOLD signal for {symbol} - no action needed")
                return OrderResult(success=True)

            # Check if signal type is supported
            supported_signals = self.order_executors.get("supported_signal_types", [])
            if signal.signal not in supported_signals:
                error_msg = f"Unknown signal type: {signal.signal}"
                logger.warning(error_msg)
                return OrderResult(success=False, message=error_msg)

            # Generate client order ID
            client_order_id = self._generate_client_order_id(strategy_id)

            # Execute the order using simplified direct API call
            success, order_id = self._execute_signal_direct(
                alpaca_symbol, signal, client_order_id, strategy_id
            )

            if success and order_id:
                self.pending_orders[alpaca_symbol] = order_id

            return OrderResult(
                success=success,
                order_id=order_id,
                client_order_id=client_order_id,
                timestamp=datetime.now(),
                message=None if success else "Order execution failed",
            )

        except Exception as e:
            error_msg = f"Error executing signal for {symbol}: {e}"
            logger.error(error_msg)
            return OrderResult(success=False, message=error_msg)

    def get_account_info(self) -> AccountInfo | None:
        """
        Get account information

        Returns:
            AccountInfo object or None if error
        """
        if not self.is_connected:
            return None

        try:
            account = self.trading_client.get_account()
            return AccountInfo(
                account_id=account.id,
                total_value=float(account.portfolio_value),
                cash=float(account.cash),
                buying_power=float(account.buying_power),
                day_trade_count=account.daytrade_count,
                pattern_day_trader=account.pattern_day_trader,
                currency="USD",
            )
        except APIError as e:
            logger.error(f"Error getting Alpaca account info: {e}")
            return None

    def get_positions(self) -> dict[str, Position]:
        """
        Get current positions

        Returns:
            Dictionary mapping symbol to Position object
        """
        if not self.is_connected:
            return {}

        try:
            positions = self.trading_client.get_all_positions()
            result = {}
            for position in positions:
                qty = float(position.qty)
                result[position.symbol] = Position(
                    symbol=position.symbol,
                    quantity=qty,
                    market_value=float(position.market_value),
                    average_cost=float(position.avg_entry_price),
                    unrealized_pnl=float(position.unrealized_pl),
                    unrealized_pnl_percent=float(position.unrealized_plpc),
                    side="long" if qty > 0 else "short",
                )
            return result
        except APIError as e:
            logger.error(f"Error getting Alpaca positions: {e}")
            return {}

    def get_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """
        Get open orders

        Args:
            symbol: Optional symbol filter

        Returns:
            List of order dictionaries
        """
        if not self.is_connected:
            return []

        try:
            if symbol:
                orders = self.trading_client.get_orders(symbol=symbol)
            else:
                orders = self.trading_client.get_orders()

            result = []
            for order in orders:
                result.append(
                    {
                        "id": order.id,
                        "client_order_id": order.client_order_id,
                        "symbol": order.symbol,
                        "side": order.side.value,
                        "order_type": order.order_type.value,
                        "qty": float(order.qty) if order.qty else None,
                        "notional": float(order.notional) if order.notional else None,
                        "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
                        "status": order.status.value,
                        "created_at": order.created_at,
                        "updated_at": order.updated_at,
                    }
                )
            return result

        except APIError as e:
            logger.error(f"Error getting Alpaca orders: {e}")
            return []

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
        Place an order through Alpaca with full order type support

        Args:
            symbol: Symbol to trade
            order_type: Type of order (MARKET, LIMIT, STOP, STOP_LIMIT, TRAILING_STOP)
            side: Order side (BUY, SELL)
            quantity: Quantity to trade
            price: Price for limit orders / stop price for stop orders
            metadata: Additional order metadata (stop_price, limit_price, trail_percent, etc.)

        Returns:
            OrderResult with execution status
        """
        if not self.is_connected:
            return OrderResult(success=False, message="Not connected to Alpaca")

        try:
            from alpaca.trading.enums import OrderSide as AlpacaOrderSide
            from alpaca.trading.enums import TimeInForce
            from alpaca.trading.requests import (
                LimitOrderRequest,
                MarketOrderRequest,
                StopLimitOrderRequest,
                StopOrderRequest,
                TrailingStopOrderRequest,
            )

            # Convert enums to Alpaca format
            alpaca_side = AlpacaOrderSide.BUY if side.value == "BUY" else AlpacaOrderSide.SELL

            # Normalize symbol
            alpaca_symbol = normalize_crypto_symbol(symbol)

            # Parse metadata for additional parameters
            metadata = metadata or {}
            stop_price = metadata.get("stop_price", price)
            limit_price = metadata.get("limit_price", price)
            trail_percent = metadata.get("trail_percent")
            trail_amount = metadata.get("trail_amount")
            time_in_force_str = metadata.get("time_in_force", "day")
            extended_hours = metadata.get("extended_hours", False)
            order_class = metadata.get("order_class")
            take_profit = metadata.get("take_profit")
            stop_loss = metadata.get("stop_loss")

            # Map time in force
            tif_map = {
                "day": TimeInForce.DAY,
                "gtc": TimeInForce.GTC,
                "ioc": TimeInForce.IOC,
                "fok": TimeInForce.FOK,
                "opg": TimeInForce.OPG,
                "cls": TimeInForce.CLS,
            }
            time_in_force = tif_map.get(time_in_force_str.lower(), TimeInForce.DAY)

            # Override for crypto
            is_crypto = "/" in alpaca_symbol
            if is_crypto:
                time_in_force = TimeInForce.GTC
                extended_hours = False  # Not applicable for crypto

            # Base parameters for all order types
            base_params = {
                "symbol": alpaca_symbol,
                "qty": float(quantity),
                "side": alpaca_side,
                "time_in_force": time_in_force,
                "extended_hours": extended_hours,
            }

            # Add order class parameters if present
            if order_class:
                base_params["order_class"] = order_class
                if take_profit:
                    base_params["take_profit"] = take_profit
                if stop_loss:
                    base_params["stop_loss"] = stop_loss

            # Create order request based on order type
            order_request = None

            if order_type.value == "MARKET":
                order_request = MarketOrderRequest(**base_params)

            elif order_type.value == "LIMIT":
                if not limit_price:
                    return OrderResult(
                        success=False,
                        error_code="MISSING_PRICE",
                        message="Limit orders require a limit_price",
                    )
                base_params["limit_price"] = float(limit_price)
                order_request = LimitOrderRequest(**base_params)

            elif order_type.value == "STOP":
                if not stop_price:
                    return OrderResult(
                        success=False,
                        error_code="MISSING_STOP_PRICE",
                        message="Stop orders require a stop_price",
                    )
                base_params["stop_price"] = float(stop_price)
                order_request = StopOrderRequest(**base_params)

            elif order_type.value == "STOP_LIMIT":
                if not stop_price or not limit_price:
                    return OrderResult(
                        success=False,
                        error_code="MISSING_PRICES",
                        message="Stop-limit orders require both stop_price and limit_price",
                    )
                base_params["stop_price"] = float(stop_price)
                base_params["limit_price"] = float(limit_price)
                order_request = StopLimitOrderRequest(**base_params)

            elif order_type.value == "TRAILING_STOP":
                if trail_percent:
                    base_params["trail_percent"] = float(trail_percent)
                elif trail_amount:
                    base_params["trail_amount"] = float(trail_amount)
                else:
                    return OrderResult(
                        success=False,
                        error_code="MISSING_TRAIL_PARAMS",
                        message="Trailing stop orders require trail_percent or trail_amount",
                    )
                order_request = TrailingStopOrderRequest(**base_params)

            else:
                return OrderResult(
                    success=False,
                    error_code="UNSUPPORTED_ORDER_TYPE",
                    message=f"Unsupported order type: {order_type.value}",
                )

            # Submit order
            order = self.trading_client.submit_order(order_request)

            return OrderResult(
                success=True,
                order_id=order.id,
                client_order_id=order.client_order_id,
                message="Order submitted successfully",
                broker_response={"order": order.__dict__},
            )

        except Exception as e:
            logger.error(f"Error placing Alpaca order: {e}")
            return OrderResult(success=False, error_code="ORDER_FAILED", message=str(e))

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancellation successful
        """
        if not self.is_connected:
            return False

        try:
            self.trading_client.cancel_order_by_id(order_id)
            logger.info(f"Successfully cancelled Alpaca order: {order_id}")
            return True
        except APIError as e:
            logger.error(f"Error cancelling Alpaca order {order_id}: {e}")
            return False

    def get_order_status(self, order_id: str) -> dict[str, Any] | None:
        """
        Get order status

        Args:
            order_id: Order ID to check

        Returns:
            Order status dictionary or None if not found
        """
        if not self.is_connected:
            return None

        try:
            order = self.trading_client.get_order_by_id(order_id)
            return {
                "id": order.id,
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "side": order.side.value,
                "order_type": order.order_type.value,
                "qty": float(order.qty) if order.qty else None,
                "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
                "status": order.status.value,
                "created_at": order.created_at,
                "updated_at": order.updated_at,
            }
        except APIError as e:
            logger.error(f"Error getting Alpaca order status {order_id}: {e}")
            return None

    def cancel_all_orders(self) -> bool:
        """
        Cancel all open orders

        Returns:
            True if cancellation successful
        """
        if not self.is_connected:
            return False

        try:
            self.trading_client.cancel_orders()
            logger.info("✅ Successfully cancelled all open Alpaca orders")
            return True
        except APIError as e:
            logger.error(f"❌ Error cancelling all Alpaca orders: {e}")
            return False

    def replace_order(self, order_id: str, **updates) -> bool:
        """
        Replace/modify an existing order

        Args:
            order_id: Order ID to modify
            **updates: Fields to update (qty, limit_price, stop_price, etc.)

        Returns:
            True if modification successful
        """
        if not self.is_connected:
            return False

        try:
            from alpaca.trading.requests import ReplaceOrderRequest

            # Convert updates to Alpaca format
            replace_request = ReplaceOrderRequest(**updates)

            self.trading_client.replace_order_by_id(order_id, replace_request)
            logger.info(f"✅ Successfully replaced Alpaca order: {order_id}")
            return True
        except APIError as e:
            logger.error(f"❌ Error replacing Alpaca order {order_id}: {e}")
            return False

    def close_all_positions(self) -> bool:
        """
        Close all open positions

        Returns:
            True if successful
        """
        if not self.is_connected:
            return False

        try:
            self.trading_client.close_all_positions(cancel_orders=True)
            logger.info("✅ Successfully closed all Alpaca positions")
            return True
        except APIError as e:
            logger.error(f"❌ Error closing all Alpaca positions: {e}")
            return False

    def _init_order_executors(self):
        """Initialize simplified order execution system"""
        # Simplified - use direct Alpaca API calls instead of complex executor classes
        self.order_executors = {
            "supported_signal_types": [
                SignalType.BUY,
                SignalType.SELL,
                SignalType.CLOSE,
                SignalType.LIMIT_BUY,
                SignalType.LIMIT_SELL,
                SignalType.STOP_BUY,
                SignalType.STOP_SELL,
                SignalType.STOP_LIMIT_BUY,
                SignalType.STOP_LIMIT_SELL,
                SignalType.TRAILING_STOP_SELL,
            ]
        }

    def _execute_signal_direct(
        self, symbol: str, signal: TradingSignal, client_order_id: str, strategy_id: str | None
    ) -> tuple[bool, str | None]:
        """
        Execute signal using direct Alpaca API calls with full order type support

        Args:
            symbol: Symbol to trade
            signal: Trading signal
            client_order_id: Unique client order ID
            strategy_id: Optional strategy ID

        Returns:
            Tuple of (success: bool, order_id: Optional[str])
        """
        try:
            from alpaca.trading.enums import OrderSide, TimeInForce
            from alpaca.trading.requests import (
                LimitOrderRequest,
                MarketOrderRequest,
                StopLimitOrderRequest,
                StopOrderRequest,
                TrailingStopOrderRequest,
            )

            logger.info(f"🔄 Processing {signal.signal.value} order for symbol: {symbol}")

            # Calculate position size using broker-independent position sizer
            if signal.size is not None and signal.size > 0:
                # If size is < 1, treat as percentage of account value
                if signal.size < 1.0:
                    account_info = self.get_account_info()
                    account_value = account_info.total_value if account_info else 10000.0
                    position_size = signal.size * account_value
                    logger.info(f"💰 Using strategy-specified position size: {signal.size*100:.1f}% = ${position_size:.2f}")
                else:
                    # Strategy has specified the exact dollar size to use
                    position_size = signal.size
                    logger.info(f"💰 Using strategy-specified position size: ${position_size:.2f}")
            else:
                # Use position sizer to calculate appropriate size
                account_info = self.get_account_info()
                account_value = account_info.total_value if account_info else 10000.0
                
                position_size = self.position_sizer.get_position_size(
                    strategy_id=strategy_id,
                    symbol=symbol,
                    signal=signal,
                    price=signal.price,
                    portfolio_manager=self.portfolio_manager,
                    account_value=account_value
                )
                logger.info(f"💰 Position size calculated by {self.position_sizer.strategy.__class__.__name__}: ${position_size:.2f}")

            # Determine order side
            is_buy_signal = signal.signal in [
                SignalType.BUY,
                SignalType.LIMIT_BUY,
                SignalType.STOP_BUY,
                SignalType.STOP_LIMIT_BUY,
            ]
            side = OrderSide.BUY if is_buy_signal else OrderSide.SELL

            # Map time in force from signal
            tif_map = {
                "day": TimeInForce.DAY,
                "gtc": TimeInForce.GTC,
                "ioc": TimeInForce.IOC,
                "fok": TimeInForce.FOK,
                "opg": TimeInForce.OPG,
                "cls": TimeInForce.CLS,
            }
            time_in_force = tif_map.get(signal.time_in_force.lower(), TimeInForce.DAY)

            # Determine if crypto and extended-hours settings
            is_crypto = "/" in symbol  # Crypto pairs have "/" like "ETH/USD"
            # Strategy passes extended-hours in metadata: {'extended_hours': True}
            extended_hours = (signal.metadata or {}).get("extended_hours", False) and not is_crypto

            # Override time in force for crypto (must be GTC)
            if is_crypto:
                time_in_force = TimeInForce.GTC

            # Check for bracket/OCO/OTO order class signals
            tp = signal.metadata.get("tp") if signal.metadata else None
            sl = signal.metadata.get("sl") if signal.metadata else None

            order_class = None
            take_profit = None
            stop_loss = None

            if tp and sl:
                order_class = "bracket"
                take_profit = {"limit_price": tp}
                stop_loss = {"stop_price": sl}
            elif tp:
                order_class = "oto"
                take_profit = {"limit_price": tp}
            elif sl:
                order_class = "oto"
                stop_loss = {"stop_price": sl}
            elif signal.signal in [
                SignalType.LIMIT_SELL,
                SignalType.STOP_SELL,
                SignalType.STOP_LIMIT_SELL,
                SignalType.TRAILING_STOP_SELL,
            ] and (tp or sl):
                # Exit-side OCO when selling with both tp and sl
                if tp and sl:
                    order_class = "oco"
                    take_profit = {"limit_price": tp}
                    stop_loss = {"stop_price": sl}

            # Calculate quantity for the order
            quantity = None
            notional_amount = None

            if is_buy_signal:
                if is_crypto and signal.signal == SignalType.BUY:
                    # For crypto market buys, use notional amount (USD value)
                    notional_amount = round(position_size, 2)
                    logger.info(
                        f"📊 Creating crypto buy order: ${notional_amount:.2f} notional of {symbol}"
                    )
                else:
                    # For all other buys (stock or crypto limit), calculate quantity
                    quantity = position_size / signal.price if signal.price else 1
                    logger.info(
                        f"📊 Creating buy order: {quantity:.6f} {symbol} @ ${signal.price:.2f}"
                    )
            else:
                # For sell orders, get current position quantity
                try:
                    logger.info(f"🔍 Checking current position for {symbol}")
                    position = self.trading_client.get_open_position(symbol)
                    quantity = abs(float(position.qty))  # Ensure positive quantity
                    logger.info(f"📍 Found position: {quantity} shares/units of {symbol}")
                except Exception as e:
                    logger.error(f"❌ No position found for {symbol}: {e}")
                    return False, None

            # Build the order request based on signal type
            order_request = None

            # Common order parameters
            base_params = {
                "symbol": symbol,
                "side": side,
                "time_in_force": time_in_force,
                "client_order_id": client_order_id,
                "extended_hours": extended_hours,
            }

            # Add validate_only if present in metadata (for testing)
            metadata = signal.metadata or {}
            if metadata.get("validate_only"):
                base_params["validate_only"] = True

            # Add order class parameters if present
            if order_class:
                base_params["order_class"] = order_class
                if take_profit:
                    base_params["take_profit"] = take_profit
                if stop_loss:
                    base_params["stop_loss"] = stop_loss

            # Add quantity or notional
            if notional_amount:
                base_params["notional"] = notional_amount
            else:
                base_params["qty"] = quantity

            # Create order request based on signal type
            if signal.signal in [SignalType.BUY, SignalType.SELL, SignalType.CLOSE]:
                order_request = MarketOrderRequest(**base_params)

            elif signal.signal in [SignalType.LIMIT_BUY, SignalType.LIMIT_SELL]:
                base_params["limit_price"] = signal.limit_price or signal.price
                order_request = LimitOrderRequest(**base_params)

            elif signal.signal in [SignalType.STOP_BUY, SignalType.STOP_SELL]:
                base_params["stop_price"] = signal.stop_price or signal.price
                order_request = StopOrderRequest(**base_params)

            elif signal.signal in [SignalType.STOP_LIMIT_BUY, SignalType.STOP_LIMIT_SELL]:
                base_params["stop_price"] = signal.stop_price
                base_params["limit_price"] = signal.limit_price or signal.price
                order_request = StopLimitOrderRequest(**base_params)

            elif signal.signal == SignalType.TRAILING_STOP_SELL:
                if signal.trail_percent:
                    base_params["trail_percent"] = signal.trail_percent
                elif signal.trail_price:
                    base_params["trail_amount"] = signal.trail_price
                else:
                    # Default to 2% trailing stop
                    base_params["trail_percent"] = 2.0
                order_request = TrailingStopOrderRequest(**base_params)

            if not order_request:
                logger.error(
                    f"❌ Failed to create order request for {symbol} - unsupported signal: {signal.signal}"
                )
                return False, None

            # Submit the order with detailed logging
            logger.info(f"🚀 Submitting {signal.signal.value} order to Alpaca: {order_request}")
            order = self.trading_client.submit_order(order_request)
            logger.info("✅ Order submitted successfully!")
            logger.info(f"   Order ID: {order.id}")
            logger.info(f"   Symbol: {order.symbol}")
            logger.info(f"   Side: {order.side}")
            logger.info(f"   Type: {order.order_type}")
            logger.info(f"   Status: {order.status}")
            if order_class:
                logger.info(f"   Order Class: {order_class}")

            # Update portfolio manager if in multi-strategy mode
            if self.portfolio_manager and strategy_id:
                if is_buy_signal:
                    # For crypto notional orders, estimate quantity for portfolio tracking
                    if notional_amount:
                        estimated_quantity = notional_amount / signal.price if signal.price else 0
                        self.portfolio_manager.record_buy(
                            strategy_id, symbol, notional_amount, estimated_quantity
                        )
                        logger.info(
                            f"📝 Portfolio: Recorded buy {strategy_id} - ${notional_amount:.2f} (~{estimated_quantity:.6f} {symbol})"
                        )

                        # Record in statistics tracker
                        if self.statistics_manager:
                            self.statistics_manager.record_trade(
                                timestamp=datetime.now(),
                                strategy_id=strategy_id,
                                symbol=symbol,
                                action="buy",
                                quantity=estimated_quantity,
                                price=signal.price,
                                commission=0.0,  # Alpaca is commission-free
                            )
                    else:
                        self.portfolio_manager.record_buy(
                            strategy_id, symbol, position_size, quantity
                        )
                        logger.info(
                            f"📝 Portfolio: Recorded buy {strategy_id} - ${position_size:.2f} ({quantity:.6f} {symbol})"
                        )

                        # Record in statistics tracker
                        if self.statistics_manager:
                            self.statistics_manager.record_trade(
                                timestamp=datetime.now(),
                                strategy_id=strategy_id,
                                symbol=symbol,
                                action="buy",
                                quantity=quantity,
                                price=signal.price,
                                commission=0.0,  # Alpaca is commission-free
                            )
                else:
                    sell_value = quantity * signal.price if signal.price else None
                    self.portfolio_manager.record_sell(strategy_id, symbol, sell_value, quantity)
                    logger.info(
                        f"📝 Portfolio: Recorded sell {strategy_id} - {quantity:.6f} {symbol}"
                    )

                    # Record in statistics tracker
                    if self.statistics_manager:
                        self.statistics_manager.record_trade(
                            timestamp=datetime.now(),
                            strategy_id=strategy_id,
                            symbol=symbol,
                            action="sell",
                            quantity=quantity,
                            price=signal.price,
                            commission=0.0,  # Alpaca is commission-free
                        )

            # NEW: Always record the executed trade in statistics manager so that
            # metrics are available for single-strategy runs where no
            # portfolio_manager is present.
            if self.statistics_manager and not (self.portfolio_manager and strategy_id):
                # Ensure we have a quantity value (crypto market buys may only set notional)
                _qty = quantity
                if _qty is None and notional_amount is not None and signal.price:
                    _qty = notional_amount / signal.price
                if _qty is None:
                    _qty = 0.0  # Fallback to 0 to avoid NoneType
                self.statistics_manager.record_trade(
                    timestamp=datetime.now(),
                    strategy_id=strategy_id,
                    symbol=symbol,
                    action="buy" if is_buy_signal else "sell",
                    quantity=_qty,
                    price=signal.price,
                    commission=0.0,
                )

            return True, order.id

        except APIError as e:
            logger.error(f"❌ Alpaca API Error for {symbol}: {e}")
            logger.error(f"   Error Code: {getattr(e, 'code', 'Unknown')}")
            logger.error(f"   Error Message: {getattr(e, 'message', str(e))}")
            return False, None
        except Exception as e:
            logger.error(f"❌ Unexpected error executing order for {symbol}: {e}")
            logger.error(f"   Error Type: {type(e).__name__}")
            import traceback

            logger.error(f"   Traceback: {traceback.format_exc()}")
            return False, None

    def _generate_client_order_id(self, strategy_id: str | None = None) -> str:
        """
        Generate a unique client_order_id with optional strategy tagging

        Args:
            strategy_id: Optional strategy identifier for tagging

        Returns:
            Unique client_order_id string
        """
        self.order_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if strategy_id:
            # Format: strategy_timestamp_counter (max 128 chars)
            return f"{strategy_id}_{timestamp}_{self.order_counter:03d}"
        else:
            # Single strategy format
            return f"single_{timestamp}_{self.order_counter:03d}"

    def _validate_portfolio_constraints(
        self, symbol: str, signal: TradingSignal
    ) -> tuple[bool, str]:
        """
        Validate signal against portfolio constraints

        Args:
            symbol: Symbol to trade
            signal: Trading signal to validate

        Returns:
            Tuple of (is_valid: bool, reason: str)
        """
        if not self.portfolio_manager:
            return True, "No portfolio constraints (single strategy mode)"

        strategy_id = getattr(signal, "strategy_id", None)
        if not strategy_id:
            return False, "Signal missing strategy_id for multi-strategy mode"

        # Update portfolio manager with current account value
        try:
            account = self.trading_client.get_account()
            self.portfolio_manager.update_account_value(float(account.portfolio_value))
        except Exception as e:
            logger.warning(f"Could not update portfolio value: {e}")

        # Validate buy signals - multiple strategies can now buy the same symbol
        if signal.signal in [
            SignalType.BUY,
            SignalType.LIMIT_BUY,
            SignalType.STOP_BUY,
            SignalType.STOP_LIMIT_BUY,
        ]:

            # Just validate that strategy exists and has some allocation
            # Order executors will handle the specific amount calculation
            strategy_status = self.portfolio_manager.get_strategy_status(strategy_id)
            available_capital = strategy_status.get("available_capital", 0.0)

            if available_capital <= 0:
                return False, f"Strategy {strategy_id} has no available capital"

            return True, "Strategy has available capital"

        # Validate sell signals - check actual Alpaca positions for more reliable validation
        elif signal.signal in [
            SignalType.SELL,
            SignalType.CLOSE,
            SignalType.LIMIT_SELL,
            SignalType.STOP_SELL,
            SignalType.STOP_LIMIT_SELL,
            SignalType.TRAILING_STOP_SELL,
        ]:

            # First check if we have any position in Alpaca at all
            try:
                position = self.trading_client.get_open_position(symbol)
                if position is None or float(position.qty) <= 0:
                    return False, f"No Alpaca position found for {symbol}"

                # Now check portfolio manager's strategy-specific tracking
                # This is for capital allocation and multi-strategy coordination
                can_sell_portfolio, portfolio_reason = self.portfolio_manager.can_sell(
                    strategy_id, symbol, None
                )

                if not can_sell_portfolio:
                    # Portfolio manager says no, but we have Alpaca position
                    # This indicates a sync issue - let's log it but allow the trade
                    logger.warning(
                        f"Portfolio manager position tracking out of sync for {strategy_id}/{symbol}: {portfolio_reason}"
                    )
                    logger.warning(
                        f"Alpaca shows position: {float(position.qty)} shares, but portfolio manager disagrees"
                    )
                    logger.warning("Allowing sell based on actual Alpaca position")

                    # Create a position in portfolio manager to get back in sync
                    try:
                        position_value = float(position.market_value)
                        quantity = float(position.qty)
                        self.portfolio_manager.record_buy(
                            strategy_id, symbol, position_value, quantity
                        )
                        logger.info(
                            f"Synced portfolio manager: recorded {strategy_id} position of {quantity} {symbol} worth ${position_value:.2f}"
                        )
                    except Exception as sync_error:
                        logger.error(f"Failed to sync portfolio position: {sync_error}")

                return True, "Alpaca position validated"

            except Exception as e:
                # No position found in Alpaca
                if "position does not exist" in str(e).lower() or "not found" in str(e).lower():
                    return False, f"No position found in Alpaca for {symbol}"
                else:
                    logger.error(f"Error checking Alpaca position for {symbol}: {e}")
                    return False, f"Error validating position: {e}"

        # Hold signals are always valid
        return True, "OK"

    def _validate_connection(self) -> bool:
        """Validate connection to Alpaca API"""
        try:
            account = self.trading_client.get_account()
            logger.info(
                f"✅ Connected to Alpaca {'Paper' if self.config.paper_trading else 'Live'} Trading"
            )
            logger.info(f"Account ID: {account.id}")
            logger.info(f"Portfolio Value: ${float(account.portfolio_value):,.2f}")
            logger.info(f"Cash Balance: ${float(account.cash):,.2f}")
            logger.info(f"Day Trade Count: {account.daytrade_count}")
            self.is_connected = True
            return True
        except APIError as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            self.is_connected = False
            return False



