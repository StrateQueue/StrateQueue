"""
Zipline-Reloaded trading engine implementation for StrateQueue.
"""

import logging
import inspect
import queue
import itertools
from typing import Any, Dict, Optional
import pandas as pd
import numpy as np

from ..core.base_signal_extractor import BaseSignalExtractor
from ..core.signal_extractor import TradingSignal, SignalType
from ..engines.engine_base import (TradingEngine, EngineStrategy, EngineSignalExtractor, 
                                  build_engine_info, EngineInfo, load_module_from_path, 
                                  find_strategy_candidates, select_single_strategy)

logger = logging.getLogger(__name__)

# Try to import Zipline dependencies
try:
    import zipline
    from zipline import TradingAlgorithm
    import zipline.api
    
    # Pre-patch zipline.api to handle strategies that call these functions at import time
    _ORIGINAL_ZIPLINE_FUNCTIONS = {}
    _SID_COUNTER = itertools.count()  # Global counter for unique asset SIDs
    
    def _pre_patch_zipline_api():
        """Pre-patch zipline.api with safe mock functions"""
        global _ORIGINAL_ZIPLINE_FUNCTIONS
        
        # Store originals
        _ORIGINAL_ZIPLINE_FUNCTIONS = {
            'symbol': getattr(zipline.api, 'symbol', None),
            'record': getattr(zipline.api, 'record', None),
            'order': getattr(zipline.api, 'order', None),
            'order_target': getattr(zipline.api, 'order_target', None),
            'order_target_percent': getattr(zipline.api, 'order_target_percent', None),
            'order_target_value': getattr(zipline.api, 'order_target_value', None),
        }
        
        # Create safe mock functions
        def safe_symbol(symbol_name):
            class MockAsset:
                def __init__(self, symbol_name):
                    self.symbol = symbol_name
                    self.sid = next(_SID_COUNTER)  # Unique SID for each asset
                def __str__(self):
                    return self.symbol
                def __repr__(self):
                    return f"MockAsset('{self.symbol}')"
            return MockAsset(symbol_name)
        
        def safe_record(**kwargs):
            pass  # Do nothing
            
        def safe_order(*args, **kwargs):
            return type('MockOrder', (), {'id': 'mock'})()
            
        def safe_order_target(*args, **kwargs):
            return type('MockOrder', (), {'id': 'mock'})()
            
        def safe_order_target_percent(*args, **kwargs):
            return type('MockOrder', (), {'id': 'mock'})()
            
        def safe_order_target_value(*args, **kwargs):
            return type('MockOrder', (), {'id': 'mock'})()
        
        # Apply patches
        zipline.api.symbol = safe_symbol
        zipline.api.record = safe_record
        zipline.api.order = safe_order
        zipline.api.order_target = safe_order_target
        zipline.api.order_target_percent = safe_order_target_percent
        zipline.api.order_target_value = safe_order_target_value
    
    # Apply pre-patching immediately
    _pre_patch_zipline_api()
    
    ZIPLINE_AVAILABLE = True
except ImportError as e:
    zipline = None
    TradingAlgorithm = None
    logger.warning(f"Zipline-Reloaded not available: {e}")
    ZIPLINE_AVAILABLE = False


class ZiplineEngineStrategy(EngineStrategy):
    """Wrapper for Zipline strategy objects"""

    def __init__(self, strategy_class: Any, strategy_params: Dict[str, Any] = None):
        super().__init__(strategy_class, strategy_params)

    def get_lookback_period(self) -> int:
        """Get the lookback period for the strategy (default: 300 bars)"""
        val = getattr(self.strategy_class, 'lookback_period', None)
        if isinstance(val, (int, float)):
            return int(val)
        return 300


