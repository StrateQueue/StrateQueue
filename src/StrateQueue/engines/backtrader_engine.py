"""
Backtrader Engine Implementation

Implements the trading engine interface for Backtrader strategies.
This module contains all the Backtrader-specific logic for loading strategies
and extracting signals using true persistence with live feed pattern.
"""

import inspect
import logging
import threading
import queue
from collections import deque
from typing import Any, Dict, Type
import time

import pandas as pd

# Conditional import for Backtrader
try:
    import backtrader as bt
    BACKTRADER_AVAILABLE = True
except ImportError as e:
    BACKTRADER_AVAILABLE = False
    bt = None
    logger = logging.getLogger(__name__)
    logger.warning(f"Backtrader not available: {e}")

from ..core.signal_extractor import SignalType, TradingSignal
from ..core.base_signal_extractor import BaseSignalExtractor
from .engine_base import (
    EngineInfo, EngineSignalExtractor, EngineStrategy, TradingEngine,
    build_engine_info
)

logger = logging.getLogger(__name__)


if BACKTRADER_AVAILABLE:
    class LiveQueueFeed(bt.feeds.DataBase):
        """Live data feed that never ends - maintains state between bars"""
        
        lines = ('open', 'high', 'low', 'close', 'volume')
        params = ()
        datafields = lines
        
        def __init__(self, tz='UTC'):
            super().__init__()
            self._queue = deque()
            self._tz = tz
            self._lastbar = None
            self._name = 'LiveQueueFeed'
            self._stop_requested = False
        
        def islive(self):
            """Tell Cerebro this is a live feed"""
            return True
        
        def haslivedata(self):
            """Keep requesting data forever unless stop is requested"""
            return not self._stop_requested
        
        def _load(self):
            """Load the next bar from the queue - blocks until data available"""
            # If stop is requested, return False to end the feed
            if self._stop_requested:
                return False
            
            # Block until data is available or stop is requested
            # This is the key to true persistence - Cerebro will wait here
            while not self._queue and not self._stop_requested:
                time.sleep(0.01)  # 10ms sleep to avoid busy waiting but stay responsive
            
            # Check again after waiting
            if self._stop_requested:
                return False
            
            # If we still don't have data, return None to indicate no data available
            # This tells Cerebro to try again later (live feed behavior)
            if not self._queue:
                return None
            
            # We have data - process it
            ts, o, h, l, c, v = self._queue.popleft()
            
            # Convert timestamp to Backtrader format
            if hasattr(ts, 'to_pydatetime'):
                dt = ts.to_pydatetime()
            else:
                dt = ts
            
            self.lines.datetime[0] = bt.date2num(dt)
            self.lines.open[0] = float(o)
            self.lines.high[0] = float(h)
            self.lines.low[0] = float(l)
            self.lines.close[0] = float(c)
            self.lines.volume[0] = float(v)
            
            self._lastbar = (ts, c)
            return True
        
        def push_bar(self, timestamp, open_price, high_price, low_price, close_price, volume=0):
            """Push a new bar to the queue"""
            self._queue.append((timestamp, open_price, high_price, low_price, close_price, volume))
        
        def push_historical_bars(self, df):
            """Push multiple historical bars to initialize the feed"""
            for idx, row in df.iterrows():
                timestamp = idx
                open_price = row.get('open', row.get('Open', row.get('close', row.get('Close', 0))))
                high_price = row.get('high', row.get('High', open_price))
                low_price = row.get('low', row.get('Low', open_price))
                close_price = row.get('close', row.get('Close', 0))
                volume = row.get('volume', row.get('Volume', 0))
                
                self.push_bar(timestamp, open_price, high_price, low_price, close_price, volume)
        
        def stop(self):
            """Request the feed to stop"""
            self._stop_requested = True
        
        def get_last_bar(self):
            """Get the last processed bar"""
            return self._lastbar
        
        def has_pending_bars(self):
            """Check if there are bars waiting to be processed"""
            return len(self._queue) > 0
else:
    # Dummy class when Backtrader is not available
    class LiveQueueFeed:
        def __init__(self):
            pass


class BacktraderEngineStrategy(EngineStrategy):
    """Wrapper for Backtrader strategies"""

    # Skip Backtrader internal attributes when collecting parameters
    _skip_attrs = {"data", "broker", "position"}

    def __init__(self, strategy_class: Type, strategy_params: Dict[str, Any] = None):
        super().__init__(strategy_class, strategy_params)

    def get_lookback_period(self) -> int:
        """Get the minimum number of bars required by this strategy"""
        # Backtrader strategies typically need at least 20 bars for meaningful signals
        return 20


