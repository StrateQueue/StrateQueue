"""
Interactive Brokers (IBKR) Broker Implementation

IBKR broker implementation that conforms to the BaseBroker interface.
Uses ib_insync for asyncio-friendly TWS/IB Gateway integration.
"""

import logging
import threading
from datetime import datetime
from typing import Any

try:
    from ib_insync import IB, util, Order
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False
    
    # Create dummy classes for graceful fallback
    class IB:
        def __init__(self, *args, **kwargs):
            raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
    
    class util:
        @staticmethod
        def startLoop():
            raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
    
    class Order:
        def __init__(self, *args, **kwargs):
            raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")

from ...core.signal_extractor import TradingSignal
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
from .contracts import stock_contract, crypto_contract, create_contract, detect_asset_type_heuristic
from .orders.order_manager import OrderManager
from .account.account_manager import AccountManager
from .account.position_manager import PositionManager

logger = logging.getLogger(__name__)


class IBKRBroker(BaseBroker):
    """
    Interactive Brokers broker implementation for live trading.
    
    Uses ib_insync to communicate with TWS or IB Gateway.
    Supports both paper and live trading modes.
    
    Key architectural decisions:
    - Maintains persistent connection to TWS/Gateway
    - Uses single event loop for all async operations
    - Delegates order management to OrderManager
    - Caches account/position data with periodic updates
    """

    def __init__(self, config: BrokerConfig, portfolio_manager=None, position_sizer=None):
        """
        Initialize IBKR broker
        
        Args:
            config: Broker configuration
            portfolio_manager: Optional portfolio manager for multi-strategy support
            position_sizer: Optional position sizer for calculating trade sizes
        """
        if not IB_INSYNC_AVAILABLE:
            raise ImportError(
                "ib_insync not installed. Please install with: pip install stratequeue[ibkr]"
            )

        # Start ib_insync's event loop once for the entire process
        util.startLoop()

        super().__init__(config, portfolio_manager, position_sizer)
        
        # Connection parameters
        self.host = config.credentials.get("host", "127.0.0.1")
        self.port = config.credentials.get("port", 7497)  # 7497 = paper, 7496 = live
        self.client_id = config.credentials.get("client_id", 1)
        
        # Initialize ib_insync client - persistent connection
        self.ib = IB()
        
        # Initialize managers
        self.order_manager = None
        self.account_manager = None
        self.position_manager = None
        
        # Connection state
        self._connection_lock = threading.Lock()
        
        logger.info(f"IBKR broker initialized - {self.host}:{self.port} (client_id={self.client_id})")

    def get_broker_info(self) -> BrokerInfo:
        """Get information about the IBKR broker"""
        return BrokerInfo(
            name="Interactive Brokers",
            version="1.0.0",
            supported_features={
                "market_orders": True,
                "limit_orders": True,
                "stop_orders": False,  # TODO: implement
                "stop_limit_orders": False,  # TODO: implement
                "trailing_stop_orders": False,  # TODO: implement
                "bracket_orders": False,  # TODO: implement
                "oco_orders": False,  # TODO: implement
                "oto_orders": False,  # TODO: implement
                "cancel_all_orders": False,  # TODO: implement
                "replace_orders": False,  # TODO: implement
                "close_all_positions": False,  # TODO: implement
                "ioc_orders": False,  # TODO: implement
                "fok_orders": False,  # TODO: implement
                "opg_orders": False,  # TODO: implement
                "cls_orders": False,  # TODO: implement
                "extended_hours": True,
                "fractional_shares": True,
                "crypto_trading": True,
                "options_trading": True,
                "futures_trading": True,
                "multi_strategy": True,
                "paper_trading": True,
            },
            description="Interactive Brokers TWS/IB Gateway integration",
            supported_markets=["stocks", "crypto", "options", "futures", "forex"],
            paper_trading=self.config.paper_trading,
        )

    def connect(self) -> bool:
        """
        Establish persistent connection to TWS/IB Gateway
        
        Returns:
            True if connection successful, False otherwise
        """
        with self._connection_lock:
            try:
                # Connect to TWS/IB Gateway
                logger.info(f"Connecting to IBKR at {self.host}:{self.port} (client_id={self.client_id})")
                
                self.ib.connect(
                    host=self.host,
                    port=self.port,
                    clientId=self.client_id,
                    timeout=10
                )
                
                self.is_connected = self.ib.isConnected()
                
                if self.is_connected:
                    # Initialize managers with connected client
                    self.order_manager = OrderManager(self.ib)
                    self.account_manager = AccountManager(self.ib)
                    self.position_manager = PositionManager(self.ib)
                    
                    trading_mode = "paper" if self.config.paper_trading else "live"
                    logger.info(f"✅ Connected to IBKR TWS/Gateway at {self.host}:{self.port} ({trading_mode} mode)")
                else:
                    logger.error("❌ Failed to connect to IBKR TWS/Gateway")
                    
                return self.is_connected
                
            except Exception as e:
                logger.error(f"IBKR connection failed: {e}")
                self.is_connected = False
                return False

    def disconnect(self):
        """Disconnect from TWS/IB Gateway and cleanup resources"""
        with self._connection_lock:
            try:
                if self.ib.isConnected():
                    self.ib.disconnect()
                    logger.info("Disconnected from IBKR TWS/Gateway")
                
                # Cleanup managers
                self.order_manager = None
                self.account_manager = None
                self.position_manager = None
                
            except Exception as e:
                logger.error(f"Error during IBKR disconnect: {e}")
            finally:
                self.is_connected = False

    def validate_credentials(self, keep_open: bool = False) -> bool:
        """
        Validate IBKR connection
        
        Args:
            keep_open: If True, keep connection open after validation
        
        Returns:
            True if credentials are valid
        """
        was_connected = self.is_connected
        
        try:
            # Connect if not already connected
            if not self.is_connected:
                if not self.connect():
                    return False
            
            # Try to get account summary as validation
            summary = self.ib.accountSummary()
            is_valid = len(summary) > 0
            
            if is_valid:
                logger.info("IBKR credentials validated successfully")
            else:
                logger.error("IBKR credential validation failed - no account data")
                
            return is_valid
            
        except Exception as e:
            logger.error(f"IBKR credential validation failed: {e}")
            return False
        finally:
            # Only disconnect if we weren't connected before AND keep_open is False
            if not was_connected and not keep_open:
                self.disconnect()

    def execute_signal(self, symbol: str, signal: TradingSignal) -> OrderResult:
        """
        Execute a trading signal using the OrderManager
        
        Args:
            symbol: Symbol to trade
            signal: Trading signal to execute
            
        Returns:
            OrderResult with execution status and details
        """
        if not self.is_connected or not self.order_manager:
            return OrderResult(
                success=False,
                message="Not connected to IBKR or OrderManager not initialized",
                timestamp=datetime.utcnow()
            )
        
        try:
            # Create contract with automatic security type detection
            from .contracts import create_contract_with_detection
            contract, security_type = create_contract_with_detection(self.ib, symbol)
            
            # Determine order parameters from signal
            signal_type = signal.signal.value if hasattr(signal.signal, 'value') else str(signal.signal)
            
            # Skip HOLD signals - they don't require any action
            if signal_type.upper() in ['HOLD', 'CLOSE']:
                return OrderResult(
                    success=True,
                    message=f"Signal {signal_type} processed - no action required",
                    timestamp=datetime.utcnow()
                )
            
            side = OrderSide.BUY if signal_type.upper() in ['BUY', 'LONG', 'LIMIT_BUY'] else OrderSide.SELL

            # ---------------- Position sizing ----------------
            account_value = self.get_account_value()

            if getattr(signal, 'size', None):
                # Strategy-supplied size
                if signal.size < 1.0:
                    position_size = signal.size * account_value
                else:
                    position_size = signal.size
            else:
                # Generic position sizer
                position_size = self.position_sizer.get_position_size(
                    strategy_id=None,
                    symbol=symbol,
                    signal=signal,
                    price=getattr(signal, 'price', 0.0),
                    portfolio_manager=self.portfolio_manager,
                    account_value=account_value,
                )

            # Handle quantity calculation based on security type
            if security_type == "CRYPTO":
                # For crypto, position_size is already in USD, use it directly as cashQty
                # Round to 2 decimals to conform to IBKR's minimum variation of 0.01
                quantity = round(position_size, 2)  # USD amount for crypto orders
                logger.info(f"Crypto order: Using ${quantity} USD for {symbol}")
            else:
                # For stocks, convert dollars to shares and round to whole shares
                price_for_qty = getattr(signal, 'price', 1.0) or 1.0
                quantity_float = position_size / price_for_qty
                quantity = max(1, int(round(quantity_float)))
                logger.info(f"Stock order: Using {quantity} shares for {symbol} (${position_size} / ${price_for_qty})")
            
            # Determine order type
            order_type = OrderType.MARKET
            price = None
            if getattr(signal, 'order_type', '').upper() == 'LIMIT':
                order_type = OrderType.LIMIT
                price = signal.price
            
            # Place order using OrderManager
            result = self.order_manager.place_order(
                contract=contract,
                order_type=order_type,
                side=side,
                quantity=quantity,
                price=price,
                security_type=security_type,
                metadata={
                    'signal_id': getattr(signal, 'id', None),
                    'strategy': getattr(signal, 'strategy', None),
                    'timestamp': signal.timestamp if hasattr(signal, 'timestamp') else datetime.utcnow(),
                }
            )
            
            if result.success:
                logger.info(f"✅ Successfully executed {side.value} signal for {symbol}: {quantity} shares")
            else:
                logger.error(f"❌ Failed to execute {side.value} signal for {symbol}: {result.message}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing signal for {symbol}: {e}")
            return OrderResult(
                success=False,
                message=str(e),
                timestamp=datetime.utcnow()
            )

    def get_account_info(self) -> AccountInfo | None:
        """
        Get account information using AccountManager
        
        Returns:
            AccountInfo object or None if error
        """
        if not self.is_connected or not self.account_manager:
            logger.error("Not connected to IBKR or AccountManager not initialized")
            return None
            
        try:
            return self.account_manager.get_account_info()
        except Exception as e:
            logger.error(f"Error getting IBKR account info: {e}")
            return None

    def get_account_value(self) -> float:
        """
        Get total account value
        
        Returns:
            Total account value or 0.0 if error
        """
        account_info = self.get_account_info()
        return account_info.total_value if account_info else 0.0

    def get_positions(self) -> dict[str, Position]:
        """
        Get current positions using PositionManager
        
        Returns:
            Dictionary mapping symbol to Position object
        """
        if not self.is_connected or not self.position_manager:
            logger.error("Not connected to IBKR or PositionManager not initialized")
            return {}
            
        try:
            return self.position_manager.get_positions()
        except Exception as e:
            logger.error(f"Error getting IBKR positions: {e}")
            return {}

    def get_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """
        Get open orders using OrderManager
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of order dictionaries
        """
        if not self.is_connected or not self.order_manager:
            logger.error("Not connected to IBKR or OrderManager not initialized")
            return []
            
        try:
            return self.order_manager.get_open_orders(symbol)
        except Exception as e:
            logger.error(f"Error getting IBKR orders: {e}")
            return []

    def place_order(
        self,
        symbol: str,
        order_type: OrderType,
        side: OrderSide,
        quantity: float,
        price: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> OrderResult:
        """
        Place an order using OrderManager
        
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
        if not self.is_connected or not self.order_manager:
            return OrderResult(
                success=False,
                message="Not connected to IBKR or OrderManager not initialized",
                timestamp=datetime.utcnow()
            )
        
        try:
            # Create contract with security type detection
            from .contracts import create_contract_with_detection
            contract, security_type = create_contract_with_detection(self.ib, symbol)
            
            # Use OrderManager to place the order
            return self.order_manager.place_order(
                contract=contract,
                order_type=order_type,
                side=side,
                quantity=quantity,
                price=price,
                security_type=security_type,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error placing IBKR order: {e}")
            return OrderResult(
                success=False,
                message=str(e),
                timestamp=datetime.utcnow()
            )

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order using OrderManager
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancellation successful
        """
        if not self.is_connected or not self.order_manager:
            logger.error("Not connected to IBKR or OrderManager not initialized")
            return False
            
        try:
            return self.order_manager.cancel_order(order_id)
        except Exception as e:
            logger.error(f"Error canceling IBKR order {order_id}: {e}")
            return False

    def get_order_status(self, order_id: str) -> dict[str, Any] | None:
        """
        Get order status using OrderManager
        
        Args:
            order_id: Order ID to check
            
        Returns:
            Order status dictionary or None if not found
        """
        if not self.is_connected or not self.order_manager:
            logger.error("Not connected to IBKR or OrderManager not initialized")
            return None
            
        try:
            return self.order_manager.get_order_status(order_id)
        except Exception as e:
            logger.error(f"Error getting IBKR order status for {order_id}: {e}")
            return None

    def cancel_all_orders(self) -> bool:
        """
        Cancel all open orders using OrderManager
        
        Returns:
            True if cancellation successful
        """
        if not self.is_connected or not self.order_manager:
            logger.error("Not connected to IBKR or OrderManager not initialized")
            return False
            
        try:
            return self.order_manager.cancel_all_orders()
        except Exception as e:
            logger.error(f"Error canceling all IBKR orders: {e}")
            return False

    def replace_order(self, order_id: str, **updates) -> bool:
        """
        Replace/modify an existing order
        
        Args:
            order_id: Order ID to modify
            **updates: Fields to update
            
        Returns:
            True if modification successful
        """
        # TODO: Implement order replacement via OrderManager
        logger.warning("IBKR order replacement not yet implemented")
        return False

    def close_all_positions(self) -> bool:
        """
        Close all open positions using PositionManager
        
        Returns:
            True if successful
        """
        if not self.is_connected or not self.position_manager:
            logger.error("Not connected to IBKR or PositionManager not initialized")
            return False
            
        try:
            return self.position_manager.close_all_positions()
        except Exception as e:
            logger.error(f"Error closing all IBKR positions: {e}")
            return False

    def __del__(self):
        """Cleanup on object destruction"""
        try:
            self.disconnect()
        except Exception:
            pass 