class ZiplineSignalExtractor(BaseSignalExtractor, EngineSignalExtractor):
    """Signal extractor for Zipline-Reloaded strategies"""

    def __init__(self, engine_strategy: ZiplineEngineStrategy, min_bars_required: int = 2, granularity: str = '1min', **strategy_params):
        super().__init__(engine_strategy)
        self.engine_strategy = engine_strategy
        self.strategy_obj = engine_strategy.strategy_class
        self.min_bars_required = min_bars_required
        self.granularity = granularity
        self.strategy_params = strategy_params
        
        # Signal capture queue
        self._signal_queue = queue.Queue()
        
        # Store original order functions for restoration
        self._original_functions = {}
        
        # Initialize capture tracking
        self._order_capture_active = False

    def _patch_order_functions(self):
        """Patch Zipline order functions to capture trading signals during strategy execution"""
        if self._order_capture_active:
            return
            
        import zipline.api
        from ..core.signal_extractor import OrderFunction, ExecStyle, TradingSignal
        
        # Store current functions (which might already be our safe mocks)
        self._original_functions = {
            'order': getattr(zipline.api, 'order', None),
            'order_value': getattr(zipline.api, 'order_value', None),
            'order_percent': getattr(zipline.api, 'order_percent', None),
            'order_target': getattr(zipline.api, 'order_target', None),
            'order_target_percent': getattr(zipline.api, 'order_target_percent', None),
            'order_target_value': getattr(zipline.api, 'order_target_value', None),
        }
        
        def _build_capture_function(func_type: OrderFunction):
            """Build a capture function for a specific order function type"""
            def _capture(asset, *args, **kwargs):
                # Extract common parameters
                limit_price = kwargs.get("limit_price")
                stop_price = kwargs.get("stop_price")
                style = kwargs.get("style")
                exchange = kwargs.get("exchange")
                
                # Determine execution style
                exec_style = ExecStyle.MARKET
                if isinstance(style, zipline.finance.execution.StopLimitOrder):
                    exec_style = ExecStyle.STOP_LIMIT
                    if not limit_price:
                        limit_price = style.limit_price
                    if not stop_price:
                        stop_price = style.stop_price
                elif isinstance(style, zipline.finance.execution.StopOrder):
                    exec_style = ExecStyle.STOP
                    if not stop_price:
                        stop_price = style.stop_price
                elif isinstance(style, zipline.finance.execution.LimitOrder):
                    exec_style = ExecStyle.LIMIT
                    if not limit_price:
                        limit_price = style.limit_price
                elif limit_price and stop_price:
                    exec_style = ExecStyle.STOP_LIMIT
                elif limit_price:
                    exec_style = ExecStyle.LIMIT
                elif stop_price:
                    exec_style = ExecStyle.STOP
                
                # Function-specific parameter extraction
                quantity = None
                value = None
                percent = None
                target_quantity = None
                target_value = None
                target_percent = None
                
                if func_type == OrderFunction.ORDER:
                    amount = args[0] if args else kwargs.get("amount", 0)
                    quantity = abs(amount)
                    side = SignalType.BUY if amount > 0 else SignalType.SELL
                    
                elif func_type == OrderFunction.ORDER_VALUE:
                    amount = args[0] if args else kwargs.get("value", 0)
                    value = abs(amount)
                    side = SignalType.BUY if amount > 0 else SignalType.SELL
                    
                elif func_type == OrderFunction.ORDER_PERCENT:
                    amount = args[0] if args else kwargs.get("percent", 0)
                    percent = abs(amount)
                    side = SignalType.BUY if amount > 0 else SignalType.SELL
                    
                elif func_type == OrderFunction.ORDER_TARGET:
                    target = args[0] if args else kwargs.get("target", 0)
                    target_quantity = target
                    side = SignalType.BUY if target > 0 else (SignalType.SELL if target == 0 else SignalType.BUY)
                    
                elif func_type == OrderFunction.ORDER_TARGET_VALUE:
                    target = args[0] if args else kwargs.get("target", 0)
                    target_value = target
                    side = SignalType.BUY if target > 0 else (SignalType.SELL if target == 0 else SignalType.BUY)
                    
                elif func_type == OrderFunction.ORDER_TARGET_PERCENT:
                    target = args[0] if args else kwargs.get("target", 0)
                    target_percent = target
                    side = SignalType.BUY if target > 0 else (SignalType.SELL if target == 0 else SignalType.BUY)
                
                # Create comprehensive signal
                signal = TradingSignal(
                    signal=side,
                    price=0.0,  # Will be filled in later
                    timestamp=pd.Timestamp.now(),
                    indicators={},
                    order_function=func_type,
                    execution_style=exec_style,
                    quantity=quantity,
                    value=value,
                    percent=percent,
                    target_quantity=target_quantity,
                    target_value=target_value,
                    target_percent=target_percent,
                    limit_price=limit_price,
                    stop_price=stop_price,
                    exchange=exchange
                )
                
                self._signal_queue.put(signal)
                return type('MockOrder', (), {'id': f'mock_{func_type.value}'})()
            
            return _capture
        
        # Create capture functions for all order types
        capture_order = _build_capture_function(OrderFunction.ORDER)
        capture_order_value = _build_capture_function(OrderFunction.ORDER_VALUE)
        capture_order_percent = _build_capture_function(OrderFunction.ORDER_PERCENT)
        capture_order_target = _build_capture_function(OrderFunction.ORDER_TARGET)
        capture_order_target_value = _build_capture_function(OrderFunction.ORDER_TARGET_VALUE)
        capture_order_target_percent = _build_capture_function(OrderFunction.ORDER_TARGET_PERCENT)

        # Patch all order functions
        zipline.api.order = capture_order
        zipline.api.order_value = capture_order_value
        zipline.api.order_percent = capture_order_percent
        zipline.api.order_target = capture_order_target
        zipline.api.order_target_value = capture_order_target_value
        zipline.api.order_target_percent = capture_order_target_percent
        
        # CRITICAL: Also patch the strategy module's local references
        # Strategy modules import functions like: from zipline.api import order_target_percent
        # This creates local references that need to be patched too
        if hasattr(self.strategy_obj, 'order'):
            self.strategy_obj.order = capture_order
        if hasattr(self.strategy_obj, 'order_value'):
            self.strategy_obj.order_value = capture_order_value
        if hasattr(self.strategy_obj, 'order_percent'):
            self.strategy_obj.order_percent = capture_order_percent
        if hasattr(self.strategy_obj, 'order_target'):
            self.strategy_obj.order_target = capture_order_target
        if hasattr(self.strategy_obj, 'order_target_value'):
            self.strategy_obj.order_target_value = capture_order_target_value
        if hasattr(self.strategy_obj, 'order_target_percent'):
            self.strategy_obj.order_target_percent = capture_order_target_percent
        
        self._order_capture_active = True

    def _restore_order_functions(self):
        """Restore original Zipline order functions"""
        if not self._order_capture_active:
            return
            
        import zipline.api
        
        # Restore original functions
        for name, func in self._original_functions.items():
            if func is not None:
                setattr(zipline.api, name, func)
        
        self._order_capture_active = False

    def _reset_signal_queue(self):
        """Clear all signals from the queue"""
        while not self._signal_queue.empty():
            try:
                self._signal_queue.get_nowait()
            except queue.Empty:
                break

    def _prepare_data_for_zipline(self, historical_data: pd.DataFrame) -> pd.DataFrame:
        """Prepare data in format expected by Zipline"""
        # Ensure we have the required OHLCV columns
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        
        # Create a copy and normalize column names to lowercase
        data = historical_data.copy()
        data.columns = [col.lower() for col in data.columns]
        
        # Check if we have the required columns
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Forward-fill and backward-fill NaN values
        data = data.ffill().bfill()
        
        return data[required_columns]

    def _determine_data_frequency(self, historical_data: pd.DataFrame) -> str:
        """Determine the data frequency from the DataFrame index"""
        if len(historical_data) < 2:
            return 'daily'  # Default fallback
        
        # Calculate the time difference between consecutive bars
        time_diff = historical_data.index[1] - historical_data.index[0]
        
        # Convert to minutes
        minutes = time_diff.total_seconds() / 60
        
        if minutes <= 1:
            return 'minute'
        elif minutes <= 60:
            return 'minute'  # Zipline handles sub-hourly as minute
        else:
            return 'daily'

    def _create_mock_data_portal(self, zipline_data: pd.DataFrame):
        """Create a minimal mock data portal for testing strategies"""
        # For our signal extraction use case, we'll use a simplified approach
        # that allows the strategy to run without full Zipline infrastructure
        
        class MockBarData:
            def __init__(self, data_df):
                self.data_df = data_df
                
            def current(self, asset, field):
                """Get current value for field"""
                if field == 'price':
                    field = 'close'
                elif field == 'volume':
                    field = 'volume'
                
                if field in self.data_df.columns and len(self.data_df) > 0:
                    return self.data_df[field].iloc[-1]
                return np.nan
                
            def history(self, asset, field, bar_count, frequency):
                """Get historical data"""
                if field == 'price':
                    field = 'close'
                
                if field in self.data_df.columns:
                    # Return last bar_count bars
                    data = self.data_df[field].tail(bar_count)
                    return data
                else:
                    # Return empty series
                    return pd.Series([], dtype=float)
                    
            def can_trade(self, asset):
                """Check if asset can be traded"""
                return True
                
            def is_stale(self, asset):
                """Check if data is stale"""
                return False
        
        return MockBarData(zipline_data)

    def _create_mock_context(self):
        """Create a mock context object for strategy execution"""
        class MockContext:
            def __init__(self):
                # Initialize empty context that strategies can populate
                # Note: strategy's initialize() will set the actual values
                pass
                
        context = MockContext()
        # Make sure context persists between calls if we've initialized before
        if hasattr(self, '_mock_context'):
            return self._mock_context
        else:
            self._mock_context = context
            return context

    def _run_strategy_with_data(self, zipline_data: pd.DataFrame) -> bool:
        """Run the strategy with our data and capture any signals"""
        try:
            # Clear any previous signals
            while not self._signal_queue.empty():
                self._signal_queue.get_nowait()
            
            # Patch order functions FIRST before getting strategy functions
            self._patch_order_functions()
            
            try:
                # Get strategy functions
                if hasattr(self.strategy_obj, 'initialize') and hasattr(self.strategy_obj, 'handle_data'):
                    # Class-based strategy
                    initialize_func = self.strategy_obj.initialize
                    handle_data_func = self.strategy_obj.handle_data
                else:
                    # Module-based strategy
                    initialize_func = getattr(self.strategy_obj, 'initialize', None)
                    handle_data_func = getattr(self.strategy_obj, 'handle_data', None)
                    
                    if not initialize_func or not handle_data_func:
                        raise ValueError("Strategy must have both initialize and handle_data functions")

                # Create mock context and data objects
                context = self._create_mock_context()
                data = self._create_mock_data_portal(zipline_data)
                
                # Run initialize function
                if initialize_func:
                    initialize_func(context)
                
                # Run handle_data function with the last bar of data
                if handle_data_func:
                    handle_data_func(context, data)
                    
            finally:
                # Always restore order functions
                self._restore_order_functions()
            
            return True
            
        except Exception as e:
            logger.error(f"Error running Zipline strategy: {e}")
            return False

    def extract_signal(self, historical_data: pd.DataFrame) -> TradingSignal:
        """Extract trading signal from historical data using Zipline algorithm"""
        try:
            # Check for insufficient data first
            if (hold_signal := self._abort_insufficient_bars(historical_data)):
                return hold_signal

            # Prepare data for Zipline
            zipline_data = self._prepare_data_for_zipline(historical_data)
            
            # Determine data frequency
            data_frequency = self._determine_data_frequency(historical_data)
            
            # Run strategy with our custom data interface
            strategy_success = self._run_strategy_with_data(zipline_data)
            
            # Extract signal from the queue
            if self._signal_queue.empty():
                # Create a basic HOLD signal
                signal = TradingSignal(
                    signal=SignalType.HOLD,
                    price=0.0,  # Will be set below
                    timestamp=pd.Timestamp.now(),
                    indicators={}
                )
            else:
                # Get the last signal (most recent trading decision)
                signal = None
                while not self._signal_queue.empty():
                    signal = self._signal_queue.get_nowait()
                
                if signal is None:
                    signal = TradingSignal(
                        signal=SignalType.HOLD,
                        price=0.0,
                        timestamp=pd.Timestamp.now(),
                        indicators={}
                    )

            # Always take price from the normalised Zipline dataframe
            current_price = self._safe_get_last_value(zipline_data['close'])
            current_timestamp = historical_data.index[-1]

            # Update the signal with actual price and indicators
            signal.price = current_price
            signal.timestamp = current_timestamp
            signal.indicators = self._clean_indicators({
                'zipline_algorithm': True,
                'data_frequency': data_frequency,
                'bars_processed': len(historical_data),
                'algorithm_result': 'success' if strategy_success else 'error'
            })
            
            # Clear signal queue for next extraction
            self._reset_signal_queue()
            
            return signal

        except Exception as e:
            logger.error(f"Error extracting Zipline signal: {e}")
            # Try to use a proper close column if it exists; otherwise 0.0
            if len(historical_data) > 0:
                if 'close' in historical_data.columns:
                    price = self._safe_get_last_value(historical_data['close'])
                elif 'Close' in historical_data.columns:
                    price = self._safe_get_last_value(historical_data['Close'])
                else:
                    price = 0.0
            else:
                price = 0.0
            return self._safe_hold(price=price, error=e)

    def reset(self):
        """Reset the signal extractor state"""
        # Clear signal queue
        while not self._signal_queue.empty():
            self._signal_queue.get_nowait()
        
        # Restore order functions if they were patched
        self._restore_order_functions()
        
        logger.debug("ZiplineSignalExtractor reset completed")

    def get_stats(self) -> dict:
        """Get extractor statistics"""
        return {
            'zipline_available': ZIPLINE_AVAILABLE,
            'signal_queue_size': self._signal_queue.qsize(),
            'min_bars_required': self.min_bars_required,
            'strategy_params': self.strategy_params
        }