class BacktraderLiveEngine:
    """Persistent Backtrader engine that runs in its own thread"""
    
    def __init__(self, strategy_class: Type, strategy_params: Dict[str, Any] = None, historical_df: pd.DataFrame = None):
        self.strategy_class = strategy_class
        self.strategy_params = strategy_params or {}
        self._historical_df = historical_df
        
        # Thread-safe communication
        self._signal_queue = queue.Queue()
        self._control_queue = queue.Queue()
        self._running = False
        self._thread = None
        
        # Backtrader components
        self.cerebro = None
        self.feed = None
        self.strategy_instance = None
        
        # State tracking
        self._initialized = False
        self._bars_processed = 0
        self._last_signal = None
        
    def start(self):
        """Start the persistent Cerebro in its own thread"""
        if self._running:
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        # Wait for initialization
        try:
            init_result = self._control_queue.get(timeout=5.0)
            if init_result != "INITIALIZED":
                raise RuntimeError(f"Failed to initialize: {init_result}")
            self._initialized = True
            logger.debug("Backtrader live engine started successfully")
        except queue.Empty:
            raise RuntimeError("Timeout waiting for Backtrader initialization")
    
    def stop(self):
        """Stop the persistent Cerebro"""
        if not self._running:
            return
            
        self._running = False
        
        # Stop the live feed first
        if self.feed:
            self.feed.stop()
        
        if self._thread and self._thread.is_alive():
            # Signal the thread to stop
            try:
                self._control_queue.put("STOP", timeout=1.0)
                self._thread.join(timeout=2.0)
            except:
                pass
        
        self._initialized = False
        logger.debug("Backtrader live engine stopped")
    
    def _run_loop(self):
        """Main loop running in separate thread"""
        try:
            # Initialize Cerebro with live mode enabled
            self.cerebro = bt.Cerebro(runonce=False, exactbars=-1, live=True)  # Enable live mode
            self.cerebro.broker.setcash(100000.0)
            self.cerebro.broker.setcommission(commission=0.0)
            self.cerebro.addsizer(bt.sizers.FixedSize, stake=1)
            
            # Create live feed as the ONLY data feed (data0)
            # This ensures true persistence with Cerebro waiting for live data
            self.feed = LiveQueueFeed()
            
            # Pre-populate live feed with historical data if provided
            if self._historical_df is not None and not self._historical_df.empty:
                logger.debug(f"Pre-populating live feed with {len(self._historical_df)} historical bars")
                self.feed.push_historical_bars(self._historical_df)
            
            # Add the single live feed to Cerebro
            self.cerebro.adddata(self.feed)
            
            # Add wrapped strategy
            wrapped_strategy = self._create_signal_wrapper(self.strategy_class)
            self.cerebro.addstrategy(
                wrapped_strategy, 
                _signal_queue=self._signal_queue,
                **self.strategy_params
            )
            
            # Signal successful initialization
            self._control_queue.put("INITIALIZED")
            
            # Run Cerebro (blocks until live feed ends or stopped)
            # With live=True and LiveQueueFeed as data0, this will persist indefinitely
            logger.debug("Starting persistent Cerebro run loop with live mode")
            results = self.cerebro.run()
            logger.debug(f"Cerebro run completed, results: {len(results) if results else 0} strategies")
            
        except Exception as e:
            logger.error(f"Error in Backtrader live engine: {e}")
            self._control_queue.put(f"ERROR: {e}")
        finally:
            self._running = False
    
    def _create_signal_wrapper(self, original_strategy_class):
        """Create a strategy wrapper that captures signals"""
        
        class SignalWrapper(original_strategy_class):
            """Wrapper that captures buy/sell calls as signals"""
            
            # Add signal queue parameter - Backtrader will handle the params metaclass
            params = (('_signal_queue', None),)
            
            def __init__(self):
                super().__init__()
                self._last_signal_type = SignalType.HOLD
                self._signal_emitted_this_bar = False
                
            def buy(self, size=None, price=None, **kwargs):
                """Override buy to capture signal"""
                # Call original buy (for broker state)
                result = super().buy(size=size, price=price, **kwargs)
                
                # Only emit signals for live feed
                if self._should_emit_signal():
                    self._emit_signal(SignalType.BUY, price)
                return result
                
            def sell(self, size=None, price=None, **kwargs):
                """Override sell to capture signal"""
                # Call original sell (for broker state)
                result = super().sell(size=size, price=price, **kwargs)
                
                # Only emit signals for live feed
                if self._should_emit_signal():
                    self._emit_signal(SignalType.SELL, price)
                return result
                
            def close(self, size=None, price=None, **kwargs):
                """Override close to capture signal"""
                # Call original close (for broker state)
                result = super().close(size=size, price=price, **kwargs)
                
                # Only emit signals for live feed
                if self._should_emit_signal():
                    self._emit_signal(SignalType.CLOSE, price)
                return result
            
            def _should_emit_signal(self):
                """Check if we should emit signals"""
                # With single live feed approach, we can always emit signals
                # The feed is pre-populated with historical data, then receives live bars
                return True
            
            def next(self):
                """Process next bar"""
                self._signal_emitted_this_bar = False
                
                # Only process if we have enough data to avoid indicator errors
                if len(self.data) < 2:
                    return
                
                # Call original strategy logic
                super().next()
                
                # Emit signals for all bars (historical + live)
                # The live feed is pre-populated with historical data for warm-up
                if self._should_emit_signal() and not self._signal_emitted_this_bar:
                    self._emit_signal(SignalType.HOLD)
            
            def _emit_signal(self, signal_type, price=None):
                """Emit a trading signal"""
                if self._signal_emitted_this_bar:
                    return  # Only one signal per bar
                
                self._signal_emitted_this_bar = True
                self._last_signal_type = signal_type
                
                # Extract current data
                timestamp = self.data.datetime.datetime(0)
                current_price = price or self.data.close[0]
                
                # Extract indicators
                indicators = self._extract_indicators()
                
                # Create signal
                signal = TradingSignal(
                    signal=signal_type,
                    price=float(current_price),
                    timestamp=pd.Timestamp(timestamp),
                    indicators=indicators
                )
                
                # Send to queue
                if hasattr(self.p, '_signal_queue') and self.p._signal_queue:
                    try:
                        self.p._signal_queue.put(signal, timeout=1.0)
                    except queue.Full:
                        logger.warning("Signal queue full, dropping signal")
            
            def _extract_indicators(self):
                """Extract indicator values"""
                indicators = {'price': float(self.data.close[0])}
                
                # Only extract indicators if we have enough data (avoid array index errors)
                if len(self.data) < 2:
                    return indicators
                
                # Extract strategy indicators
                for attr_name in dir(self):
                    if (not attr_name.startswith('_') and 
                        hasattr(self, attr_name) and 
                        attr_name not in ['data', 'broker', 'position', 'p', 'params']):
                        
                        attr_val = getattr(self, attr_name)
                        
                        # Check if it's a Backtrader indicator
                        if hasattr(attr_val, '__class__') and 'backtrader' in str(attr_val.__class__):
                            try:
                                # Check if indicator has enough data
                                if hasattr(attr_val, '__len__') and len(attr_val) > 0:
                                    if hasattr(attr_val, '__getitem__'):
                                        current_value = attr_val[0]
                                        if not pd.isna(current_value):
                                            indicators[attr_name] = float(current_value)
                            except (IndexError, TypeError, KeyError, ValueError, AttributeError):
                                # Silently skip indicators that can't be accessed yet
                                pass
                
                # Add broker state
                try:
                    indicators['portfolio_value'] = float(self.broker.getvalue())
                    indicators['cash'] = float(self.broker.getcash())
                    if self.position:
                        indicators['position_size'] = float(self.position.size)
                        indicators['position_price'] = float(self.position.price)
                except:
                    pass
                
                return indicators
        
        return SignalWrapper
    
    def push_bar(self, timestamp, open_price, high_price, low_price, close_price, volume=0):
        """Push a new bar to the live feed"""
        if not self._initialized or not self.feed:
            logger.debug(f"Cannot push bar - initialized: {self._initialized}, feed: {self.feed is not None}")
            return False
        
        logger.debug(f"Pushing bar to live feed: {timestamp} @ {close_price}")
        self.feed.push_bar(timestamp, open_price, high_price, low_price, close_price, volume)
        self._bars_processed += 1
        return True
    
    def get_latest_signal(self, timeout=0.1):
        """Get the latest signal from the queue"""
        try:
            signal = self._signal_queue.get(timeout=timeout)
            self._last_signal = signal
            logger.debug(f"Got signal from queue: {signal.signal.name} @ {signal.price}")
            return signal
        except queue.Empty:
            logger.debug(f"No signal in queue (timeout={timeout}s), returning last signal")
            # Return last known signal if no new signal
            return self._last_signal
    
    def has_processed_bars(self):
        """Check if any bars have been processed by the live feed"""
        return self._bars_processed > 0
    
    def get_stats(self):
        """Get engine statistics"""
        # Safely check pending bars without triggering Backtrader's boolean evaluation
        pending_bars = 0
        if self.feed is not None:
            try:
                pending_bars = self.feed.has_pending_bars()
            except:
                pending_bars = 0
        
        return {
            'initialized': self._initialized,
            'running': self._running,
            'bars_processed': self._bars_processed,
            'pending_bars': pending_bars,
            'signal_queue_size': self._signal_queue.qsize()
        }


