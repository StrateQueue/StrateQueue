"""
Alpaca Main Executor

The main executor class that coordinates order execution using the modular order system.
"""

import logging
from typing import Dict, Optional
from datetime import datetime

from alpaca.trading.client import TradingClient
from alpaca.common.exceptions import APIError

from .config import AlpacaConfig, PositionSizeConfig
from .orders import (
    MarketBuyOrderExecutor, MarketSellOrderExecutor,
    LimitBuyOrderExecutor, LimitSellOrderExecutor,
    StopOrderExecutor, StopLimitOrderExecutor, TrailingStopOrderExecutor
)
from .utils import normalize_crypto_symbol
from ..signal_extractor import TradingSignal, SignalType
from ..simple_portfolio_manager import SimplePortfolioManager

logger = logging.getLogger(__name__)

class AlpacaExecutor:
    """
    Main Alpaca trading executor for live trading.
    
    Handles the actual execution of trading signals through the Alpaca API using
    a modular order execution system. Supports multi-strategy trading with portfolio
    management and conflict prevention.
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
            paper=config.paper_trading,
            url_override=config.base_url if config.base_url else None
        )
        
        # Initialize order executors
        self._init_order_executors()
        
        # Track pending orders and order counter for unique IDs
        self.pending_orders = {}
        self.order_counter = 0
        
        # Validate connection
        self._validate_connection()
    
    def _init_order_executors(self):
        """Initialize the modular order execution system"""
        self.order_executors = {
            SignalType.BUY: MarketBuyOrderExecutor(self.trading_client, self.portfolio_manager),
            SignalType.SELL: MarketSellOrderExecutor(self.trading_client, self.portfolio_manager),
            SignalType.CLOSE: MarketSellOrderExecutor(self.trading_client, self.portfolio_manager),  # Close uses sell executor
            SignalType.LIMIT_BUY: LimitBuyOrderExecutor(self.trading_client, self.portfolio_manager),
            SignalType.LIMIT_SELL: LimitSellOrderExecutor(self.trading_client, self.portfolio_manager),
            SignalType.STOP_BUY: StopOrderExecutor(self.trading_client, self.portfolio_manager),
            SignalType.STOP_SELL: StopOrderExecutor(self.trading_client, self.portfolio_manager),
            SignalType.STOP_LIMIT_BUY: StopLimitOrderExecutor(self.trading_client, self.portfolio_manager),
            SignalType.STOP_LIMIT_SELL: StopLimitOrderExecutor(self.trading_client, self.portfolio_manager),
            SignalType.TRAILING_STOP_SELL: TrailingStopOrderExecutor(self.trading_client, self.portfolio_manager)
        }
    
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
    
    def _validate_connection(self):
        """Validate connection to Alpaca API"""
        try:
            account = self.trading_client.get_account()
            logger.info(f"✅ Connected to Alpaca {'Paper' if self.config.paper_trading else 'Live'} Trading")
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
            
            # Handle HOLD signals
            if signal.signal == SignalType.HOLD:
                logger.debug(f"HOLD signal for {symbol} - no action needed")
                return True
            
            # Get the appropriate order executor
            order_executor = self.order_executors.get(signal.signal)
            if not order_executor:
                logger.warning(f"Unknown signal type: {signal.signal}")
                return False
            
            # Generate client order ID
            client_order_id = self._generate_client_order_id(strategy_id)
            
            # Execute the order with strategy context
            success, order_id = order_executor.execute(alpaca_symbol, signal, client_order_id, strategy_id)
            
            if success and order_id:
                self.pending_orders[alpaca_symbol] = order_id
                
                # Note: Trade recording for portfolio tracking will be handled
                # when actual order fills are received. For now, we just track
                # that orders were placed successfully.
            
            return success
                
        except Exception as e:
            logger.error(f"Error executing signal for {symbol}: {e}")
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