class ZiplineEngine(TradingEngine):
    """Trading engine implementation for Zipline-Reloaded"""

    # Set dependency management attributes
    _dependency_available_flag = ZIPLINE_AVAILABLE
    _dependency_help = (
        "Zipline-Reloaded not installed. Run:\n"
        "    pip install stratequeue[zipline]\n"
        "or\n"
        "    pip install zipline-reloaded"
    )

    @classmethod
    def dependencies_available(cls) -> bool:
        """Check if Zipline dependencies are available"""
        return ZIPLINE_AVAILABLE

    def get_engine_info(self) -> EngineInfo:
        """Get information about this engine"""
        return build_engine_info(
            name="zipline",
            lib_version=zipline.__version__ if zipline else "unknown",
            description="Quantopian-style event-driven algorithmic trading engine",
            vectorized_backtesting=False,
            live_trading=True,
            multi_strategy=True,  # Multi-asset support available
            pandas_integration=True
        )

    def is_valid_strategy(self, name: str, obj: Any) -> bool:
        """Check if object is a valid Zipline strategy"""

        # Class-based strategies (methods or attributes)
        if inspect.isclass(obj):
            return hasattr(obj, 'initialize') and hasattr(obj, 'handle_data')

        # Module-level strategies – have both required functions
        if inspect.ismodule(obj):
            return hasattr(obj, 'initialize') and hasattr(obj, 'handle_data')

        # Individual functions – valid if they are named initialize or handle_data
        if callable(obj) and getattr(obj, '__name__', None) in {'initialize', 'handle_data'}:
            return True

        # Generic objects (e.g. mocks) that simply expose both functions
        if hasattr(obj, 'initialize') and hasattr(obj, 'handle_data'):
            return True

        return False

    def get_explicit_marker(self) -> str:
        """Get the explicit marker for Zipline strategies"""
        return '__zipline_strategy__'

    def create_engine_strategy(self, strategy_obj: Any) -> ZiplineEngineStrategy:
        """Create a Zipline engine strategy wrapper"""
        return ZiplineEngineStrategy(strategy_obj)

    def load_strategy_from_file(self, strategy_path: str) -> ZiplineEngineStrategy:
        """
        Load a Zipline strategy from a file with special handling for module-level strategies.
        """
        try:
            # Load the module using shared helper
            module = load_module_from_path(strategy_path, f"zipline_strategy")
            
            # Special case: Check if the module itself is a complete Zipline strategy
            if (hasattr(module, 'initialize') and hasattr(module, 'handle_data') and 
                getattr(module, '__zipline_strategy__', False)):
                logger.info(f"Using module-level strategy from {strategy_path}")
                return self.create_engine_strategy(module)
            
            # Otherwise use the standard loading process for individual functions/classes
            strategy_candidates = find_strategy_candidates(module, self.is_valid_strategy)
            strategy_name, strategy_obj = select_single_strategy(
                strategy_candidates, strategy_path, self.get_explicit_marker()
            )
            
            logger.info(f"Loaded ZiplineEngine strategy: {strategy_name} from {strategy_path}")
            return self.create_engine_strategy(strategy_obj)
            
        except Exception as e:
            logger.error(f"Error loading ZiplineEngine strategy from {strategy_path}: {e}")
            raise

    def create_signal_extractor(self, engine_strategy: ZiplineEngineStrategy, 
                              **kwargs) -> ZiplineSignalExtractor:
        """Create a signal extractor for the given strategy"""
        return ZiplineSignalExtractor(engine_strategy, **kwargs)
    
    def create_multi_ticker_signal_extractor(self, engine_strategy: ZiplineEngineStrategy, 
                                           symbols: list[str], **kwargs) -> 'ZiplineMultiTickerSignalExtractor':
        """Create a multi-ticker signal extractor for processing multiple symbols in one shot"""
        return ZiplineMultiTickerSignalExtractor(engine_strategy, symbols, **kwargs)


