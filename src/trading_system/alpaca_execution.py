"""
Alpaca trading execution module for live trading integration.
"""

import os
import logging
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest, 
    LimitOrderRequest,
    StopOrderRequest,
    StopLimitOrderRequest,
    TrailingStopOrderRequest
)
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.common.exceptions import APIError

from .signal_extractor import TradingSignal, SignalType
from .simple_portfolio_manager import SimplePortfolioManager

logger = logging.getLogger(__name__)

@dataclass
class AlpacaConfig:
    """Alpaca API configuration"""
    api_key: str
    secret_key: str
    base_url: str
    paper: bool = True

def normalize_crypto_symbol(symbol: str) -> str:
    """
    Normalize crypto symbols for Alpaca format.
    
    Args:
        symbol: Original symbol (e.g., 'ETH', 'BTC')
        
    Returns:
        Alpaca-formatted symbol (e.g., 'ETH/USD', 'BTC/USD')
    """
    # If already has a slash, assume it's properly formatted
    if '/' in symbol:
        return symbol
    
    # Add /USD for crypto symbols
    crypto_symbols = ['BTC', 'ETH', 'LTC', 'BCH', 'DOGE', 'SHIB', 'AVAX', 'UNI']
    if symbol.upper() in crypto_symbols:
        return f"{symbol.upper()}/USD"
    
    # For other symbols, return as-is (stocks, etc.)
    return symbol.upper()

class PositionSizeMode(Enum):
    """Position sizing modes"""
    FIXED_AMOUNT = "fixed_amount"  # Fixed dollar amount per trade
    FIXED_SHARES = "fixed_shares"  # Fixed number of shares
    PERCENTAGE = "percentage"      # Percentage of portfolio
    SIGNAL_BASED = "signal_based"  # Use signal's suggested position size
    ALL_IN = "all_in"             # Use all available buying power

@dataclass
class PositionSizeConfig:
    """Position sizing configuration"""
    mode: PositionSizeMode = PositionSizeMode.ALL_IN
    value: float = 1.0  # Default 100% of buying power for ALL_IN mode

