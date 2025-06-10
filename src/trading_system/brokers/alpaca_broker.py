"""
Alpaca Broker Implementation

Alpaca broker implementation that conforms to the BaseBroker interface.
This refactors the existing AlpacaExecutor to fit the new broker factory pattern.
"""

import logging
from typing import Dict, Optional, List, Any
from datetime import datetime

try:
    from alpaca.trading.client import TradingClient
    from alpaca.common.exceptions import APIError
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    # Create dummy classes for graceful fallback
    class TradingClient:
        def __init__(self, *args, **kwargs):
            raise ImportError("alpaca-trade-api not installed")
    class APIError(Exception):
        pass

from .base import BaseBroker, BrokerConfig, BrokerInfo, AccountInfo, Position, OrderResult, OrderType, OrderSide
from ..core.signal_extractor import TradingSignal, SignalType

# Define Alpaca-specific components inline since legacy code was removed
if ALPACA_AVAILABLE:
    # Inline AlpacaConfig and PositionSizeConfig since legacy code removed
    class AlpacaConfig:
        def __init__(self, api_key: str, secret_key: str, base_url: Optional[str] = None, paper: bool = True):
            self.api_key = api_key
            self.secret_key = secret_key
            self.base_url = base_url
            self.paper = paper
    
    class PositionSizeConfig:
        def __init__(self, default_position_size: float = 100.0, max_position_size: float = 10000.0):
            self.default_position_size = default_position_size
            self.max_position_size = max_position_size
    
    # Simple crypto symbol normalization function
    def normalize_crypto_symbol(symbol: str) -> str:
        """Normalize crypto symbols for Alpaca format"""
        if '/' in symbol:
            # Already in pair format (e.g., "BTC/USD")
            return symbol.upper()
        
        # Convert single symbol to USD pair for crypto
        crypto_symbols = ['BTC', 'ETH', 'LTC', 'BCH', 'DOGE', 'SHIB', 'AVAX', 'UNI', 'LINK', 'MATIC']
        symbol_upper = symbol.upper()
        
        if symbol_upper in crypto_symbols:
            return f"{symbol_upper}/USD"
        
        # For stocks, return as-is
        return symbol_upper

logger = logging.getLogger(__name__)


