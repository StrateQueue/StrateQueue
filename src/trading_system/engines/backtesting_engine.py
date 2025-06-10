"""
Backtesting.py Engine Implementation

Implements the trading engine interface for backtesting.py strategies.
This module contains all the backtesting.py-specific logic for loading strategies
and extracting signals.
"""

import pandas as pd
import numpy as np
import os
import importlib.util
import inspect
import re
import logging
from typing import Type, Optional, Dict, Any
from pathlib import Path

from backtesting import Backtest, Strategy
from backtesting.lib import crossover

from .base import TradingEngine, EngineStrategy, EngineSignalExtractor, EngineInfo
from ..core.signal_extractor import TradingSignal, SignalType
from ..utils.mocks import Order

logger = logging.getLogger(__name__)


class BacktestingEngineStrategy(EngineStrategy):
    """Wrapper for backtesting.py strategies"""
    
    def __init__(self, strategy_class: Type, strategy_params: Dict[str, Any] = None):
        super().__init__(strategy_class, strategy_params)
        self.lookback_period = None
        
    def get_lookback_period(self) -> int:
        """Get the minimum number of bars required by this strategy"""
        if self.lookback_period is not None:
            return self.lookback_period
        
        # Try to extract from class attributes or calculate from indicators
        # This is a simplified version - more sophisticated analysis could be added
        return getattr(self.strategy_class, 'LOOKBACK', 50)  # Default fallback
    
    def get_strategy_name(self) -> str:
        """Get a human-readable name for this strategy"""
        return self.strategy_class.__name__
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get strategy parameters"""
        params = {}
        
        # Extract class-level parameters
        for attr_name in dir(self.strategy_class):
            if (not attr_name.startswith('_') and 
                not callable(getattr(self.strategy_class, attr_name)) and
                attr_name not in ['data', 'broker', 'position']):  # Skip backtesting internals
                try:
                    params[attr_name] = getattr(self.strategy_class, attr_name)
                except (AttributeError, TypeError):
                    pass
        
        # Add strategy_params passed to constructor
        params.update(self.strategy_params)
        
        return params


class SignalExtractorStrategy(Strategy):
    """
    Modified backtesting.py strategy that captures signals instead of executing trades.
    This allows us to extract the current signal from the last timestep.
    """
    
    def __init__(self, *args, **kwargs):
        # Initialize with any arguments backtesting.py provides
        super().__init__(*args, **kwargs)
        
        self.current_signal = SignalType.HOLD
        self.signal_confidence = 0.0
        self.indicators_values = {}
        self.signal_history = []
        
    def next(self):
        """
        Override this method in your strategy to:
        1. Calculate indicators
        2. Determine signal
        3. Store signal instead of executing trades
        """
        # This will be overridden by actual strategy implementations
        pass
    
    def set_signal(self, signal: SignalType, confidence: float = 1.0, metadata: Dict[str, Any] = None, 
                   size: Optional[float] = None, limit_price: Optional[float] = None,
                   stop_price: Optional[float] = None, trail_percent: Optional[float] = None,
                   trail_price: Optional[float] = None, time_in_force: str = "gtc"):
        """Set the current signal instead of calling buy/sell"""
        self.current_signal = signal
        self.signal_confidence = confidence
        
        # Store signal with current data
        signal_obj = TradingSignal(
            signal=signal,
            confidence=confidence,
            price=self.data.Close[-1],
            timestamp=self.data.index[-1] if hasattr(self.data.index, '__getitem__') else pd.Timestamp.now(),
            indicators=self.indicators_values.copy(),
            metadata=metadata or {},
            size=size,
            limit_price=limit_price,
            stop_price=stop_price,
            trail_percent=trail_percent,
            trail_price=trail_price,
            time_in_force=time_in_force
        )
        
        self.signal_history.append(signal_obj)
        
    def set_limit_buy_signal(self, limit_price: float, confidence: float = 1.0, size: Optional[float] = None, metadata: Dict[str, Any] = None):
        """Set a limit buy signal with specified limit price"""
        self.set_signal(SignalType.LIMIT_BUY, confidence, metadata, size, limit_price)
        
    def set_limit_sell_signal(self, limit_price: float, confidence: float = 1.0, size: Optional[float] = None, metadata: Dict[str, Any] = None):
        """Set a limit sell signal with specified limit price"""
        self.set_signal(SignalType.LIMIT_SELL, confidence, metadata, size, limit_price)
    
    def get_current_signal(self) -> TradingSignal:
        """Get the most recent signal"""
        if self.signal_history:
            return self.signal_history[-1]
        else:
            return TradingSignal(
                signal=SignalType.HOLD,
                confidence=0.0,
                price=self.data.Close[-1] if len(self.data.Close) > 0 else 0.0,
                timestamp=pd.Timestamp.now(),
                indicators=self.indicators_values.copy()
            )


class BacktestingSignalExtractor(EngineSignalExtractor):
    """Signal extractor for backtesting.py strategies"""
    
    def __init__(self, engine_strategy: BacktestingEngineStrategy, min_bars_required: int = 2, **strategy_params):
        super().__init__(engine_strategy)
        self.strategy_class = engine_strategy.strategy_class
        self.strategy_params = strategy_params
        self.min_bars_required = min_bars_required
        
        # Create the signal-extracting version of the strategy
        self.signal_strategy_class = self._convert_to_signal_strategy(engine_strategy.strategy_class)
        
    def extract_signal(self, historical_data: pd.DataFrame) -> TradingSignal:
        """Extract trading signal from historical data"""
        try:
            # Ensure we have enough data
            if len(historical_data) < self.min_bars_required:
                logger.warning("Insufficient historical data for signal extraction")
                return TradingSignal(
                    signal=SignalType.HOLD,
                    confidence=0.0,
                    price=0.0,
                    timestamp=pd.Timestamp.now(),
                    indicators={}
                )
            
            # Prepare data for backtesting.py format
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            if not all(col in historical_data.columns for col in required_columns):
                logger.error(f"Historical data missing required columns: {required_columns}")
                raise ValueError("Invalid data format")
            
            data = historical_data[required_columns].copy()
            
            # Create a backtest instance but don't run full backtest
            bt = Backtest(data, self.signal_strategy_class, 
                         cash=10000,  # Dummy cash amount
                         commission=0.0,  # No commission for signal extraction
                         **self.strategy_params)
            
            # Run the backtest to initialize strategy and process all historical data
            results = bt.run()
            
            # Extract the strategy instance to get the current signal
            strategy_instance = results._strategy
            
            # Get the current signal
            current_signal = strategy_instance.get_current_signal()
            
            self.last_signal = current_signal
            
            logger.debug(f"Extracted signal: {current_signal.signal.value} "
                        f"(confidence: {current_signal.confidence:.2f}) "
                        f"at price: ${current_signal.price:.2f}")
            
            return current_signal
            
        except Exception as e:
            logger.error(f"Error extracting signal: {e}")
            # Return safe default signal
            return TradingSignal(
                signal=SignalType.HOLD,
                confidence=0.0,
                price=historical_data['Close'].iloc[-1] if len(historical_data) > 0 else 0.0,
                timestamp=pd.Timestamp.now(),
                indicators={},
                metadata={'error': str(e)}
            )
    
    def get_minimum_bars_required(self) -> int:
        """Get minimum number of bars needed for signal extraction"""
        return max(self.min_bars_required, self.engine_strategy.get_lookback_period())
    
    def _convert_to_signal_strategy(self, original_strategy: Type) -> Type[SignalExtractorStrategy]:
        """Convert a regular backtesting.py strategy to a signal-extracting strategy"""
        
        class ConvertedSignalStrategy(SignalExtractorStrategy):
            """Dynamically converted signal strategy"""
            
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                # Copy only safe class attributes from original strategy
                for attr_name in dir(original_strategy):
                    if (not attr_name.startswith('_') and 
                        not callable(getattr(original_strategy, attr_name)) and
                        not hasattr(self, attr_name) and  # Don't override existing attributes
                        attr_name not in ['closed_trades', 'trades', 'data', 'broker', 'position']):
                        try:
                            setattr(self, attr_name, getattr(original_strategy, attr_name))
                        except (AttributeError, TypeError):
                            pass
            
            def init(self):
                # Call original init method
                if hasattr(original_strategy, 'init'):
                    original_init = getattr(original_strategy, 'init')
                    original_init(self)
            
            def next(self):
                # Mock trading methods to capture signals
                buy_called = False
                sell_called = False
                close_called = False
                trade_params = {}
                
                def mock_buy(*args, **kwargs):
                    nonlocal buy_called, trade_params
                    buy_called = True
                    trade_params = kwargs
                    if args:
                        if 'price' not in kwargs and len(args) > 0:
                            trade_params['price'] = args[0]
                    return None
                
                def mock_sell(*args, **kwargs):
                    nonlocal sell_called, trade_params
                    sell_called = True
                    trade_params = kwargs
                    if args:
                        if 'price' not in kwargs and len(args) > 0:
                            trade_params['price'] = args[0]
                    return None
                
                def mock_close(*args, **kwargs):
                    nonlocal close_called
                    close_called = True
                    return None
                
                # Replace methods temporarily
                original_buy = getattr(self, 'buy', None)
                original_sell = getattr(self, 'sell', None)
                original_close = getattr(self.position, 'close', None) if hasattr(self, 'position') else None
                
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
                
                if buy_called:
                    if limit_price is not None:
                        self.set_signal(SignalType.LIMIT_BUY, confidence=0.8, size=signal_size, 
                                      limit_price=limit_price)
                    else:
                        self.set_signal(SignalType.BUY, confidence=0.8, size=signal_size)
                elif sell_called:
                    if limit_price is not None:
                        self.set_signal(SignalType.LIMIT_SELL, confidence=0.8, size=signal_size, 
                                      limit_price=limit_price)
                    else:
                        self.set_signal(SignalType.SELL, confidence=0.8, size=signal_size)
                elif close_called:
                    self.set_signal(SignalType.CLOSE, confidence=0.8)
                else:
                    self.set_signal(SignalType.HOLD, confidence=0.1)
                
                # Restore original methods
                if original_buy:
                    self.buy = original_buy
                if original_sell:
                    self.sell = original_sell
                if original_close and hasattr(self, 'position'):
                    self.position.close = original_close
        
        return ConvertedSignalStrategy


class BacktestingEngine(TradingEngine):
    """Trading engine implementation for backtesting.py"""
    
    def get_engine_info(self) -> EngineInfo:
        """Get information about this engine"""
        return EngineInfo(
            name="backtesting.py",
            version="0.3.3",  # Common version
            supported_features={
                "signal_extraction": True,
                "live_trading": True,
                "multi_strategy": True,
                "limit_orders": True,
                "stop_orders": True
            },
            description="Python backtesting library for trading strategies"
        )
    
    def load_strategy_from_file(self, strategy_path: str) -> BacktestingEngineStrategy:
        """Load a backtesting.py strategy from file"""
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
            
            # Create wrapper
            engine_strategy = BacktestingEngineStrategy(strategy_class)
            
            # Calculate lookback period
            lookback = self.calculate_lookback_period(strategy_path)
            engine_strategy.lookback_period = lookback
            
            return engine_strategy
            
        except Exception as e:
            logger.error(f"Error loading strategy from {strategy_path}: {e}")
            raise
    
    def create_signal_extractor(self, engine_strategy: BacktestingEngineStrategy, 
                              **kwargs) -> BacktestingSignalExtractor:
        """Create a signal extractor for backtesting.py strategy"""
        return BacktestingSignalExtractor(engine_strategy, **kwargs)
    
    def validate_strategy_file(self, strategy_path: str) -> bool:
        """Check if strategy file is compatible with backtesting.py"""
        try:
            if not os.path.exists(strategy_path):
                return False
            
            with open(strategy_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for backtesting.py imports
            if 'from backtesting import' not in content:
                return False
            
            # Check for Strategy class inheritance
            if not re.search(r'class\s+\w+\(Strategy\)', content):
                return False
            
            # Check for required methods
            if 'def init(' not in content or 'def next(' not in content:
                return False
            
            return True
            
        except Exception:
            return False
    
    def calculate_lookback_period(self, strategy_path: str, default_lookback: int = 50) -> int:
        """Calculate required lookback period for strategy"""
        try:
            # First try to find LOOKBACK variable in file
            lookback = self._parse_lookback_from_file(strategy_path)
            if lookback is not None:
                logger.debug(f"Found LOOKBACK={lookback} in {strategy_path}")
                return lookback
            
            # Try to analyze indicator usage (simplified approach)
            with open(strategy_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for common moving average periods
            ma_periods = []
            
            # Search for patterns like SMA(data, 20) or self.n1 = 10
            patterns = [
                r'SMA\([^,]+,\s*(\d+)\)',
                r'EMA\([^,]+,\s*(\d+)\)',
                r'RSI\([^,]+,\s*(\d+)\)',
                r'self\.n\d*\s*=\s*(\d+)',
                r'n\d*\s*=\s*(\d+)',
                r'period\s*=\s*(\d+)',
                r'window\s*=\s*(\d+)'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    try:
                        period = int(match)
                        if 1 <= period <= 500:  # Reasonable range
                            ma_periods.append(period)
                    except ValueError:
                        continue
            
            if ma_periods:
                # Use the maximum period found plus some buffer
                calculated_lookback = max(ma_periods) + 10
                logger.debug(f"Calculated lookback={calculated_lookback} from indicators: {ma_periods}")
                return calculated_lookback
            
            logger.debug(f"Using default lookback={default_lookback} for {strategy_path}")
            return default_lookback
            
        except Exception as e:
            logger.warning(f"Error calculating lookback for {strategy_path}: {e}")
            return default_lookback
    
    def _parse_lookback_from_file(self, strategy_path: str) -> Optional[int]:
        """Parse LOOKBACK variable from strategy file"""
        try:
            with open(strategy_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for LOOKBACK = number pattern
            lookback_pattern = r'^LOOKBACK\s*=\s*(\d+)'
            match = re.search(lookback_pattern, content, re.MULTILINE)
            
            if match:
                return int(match.group(1))
                
        except Exception as e:
            logger.warning(f"Error parsing LOOKBACK from {strategy_path}: {e}")
        
        return None 