class AlpacaExecutor:
    """
    Alpaca trading executor for live trading.
    
    Handles the actual execution of trading signals through the Alpaca API.
    Supports multi-strategy trading with portfolio management and conflict prevention.
    """
    
    def __init__(self, config: AlpacaConfig, position_config: Optional[PositionSizeConfig] = None,
                 portfolio_manager: Optional[SimplePortfolioManager] = None):
        """
        Initialize Alpaca executor
        
        Args:
            config: Alpaca API configuration
            position_config: Position sizing configuration
            portfolio_manager: Optional portfolio manager for multi-strategy support
        """
        self.config = config
        self.position_config = position_config or PositionSizeConfig()
        self.portfolio_manager = portfolio_manager
        
        # Initialize Alpaca trading client
        self.trading_client = TradingClient(
            api_key=config.api_key,
            secret_key=config.secret_key,
            paper=config.paper,
            url_override=config.base_url if config.base_url else None
        )
        
        # Track pending orders and order counter for unique IDs
        self.pending_orders = {}
        self.order_counter = 0
        
        # Validate connection
        self._validate_connection()
    
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
        
        # Validate buy signals
        if signal.signal in [SignalType.BUY, SignalType.LIMIT_BUY, SignalType.STOP_BUY, 
                           SignalType.STOP_LIMIT_BUY]:
            
            # Calculate order amount based on signal size and account value
            account_value = float(account.portfolio_value)
            if signal.size and 0 < signal.size <= 1:
                order_amount = account_value * signal.size
            else:
                # Default to using available cash
                cash_balance = float(account.cash)
                order_amount = cash_balance * 0.99
            
            return self.portfolio_manager.can_buy(strategy_id, symbol, order_amount)
        
        # Validate sell signals
        elif signal.signal in [SignalType.SELL, SignalType.CLOSE, SignalType.LIMIT_SELL,
                             SignalType.STOP_SELL, SignalType.STOP_LIMIT_SELL, 
                             SignalType.TRAILING_STOP_SELL]:
            
            return self.portfolio_manager.can_sell(strategy_id, symbol)
        
        # Hold signals are always valid
        return True, "OK"
    
    def _record_trade_execution(self, symbol: str, signal: TradingSignal, execution_amount: float,
                              execution_successful: bool):
        """
        Record trade execution in portfolio manager
        
        Args:
            symbol: Symbol that was traded
            signal: Signal that was executed
            execution_amount: Dollar amount of the trade
            execution_successful: Whether execution was successful
        """
        if not self.portfolio_manager or not execution_successful:
            return
        
        strategy_id = getattr(signal, 'strategy_id', None)
        if not strategy_id:
            return
        
        # Record in portfolio manager
        if signal.signal in [SignalType.BUY, SignalType.LIMIT_BUY, SignalType.STOP_BUY, 
                           SignalType.STOP_LIMIT_BUY]:
            self.portfolio_manager.record_buy(strategy_id, symbol, execution_amount)
            
        elif signal.signal in [SignalType.SELL, SignalType.CLOSE, SignalType.LIMIT_SELL,
                             SignalType.STOP_SELL, SignalType.STOP_LIMIT_SELL, 
                             SignalType.TRAILING_STOP_SELL]:
            self.portfolio_manager.record_sell(strategy_id, symbol, execution_amount)
        
    def _validate_connection(self):
        """Validate connection to Alpaca API"""
        try:
            account = self.trading_client.get_account()
            logger.info(f"✅ Connected to Alpaca {'Paper' if self.config.paper else 'Live'} Trading")
            logger.info(f"Account ID: {account.id}")
            logger.info(f"Portfolio Value: ${float(account.portfolio_value):,.2f}")
            logger.info(f"Cash Balance: ${float(account.cash):,.2f}")
            logger.info(f"Day Trade Count: {account.daytrade_count}")
        except APIError as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            raise
        
    def execute_signal(self, symbol: str, signal: TradingSignal) -> bool:
        """
        Execute a trading signal with portfolio constraint validation
        
        Args:
            symbol: Symbol to trade
            signal: Trading signal to execute
            
        Returns:
            True if order was successfully placed, False otherwise
        """
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
                return False
            
            if signal.signal == SignalType.BUY:
                return self._execute_buy(alpaca_symbol, signal)
            elif signal.signal == SignalType.SELL:
                return self._execute_sell(alpaca_symbol, signal)
            elif signal.signal == SignalType.CLOSE:
                return self._execute_close(alpaca_symbol, signal)
            elif signal.signal == SignalType.LIMIT_BUY:
                return self._execute_limit_buy(alpaca_symbol, signal)
            elif signal.signal == SignalType.LIMIT_SELL:
                return self._execute_limit_sell(alpaca_symbol, signal)
            elif signal.signal == SignalType.STOP_BUY:
                return self._execute_stop_buy(alpaca_symbol, signal)
            elif signal.signal == SignalType.STOP_SELL:
                return self._execute_stop_sell(alpaca_symbol, signal)
            elif signal.signal == SignalType.STOP_LIMIT_BUY:
                return self._execute_stop_limit_buy(alpaca_symbol, signal)
            elif signal.signal == SignalType.STOP_LIMIT_SELL:
                return self._execute_stop_limit_sell(alpaca_symbol, signal)
            elif signal.signal == SignalType.TRAILING_STOP_SELL:
                return self._execute_trailing_stop_sell(alpaca_symbol, signal)
            elif signal.signal == SignalType.HOLD:
                logger.debug(f"HOLD signal for {symbol} - no action needed")
                return True
            else:
                logger.warning(f"Unknown signal type: {signal.signal}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing signal for {symbol}: {e}")
            return False
    
    def _execute_buy(self, symbol: str, signal: TradingSignal) -> bool:
        """Execute a buy signal using notional value."""
        try:
            order_data = None
            account = self.trading_client.get_account()

            # Generate client_order_id with strategy tagging
            strategy_id = getattr(signal, 'strategy_id', None)
            client_order_id = self._generate_client_order_id(strategy_id)
            
            # Case 1: Strategy specifies a size (e.g., self.buy(size=0.5) for 50% equity)
            if signal.size and 0 < signal.size <= 1:
                notional_amount = float(account.portfolio_value) * signal.size
                # Round to exactly 2 decimal places to meet Alpaca API requirements
                notional_amount = round(notional_amount, 2)
                logger.info(f"Signal size is {signal.size:.2%}. Buying notional amount: ${notional_amount:.2f}")
                order_data = MarketOrderRequest(
                    symbol=symbol,
                    notional=notional_amount,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.GTC,
                    client_order_id=client_order_id
                )
            # Case 2: Strategy calls self.buy() with no size, so go all-in with available buying power
            else:
                cash_balance = float(account.cash)
                # Use 99% of cash balance to be safe and leave room for fees/slippage
                notional_amount = cash_balance * 0.99
                # Round to exactly 2 decimal places to meet Alpaca API requirements
                notional_amount = round(notional_amount, 2)
                logger.info(f"Signal size not specified. Using 99% of cash balance: ${notional_amount:.2f}")
                order_data = MarketOrderRequest(
                    symbol=symbol,
                    notional=notional_amount,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.GTC,
                    client_order_id=client_order_id
                )

            # Submit order
            order = self.trading_client.submit_order(order_data=order_data)
            self.pending_orders[symbol] = order.id
            
            # Record execution in portfolio manager
            self._record_trade_execution(symbol, signal, order_data.notional, True)
            
            logger.info(f"✅ BUY order placed for {symbol}: Notional=${order_data.notional:.2f}, "
                       f"Order ID: {order.id}, Client ID: {client_order_id}")
            return True
            
        except APIError as e:
            logger.error(f"Alpaca API error placing BUY order for {symbol}: {e}")
            if "forbidden" in str(e).lower() or "unauthorized" in str(e).lower():
                logger.critical("Alpaca authentication failed. Check API keys, permissions, and paper/live mode.")
            elif "not found" in str(e).lower():
                 logger.error("Could not get account information. Check API endpoint and credentials.")
            return False
        except Exception as e:
            logger.error(f"Unexpected error placing BUY order for {symbol}: {e}", exc_info=True)
            return False
    
    def _execute_sell(self, symbol: str, signal: TradingSignal) -> bool:
        """Execute a sell signal based on existing position and signal size."""
        try:
            # First, find out if a position exists and its quantity
            # Try both symbol formats since Alpaca can be inconsistent
            position = None
            qty_available = 0
            
            try:
                # Try the original symbol format first
                position = self.trading_client.get_open_position(symbol)
                qty_available = abs(float(position.qty))
                logger.debug(f"Found position for {symbol}: {qty_available}")
            except APIError as e:
                if "position does not exist" in str(e).lower() or "not found" in str(e).lower():
                    # Try alternative symbol format (remove slash for crypto)
                    alt_symbol = symbol.replace('/', '')
                    try:
                        position = self.trading_client.get_open_position(alt_symbol)
                        qty_available = abs(float(position.qty))
                        logger.info(f"Found position using alternative symbol {alt_symbol}: {qty_available}")
                        # Update symbol to the one that worked
                        symbol = alt_symbol
                    except APIError as alt_e:
                        if "position does not exist" in str(alt_e).lower() or "not found" in str(alt_e).lower():
                            logger.warning(f"SELL signal for {symbol}, but no position exists (tried both {symbol} and {alt_symbol}). No action taken.")
                            return True  # Not a failure, just nothing to sell
                        else:
                            raise alt_e  # Re-raise other critical API errors
                else:
                    raise e  # Re-raise other critical API errors

            # Generate client_order_id with strategy tagging
            strategy_id = getattr(signal, 'strategy_id', None)
            client_order_id = self._generate_client_order_id(strategy_id)
            
            # Get current position value for portfolio tracking
            current_price = float(position.market_value) / qty_available if qty_available > 0 else 0
            
            # Case 1: Strategy specifies a size (e.g., self.sell(size=0.5) for 50% of position)
            if signal.size and 0 < signal.size <= 1:
                qty_to_sell = qty_available * signal.size
                sell_value = qty_to_sell * current_price
                logger.info(f"Signal size is {signal.size:.2%}. Selling {qty_to_sell:.8f} of {qty_available:.8f} {symbol}.")
                order_data = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty_to_sell,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.GTC,
                    client_order_id=client_order_id
                )
                order = self.trading_client.submit_order(order_data=order_data)
                self.pending_orders[symbol] = order.id
                
                # Record execution in portfolio manager
                self._record_trade_execution(symbol, signal, sell_value, True)
                
                logger.info(f"✅ SELL order placed for {qty_to_sell:.8f} {symbol}. "
                           f"Order ID: {order.id}, Client ID: {client_order_id}")

            # Case 2: Strategy calls self.sell() or self.position.close(), so sell the entire position
            else:
                total_value = float(position.market_value)
                logger.info(f"Signal size not specified. Closing entire position of {qty_available:.8f} {symbol}.")
                close_order = self.trading_client.close_position(symbol)
                self.pending_orders[symbol] = close_order.id
                
                # Record execution in portfolio manager
                self._record_trade_execution(symbol, signal, total_value, True)
                
                logger.info(f"✅ CLOSE position order placed for {symbol}. "
                           f"Order ID: {close_order.id}")

            return True

        except APIError as e:
            logger.error(f"Alpaca API error placing SELL order for {symbol}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error placing SELL order for {symbol}: {e}", exc_info=True)
            return False
    
    def _execute_close(self, symbol: str, signal: TradingSignal) -> bool:
        """Execute a close position signal by treating it as a full sell."""
        logger.info(f"CLOSE signal received for {symbol}. Closing entire position.")
        return self._execute_sell(symbol, signal) # Passing original signal, _execute_sell handles lack of size
    
    def _execute_limit_buy(self, symbol: str, signal: TradingSignal) -> bool:
        """Execute a limit buy signal."""
        try:
            if not signal.limit_price:
                logger.error(f"LIMIT_BUY signal for {symbol} missing limit_price")
                return False
                
            account = self.trading_client.get_account()
            
            # Generate client_order_id with strategy tagging
            strategy_id = getattr(signal, 'strategy_id', None)
            client_order_id = self._generate_client_order_id(strategy_id)
            
            order_data = None

            # Case 1: Strategy specifies a size (e.g., self.buy(size=0.5) for 50% equity)
            if signal.size and 0 < signal.size <= 1:
                notional_amount = float(account.portfolio_value) * signal.size
                notional_amount = round(notional_amount, 2)
                logger.info(f"LIMIT_BUY signal size is {signal.size:.2%}. Buying notional amount: ${notional_amount:.2f} at limit ${signal.limit_price:.2f}")
                order_data = LimitOrderRequest(
                    symbol=symbol,
                    notional=notional_amount,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.GTC,
                    limit_price=signal.limit_price,
                    client_order_id=client_order_id
                )
            else:
                # Case 2: Use all available cash for the buy
                cash_balance = float(account.cash)
                notional_amount = cash_balance * 0.99
                notional_amount = round(notional_amount, 2)
                logger.info(f"LIMIT_BUY signal size not specified. Using 99% of cash balance: ${notional_amount:.2f} at limit ${signal.limit_price:.2f}")
                order_data = LimitOrderRequest(
                    symbol=symbol,
                    notional=notional_amount,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.GTC,
                    limit_price=signal.limit_price,
                    client_order_id=client_order_id
                )

            # Submit order
            order = self.trading_client.submit_order(order_data=order_data)
            self.pending_orders[symbol] = order.id
            
            # Record execution in portfolio manager
            self._record_trade_execution(symbol, signal, order_data.notional, True)
            
            logger.info(f"✅ LIMIT BUY order placed for {symbol}: Notional=${order_data.notional:.2f}, "
                       f"Limit=${signal.limit_price:.2f}, Order ID: {order.id}, Client ID: {client_order_id}")
            return True
            
        except APIError as e:
            logger.error(f"Alpaca API error placing LIMIT BUY order for {symbol}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error placing LIMIT BUY order for {symbol}: {e}", exc_info=True)
            return False
    
    def _execute_limit_sell(self, symbol: str, signal: TradingSignal) -> bool:
        """Execute a limit sell signal based on existing position and signal size."""
        try:
            if not signal.limit_price:
                logger.error(f"LIMIT_SELL signal for {symbol} missing limit_price")
                return False
                
            # First, find out if a position exists and its quantity
            position = None
            qty_available = 0
            
            try:
                position = self.trading_client.get_open_position(symbol)
                qty_available = abs(float(position.qty))
                logger.debug(f"Found position for {symbol}: {qty_available}")
            except APIError as e:
                if "position does not exist" in str(e).lower() or "not found" in str(e).lower():
                    # Try alternative symbol format (remove slash for crypto)
                    alt_symbol = symbol.replace('/', '')
                    try:
                        position = self.trading_client.get_open_position(alt_symbol)
                        qty_available = abs(float(position.qty))
                        logger.info(f"Found position using alternative symbol {alt_symbol}: {qty_available}")
                        symbol = alt_symbol
                    except APIError as alt_e:
                        if "position does not exist" in str(alt_e).lower() or "not found" in str(alt_e).lower():
                            logger.warning(f"LIMIT_SELL signal for {symbol}, but no position exists. No action taken.")
                            return True
                        else:
                            raise alt_e
                else:
                    raise e

            # Case 1: Strategy specifies a size (e.g., self.sell(size=0.5) for 50% of position)
            if signal.size and 0 < signal.size <= 1:
                qty_to_sell = qty_available * signal.size
                logger.info(f"LIMIT_SELL signal size is {signal.size:.2%}. Selling {qty_to_sell:.8f} of {qty_available:.8f} {symbol} at limit ${signal.limit_price:.2f}")
                order_data = LimitOrderRequest(
                    symbol=symbol,
                    qty=qty_to_sell,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.GTC,
                    limit_price=signal.limit_price
                )
            else:
                # Case 2: Sell entire position
                logger.info(f"LIMIT_SELL signal size not specified. Selling entire position of {qty_available:.8f} {symbol} at limit ${signal.limit_price:.2f}")
                order_data = LimitOrderRequest(
                    symbol=symbol,
                    qty=qty_available,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.GTC,
                    limit_price=signal.limit_price
                )

            # Submit order
            order = self.trading_client.submit_order(order_data=order_data)
            self.pending_orders[symbol] = order.id
            logger.info(f"✅ LIMIT SELL order placed for {qty_to_sell if signal.size else qty_available:.8f} {symbol}. Limit=${signal.limit_price:.2f}, Order ID: {order.id}")
            return True

        except APIError as e:
            logger.error(f"Alpaca API error placing LIMIT SELL order for {symbol}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error placing LIMIT SELL order for {symbol}: {e}", exc_info=True)
            return False
    
    def get_account_info(self) -> Dict:
        """Get account information"""
        try:
            account = self.trading_client.get_account()
            return {
                'portfolio_value': float(account.portfolio_value),
                'cash': float(account.cash),
                'buying_power': float(account.buying_power),
                'daytrade_count': account.daytrade_count,
                'pattern_day_trader': account.pattern_day_trader
            }
        except APIError as e:
            logger.error(f"Error getting account info: {e}")
            return {}
    
    def get_positions(self) -> Dict[str, Dict]:
        """Get current positions"""
        try:
            positions = self.trading_client.get_all_positions()
            result = {}
            for position in positions:
                result[position.symbol] = {
                    'qty': float(position.qty),
                    'market_value': float(position.market_value),
                    'avg_entry_price': float(position.avg_entry_price),
                    'unrealized_pl': float(position.unrealized_pl),
                    'unrealized_plpc': float(position.unrealized_plpc),
                }
            return result
        except APIError as e:
            logger.error(f"Error getting positions: {e}")
            return {}
    
    def _execute_stop_buy(self, symbol: str, signal: TradingSignal) -> bool:
        """Execute a stop buy order."""
        try:
            if not signal.stop_price:
                logger.error(f"STOP_BUY signal for {symbol} missing stop_price")
                return False
                
            account = self.trading_client.get_account()
            
            # Calculate notional amount
            if signal.size and 0 < signal.size <= 1:
                notional_amount = float(account.portfolio_value) * signal.size
            else:
                cash_balance = float(account.cash)
                notional_amount = cash_balance * 0.99
            
            notional_amount = round(notional_amount, 2)
            
            # Get time in force
            time_in_force = TimeInForce.GTC
            if signal.time_in_force.upper() == "DAY":
                time_in_force = TimeInForce.DAY
            
            order_data = StopOrderRequest(
                symbol=symbol,
                notional=notional_amount,
                side=OrderSide.BUY,
                time_in_force=time_in_force,
                stop_price=signal.stop_price
            )
            
            order = self.trading_client.submit_order(order_data=order_data)
            self.pending_orders[symbol] = order.id
            logger.info(f"✅ STOP BUY order placed for {symbol}: Notional=${notional_amount:.2f}, Stop=${signal.stop_price:.2f}, Order ID: {order.id}")
            return True
            
        except APIError as e:
            logger.error(f"Alpaca API error placing STOP BUY order for {symbol}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error placing STOP BUY order for {symbol}: {e}", exc_info=True)
            return False
    
    def _execute_stop_sell(self, symbol: str, signal: TradingSignal) -> bool:
        """Execute a stop sell order."""
        try:
            if not signal.stop_price:
                logger.error(f"STOP_SELL signal for {symbol} missing stop_price")
                return False
                
            # Get position
            position = None
            qty_available = 0
            
            try:
                position = self.trading_client.get_open_position(symbol)
                qty_available = abs(float(position.qty))
            except APIError as e:
                if "position does not exist" in str(e).lower() or "not found" in str(e).lower():
                    alt_symbol = symbol.replace('/', '')
                    try:
                        position = self.trading_client.get_open_position(alt_symbol)
                        qty_available = abs(float(position.qty))
                        symbol = alt_symbol
                    except APIError:
                        logger.warning(f"STOP_SELL signal for {symbol}, but no position exists. No action taken.")
                        return True
                else:
                    raise e
            
            # Calculate quantity to sell
            if signal.size and 0 < signal.size <= 1:
                qty_to_sell = qty_available * signal.size
            else:
                qty_to_sell = qty_available
            
            # Get time in force
            time_in_force = TimeInForce.GTC
            if signal.time_in_force.upper() == "DAY":
                time_in_force = TimeInForce.DAY
            
            order_data = StopOrderRequest(
                symbol=symbol,
                qty=qty_to_sell,
                side=OrderSide.SELL,
                time_in_force=time_in_force,
                stop_price=signal.stop_price
            )
            
            order = self.trading_client.submit_order(order_data=order_data)
            self.pending_orders[symbol] = order.id
            logger.info(f"✅ STOP SELL order placed for {qty_to_sell:.8f} {symbol}. Stop=${signal.stop_price:.2f}, Order ID: {order.id}")
            return True
            
        except APIError as e:
            logger.error(f"Alpaca API error placing STOP SELL order for {symbol}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error placing STOP SELL order for {symbol}: {e}", exc_info=True)
            return False
    
    def _execute_stop_limit_buy(self, symbol: str, signal: TradingSignal) -> bool:
        """Execute a stop-limit buy order."""
        try:
            if not signal.stop_price or not signal.limit_price:
                logger.error(f"STOP_LIMIT_BUY signal for {symbol} missing stop_price or limit_price")
                return False
                
            account = self.trading_client.get_account()
            
            # Calculate notional amount
            if signal.size and 0 < signal.size <= 1:
                notional_amount = float(account.portfolio_value) * signal.size
            else:
                cash_balance = float(account.cash)
                notional_amount = cash_balance * 0.99
            
            notional_amount = round(notional_amount, 2)
            
            # Get time in force
            time_in_force = TimeInForce.GTC
            if signal.time_in_force.upper() == "DAY":
                time_in_force = TimeInForce.DAY
            
            order_data = StopLimitOrderRequest(
                symbol=symbol,
                notional=notional_amount,
                side=OrderSide.BUY,
                time_in_force=time_in_force,
                stop_price=signal.stop_price,
                limit_price=signal.limit_price
            )
            
            order = self.trading_client.submit_order(order_data=order_data)
            self.pending_orders[symbol] = order.id
            logger.info(f"✅ STOP LIMIT BUY order placed for {symbol}: Notional=${notional_amount:.2f}, Stop=${signal.stop_price:.2f}, Limit=${signal.limit_price:.2f}, Order ID: {order.id}")
            return True
            
        except APIError as e:
            logger.error(f"Alpaca API error placing STOP LIMIT BUY order for {symbol}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error placing STOP LIMIT BUY order for {symbol}: {e}", exc_info=True)
            return False
    
    def _execute_stop_limit_sell(self, symbol: str, signal: TradingSignal) -> bool:
        """Execute a stop-limit sell order."""
        try:
            if not signal.stop_price or not signal.limit_price:
                logger.error(f"STOP_LIMIT_SELL signal for {symbol} missing stop_price or limit_price")
                return False
                
            # Get position
            position = None
            qty_available = 0
            
            try:
                position = self.trading_client.get_open_position(symbol)
                qty_available = abs(float(position.qty))
            except APIError as e:
                if "position does not exist" in str(e).lower() or "not found" in str(e).lower():
                    alt_symbol = symbol.replace('/', '')
                    try:
                        position = self.trading_client.get_open_position(alt_symbol)
                        qty_available = abs(float(position.qty))
                        symbol = alt_symbol
                    except APIError:
                        logger.warning(f"STOP_LIMIT_SELL signal for {symbol}, but no position exists. No action taken.")
                        return True
                else:
                    raise e
            
            # Calculate quantity to sell
            if signal.size and 0 < signal.size <= 1:
                qty_to_sell = qty_available * signal.size
            else:
                qty_to_sell = qty_available
            
            # Get time in force
            time_in_force = TimeInForce.GTC
            if signal.time_in_force.upper() == "DAY":
                time_in_force = TimeInForce.DAY
            
            order_data = StopLimitOrderRequest(
                symbol=symbol,
                qty=qty_to_sell,
                side=OrderSide.SELL,
                time_in_force=time_in_force,
                stop_price=signal.stop_price,
                limit_price=signal.limit_price
            )
            
            order = self.trading_client.submit_order(order_data=order_data)
            self.pending_orders[symbol] = order.id
            logger.info(f"✅ STOP LIMIT SELL order placed for {qty_to_sell:.8f} {symbol}. Stop=${signal.stop_price:.2f}, Limit=${signal.limit_price:.2f}, Order ID: {order.id}")
            return True
            
        except APIError as e:
            logger.error(f"Alpaca API error placing STOP LIMIT SELL order for {symbol}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error placing STOP LIMIT SELL order for {symbol}: {e}", exc_info=True)
            return False
    
    def _execute_trailing_stop_sell(self, symbol: str, signal: TradingSignal) -> bool:
        """Execute a trailing stop sell order."""
        try:
            if not signal.trail_percent and not signal.trail_price:
                logger.error(f"TRAILING_STOP_SELL signal for {symbol} missing trail_percent or trail_price")
                return False
                
            # Get position
            position = None
            qty_available = 0
            
            try:
                position = self.trading_client.get_open_position(symbol)
                qty_available = abs(float(position.qty))
            except APIError as e:
                if "position does not exist" in str(e).lower() or "not found" in str(e).lower():
                    alt_symbol = symbol.replace('/', '')
                    try:
                        position = self.trading_client.get_open_position(alt_symbol)
                        qty_available = abs(float(position.qty))
                        symbol = alt_symbol
                    except APIError:
                        logger.warning(f"TRAILING_STOP_SELL signal for {symbol}, but no position exists. No action taken.")
                        return True
                else:
                    raise e
            
            # Calculate quantity to sell
            if signal.size and 0 < signal.size <= 1:
                qty_to_sell = qty_available * signal.size
            else:
                qty_to_sell = qty_available
            
            # Get time in force
            time_in_force = TimeInForce.GTC
            if signal.time_in_force.upper() == "DAY":
                time_in_force = TimeInForce.DAY
            
            # Create trailing stop order (prefer percentage over absolute price)
            if signal.trail_percent:
                order_data = TrailingStopOrderRequest(
                    symbol=symbol,
                    qty=qty_to_sell,
                    side=OrderSide.SELL,
                    time_in_force=time_in_force,
                    trail_percent=signal.trail_percent
                )
                trail_info = f"Trail%={signal.trail_percent:.2%}"
            else:
                order_data = TrailingStopOrderRequest(
                    symbol=symbol,
                    qty=qty_to_sell,
                    side=OrderSide.SELL,
                    time_in_force=time_in_force,
                    trail_price=signal.trail_price
                )
                trail_info = f"Trail=${signal.trail_price:.2f}"
            
            order = self.trading_client.submit_order(order_data=order_data)
            self.pending_orders[symbol] = order.id
            logger.info(f"✅ TRAILING STOP SELL order placed for {qty_to_sell:.8f} {symbol}. {trail_info}, Order ID: {order.id}")
            return True
            
        except APIError as e:
            logger.error(f"Alpaca API error placing TRAILING STOP SELL order for {symbol}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error placing TRAILING STOP SELL order for {symbol}: {e}", exc_info=True)
            return False