class AlpacaBroker(BaseBroker):
    """
    Alpaca broker implementation for live trading.
    
    Handles the actual execution of trading signals through the Alpaca API using
    a modular order execution system. Supports multi-strategy trading with portfolio
    management and conflict prevention.
    """
    
    def __init__(self, config: BrokerConfig, portfolio_manager=None, statistics_manager=None):
        """
        Initialize Alpaca broker
        
        Args:
            config: Broker configuration
            portfolio_manager: Optional portfolio manager for multi-strategy support
            statistics_manager: Optional statistics manager for trade tracking
        """
        if not ALPACA_AVAILABLE:
            raise ImportError("alpaca-trade-api not installed. Install with: pip install stratequeue[trading]")
        
        super().__init__(config, portfolio_manager)
        
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
    
    def _create_alpaca_config(self, config: BrokerConfig) -> 'AlpacaConfig':
        """Convert BrokerConfig to AlpacaConfig"""
        return AlpacaConfig(
            api_key=config.credentials.get('api_key'),
            secret_key=config.credentials.get('secret_key'),
            base_url=config.credentials.get('base_url'),
            paper=config.paper_trading
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
                "fractional_shares": True,
                "crypto_trading": True,
                "options_trading": False,
                "futures_trading": False,
                "multi_strategy": True,
                "paper_trading": True
            },
            description="Commission-free stock and crypto trading",
            supported_markets=["stocks", "crypto"],
            paper_trading=self.config.paper_trading
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
                url_override=self.alpaca_config.base_url if self.alpaca_config.base_url else None
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
                url_override=self.alpaca_config.base_url if self.alpaca_config.base_url else None
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
            return OrderResult(
                success=False,
                message="Not connected to Alpaca"
            )
        
        try:
            # Normalize symbol for Alpaca format
            alpaca_symbol = normalize_crypto_symbol(symbol)
            
            strategy_id = getattr(signal, 'strategy_id', None)
            strategy_info = f" [{strategy_id}]" if strategy_id else ""
            
            logger.info(f"Executing signal{strategy_info} for {symbol} ({alpaca_symbol}): "
                       f"{signal.signal.value} @ ${signal.price:.2f}")
            
            # Validate portfolio constraints if in multi-strategy mode
            is_valid, reason = self._validate_portfolio_constraints(alpaca_symbol, signal)
            if not is_valid:
                logger.warning(f"❌ Signal blocked{strategy_info} for {symbol}: {reason}")
                return OrderResult(
                    success=False,
                    message=f"Portfolio constraint violation: {reason}"
                )
            
                        # Handle HOLD signals
            if signal.signal == SignalType.HOLD:
                logger.debug(f"HOLD signal for {symbol} - no action needed")
                return OrderResult(success=True)

            # Check if signal type is supported
            supported_signals = self.order_executors.get('supported_signal_types', [])
            if signal.signal not in supported_signals:
                error_msg = f"Unknown signal type: {signal.signal}"
                logger.warning(error_msg)
                return OrderResult(
                    success=False,
                    message=error_msg
                )

            # Generate client order ID
            client_order_id = self._generate_client_order_id(strategy_id)

            # Execute the order using simplified direct API call
            success, order_id = self._execute_signal_direct(alpaca_symbol, signal, client_order_id, strategy_id)

            if success and order_id:
                self.pending_orders[alpaca_symbol] = order_id

            return OrderResult(
                success=success,
                order_id=order_id,
                client_order_id=client_order_id,
                timestamp=datetime.now(),
                message=None if success else "Order execution failed"
            )
                
        except Exception as e:
            error_msg = f"Error executing signal for {symbol}: {e}"
            logger.error(error_msg)
            return OrderResult(
                success=False,
                message=error_msg
            )
    
    def get_account_info(self) -> Optional[AccountInfo]:
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
                currency="USD"
            )
        except APIError as e:
            logger.error(f"Error getting Alpaca account info: {e}")
            return None
    
    def get_positions(self) -> Dict[str, Position]:
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
                    side="long" if qty > 0 else "short"
                )
            return result
        except APIError as e:
            logger.error(f"Error getting Alpaca positions: {e}")
            return {}
    
    def get_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
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
                result.append({
                    'id': order.id,
                    'client_order_id': order.client_order_id,
                    'symbol': order.symbol,
                    'side': order.side.value,
                    'order_type': order.order_type.value,
                    'qty': float(order.qty) if order.qty else None,
                    'notional': float(order.notional) if order.notional else None,
                    'filled_qty': float(order.filled_qty) if order.filled_qty else 0,
                    'status': order.status.value,
                    'created_at': order.created_at,
                    'updated_at': order.updated_at
                })
            return result
            
        except APIError as e:
            logger.error(f"Error getting Alpaca orders: {e}")
            return []
    
    def place_order(self, symbol: str, order_type: 'OrderType', 
                   side: 'OrderSide', quantity: float, 
                   price: Optional[float] = None, 
                   metadata: Optional[Dict[str, Any]] = None) -> OrderResult:
        """
        Place an order through Alpaca
        
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
        if not self.is_connected:
            return OrderResult(
                success=False,
                message="Not connected to Alpaca"
            )
        
        try:
            from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
            from alpaca.trading.enums import OrderSide as AlpacaOrderSide, TimeInForce
            
            # Convert enums to Alpaca format
            alpaca_side = AlpacaOrderSide.BUY if side.value == 'BUY' else AlpacaOrderSide.SELL
            
            # Normalize symbol
            alpaca_symbol = normalize_crypto_symbol(symbol)
            
            # Create order request
            if order_type.value == 'MARKET':
                order_request = MarketOrderRequest(
                    symbol=alpaca_symbol,
                    qty=float(quantity),
                    side=alpaca_side,
                    time_in_force=TimeInForce.DAY
                )
            elif order_type.value == 'LIMIT':
                if not price:
                    return OrderResult(
                        success=False,
                        error_code="MISSING_PRICE",
                        message="Limit orders require a price"
                    )
                order_request = LimitOrderRequest(
                    symbol=alpaca_symbol,
                    qty=float(quantity),
                    side=alpaca_side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=float(price)
                )
            else:
                return OrderResult(
                    success=False,
                    error_code="UNSUPPORTED_ORDER_TYPE",
                    message=f"Unsupported order type: {order_type.value}"
                )
            
            # Submit order
            order = self.trading_client.submit_order(order_data=order_request)
            
            return OrderResult(
                success=True,
                order_id=order.id,
                client_order_id=order.client_order_id,
                message="Order submitted successfully",
                broker_response={'order': order.__dict__}
            )
            
        except Exception as e:
            logger.error(f"Error placing Alpaca order: {e}")
            return OrderResult(
                success=False,
                error_code="ORDER_FAILED",
                message=str(e)
            )
    
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
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
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
                'id': order.id,
                'client_order_id': order.client_order_id,
                'symbol': order.symbol,
                'side': order.side.value,
                'order_type': order.order_type.value,
                'qty': float(order.qty) if order.qty else None,
                'filled_qty': float(order.filled_qty) if order.filled_qty else 0,
                'status': order.status.value,
                'created_at': order.created_at,
                'updated_at': order.updated_at
            }
        except APIError as e:
            logger.error(f"Error getting Alpaca order status {order_id}: {e}")
            return None
    
    def _init_order_executors(self):
        """Initialize simplified order execution system"""
        # Simplified - use direct Alpaca API calls instead of complex executor classes
        self.order_executors = {
            'supported_signal_types': [
                SignalType.BUY, SignalType.SELL, SignalType.CLOSE,
                SignalType.LIMIT_BUY, SignalType.LIMIT_SELL,
                SignalType.STOP_BUY, SignalType.STOP_SELL,
                SignalType.STOP_LIMIT_BUY, SignalType.STOP_LIMIT_SELL,
                SignalType.TRAILING_STOP_SELL
            ]
        }
    
    def _execute_signal_direct(self, symbol: str, signal: TradingSignal, client_order_id: str, strategy_id: Optional[str]) -> tuple[bool, Optional[str]]:
        """
        Execute signal using direct Alpaca API calls
        
        Args:
            symbol: Symbol to trade
            signal: Trading signal
            client_order_id: Unique client order ID
            strategy_id: Optional strategy ID
            
        Returns:
            Tuple of (success: bool, order_id: Optional[str])
        """
        try:
            from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce
            
            logger.info(f"🔄 Processing order for symbol: {symbol}")
            
            # Calculate position size - simplified approach
            if self.portfolio_manager and strategy_id:
                # Multi-strategy mode: get position size from portfolio manager
                strategy_status = self.portfolio_manager.get_strategy_status(strategy_id)
                available_capital = strategy_status.get('available_capital', 100.0)
                position_size = min(available_capital * 0.1, 1000.0)  # Use 10% of available capital, max $1000
            else:
                # Single strategy mode: use default position size
                position_size = self.position_config.default_position_size
            
            logger.info(f"💰 Position size calculated: ${position_size:.2f}")
            
            # Determine order side
            is_buy_signal = signal.signal in [SignalType.BUY, SignalType.LIMIT_BUY, SignalType.STOP_BUY, SignalType.STOP_LIMIT_BUY]
            side = OrderSide.BUY if is_buy_signal else OrderSide.SELL
            
            # Determine time in force based on asset type
            is_crypto = '/' in symbol  # Crypto pairs have "/" like "ETH/USD"
            time_in_force = TimeInForce.GTC if is_crypto else TimeInForce.DAY
            
            # For crypto, use notional orders; for stocks, use quantity orders
            order_request = None
            
            if is_buy_signal:
                if is_crypto:
                    # For crypto buys, use notional amount (USD value)
                    # Round notional to 2 decimal places for Alpaca API requirement
                    notional_amount = round(position_size, 2)
                    logger.info(f"📊 Creating crypto buy order: ${notional_amount:.2f} notional of {symbol}")
                    if signal.signal == SignalType.BUY:
                        order_request = MarketOrderRequest(
                            symbol=symbol,
                            side=side,
                            notional=notional_amount,
                            time_in_force=time_in_force,
                            client_order_id=client_order_id
                        )
                    elif signal.signal == SignalType.LIMIT_BUY:
                        # For limit orders, calculate quantity
                        quantity = position_size / signal.price if signal.price else None
                        if quantity:
                            logger.info(f"📊 Creating crypto limit buy: {quantity:.6f} {symbol} @ ${signal.price:.2f}")
                            order_request = LimitOrderRequest(
                                symbol=symbol,
                                side=side,
                                qty=quantity,
                                limit_price=signal.price,
                                time_in_force=time_in_force,
                                client_order_id=client_order_id
                            )
                else:
                    # For stock buys, calculate quantity
                    quantity = position_size / signal.price if signal.price else 1
                    logger.info(f"📊 Creating stock buy order: {quantity:.2f} shares of {symbol}")
                    if signal.signal == SignalType.BUY:
                        order_request = MarketOrderRequest(
                            symbol=symbol,
                            side=side,
                            qty=quantity,
                            time_in_force=time_in_force,
                            client_order_id=client_order_id
                        )
                    elif signal.signal == SignalType.LIMIT_BUY:
                        order_request = LimitOrderRequest(
                            symbol=symbol,
                            side=side,
                            qty=quantity,
                            limit_price=signal.price,
                            time_in_force=time_in_force,
                            client_order_id=client_order_id
                        )
            else:
                # For sell orders, get current position quantity
                try:
                    logger.info(f"🔍 Checking current position for {symbol}")
                    position = self.trading_client.get_open_position(symbol)
                    quantity = abs(float(position.qty))  # Ensure positive quantity
                    logger.info(f"📍 Found position: {quantity} shares/units of {symbol}")
                    
                    if signal.signal in [SignalType.SELL, SignalType.CLOSE]:
                        order_request = MarketOrderRequest(
                            symbol=symbol,
                            side=side,
                            qty=quantity,
                            time_in_force=time_in_force,
                            client_order_id=client_order_id
                        )
                    elif signal.signal == SignalType.LIMIT_SELL:
                        order_request = LimitOrderRequest(
                            symbol=symbol,
                            side=side,
                            qty=quantity,
                            limit_price=signal.price,
                            time_in_force=time_in_force,
                            client_order_id=client_order_id
                        )
                        
                except Exception as e:
                    logger.error(f"❌ No position found for {symbol}: {e}")
                    return False, None
            
            if not order_request:
                logger.error(f"❌ Failed to create order request for {symbol}")
                return False, None
            
            # Submit the order with detailed logging
            logger.info(f"🚀 Submitting order to Alpaca: {order_request}")
            order = self.trading_client.submit_order(order_request)
            logger.info(f"✅ Order submitted successfully!")
            logger.info(f"   Order ID: {order.id}")
            logger.info(f"   Symbol: {order.symbol}")
            logger.info(f"   Side: {order.side}")
            logger.info(f"   Status: {order.status}")
            
                        # Update portfolio manager if in multi-strategy mode
            if self.portfolio_manager and strategy_id:
                if is_buy_signal:
                    # For crypto notional orders, estimate quantity for portfolio tracking
                    if is_crypto and hasattr(order_request, 'notional'):
                        notional_used = getattr(order_request, 'notional', position_size)
                        estimated_quantity = notional_used / signal.price if signal.price else 0
                        self.portfolio_manager.record_buy(strategy_id, symbol, notional_used, estimated_quantity)
                        logger.info(f"📝 Portfolio: Recorded buy {strategy_id} - ${notional_used:.2f} (~{estimated_quantity:.6f} {symbol})")
                        
                        # Record in statistics tracker
                        if self.statistics_manager:
                            self.statistics_manager.record_trade(
                                timestamp=datetime.now(),
                                strategy_id=strategy_id,
                                symbol=symbol,
                                action="buy",
                                quantity=estimated_quantity,
                                price=signal.price,
                                commission=0.0  # Alpaca is commission-free
                            )
                    else:
                        quantity = getattr(order_request, 'qty', 0)
                        self.portfolio_manager.record_buy(strategy_id, symbol, position_size, quantity)
                        logger.info(f"📝 Portfolio: Recorded buy {strategy_id} - ${position_size:.2f} ({quantity:.6f} {symbol})")
                        
                        # Record in statistics tracker
                        if self.statistics_manager:
                            self.statistics_manager.record_trade(
                                timestamp=datetime.now(),
                                strategy_id=strategy_id,
                                symbol=symbol,
                                action="buy",
                                quantity=quantity,
                                price=signal.price,
                                commission=0.0  # Alpaca is commission-free
                            )
                else:
                    quantity = getattr(order_request, 'qty', 0)
                    sell_value = quantity * signal.price if signal.price else None
                    self.portfolio_manager.record_sell(strategy_id, symbol, sell_value, quantity)
                    logger.info(f"📝 Portfolio: Recorded sell {strategy_id} - {quantity:.6f} {symbol}")
                    
                    # Record in statistics tracker
                    if self.statistics_manager:
                        self.statistics_manager.record_trade(
                            timestamp=datetime.now(),
                            strategy_id=strategy_id,
                            symbol=symbol,
                            action="sell",
                            quantity=quantity,
                            price=signal.price,
                            commission=0.0  # Alpaca is commission-free
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
    
    def _generate_client_order_id(self, strategy_id: Optional[str] = None) -> str:
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
    
    def _validate_portfolio_constraints(self, symbol: str, signal: TradingSignal) -> tuple[bool, str]:
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
        
        strategy_id = getattr(signal, 'strategy_id', None)
        if not strategy_id:
            return False, "Signal missing strategy_id for multi-strategy mode"
        
        # Update portfolio manager with current account value
        try:
            account = self.trading_client.get_account()
            self.portfolio_manager.update_account_value(float(account.portfolio_value))
        except Exception as e:
            logger.warning(f"Could not update portfolio value: {e}")
        
        # Validate buy signals - multiple strategies can now buy the same symbol
        if signal.signal in [SignalType.BUY, SignalType.LIMIT_BUY, SignalType.STOP_BUY, 
                           SignalType.STOP_LIMIT_BUY]:
            
            # Just validate that strategy exists and has some allocation
            # Order executors will handle the specific amount calculation
            strategy_status = self.portfolio_manager.get_strategy_status(strategy_id)
            available_capital = strategy_status.get('available_capital', 0.0)
            
            if available_capital <= 0:
                return False, f"Strategy {strategy_id} has no available capital"
            
            return True, "Strategy has available capital"
        
        # Validate sell signals - check actual Alpaca positions for more reliable validation
        elif signal.signal in [SignalType.SELL, SignalType.CLOSE, SignalType.LIMIT_SELL,
                             SignalType.STOP_SELL, SignalType.STOP_LIMIT_SELL, 
                             SignalType.TRAILING_STOP_SELL]:
            
            # First check if we have any position in Alpaca at all
            try:
                position = self.trading_client.get_open_position(symbol)
                if position is None or float(position.qty) <= 0:
                    return False, f"No Alpaca position found for {symbol}"
                
                # Now check portfolio manager's strategy-specific tracking
                # This is for capital allocation and multi-strategy coordination
                can_sell_portfolio, portfolio_reason = self.portfolio_manager.can_sell(strategy_id, symbol, None)
                
                if not can_sell_portfolio:
                    # Portfolio manager says no, but we have Alpaca position
                    # This indicates a sync issue - let's log it but allow the trade
                    logger.warning(f"Portfolio manager position tracking out of sync for {strategy_id}/{symbol}: {portfolio_reason}")
                    logger.warning(f"Alpaca shows position: {float(position.qty)} shares, but portfolio manager disagrees")
                    logger.warning(f"Allowing sell based on actual Alpaca position")
                    
                    # Create a position in portfolio manager to get back in sync
                    try:
                        position_value = float(position.market_value)
                        quantity = float(position.qty)
                        self.portfolio_manager.record_buy(strategy_id, symbol, position_value, quantity)
                        logger.info(f"Synced portfolio manager: recorded {strategy_id} position of {quantity} {symbol} worth ${position_value:.2f}")
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
            logger.info(f"✅ Connected to Alpaca {'Paper' if self.config.paper_trading else 'Live'} Trading")
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


# Factory function for backward compatibility with existing create_alpaca_executor_from_env
def create_alpaca_broker_from_env(portfolio_manager=None, statistics_manager=None) -> AlpacaBroker:
    """
    Create AlpacaBroker from environment variables (backward compatibility)
    
    Args:
        portfolio_manager: Optional portfolio manager for multi-strategy support
        statistics_manager: Optional statistics manager for trade tracking
    
    Returns:
        Configured AlpacaBroker instance
    """
    from .broker_factory import auto_create_broker
    return auto_create_broker(portfolio_manager, statistics_manager) 