"""
Strategy Loading and Conversion

This module handles:
1. Dynamically loading strategy scripts
2. Converting backtesting strategies to signal-generating strategies
3. Parsing strategy configuration
"""

import importlib.util
import inspect
import logging
import os

from .signal_extractor import SignalExtractorStrategy, SignalType

logger = logging.getLogger(__name__)

class StrategyLoader:
    """Dynamically load and analyze trading strategies"""

    @staticmethod
    def load_strategy_from_file(strategy_path: str) -> type[SignalExtractorStrategy]:
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

            # No need to inject Order class - backtesting.py uses different order syntax

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
    def convert_to_signal_strategy(original_strategy: type) -> type[SignalExtractorStrategy]:
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
                    original_init = original_strategy.init
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
                    if args and 'price' not in kwargs and len(args) > 0:
                        trade_params['price'] = args[0]
                    return None

                def mock_sell(*args, **kwargs):
                    nonlocal sell_called, trade_params
                    sell_called = True
                    trade_params = kwargs
                    # Also capture positional args if any (like price as first arg)
                    if args and 'price' not in kwargs and len(args) > 0:
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
                    original_next = original_strategy.next
                    original_next(self)

                # Determine signal based on what was called
                signal_size = trade_params.get('size')
                limit_price = trade_params.get('limit')
                stop_price = trade_params.get('stop')
                # Protective orders (backtesting-py supports these on every entry order)
                sl_price = trade_params.get('sl')       # stop-loss price
                tp_price = trade_params.get('tp')       # take-profit price
                trail = trade_params.get('trail')       # trailing stop (absolute price)
                trail_pct = trade_params.get('trail_percent')  # trailing stop (percentage)

                # Build generic metadata once so we can re-use it in every set_signal(...)
                metadata = {}
                if sl_price is not None:
                    metadata['stop_loss'] = sl_price
                if tp_price is not None:
                    metadata['take_profit'] = tp_price
                if trail is not None:
                    metadata['trail'] = trail
                if trail_pct is not None:
                    metadata['trail_percent'] = trail_pct
                trade_params.get('exectype')
                valid = trade_params.get('valid')

                # Convert valid to time_in_force
                time_in_force = "gtc"          # default
                if valid is not None:
                    import datetime as _dt
                    if valid == 0:
                        time_in_force = "day"
                    elif isinstance(valid, int):                 # n-day expiry
                        time_in_force = f"day+{valid}"
                    elif isinstance(valid, _dt.timedelta):
                        import pandas as pd
                        time_in_force = f"gt_date:{(pd.Timestamp.now() + valid).isoformat()}"
                    
                    # Store raw valid value for transparency
                    metadata["raw_valid"] = valid

                if buy_called:
                    # Determine order type based on backtesting.py parameters
                    if trail or trail_pct:
                        # Trailing stop order
                        self.set_signal(
                            SignalType.TRAILING_STOP_BUY,
                            metadata=metadata,
                            size=signal_size,
                            trail_price=trail,
                            trail_percent=trail_pct,
                            time_in_force=time_in_force
                        )
                    elif sl_price is not None or tp_price is not None:
                        # Bracket order: stop-loss and/or take-profit specified
                        self.set_signal(
                            SignalType.BRACKET_BUY,
                            metadata=metadata,
                            size=signal_size,
                            stop_price=sl_price,
                            limit_price=tp_price,
                            time_in_force=time_in_force
                        )
                    elif stop_price is not None and limit_price is not None:
                        # Stop-limit order: both stop and limit specified
                        self.set_signal(SignalType.STOP_LIMIT_BUY, metadata=metadata, size=signal_size,
                                      stop_price=stop_price, limit_price=limit_price, time_in_force=time_in_force)
                    elif stop_price is not None:
                        # Stop order: only stop specified
                        self.set_signal(SignalType.STOP_BUY, metadata=metadata, size=signal_size,
                                      stop_price=stop_price, time_in_force=time_in_force)
                    elif limit_price is not None:
                        # Limit order: only limit specified
                        self.set_signal(SignalType.LIMIT_BUY, metadata=metadata, size=signal_size,
                                      limit_price=limit_price, time_in_force=time_in_force)
                    else:
                        # Market order: no limit or stop specified
                        self.set_signal(SignalType.BUY, metadata=metadata, size=signal_size, time_in_force=time_in_force)

                elif sell_called:
                    # Determine order type based on backtesting.py parameters
                    if trail or trail_pct:
                        # Trailing stop order
                        self.set_signal(
                            SignalType.TRAILING_STOP_SELL,
                            metadata=metadata,
                            size=signal_size,
                            trail_price=trail,
                            trail_percent=trail_pct,
                            time_in_force=time_in_force
                        )
                    elif sl_price is not None or tp_price is not None:
                        # Bracket order: stop-loss and/or take-profit specified
                        self.set_signal(
                            SignalType.BRACKET_SELL,
                            metadata=metadata,
                            size=signal_size,
                            stop_price=sl_price,
                            limit_price=tp_price,
                            time_in_force=time_in_force
                        )
                    elif stop_price is not None and limit_price is not None:
                        # Stop-limit order: both stop and limit specified
                        self.set_signal(SignalType.STOP_LIMIT_SELL, metadata=metadata, size=signal_size,
                                      stop_price=stop_price, limit_price=limit_price, time_in_force=time_in_force)
                    elif stop_price is not None:
                        # Stop order: only stop specified
                        self.set_signal(SignalType.STOP_SELL, metadata=metadata, size=signal_size,
                                      stop_price=stop_price, time_in_force=time_in_force)
                    elif limit_price is not None:
                        # Limit order: only limit specified
                        self.set_signal(SignalType.LIMIT_SELL, metadata=metadata, size=signal_size,
                                      limit_price=limit_price, time_in_force=time_in_force)
                    else:
                        # Market order: no limit or stop specified
                        self.set_signal(SignalType.SELL, metadata=metadata, size=signal_size, time_in_force=time_in_force)

                elif close_called:
                    self.set_signal(SignalType.CLOSE, metadata=metadata, time_in_force=time_in_force)
                else:
                    self.set_signal(SignalType.HOLD, metadata=metadata)

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