def create_alpaca_executor_from_env(portfolio_manager: Optional[SimplePortfolioManager] = None) -> AlpacaExecutor:
    """
    Create AlpacaExecutor from environment variables
    
    Expected environment variables:
    - PAPER_KEY: Alpaca API key for paper trading
    - PAPER_SECRET: Alpaca secret key for paper trading  
    - PAPER_ENDPOINT: Alpaca base URL for paper trading
    
    Args:
        portfolio_manager: Optional portfolio manager for multi-strategy support
    
    Returns:
        Configured AlpacaExecutor instance
    """
    # Get environment variables
    api_key = os.getenv('PAPER_KEY')
    secret_key = os.getenv('PAPER_SECRET')
    base_url = os.getenv('PAPER_ENDPOINT')
    
    if not api_key or not secret_key:
        raise ValueError("Missing required environment variables: PAPER_KEY and PAPER_SECRET")
    
    # Remove /v2 suffix if present in base_url since TradingClient adds it automatically
    if base_url and base_url.endswith('/v2'):
        base_url = base_url[:-3]
        logger.info(f"Removed /v2 suffix from base_url: {base_url}")
    
    config = AlpacaConfig(
        api_key=api_key,
        secret_key=secret_key, 
        base_url=base_url,
        paper=True  # Always use paper trading for safety
    )
    
    return AlpacaExecutor(config, portfolio_manager=portfolio_manager)
