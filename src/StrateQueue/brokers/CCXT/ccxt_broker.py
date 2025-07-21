"""
CCXT Broker Implementation

CCXT broker implementation that provides unified access to 250+ cryptocurrency exchanges.
Follows StrateQueue's BaseBroker interface for seamless integration.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

# CCXT import with graceful fallback
try:
    import ccxt
    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False
    ccxt = None

from ...core.signal_extractor import SignalType, TradingSignal
from ..broker_base import (
    AccountInfo,
    BaseBroker,
    BrokerCapabilities,
    BrokerConfig,
    BrokerInfo,
    OrderResult,
    OrderSide,
    OrderType,
    Position,
)
from .exchange_config import ExchangeConfig

logger = logging.getLogger(__name__)


class CCXTBroker(BaseBroker):
    """
    CCXT broker implementation for cryptocurrency trading across multiple exchanges.
    
    Provides unified access to 250+ cryptocurrency exchanges through the CCXT library
    while maintaining compatibility with StrateQueue's broker interface.
    """
    
    def __init__(self, config: BrokerConfig, portfolio_manager=None, position_sizer=None):
        """
        Initialize CCXT broker
        
        Args:
            config: Broker configuration containing exchange and credentials
            portfolio_manager: Optional portfolio manager for multi-strategy support
            position_sizer: Optional position sizer for calculating trade sizes
        """
        if not CCXT_AVAILABLE:
            raise ImportError(
                "CCXT library not installed. Please install with: pip install ccxt"
            )
        
        super().__init__(config, portfolio_manager, position_sizer)
        
        # Extract exchange information from config
        self.exchange_id = self._extract_exchange_id(config)
        self.exchange = None
        self.exchange_config = ExchangeConfig()
        
        # Order type mapping from StrateQueue to CCXT
        self.order_type_mapping = {
            OrderType.MARKET: "market",
            OrderType.LIMIT: "limit",
            OrderType.STOP: "stop",
            OrderType.STOP_LIMIT: "stop_limit",
            OrderType.TRAILING_STOP: "trailing_stop"
        }
        
        logger.info(f"Initialized CCXT broker for exchange: {self.exchange_id}")
    
    def _extract_exchange_id(self, config: BrokerConfig) -> str:
        """Extract exchange ID from broker configuration"""
        # Check if exchange is specified in additional_params (from ccxt.exchange syntax)
        if config.additional_params and 'exchange' in config.additional_params:
            return config.additional_params['exchange']
        
        # Check credentials for exchange specification
        if config.credentials and 'exchange' in config.credentials:
            return config.credentials['exchange']
        
        # Default to binance if not specified
        logger.warning("No exchange specified, defaulting to binance")
        return 'binance'
    
    def get_broker_info(self) -> BrokerInfo:
        """Get information about the CCXT broker"""
        exchange_info = self.exchange_config.get_exchange_info(self.exchange_id)
        exchange_name = exchange_info.name if exchange_info else self.exchange_id.title()
        
        return BrokerInfo(
            name=f"CCXT-{exchange_name}",
            version="1.0.0",
            supported_features={
                "market_orders": True,
                "limit_orders": True,
                "stop_orders": True,
                "stop_limit_orders": False,  # Varies by exchange
                "trailing_stop_orders": False,  # Varies by exchange
                "cancel_all_orders": True,
                "replace_orders": False,  # Most exchanges don't support this
                "close_all_positions": False,  # Spot trading focused
                "crypto_trading": True,
                "options_trading": False,
                "futures_trading": False,  # Could be enabled per exchange
                "multi_strategy": True,
                "paper_trading": exchange_info.supports_sandbox if exchange_info else False,
            },
            description=f"Cryptocurrency trading via {exchange_name} through CCXT",
            supported_markets=["crypto"],
            paper_trading=self.config.paper_trading,
        )

    def get_broker_capabilities(self) -> BrokerCapabilities:
        """Get broker trading capabilities and constraints"""
        # Get exchange-specific minimum notional requirements
        min_notional = self._get_exchange_min_notional()
        
        return BrokerCapabilities(
            min_notional=min_notional,
            max_position_size=None,  # No hard limit for crypto spot trading
            min_lot_size=0.0,  # Crypto typically allows very small amounts
            step_size=0.0,  # Will be determined per symbol if needed
            fractional_shares=True,  # Crypto supports fractional amounts
            supported_order_types=["market", "limit", "stop"]
        )
    
    def _get_exchange_min_notional(self) -> float:
        """Get minimum notional value for the exchange"""
        # Exchange-specific minimum notional requirements
        exchange_minimums = {
            'binance': 10.0,  # Binance requires $10 minimum
            'coinbase': 1.0,   # Coinbase Pro lower minimum
            'kraken': 5.0,     # Kraken minimum
            'bitfinex': 15.0,  # Bitfinex higher minimum
            'huobi': 5.0,      # Huobi minimum
            'okx': 1.0,        # OKX lower minimum
            'kucoin': 1.0,     # KuCoin lower minimum
        }
        
        return exchange_minimums.get(self.exchange_id, 10.0)  # Default to $10
    
    def connect(self) -> bool:
        """
        Establish connection to the cryptocurrency exchange
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Get exchange class from CCXT
            if not hasattr(ccxt, self.exchange_id):
                logger.error(f"Exchange '{self.exchange_id}' not supported by CCXT")
                return False
            
            exchange_class = getattr(ccxt, self.exchange_id)
            
            # Prepare exchange configuration
            exchange_config = {
                'apiKey': self.config.credentials.get('api_key', ''),
                'secret': self.config.credentials.get('secret_key', ''),
                'enableRateLimit': True,
                'timeout': self.config.timeout * 1000,  # CCXT uses milliseconds
            }
            
            # Add passphrase if required
            if self.config.credentials.get('passphrase'):
                exchange_config['password'] = self.config.credentials['passphrase']
            
            # Enable sandbox/testnet if paper trading
            if self.config.paper_trading:
                exchange_config['sandbox'] = True
            
            # Initialize exchange
            self.exchange = exchange_class(exchange_config)
            
            # Test connection by loading markets
            markets = self.exchange.load_markets()
            logger.info(f"Connected to {self.exchange_id} with {len(markets)} markets")
            
            self.is_connected = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to {self.exchange_id}: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """Disconnect from the exchange"""
        if self.exchange:
            try:
                # Close any open connections
                if hasattr(self.exchange, 'close'):
                    self.exchange.close()
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
        
        self.exchange = None
        self.is_connected = False
        logger.info(f"Disconnected from {self.exchange_id}")
    
    def validate_credentials(self) -> bool:
        """
        Validate exchange credentials without establishing full connection
        
        Returns:
            True if credentials are valid
        """
        try:
            # Create temporary exchange instance
            if not hasattr(ccxt, self.exchange_id):
                return False
            
            exchange_class = getattr(ccxt, self.exchange_id)
            temp_exchange = exchange_class({
                'apiKey': self.config.credentials.get('api_key', ''),
                'secret': self.config.credentials.get('secret_key', ''),
                'password': self.config.credentials.get('passphrase', ''),
                'sandbox': self.config.paper_trading,
                'enableRateLimit': True,
            })
            
            # Try to fetch account balance as credential test
            balance = temp_exchange.fetch_balance()
            logger.info(f"Credentials validated for {self.exchange_id}")
            return True
            
        except Exception as e:
            logger.error(f"Credential validation failed for {self.exchange_id}: {e}")
            return False
    
    def execute_signal(self, symbol: str, signal: TradingSignal) -> OrderResult:
        """
        Execute a trading signal
        
        Args:
            symbol: Symbol to trade (e.g., 'BTC/USDT')
            signal: Trading signal to execute
            
        Returns:
            OrderResult with execution status and details
        """
        if not self.is_connected:
            return OrderResult(success=False, message=f"Not connected to {self.exchange_id}")
        
        try:
            # Handle HOLD signals
            if signal.signal == SignalType.HOLD:
                logger.debug(f"HOLD signal for {symbol} - no action needed")
                return OrderResult(success=True, message="HOLD signal processed")
            
            # Convert signal to order parameters
            order_params = self._signal_to_order_params(symbol, signal)
            if not order_params:
                return OrderResult(success=False, message="Could not convert signal to order parameters")
            
            # Execute order
            order = self.exchange.create_order(**order_params)
            
            return OrderResult(
                success=True,
                order_id=order.get('id'),
                client_order_id=order.get('clientOrderId'),
                message="Order executed successfully",
                timestamp=datetime.now(),
                broker_response=order
            )
            
        except Exception as e:
            error_msg = f"Error executing signal for {symbol}: {e}"
            logger.error(error_msg)
            return OrderResult(success=False, message=error_msg)
    
    def get_account_info(self) -> Optional[AccountInfo]:
        """
        Get account information
        
        Returns:
            AccountInfo object or None if error
        """
        if not self.is_connected:
            return None
        
        try:
            balance = self.exchange.fetch_balance()
            
            # Calculate total value (sum of all balances in base currency)
            total_value = 0.0
            cash = 0.0
            
            # Get free balance in USDT or USD as cash
            for currency in ['USDT', 'USD', 'BUSD', 'USDC']:
                if currency in balance['free']:
                    cash += balance['free'][currency]
                    break
            
            # Calculate total portfolio value
            for currency, amounts in balance['total'].items():
                if amounts > 0:
                    total_value += amounts  # Simplified - would need price conversion
            
            return AccountInfo(
                account_id=f"{self.exchange_id}_account",
                total_value=total_value,
                cash=cash,
                buying_power=cash,  # Simplified for spot trading
                currency="USDT",  # Most common base currency for crypto
                additional_fields={"exchange": self.exchange_id, "raw_balance": balance}
            )
            
        except Exception as e:
            logger.error(f"Error getting account info from {self.exchange_id}: {e}")
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
            balance = self.exchange.fetch_balance()
            positions = {}
            
            # Convert non-zero balances to positions
            for currency, amounts in balance['total'].items():
                if amounts > 0 and currency not in ['USDT', 'USD', 'BUSD', 'USDC']:
                    # Create position for each held currency
                    positions[currency] = Position(
                        symbol=f"{currency}/USDT",  # Assume USDT pair
                        quantity=amounts,
                        market_value=amounts,  # Would need current price
                        average_cost=0.0,  # Not available from balance
                        side="long",
                        additional_fields={"exchange": self.exchange_id}
                    )
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting positions from {self.exchange_id}: {e}")
            return {}
    
    def get_orders(self, symbol: Optional[str] = None) -> list[Dict[str, Any]]:
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
                orders = self.exchange.fetch_open_orders(symbol)
            else:
                orders = self.exchange.fetch_open_orders()
            
            # Convert to standardized format
            standardized_orders = []
            for order in orders:
                standardized_orders.append({
                    "id": order.get('id'),
                    "client_order_id": order.get('clientOrderId'),
                    "symbol": order.get('symbol'),
                    "side": order.get('side'),
                    "order_type": order.get('type'),
                    "qty": order.get('amount'),
                    "filled_qty": order.get('filled', 0),
                    "limit_price": order.get('price'),
                    "status": order.get('status'),
                    "created_at": order.get('timestamp'),
                    "exchange": self.exchange_id
                })
            
            return standardized_orders
            
        except Exception as e:
            logger.error(f"Error getting orders from {self.exchange_id}: {e}")
            return []
    
    def place_order(
        self,
        symbol: str,
        order_type: OrderType,
        side: OrderSide,
        quantity: float,
        price: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrderResult:
        """
        Place an order
        
        Args:
            symbol: Symbol to trade (e.g., 'BTC/USDT')
            order_type: Type of order
            side: Order side (BUY/SELL)
            quantity: Quantity to trade
            price: Price for limit orders
            metadata: Additional order metadata
            
        Returns:
            OrderResult with execution status
        """
        if not self.is_connected:
            return OrderResult(success=False, message=f"Not connected to {self.exchange_id}")
        
        try:
            # Convert order type
            ccxt_order_type = self.order_type_mapping.get(order_type)
            if not ccxt_order_type:
                return OrderResult(
                    success=False,
                    message=f"Order type {order_type.value} not supported"
                )
            
            # Prepare order parameters
            order_params = {
                'symbol': symbol,
                'type': ccxt_order_type,
                'side': side.value.lower(),
                'amount': quantity,
            }
            
            # Add price for limit orders
            if order_type == OrderType.LIMIT and price:
                order_params['price'] = price
            
            # Execute order
            order = self.exchange.create_order(**order_params)
            
            return OrderResult(
                success=True,
                order_id=order.get('id'),
                client_order_id=order.get('clientOrderId'),
                message="Order placed successfully",
                timestamp=datetime.now(),
                broker_response=order
            )
            
        except Exception as e:
            error_msg = f"Error placing order on {self.exchange_id}: {e}"
            logger.error(error_msg)
            return OrderResult(success=False, message=error_msg)
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order"""
        if not self.is_connected:
            return False
        
        try:
            self.exchange.cancel_order(order_id)
            logger.info(f"Successfully cancelled order {order_id} on {self.exchange_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order {order_id} on {self.exchange_id}: {e}")
            return False
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order status"""
        if not self.is_connected:
            return None
        
        try:
            order = self.exchange.fetch_order(order_id)
            return {
                "id": order.get('id'),
                "client_order_id": order.get('clientOrderId'),
                "symbol": order.get('symbol'),
                "side": order.get('side'),
                "order_type": order.get('type'),
                "qty": order.get('amount'),
                "filled_qty": order.get('filled', 0),
                "status": order.get('status'),
                "limit_price": order.get('price'),
                "created_at": order.get('timestamp'),
                "exchange": self.exchange_id
            }
        except Exception as e:
            logger.error(f"Error getting order status for {order_id} on {self.exchange_id}: {e}")
            return None
    
    def cancel_all_orders(self) -> bool:
        """Cancel all open orders"""
        if not self.is_connected:
            return False
        
        try:
            # Get all open orders and cancel them
            open_orders = self.exchange.fetch_open_orders()
            for order in open_orders:
                self.exchange.cancel_order(order['id'])
            
            logger.info(f"Successfully cancelled {len(open_orders)} orders on {self.exchange_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling all orders on {self.exchange_id}: {e}")
            return False
    
    def replace_order(self, order_id: str, **updates) -> bool:
        """Replace/modify an existing order (not supported by most exchanges)"""
        logger.warning(f"Order replacement not supported by {self.exchange_id}")
        return False
    
    def close_all_positions(self) -> bool:
        """Close all open positions (not applicable for spot trading)"""
        logger.warning(f"Position closing not applicable for spot trading on {self.exchange_id}")
        return False
    
    def _signal_to_order_params(self, symbol: str, signal: TradingSignal, current_price: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Convert TradingSignal to CCXT order parameters with proper position sizing"""
        try:
            # Determine order side
            is_buy = signal.signal in [SignalType.BUY, SignalType.LIMIT_BUY]
            side = 'buy' if is_buy else 'sell'
            
            # Determine order type and price
            if signal.signal in [SignalType.BUY, SignalType.SELL]:
                order_type = 'market'
                # Use provided price or get current price
                price = current_price or self._get_current_price(symbol)
            elif signal.signal in [SignalType.LIMIT_BUY, SignalType.LIMIT_SELL]:
                order_type = 'limit'
                price = signal.price
            else:
                logger.warning(f"Unsupported signal type: {signal.signal}")
                return None
            
            if not price or price <= 0:
                logger.error(f"Invalid price for {symbol}: {price}")
                return None
            
            # Calculate proper position size using position sizer
            amount = self._calculate_position_size(signal, symbol, price)
            
            if amount <= 0:
                logger.warning(f"Position size calculation resulted in zero or negative amount for {symbol}")
                return None
            
            return {
                'symbol': symbol,
                'type': order_type,
                'side': side,
                'amount': amount,
                'price': price if order_type == 'limit' else None,
            }
            
        except Exception as e:
            logger.error(f"Error converting signal to order params: {e}")
            return None
    
    def _calculate_position_size(self, signal: TradingSignal, symbol: str, price: float) -> float:
        """Calculate position size using the position sizer with broker constraints"""
        try:
            # Get account info for position sizing
            account_info = self.get_account_info()
            if not account_info:
                logger.warning(f"Could not get account info for position sizing, using fallback")
                account_value = 10000.0  # Fallback account value
                available_cash = 10000.0  # Fallback - same as account value for testing
            else:
                account_value = account_info.total_value
                available_cash = account_info.cash
            
            # Get broker capabilities
            capabilities = self.get_broker_capabilities()
            
            # Use position sizer to calculate proper size
            quantity, reasoning = self.position_sizer.calculate_position_size(
                signal=signal,
                symbol=symbol,
                price=price,
                broker_capabilities=capabilities,
                account_value=account_value,
                available_cash=available_cash,
                portfolio_manager=self.portfolio_manager
            )
            
            from ...utils.price_formatter import PriceFormatter
            logger.info(f"Position sizing for {symbol}: {PriceFormatter.format_quantity(quantity)} units ({PriceFormatter.format_price_for_display(quantity * price)}) - {reasoning}")
            
            return quantity
            
        except Exception as e:
            logger.error(f"Error calculating position size for {symbol}: {e}")
            # Emergency fallback - calculate minimum viable position
            capabilities = self.get_broker_capabilities()
            min_notional = capabilities.min_notional
            fallback_quantity = min_notional / price
            logger.warning(f"Using fallback position size for {symbol}: {fallback_quantity:.6f} units")
            return fallback_quantity
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol"""
        try:
            if not self.exchange:
                return None
            
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker.get('last') or ticker.get('close')
            
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {e}")
            return None