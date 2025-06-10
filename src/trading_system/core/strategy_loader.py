"""
Strategy Loading and Conversion

This module handles:
1. Dynamically loading strategy scripts
2. Converting backtesting strategies to signal-generating strategies
3. Calculating required lookback periods
4. Parsing strategy configuration
"""

import importlib.util
import inspect
import logging
import os
import re
from pathlib import Path
from typing import Type, Optional

from .signal_extractor import SignalExtractorStrategy, SignalType
from ..utils.mocks import Order

logger = logging.getLogger(__name__)

class StrategyLoader:
    """Dynamically load and analyze trading strategies"""
    
    @staticmethod
    def load_strategy_from_file(strategy_path: str) -> Type[SignalExtractorStrategy]:
        """
        Load a strategy class from a Python file
        
        Args:
            strategy_path: Path to the strategy file
            
        Returns:
            Strategy class that inherits from SignalExtractorStrategy
        """
        try:
            if not os.path.exists(strategy_path):
                raise FileNotFoundError(f"Strategy file not found: {strategy_path}")
            
            # Load the module
            spec = importlib.util.spec_from_file_location("strategy_module", strategy_path)
            module = importlib.util.module_from_spec(spec)
            
            # Inject Order class into module namespace before execution
            module.Order = Order
            
            spec.loader.exec_module(module)
            
            # Find strategy classes
            strategy_classes = []
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    hasattr(obj, 'init') and hasattr(obj, 'next') and 
                    name != 'Strategy' and name != 'SignalExtractorStrategy'):
                    strategy_classes.append(obj)
            
            if not strategy_classes:
                raise ValueError(f"No valid strategy class found in {strategy_path}")
            
            if len(strategy_classes) > 1:
                logger.warning(f"Multiple strategy classes found, using first one: {strategy_classes[0].__name__}")
            
            strategy_class = strategy_classes[0]
            logger.info(f"Loaded strategy: {strategy_class.__name__} from {strategy_path}")
            
            return strategy_class
            
        except Exception as e:
            logger.error(f"Error loading strategy from {strategy_path}: {e}")
            raise

    @staticmethod
    def convert_to_signal_strategy(original_strategy: Type) -> Type[SignalExtractorStrategy]:
        """
        Convert a regular backtesting.py strategy to a signal-extracting strategy
        
        Args:
            original_strategy: Original strategy class
            
        Returns:
            Modified strategy class that generates signals instead of trades
        """
        
        class ConvertedSignalStrategy(SignalExtractorStrategy):
            """Dynamically converted signal strategy"""
            
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                # Copy only safe class attributes from original strategy (parameters, not internal state)
                for attr_name in dir(original_strategy):
                    if (not attr_name.startswith('_') and 
                        not callable(getattr(original_strategy, attr_name)) and
                        not hasattr(self, attr_name) and  # Don't override existing attributes
                        attr_name not in ['closed_trades', 'trades', 'data', 'broker', 'position']):  # Skip backtesting internals
                        try:
                            setattr(self, attr_name, getattr(original_strategy, attr_name))
                        except (AttributeError, TypeError):
                            # Skip attributes that can't be set
                            pass
            
            def init(self):
                # Call original init method
                if hasattr(original_strategy, 'init'):
                    original_init = getattr(original_strategy, 'init')
                    original_init(self)
            
            def next(self):
                # Store original position methods
                original_buy = getattr(self, 'buy', None)
                original_sell = getattr(self, 'sell', None)
                original_close = getattr(self.position, 'close', None) if hasattr(self, 'position') else None
                
                buy_called = False
                sell_called = False
                close_called = False
                trade_params = {}
                
                # Create mock methods that track calls and parameters
                def mock_buy(*args, **kwargs):
                    nonlocal buy_called, trade_params
                    buy_called = True
                    trade_params = kwargs
                    # Also capture positional args if any (like price as first arg)
                    if args:
                        if 'price' not in kwargs and len(args) > 0:
                            trade_params['price'] = args[0]
                    return None
                
                def mock_sell(*args, **kwargs):
                    nonlocal sell_called, trade_params
                    sell_called = True
                    trade_params = kwargs
                    # Also capture positional args if any (like price as first arg)
                    if args:
                        if 'price' not in kwargs and len(args) > 0:
                            trade_params['price'] = args[0]
                    return None
                
                def mock_close(*args, **kwargs):
                    nonlocal close_called
                    close_called = True
                    return None
                
                # Replace methods temporarily
                self.buy = mock_buy
                self.sell = mock_sell
                if hasattr(self, 'position'):
                    self.position.close = mock_close
                
                # Call original next method
                if hasattr(original_strategy, 'next'):
                    original_next = getattr(original_strategy, 'next')
                    original_next(self)
                
                # Determine signal based on what was called
                signal_size = trade_params.get('size')
                limit_price = trade_params.get('limit')
                stop_price = trade_params.get('stop')
                stop_loss = trade_params.get('sl')
                take_profit = trade_params.get('tp')
                exectype = trade_params.get('exectype')
                valid = trade_params.get('valid')
                
                # Convert valid to time_in_force
                time_in_force = "gtc"
                if valid is not None:
                    if valid == 0 or (hasattr(valid, 'days') and valid.days == 0):
                        time_in_force = "day"

                if buy_called:
                    if exectype and hasattr(exectype, '__name__'):
                        exec_name = exectype.__name__
                        if 'Stop' in exec_name and 'Limit' in exec_name:
                            # StopLimit order
                            self.set_signal(SignalType.STOP_LIMIT_BUY, confidence=0.8, size=signal_size, 
                                          stop_price=stop_price, limit_price=limit_price, time_in_force=time_in_force)
                        elif 'Stop' in exec_name:
                            # Stop order
                            self.set_signal(SignalType.STOP_BUY, confidence=0.8, size=signal_size, 
                                          stop_price=stop_price, time_in_force=time_in_force)
                        elif 'Limit' in exec_name:
                            # Limit order
                            self.set_signal(SignalType.LIMIT_BUY, confidence=0.8, size=signal_size, 
                                          limit_price=limit_price, time_in_force=time_in_force)
                        else:
                            # Market order
                            self.set_signal(SignalType.BUY, confidence=0.8, size=signal_size, time_in_force=time_in_force)
                    elif limit_price is not None:
                        # Legacy limit order detection
                        self.set_signal(SignalType.LIMIT_BUY, confidence=0.8, size=signal_size, 
                                      limit_price=limit_price, time_in_force=time_in_force)
                    else:
                        # Market order
                        self.set_signal(SignalType.BUY, confidence=0.8, size=signal_size, time_in_force=time_in_force)
                        
                elif sell_called:
                    if exectype and hasattr(exectype, '__name__'):
                        exec_name = exectype.__name__
                        if 'Stop' in exec_name and 'Limit' in exec_name:
                            # StopLimit order
                            self.set_signal(SignalType.STOP_LIMIT_SELL, confidence=0.8, size=signal_size, 
                                          stop_price=stop_price, limit_price=limit_price, time_in_force=time_in_force)
                        elif 'Stop' in exec_name:
                            # Stop order
                            self.set_signal(SignalType.STOP_SELL, confidence=0.8, size=signal_size, 
                                          stop_price=stop_price, time_in_force=time_in_force)
                        elif 'Limit' in exec_name:
                            # Limit order
                            self.set_signal(SignalType.LIMIT_SELL, confidence=0.8, size=signal_size, 
                                          limit_price=limit_price, time_in_force=time_in_force)
                        else:
                            # Market order
                            self.set_signal(SignalType.SELL, confidence=0.8, size=signal_size, time_in_force=time_in_force)
                    elif limit_price is not None:
                        # Legacy limit order detection
                        self.set_signal(SignalType.LIMIT_SELL, confidence=0.8, size=signal_size, 
                                      limit_price=limit_price, time_in_force=time_in_force)
                    else:
                        # Market order
                        self.set_signal(SignalType.SELL, confidence=0.8, size=signal_size, time_in_force=time_in_force)
                        
                elif close_called:
                    self.set_signal(SignalType.CLOSE, confidence=0.6, time_in_force=time_in_force)
                else:
                    self.set_signal(SignalType.HOLD, confidence=0.1)
                
                # Store current indicators (try to extract common ones)
                self.indicators_values = {}
                if hasattr(self, 'data'):
                    self.indicators_values['price'] = self.data.Close[-1]
                    
                # Try to extract SMA values
                for attr_name in dir(self):
                    if 'sma' in attr_name.lower() and not attr_name.startswith('_'):
                        try:
                            sma_values = getattr(self, attr_name)
                            if hasattr(sma_values, '__getitem__'):
                                self.indicators_values[attr_name] = sma_values[-1]
                        except:
                            pass
                
                # Restore original methods
                if original_buy:
                    self.buy = original_buy
                if original_sell:
                    self.sell = original_sell
                if original_close and hasattr(self, 'position'):
                    self.position.close = original_close
        
        # Copy class attributes
        for attr_name in dir(original_strategy):
            if not attr_name.startswith('_') and not callable(getattr(original_strategy, attr_name)):
                setattr(ConvertedSignalStrategy, attr_name, getattr(original_strategy, attr_name))
        
        ConvertedSignalStrategy.__name__ = f"Signal{original_strategy.__name__}"
        return ConvertedSignalStrategy

    @staticmethod
    def calculate_lookback_period(strategy_class: Type, strategy_path: str = None, default_lookback: int = 50) -> int:
        """
        Calculate required lookback period for a strategy
        
        Args:
            strategy_class: The strategy class
            strategy_path: Path to the strategy file (for parsing LOOKBACK config)
            default_lookback: Default lookback if none specified
            
        Returns:
            Required lookback period
        """
        
        # First, try to parse LOOKBACK configuration from the strategy file
        if strategy_path:
            try:
                lookback_from_file = StrategyLoader._parse_lookback_from_file(strategy_path)
                if lookback_from_file is not None:
                    logger.info(f"Using LOOKBACK={lookback_from_file} from strategy file")
                    return lookback_from_file
            except Exception as e:
                logger.warning(f"Could not parse LOOKBACK from strategy file: {e}")
        
        # Fallback to automatic detection from class attributes
        try:
            # Look for common indicator period attributes
            max_period = 0
            
            # Check for moving average periods
            for attr in ['n1', 'n2', 'n3', 'short_period', 'long_period', 'period', 'window']:
                if hasattr(strategy_class, attr):
                    value = getattr(strategy_class, attr)
                    if isinstance(value, int) and value > max_period:
                        max_period = value
            
            # Check for RSI periods (common default is 14)
            if hasattr(strategy_class, 'rsi_period'):
                rsi_period = getattr(strategy_class, 'rsi_period')
                if isinstance(rsi_period, int):
                    max_period = max(max_period, rsi_period)
            
            # Add buffer for indicator calculation
            if max_period > 0:
                calculated_lookback = max_period + 10  # Add 10 bar buffer
                logger.info(f"Calculated lookback period: {calculated_lookback} (based on max period {max_period})")
                return calculated_lookback
            
        except Exception as e:
            logger.warning(f"Error in automatic lookback calculation: {e}")
        
        # Final fallback
        logger.info(f"Using default lookback period: {default_lookback}")
        return default_lookback
    
    @staticmethod
    def _parse_lookback_from_file(strategy_path: str) -> Optional[int]:
        """
        Parse LOOKBACK configuration from strategy file
        
        Args:
            strategy_path: Path to strategy file
            
        Returns:
            LOOKBACK value if found, None otherwise
        """
        try:
            with open(strategy_path, 'r') as f:
                content = f.read()
            
            # Look for LOOKBACK = <number> pattern
            
            # Match patterns like "LOOKBACK = 20" or "LOOKBACK=20"
            pattern = r'^\s*LOOKBACK\s*=\s*(\d+)'
            
            for line in content.split('\n'):
                match = re.match(pattern, line.strip())
                if match:
                    lookback_value = int(match.group(1))
                    return lookback_value
            
            return None
            
        except Exception as e:
            logger.warning(f"Error parsing lookback from {strategy_path}: {e}")
            return None 