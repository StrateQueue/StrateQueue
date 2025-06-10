"""
Alpaca Order Management

Contains base order classes and specific order type implementations.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
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

from ..signal_extractor import TradingSignal, SignalType

logger = logging.getLogger(__name__)

class BaseOrderExecutor(ABC):
    """
    Base class for order execution strategies.
    
    Each order type inherits from this and implements its specific execution logic.
    """
    
    def __init__(self, trading_client: TradingClient, portfolio_manager=None):
        self.trading_client = trading_client
        self.portfolio_manager = portfolio_manager
    
    @abstractmethod
    def execute(self, symbol: str, signal: TradingSignal, client_order_id: str, strategy_id: Optional[str] = None) -> tuple[bool, Optional[str]]:
        """
        Execute the order for this signal type.
        
        Args:
            symbol: Symbol to trade
            signal: Trading signal
            client_order_id: Unique client order ID
            strategy_id: Strategy identifier for portfolio allocation (optional)
            
        Returns:
            Tuple of (success: bool, order_id: Optional[str])
        """
        pass
    
    def _get_account(self):
        """Get account information"""
        return self.trading_client.get_account()
    
    def _get_position(self, symbol: str):
        """Get position for symbol, trying alternative formats if needed"""
        try:
            return self.trading_client.get_open_position(symbol)
        except APIError as e:
            if "position does not exist" in str(e).lower() or "not found" in str(e).lower():
                # Try alternative symbol format (remove slash for crypto)
                alt_symbol = symbol.replace('/', '')
                try:
                    position = self.trading_client.get_open_position(alt_symbol)
                    logger.info(f"Found position using alternative symbol {alt_symbol}")
                    return position, alt_symbol
                except APIError:
                    return None, symbol
            else:
                raise e
        return self.trading_client.get_open_position(symbol), symbol
    
    def _calculate_notional_amount(self, signal: TradingSignal, account, strategy_id: Optional[str] = None) -> float:
        """Calculate notional amount based on signal size and strategy allocation"""
        
        # If we have portfolio manager and strategy context, use strategy allocation
        if self.portfolio_manager and strategy_id:
            strategy_status = self.portfolio_manager.get_strategy_status(strategy_id)
            
            if signal.size and 0 < signal.size <= 1:
                # Use signal size as percentage of strategy's allocated capital
                strategy_allocation = strategy_status.get('total_allocated', 0.0)
                notional_amount = strategy_allocation * signal.size
            else:
                # Use most of strategy's available capital
                available_capital = strategy_status.get('available_capital', 0.0)
                notional_amount = available_capital * 0.99
                
            logger.debug(f"Strategy {strategy_id} notional calculation: ${notional_amount:.2f} "
                        f"(allocation: ${strategy_status.get('total_allocated', 0.0):.2f}, "
                        f"available: ${strategy_status.get('available_capital', 0.0):.2f})")
        else:
            # Fallback to original logic for backward compatibility
            if signal.size and 0 < signal.size <= 1:
                notional_amount = float(account.portfolio_value) * signal.size
            else:
                cash_balance = float(account.cash)
                notional_amount = cash_balance * 0.99  # Use 99% of cash balance
        
        return round(notional_amount, 2)
    
    def _calculate_sell_quantity(self, signal: TradingSignal, position) -> float:
        """Calculate quantity to sell based on signal size and position"""
        qty_available = abs(float(position.qty))
        
        if signal.size and 0 < signal.size <= 1:
            return qty_available * signal.size
        else:
            return qty_available
    
    def _get_time_in_force(self, signal: TradingSignal) -> TimeInForce:
        """Get TimeInForce from signal"""
        if hasattr(signal, 'time_in_force') and signal.time_in_force.upper() == "DAY":
            return TimeInForce.DAY
        return TimeInForce.GTC

class MarketBuyOrderExecutor(BaseOrderExecutor):
    """Executor for market buy orders"""
    
    def execute(self, symbol: str, signal: TradingSignal, client_order_id: str, strategy_id: Optional[str] = None) -> tuple[bool, Optional[str]]:
        try:
            account = self._get_account()
            notional_amount = self._calculate_notional_amount(signal, account, strategy_id)
            
            logger.info(f"Market BUY: ${notional_amount:.2f} of {symbol}")
            
            order_data = MarketOrderRequest(
                symbol=symbol,
                notional=notional_amount,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC,
                client_order_id=client_order_id
            )
            
            order = self.trading_client.submit_order(order_data=order_data)
            logger.info(f"✅ Market BUY order placed for {symbol}: ${notional_amount:.2f}, Order ID: {order.id}")
            return True, order.id
            
        except APIError as e:
            logger.error(f"Alpaca API error placing market BUY order for {symbol}: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Unexpected error placing market BUY order for {symbol}: {e}", exc_info=True)
            return False, None

class MarketSellOrderExecutor(BaseOrderExecutor):
    """Executor for market sell orders"""
    
    def execute(self, symbol: str, signal: TradingSignal, client_order_id: str, strategy_id: Optional[str] = None) -> tuple[bool, Optional[str]]:
        try:
            position, actual_symbol = self._get_position(symbol)
            
            if position is None:
                logger.warning(f"Market SELL signal for {symbol}, but no position exists. No action taken.")
                return True, None  # Not a failure, just nothing to sell
            
            qty_to_sell = self._calculate_sell_quantity(signal, position)
            current_price = float(position.market_value) / abs(float(position.qty))
            
            logger.info(f"Market SELL: {qty_to_sell:.8f} {actual_symbol} (~${qty_to_sell * current_price:.2f})")
            
            if signal.size and 0 < signal.size <= 1:
                # Partial sell
                order_data = MarketOrderRequest(
                    symbol=actual_symbol,
                    qty=qty_to_sell,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.GTC,
                    client_order_id=client_order_id
                )
                order = self.trading_client.submit_order(order_data=order_data)
                logger.info(f"✅ Market SELL order placed for {qty_to_sell:.8f} {actual_symbol}, Order ID: {order.id}")
                return True, order.id
            else:
                # Close entire position
                close_order = self.trading_client.close_position(actual_symbol)
                logger.info(f"✅ CLOSE position order placed for {actual_symbol}, Order ID: {close_order.id}")
                return True, close_order.id
                
        except APIError as e:
            logger.error(f"Alpaca API error placing market SELL order for {symbol}: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Unexpected error placing market SELL order for {symbol}: {e}", exc_info=True)
            return False, None

class LimitBuyOrderExecutor(BaseOrderExecutor):
    """Executor for limit buy orders"""
    
    def execute(self, symbol: str, signal: TradingSignal, client_order_id: str, strategy_id: Optional[str] = None) -> tuple[bool, Optional[str]]:
        try:
            if not signal.limit_price:
                logger.error(f"LIMIT_BUY signal for {symbol} missing limit_price")
                return False, None
            
            account = self._get_account()
            notional_amount = self._calculate_notional_amount(signal, account, strategy_id)
            
            logger.info(f"Limit BUY: ${notional_amount:.2f} of {symbol} @ ${signal.limit_price:.2f}")
            
            order_data = LimitOrderRequest(
                symbol=symbol,
                notional=notional_amount,
                side=OrderSide.BUY,
                time_in_force=self._get_time_in_force(signal),
                limit_price=signal.limit_price,
                client_order_id=client_order_id
            )
            
            order = self.trading_client.submit_order(order_data=order_data)
            logger.info(f"✅ Limit BUY order placed for {symbol}: ${notional_amount:.2f} @ ${signal.limit_price:.2f}, Order ID: {order.id}")
            return True, order.id
            
        except APIError as e:
            logger.error(f"Alpaca API error placing limit BUY order for {symbol}: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Unexpected error placing limit BUY order for {symbol}: {e}", exc_info=True)
            return False, None

class LimitSellOrderExecutor(BaseOrderExecutor):
    """Executor for limit sell orders"""
    
    def execute(self, symbol: str, signal: TradingSignal, client_order_id: str, strategy_id: Optional[str] = None) -> tuple[bool, Optional[str]]:
        try:
            if not signal.limit_price:
                logger.error(f"LIMIT_SELL signal for {symbol} missing limit_price")
                return False, None
            
            position, actual_symbol = self._get_position(symbol)
            
            if position is None:
                logger.warning(f"Limit SELL signal for {symbol}, but no position exists. No action taken.")
                return True, None
            
            qty_to_sell = self._calculate_sell_quantity(signal, position)
            
            logger.info(f"Limit SELL: {qty_to_sell:.8f} {actual_symbol} @ ${signal.limit_price:.2f}")
            
            order_data = LimitOrderRequest(
                symbol=actual_symbol,
                qty=qty_to_sell,
                side=OrderSide.SELL,
                time_in_force=self._get_time_in_force(signal),
                limit_price=signal.limit_price,
                client_order_id=client_order_id
            )
            
            order = self.trading_client.submit_order(order_data=order_data)
            logger.info(f"✅ Limit SELL order placed for {qty_to_sell:.8f} {actual_symbol} @ ${signal.limit_price:.2f}, Order ID: {order.id}")
            return True, order.id
            
        except APIError as e:
            logger.error(f"Alpaca API error placing limit SELL order for {symbol}: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Unexpected error placing limit SELL order for {symbol}: {e}", exc_info=True)
            return False, None

class StopOrderExecutor(BaseOrderExecutor):
    """Executor for stop orders (both buy and sell)"""
    
    def execute(self, symbol: str, signal: TradingSignal, client_order_id: str, strategy_id: Optional[str] = None) -> tuple[bool, Optional[str]]:
        try:
            if not signal.stop_price:
                logger.error(f"STOP order signal for {symbol} missing stop_price")
                return False, None
            
            if signal.signal == SignalType.STOP_BUY:
                return self._execute_stop_buy(symbol, signal, client_order_id, strategy_id)
            elif signal.signal == SignalType.STOP_SELL:
                return self._execute_stop_sell(symbol, signal, client_order_id, strategy_id)
            else:
                logger.error(f"Invalid signal type for StopOrderExecutor: {signal.signal}")
                return False, None
                
        except Exception as e:
            logger.error(f"Unexpected error placing stop order for {symbol}: {e}", exc_info=True)
            return False, None
    
    def _execute_stop_buy(self, symbol: str, signal: TradingSignal, client_order_id: str, strategy_id: Optional[str] = None) -> tuple[bool, Optional[str]]:
        account = self._get_account()
        notional_amount = self._calculate_notional_amount(signal, account, strategy_id)
        
        logger.info(f"Stop BUY: ${notional_amount:.2f} of {symbol} @ stop ${signal.stop_price:.2f}")
        
        order_data = StopOrderRequest(
            symbol=symbol,
            notional=notional_amount,
            side=OrderSide.BUY,
            time_in_force=self._get_time_in_force(signal),
            stop_price=signal.stop_price,
            client_order_id=client_order_id
        )
        
        order = self.trading_client.submit_order(order_data=order_data)
        logger.info(f"✅ Stop BUY order placed for {symbol}: ${notional_amount:.2f} @ stop ${signal.stop_price:.2f}, Order ID: {order.id}")
        return True, order.id
    
    def _execute_stop_sell(self, symbol: str, signal: TradingSignal, client_order_id: str, strategy_id: Optional[str] = None) -> tuple[bool, Optional[str]]:
        position, actual_symbol = self._get_position(symbol)
        
        if position is None:
            logger.warning(f"Stop SELL signal for {symbol}, but no position exists. No action taken.")
            return True, None
        
        qty_to_sell = self._calculate_sell_quantity(signal, position)
        
        logger.info(f"Stop SELL: {qty_to_sell:.8f} {actual_symbol} @ stop ${signal.stop_price:.2f}")
        
        order_data = StopOrderRequest(
            symbol=actual_symbol,
            qty=qty_to_sell,
            side=OrderSide.SELL,
            time_in_force=self._get_time_in_force(signal),
            stop_price=signal.stop_price,
            client_order_id=client_order_id
        )
        
        order = self.trading_client.submit_order(order_data=order_data)
        logger.info(f"✅ Stop SELL order placed for {qty_to_sell:.8f} {actual_symbol} @ stop ${signal.stop_price:.2f}, Order ID: {order.id}")
        return True, order.id

class StopLimitOrderExecutor(BaseOrderExecutor):
    """Executor for stop-limit orders (both buy and sell)"""
    
    def execute(self, symbol: str, signal: TradingSignal, client_order_id: str, strategy_id: Optional[str] = None) -> tuple[bool, Optional[str]]:
        try:
            if not signal.stop_price or not signal.limit_price:
                logger.error(f"STOP_LIMIT order signal for {symbol} missing stop_price or limit_price")
                return False, None
            
            if signal.signal == SignalType.STOP_LIMIT_BUY:
                return self._execute_stop_limit_buy(symbol, signal, client_order_id, strategy_id)
            elif signal.signal == SignalType.STOP_LIMIT_SELL:
                return self._execute_stop_limit_sell(symbol, signal, client_order_id, strategy_id)
            else:
                logger.error(f"Invalid signal type for StopLimitOrderExecutor: {signal.signal}")
                return False, None
                
        except Exception as e:
            logger.error(f"Unexpected error placing stop-limit order for {symbol}: {e}", exc_info=True)
            return False, None
    
    def _execute_stop_limit_buy(self, symbol: str, signal: TradingSignal, client_order_id: str, strategy_id: Optional[str] = None) -> tuple[bool, Optional[str]]:
        account = self._get_account()
        notional_amount = self._calculate_notional_amount(signal, account, strategy_id)
        
        logger.info(f"Stop-Limit BUY: ${notional_amount:.2f} of {symbol} @ stop ${signal.stop_price:.2f}, limit ${signal.limit_price:.2f}")
        
        order_data = StopLimitOrderRequest(
            symbol=symbol,
            notional=notional_amount,
            side=OrderSide.BUY,
            time_in_force=self._get_time_in_force(signal),
            stop_price=signal.stop_price,
            limit_price=signal.limit_price,
            client_order_id=client_order_id
        )
        
        order = self.trading_client.submit_order(order_data=order_data)
        logger.info(f"✅ Stop-Limit BUY order placed for {symbol}: ${notional_amount:.2f} @ stop ${signal.stop_price:.2f}, limit ${signal.limit_price:.2f}, Order ID: {order.id}")
        return True, order.id
    
    def _execute_stop_limit_sell(self, symbol: str, signal: TradingSignal, client_order_id: str, strategy_id: Optional[str] = None) -> tuple[bool, Optional[str]]:
        position, actual_symbol = self._get_position(symbol)
        
        if position is None:
            logger.warning(f"Stop-Limit SELL signal for {symbol}, but no position exists. No action taken.")
            return True, None
        
        qty_to_sell = self._calculate_sell_quantity(signal, position)
        
        logger.info(f"Stop-Limit SELL: {qty_to_sell:.8f} {actual_symbol} @ stop ${signal.stop_price:.2f}, limit ${signal.limit_price:.2f}")
        
        order_data = StopLimitOrderRequest(
            symbol=actual_symbol,
            qty=qty_to_sell,
            side=OrderSide.SELL,
            time_in_force=self._get_time_in_force(signal),
            stop_price=signal.stop_price,
            limit_price=signal.limit_price,
            client_order_id=client_order_id
        )
        
        order = self.trading_client.submit_order(order_data=order_data)
        logger.info(f"✅ Stop-Limit SELL order placed for {qty_to_sell:.8f} {actual_symbol} @ stop ${signal.stop_price:.2f}, limit ${signal.limit_price:.2f}, Order ID: {order.id}")
        return True, order.id

class TrailingStopOrderExecutor(BaseOrderExecutor):
    """Executor for trailing stop orders"""
    
    def execute(self, symbol: str, signal: TradingSignal, client_order_id: str, strategy_id: Optional[str] = None) -> tuple[bool, Optional[str]]:
        try:
            if not signal.trail_percent and not signal.trail_price:
                logger.error(f"TRAILING_STOP_SELL signal for {symbol} missing trail_percent or trail_price")
                return False, None
            
            position, actual_symbol = self._get_position(symbol)
            
            if position is None:
                logger.warning(f"Trailing stop SELL signal for {symbol}, but no position exists. No action taken.")
                return True, None
            
            qty_to_sell = self._calculate_sell_quantity(signal, position)
            
            # Create trailing stop order (prefer percentage over absolute price)
            if signal.trail_percent:
                trail_info = f"Trail%={signal.trail_percent:.2%}"
                order_data = TrailingStopOrderRequest(
                    symbol=actual_symbol,
                    qty=qty_to_sell,
                    side=OrderSide.SELL,
                    time_in_force=self._get_time_in_force(signal),
                    trail_percent=signal.trail_percent,
                    client_order_id=client_order_id
                )
            else:
                trail_info = f"Trail=${signal.trail_price:.2f}"
                order_data = TrailingStopOrderRequest(
                    symbol=actual_symbol,
                    qty=qty_to_sell,
                    side=OrderSide.SELL,
                    time_in_force=self._get_time_in_force(signal),
                    trail_price=signal.trail_price,
                    client_order_id=client_order_id
                )
            
            logger.info(f"Trailing Stop SELL: {qty_to_sell:.8f} {actual_symbol} @ {trail_info}")
            
            order = self.trading_client.submit_order(order_data=order_data)
            logger.info(f"✅ Trailing Stop SELL order placed for {qty_to_sell:.8f} {actual_symbol} @ {trail_info}, Order ID: {order.id}")
            return True, order.id
            
        except APIError as e:
            logger.error(f"Alpaca API error placing trailing stop SELL order for {symbol}: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Unexpected error placing trailing stop SELL order for {symbol}: {e}", exc_info=True)
            return False, None 