class BacktraderSignalExtractor(BaseSignalExtractor, EngineSignalExtractor):
    """Signal extractor using true persistent Backtrader engine"""

    def __init__(self, engine_strategy: BacktraderEngineStrategy, min_bars_required: int = 2, **strategy_params):
        super().__init__(engine_strategy)
        self.strategy_class = engine_strategy.strategy_class
        self.strategy_params = strategy_params
        self.min_bars_required = min_bars_required
        
        # Persistent engine
        self.live_engine = None
        self.last_timestamp = None
        self._initialized = False
        self._bars_processed = 0

    def _initialize_live_engine(self, initial_data: pd.DataFrame):
        """Initialize the persistent live engine"""
        if not BACKTRADER_AVAILABLE:
            raise ImportError("Backtrader not available")
        
        # Create and start live engine with historical data
        logger.debug(f"Initializing Backtrader with {len(initial_data)} historical bars")
        self.live_engine = BacktraderLiveEngine(
            self.strategy_class, 
            self.strategy_params,
            historical_df=initial_data
        )
        self.live_engine.start()
        
        # Engine is now warmed up with historical data
        if len(initial_data) > 0:
            self.last_timestamp = initial_data.index[-1]
        
        self._initialized = True
        logger.debug("Persistent Backtrader engine initialized and warmed up")

    def extract_signal(self, historical_data: pd.DataFrame) -> TradingSignal:
        """Extract trading signal using true persistent Backtrader engine"""
        try:
            # Check for insufficient data first
            if (hold_signal := self._abort_insufficient_bars(historical_data)):
                return hold_signal

            # Get the last bar info
            current_timestamp = historical_data.index[-1]
            current_price = self._safe_get_last_value(historical_data['Close'])
            
            # Skip if we've already processed this timestamp
            if self.last_timestamp is not None and current_timestamp <= self.last_timestamp:
                # Get cached signal from live engine
                if self.live_engine:
                    cached_signal = self.live_engine.get_latest_signal(timeout=0)
                    if cached_signal:
                        # Update the cached signal with duplicate status
                        cached_signal.indicators = cached_signal.indicators.copy()
                        cached_signal.indicators["status"] = "duplicate_timestamp"
                        return cached_signal
                
                return TradingSignal(
                    signal=SignalType.HOLD,
                    price=current_price,
                    timestamp=current_timestamp,
                    indicators={"status": "duplicate_timestamp"}
                )

            # Initialize on first call
            if not self._initialized:
                if len(historical_data) > 1:
                    # Use all but the last bar for initialization
                    init_data = historical_data.iloc[:-1]
                    self._initialize_live_engine(init_data)
                else:
                    # Not enough data for initialization
                    return TradingSignal(
                        signal=SignalType.HOLD,
                        price=current_price,
                        timestamp=current_timestamp,
                        indicators={"status": "insufficient_data_for_initialization"}
                    )

            # Process the new bar using the persistent engine
            new_bar_data = historical_data.iloc[-1]
            open_price = new_bar_data.get('Open', new_bar_data.get('open', new_bar_data['Close']))
            high_price = new_bar_data.get('High', new_bar_data.get('high', new_bar_data['Close']))
            low_price = new_bar_data.get('Low', new_bar_data.get('low', new_bar_data['Close']))
            close_price = new_bar_data.get('Close', new_bar_data.get('close', new_bar_data['Close']))
            volume = new_bar_data.get('Volume', new_bar_data.get('volume', 0))
            
            # Push the new bar to the live engine
            if self.live_engine:
                success = self.live_engine.push_bar(
                    timestamp=current_timestamp,
                    open_price=float(open_price),
                    high_price=float(high_price),
                    low_price=float(low_price),
                    close_price=float(close_price),
                    volume=float(volume)
                )
                
                if success:
                    # Get the signal (wait a bit for processing)
                    logger.debug(f"Waiting for signal from live engine (timeout=0.5s)...")
                    signal = self.live_engine.get_latest_signal(timeout=0.5)
                    
                    if signal:
                        # Update timestamp tracking
                        self.last_timestamp = current_timestamp
                        self._bars_processed += 1
                        logger.debug(f"Successfully got signal: {signal.signal.name} with {len(signal.indicators)} indicators")
                        return signal
                    elif self.live_engine.has_processed_bars():
                        # Engine has processed bars before, this might be a timeout
                        logger.debug("Signal timeout but engine has processed bars before")
                        return TradingSignal(
                            signal=SignalType.HOLD,
                            price=current_price,
                            timestamp=current_timestamp,
                            indicators={"status": "signal_timeout", "bars_processed": self._bars_processed}
                        )
                    else:
                        logger.debug("No signal received and no bars processed yet")
                else:
                    logger.debug("Failed to push bar to live engine")
            
            # Fallback signal if live engine failed
            return TradingSignal(
                signal=SignalType.HOLD,
                price=current_price,
                timestamp=current_timestamp,
                indicators={"error": "live_engine_failed", "bars_processed": self._bars_processed}
            )

        except Exception as e:
            logger.debug(f"Persistent Backtrader processing failed (using fallback): {e}")
            # Return safe default signal with latest price
            price = self._safe_get_last_value(historical_data['Close']) if len(historical_data) > 0 and 'Close' in historical_data.columns else 0.0
            return self._safe_hold(price=price, error=e)

    def reset(self):
        """Reset the persistent state"""
        if self.live_engine:
            self.live_engine.stop()
            self.live_engine = None
        
        self.last_timestamp = None
        self._initialized = False
        self._bars_processed = 0
        logger.debug("Persistent Backtrader state reset")

    def get_stats(self):
        """Get extractor statistics"""
        stats = {
            'initialized': self._initialized,
            'bars_processed': self._bars_processed,
            'last_timestamp': str(self.last_timestamp) if self.last_timestamp else None
        }
        
        if self.live_engine:
            stats.update(self.live_engine.get_stats())
        
        return stats


