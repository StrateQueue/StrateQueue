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
            paper=config.paper,
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
            SignalType.BUY: MarketBuyOrderExecutor(self.trading_client),
            SignalType.SELL: MarketSellOrderExecutor(self.trading_client),
            SignalType.CLOSE: MarketSellOrderExecutor(self.trading_client),  # Close uses sell executor
            SignalType.LIMIT_BUY: LimitBuyOrderExecutor(self.trading_client),
            SignalType.LIMIT_SELL: LimitSellOrderExecutor(self.trading_client),
            SignalType.STOP_BUY: StopOrderExecutor(self.trading_client),
            SignalType.STOP_SELL: StopOrderExecutor(self.trading_client),
            SignalType.STOP_LIMIT_BUY: StopLimitOrderExecutor(self.trading_client),
            SignalType.STOP_LIMIT_SELL: StopLimitOrderExecutor(self.trading_client),
            SignalType.TRAILING_STOP_SELL: TrailingStopOrderExecutor(self.trading_client)
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
            
            # Execute the order
            success, order_id = order_executor.execute(alpaca_symbol, signal, client_order_id)
            
            if success and order_id:
                self.pending_orders[alpaca_symbol] = order_id
                
                # Record execution for portfolio tracking (estimate execution amount)
                try:
                    account = self.trading_client.get_account()
                    if signal.signal in [SignalType.BUY, SignalType.LIMIT_BUY, SignalType.STOP_BUY, 
                                       SignalType.STOP_LIMIT_BUY]:
                        if signal.size and 0 < signal.size <= 1:
                            execution_amount = float(account.portfolio_value) * signal.size
                        else:
                            execution_amount = float(account.cash) * 0.99
                    else:
                        # For sell orders, estimate based on current position value
                        try:
                            position = self.trading_client.get_open_position(alpaca_symbol)
                            execution_amount = float(position.market_value)
                            if signal.size and 0 < signal.size <= 1:
                                execution_amount *= signal.size
                        except:
                            execution_amount = 0  # Can't estimate
                    
                    self._record_trade_execution(alpaca_symbol, signal, execution_amount, True)
                except Exception as e:
                    logger.warning(f"Could not record trade execution: {e}")
            
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