class ZiplineMultiTickerSignalExtractor(BaseSignalExtractor, EngineSignalExtractor):
    """Multi-ticker signal extractor for Zipline strategies"""
    
    def __init__(self, engine_strategy: ZiplineEngineStrategy, symbols: list[str], min_bars_required: int = 2, granularity: str = '1min', **strategy_params):
        super().__init__(engine_strategy)
        self.engine_strategy = engine_strategy
        self.strategy_obj = engine_strategy.strategy_class
        self.strategy_params = strategy_params
        self.min_bars_required = min_bars_required
        self.granularity = granularity
        self.symbols = symbols
        
        # Cache of per-symbol extractors
        self._symbol_extractors = {}
        
    def _get_symbol_extractor(self, symbol: str) -> ZiplineSignalExtractor:
        """Get or create a signal extractor for a specific symbol"""
        if symbol not in self._symbol_extractors:
            self._symbol_extractors[symbol] = ZiplineSignalExtractor(
                self.engine_strategy,
                min_bars_required=self.min_bars_required,
                granularity=self.granularity,
                **self.strategy_params
            )
        return self._symbol_extractors[symbol]
        
    def extract_signals(self, multi_symbol_data: dict[str, pd.DataFrame]) -> dict[str, TradingSignal]:
        """Extract trading signals for multiple symbols using per-symbol Zipline strategy execution"""
        try:
            # Check if we have data for all symbols
            missing_symbols = [symbol for symbol in self.symbols if symbol not in multi_symbol_data]
            if missing_symbols:
                logger.warning(f"Missing data for symbols: {missing_symbols}")
                # Return HOLD signals for missing symbols
                return {symbol: self._safe_hold() for symbol in missing_symbols}
            
            # Check minimum bars requirement for each symbol
            insufficient_symbols = []
            for symbol in self.symbols:
                if len(multi_symbol_data[symbol]) < self.min_bars_required:
                    insufficient_symbols.append(symbol)
            
            if insufficient_symbols:
                logger.warning(f"Insufficient data for symbols: {insufficient_symbols}")
                # Return HOLD signals for insufficient symbols, process the rest
                signals = {symbol: self._safe_hold() for symbol in insufficient_symbols}
                valid_symbols = [s for s in self.symbols if s not in insufficient_symbols]
                if valid_symbols:
                    valid_signals = self._process_multi_symbol_data(
                        {s: multi_symbol_data[s] for s in valid_symbols}
                    )
                    signals.update(valid_signals)
                return signals
            
            # All symbols have sufficient data - process them together
            return self._process_multi_symbol_data(multi_symbol_data)
            
        except Exception as e:
            logger.error(f"Error extracting Zipline multi-ticker signals: {e}")
            # Return HOLD signals for all symbols
            return {symbol: self._safe_hold(error=e) for symbol in self.symbols}
    
    def _process_multi_symbol_data(self, symbol_data: dict[str, pd.DataFrame]) -> dict[str, TradingSignal]:
        """Process multiple symbols using per-symbol strategy execution for safety"""
        signals = {}
        
        for symbol, df in symbol_data.items():
            try:
                # Get the per-symbol extractor and run the strategy on this symbol's data
                extractor = self._get_symbol_extractor(symbol)
                signal = extractor.extract_signal(df)
                signals[symbol] = signal
                
            except Exception as e:
                logger.error(f"Error processing symbol {symbol}: {e}")
                signals[symbol] = self._safe_hold(error=e)
        
        return signals
    
    def reset(self):
        """Reset all symbol extractors"""
        for extractor in self._symbol_extractors.values():
            extractor.reset()
        
    def extract_signal(self, historical_data: pd.DataFrame) -> TradingSignal:
        """
        Single-symbol signal extraction method for compatibility with BaseSignalExtractor.
        
        This method is required by the abstract base class but shouldn't be used directly
        for multi-ticker extractors. Use extract_signals() instead.
        """
        # For multi-ticker extractors, this shouldn't be called directly
        # Return a safe HOLD signal as fallback
        return self._safe_hold(error="extract_signal called on multi-ticker extractor - use extract_signals instead")
    
    def get_stats(self) -> dict:
        """Get extractor statistics"""
        return {
            'zipline_available': ZIPLINE_AVAILABLE,
            'symbols': self.symbols,
            'extractors_cached': len(self._symbol_extractors),
            'min_bars_required': self.min_bars_required,
            'strategy_params': self.strategy_params
        } 