class BacktraderEngine(TradingEngine):
    """Trading engine implementation for Backtrader"""
    
    # Set dependency management attributes
    _dependency_available_flag = BACKTRADER_AVAILABLE
    _dependency_help = (
        "Backtrader support is not installed. Run:\n"
        "    pip install stratequeue[backtrader]\n"
        "or\n"
        "    pip install backtrader"
    )
    
    @classmethod
    def dependencies_available(cls) -> bool:
        """Check if Backtrader dependencies are available"""
        return BACKTRADER_AVAILABLE
    
    def get_engine_info(self) -> EngineInfo:
        """Get information about this engine"""
        return build_engine_info(
            name="backtrader",
            lib_version=bt.__version__ if bt else "unknown",
            description="Feature-rich Python backtesting library for trading strategies (true persistence)",
            strategy_lifecycle=True,
            comprehensive_indicators=True,
            live_trading=True,
            persistent_state=True
        )
    
    def is_valid_strategy(self, name: str, obj: Any) -> bool:
        """Check if object is a valid Backtrader strategy"""
        if not inspect.isclass(obj):
            return False
        
        # Check if it's a Backtrader Strategy subclass (but not the base Strategy itself)
        if bt and hasattr(bt, 'Strategy'):
            return (issubclass(obj, bt.Strategy) and 
                    obj is not bt.Strategy and
                    name != 'Strategy')
        
        return False
    
    def create_engine_strategy(self, strategy_obj: Any) -> BacktraderEngineStrategy:
        """Create a Backtrader engine strategy wrapper"""
        return BacktraderEngineStrategy(strategy_obj)
    
    def create_signal_extractor(self, engine_strategy: BacktraderEngineStrategy, 
                              **kwargs) -> BacktraderSignalExtractor:
        """Create a signal extractor for the given strategy"""
        # Filter out parameters that Backtrader strategies don't understand
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ['granularity', 'symbol']}
        return BacktraderSignalExtractor(engine_strategy, **filtered_kwargs) 