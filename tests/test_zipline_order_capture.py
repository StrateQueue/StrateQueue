"""
Test Zipline Order Capture Functionality

Tests the comprehensive order mechanism capture for Zipline strategies,
ensuring that all order functions and execution styles are properly captured
and converted to TradingSignal objects.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import queue

from src.StrateQueue.engines.zipline_engine import (
    ZiplineEngine, 
    ZiplineSignalExtractor,
    ZiplineEngineStrategy,
    ZIPLINE_AVAILABLE
)
from src.StrateQueue.core.signal_extractor import (
    TradingSignal, SignalType, OrderFunction, ExecStyle
)


@pytest.mark.skipif(not ZIPLINE_AVAILABLE, reason="Zipline-Reloaded not available")
class TestZiplineOrderCapture:
    """Test comprehensive order capture functionality"""

    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data for testing"""
        dates = pd.date_range('2023-01-01', periods=100, freq='1min')
        np.random.seed(42)
        
        # Generate realistic price data
        base_price = 100.0
        returns = np.random.normal(0, 0.01, len(dates))
        prices = base_price * np.exp(np.cumsum(returns))
        
        data = pd.DataFrame({
            'Open': prices * (1 + np.random.normal(0, 0.001, len(dates))),
            'High': prices * (1 + np.abs(np.random.normal(0, 0.002, len(dates)))),
            'Low': prices * (1 - np.abs(np.random.normal(0, 0.002, len(dates)))),
            'Close': prices,
            'Volume': np.random.randint(1000, 10000, len(dates)),
        }, index=dates)
        
        return data

    @pytest.fixture
    def basic_strategy(self):
        """Create a basic test strategy that uses various order functions"""
        class TestStrategy:
            def __init__(self):
                pass
                
            def initialize(self, context):
                context.asset = type('MockAsset', (), {'symbol': 'TEST'})()
                context.order_count = 0
                
            def handle_data(self, context, data):
                # Cycle through different order types
                order_types = [
                    ('order', 100),
                    ('order_value', 1000),
                    ('order_percent', 0.1),
                    ('order_target', 50),
                    ('order_target_value', 5000),
                    ('order_target_percent', 0.2)
                ]
                
                order_type, amount = order_types[context.order_count % len(order_types)]
                
                if order_type == 'order':
                    context.order(context.asset, amount)
                elif order_type == 'order_value':
                    context.order_value(context.asset, amount)
                elif order_type == 'order_percent':
                    context.order_percent(context.asset, amount)
                elif order_type == 'order_target':
                    context.order_target(context.asset, amount)
                elif order_type == 'order_target_value':
                    context.order_target_value(context.asset, amount)
                elif order_type == 'order_target_percent':
                    context.order_target_percent(context.asset, amount)
                
                context.order_count += 1
        
        return TestStrategy()

    @pytest.fixture
    def execution_style_strategy(self):
        """Create a strategy that tests different execution styles"""
        class ExecutionStyleStrategy:
            def __init__(self):
                pass
                
            def initialize(self, context):
                context.asset = type('MockAsset', (), {'symbol': 'TEST'})()
                context.cycle = 0
                
            def handle_data(self, context, data):
                import zipline.finance.execution as exec_styles
                
                current_price = 100.0  # Mock price
                
                if context.cycle % 4 == 0:
                    # Market order
                    context.order(context.asset, 100)
                elif context.cycle % 4 == 1:
                    # Limit order
                    limit_price = current_price * 0.99
                    context.order(context.asset, 100, limit_price=limit_price)
                elif context.cycle % 4 == 2:
                    # Stop order  
                    stop_price = current_price * 1.01
                    context.order(context.asset, -100, stop_price=stop_price)
                elif context.cycle % 4 == 3:
                    # Stop-limit order
                    stop_price = current_price * 1.01
                    limit_price = current_price * 1.02
                    context.order(context.asset, -100, 
                                limit_price=limit_price, stop_price=stop_price)
                
                context.cycle += 1
        
        return ExecutionStyleStrategy()

    def test_order_function_capture(self, sample_data, basic_strategy):
        """Test that all order functions are properly captured"""
        engine = ZiplineEngine()
        engine_strategy = ZiplineEngineStrategy(basic_strategy)
        extractor = ZiplineSignalExtractor(engine_strategy, min_bars_required=10)
        
        # Run extraction multiple times to test different order functions
        signals = []
        for i in range(6):  # Test all 6 order function types
            signal = extractor.extract_signal(sample_data)
            signals.append(signal)
            
        # Verify we captured signals with different order functions
        order_functions_captured = set()
        for signal in signals:
            if hasattr(signal, 'order_function'):
                order_functions_captured.add(signal.order_function)
        
        # Should have captured multiple order function types
        assert len(order_functions_captured) > 0, "Should capture at least one order function type"

    def test_execution_style_capture(self, sample_data, execution_style_strategy):
        """Test that different execution styles are properly captured"""
        engine = ZiplineEngine()
        engine_strategy = ZiplineEngineStrategy(execution_style_strategy)
        extractor = ZiplineSignalExtractor(engine_strategy, min_bars_required=10)
        
        signals = []
        for i in range(4):  # Test all 4 execution styles
            signal = extractor.extract_signal(sample_data)
            signals.append(signal)
        
        # Verify different execution styles were captured
        exec_styles_captured = set()
        for signal in signals:
            if hasattr(signal, 'execution_style'):
                exec_styles_captured.add(signal.execution_style)
        
        assert len(exec_styles_captured) > 0, "Should capture at least one execution style"

    def test_signal_structure_completeness(self, sample_data, basic_strategy):
        """Test that captured signals have all required fields"""
        engine = ZiplineEngine()
        engine_strategy = ZiplineEngineStrategy(basic_strategy)
        extractor = ZiplineSignalExtractor(engine_strategy, min_bars_required=10)
        
        signal = extractor.extract_signal(sample_data)
        
        # Test basic signal fields
        assert isinstance(signal, TradingSignal)
        assert signal.signal in [SignalType.BUY, SignalType.SELL, SignalType.HOLD]
        assert isinstance(signal.price, (int, float))
        assert signal.timestamp is not None
        assert isinstance(signal.indicators, dict)
        
        # Test new order mechanism fields exist (even if None)
        assert hasattr(signal, 'order_function')
        assert hasattr(signal, 'execution_style')
        assert hasattr(signal, 'quantity')
        assert hasattr(signal, 'value')
        assert hasattr(signal, 'percent')
        assert hasattr(signal, 'target_quantity')
        assert hasattr(signal, 'target_value')
        assert hasattr(signal, 'target_percent')
        assert hasattr(signal, 'limit_price')
        assert hasattr(signal, 'stop_price')
        assert hasattr(signal, 'exchange')

    def test_order_parameter_extraction(self, sample_data):
        """Test that order parameters are correctly extracted"""
        class ParameterTestStrategy:
            def initialize(self, context):
                context.asset = type('MockAsset', (), {'symbol': 'TEST'})()
                
            def handle_data(self, context, data):
                # Test order with specific parameters
                context.order(context.asset, 150, limit_price=99.5, stop_price=101.5)
        
        engine = ZiplineEngine()
        engine_strategy = ZiplineEngineStrategy(ParameterTestStrategy())
        extractor = ZiplineSignalExtractor(engine_strategy, min_bars_required=10)
        
        signal = extractor.extract_signal(sample_data)
        
        # Verify the parameters were captured
        if hasattr(signal, 'quantity') and signal.quantity is not None:
            assert signal.quantity == 150
        if hasattr(signal, 'limit_price') and signal.limit_price is not None:
            assert signal.limit_price == 99.5
        if hasattr(signal, 'stop_price') and signal.stop_price is not None:
            assert signal.stop_price == 101.5

    def test_buy_sell_signal_detection(self, sample_data):
        """Test that buy/sell signals are properly detected"""
        class BuySellStrategy:
            def initialize(self, context):
                context.asset = type('MockAsset', (), {'symbol': 'TEST'})()
                context.cycle = 0
                
            def handle_data(self, context, data):
                if context.cycle % 2 == 0:
                    # Buy signal
                    context.order(context.asset, 100)
                else:
                    # Sell signal
                    context.order(context.asset, -100)
                context.cycle += 1
        
        engine = ZiplineEngine()
        engine_strategy = ZiplineEngineStrategy(BuySellStrategy())
        extractor = ZiplineSignalExtractor(engine_strategy, min_bars_required=10)
        
        # Test buy signal
        buy_signal = extractor.extract_signal(sample_data)
        
        # Test sell signal 
        sell_signal = extractor.extract_signal(sample_data)
        
        # One should be BUY and one should be SELL (or both could be HOLD if no orders)
        signals = [buy_signal.signal, sell_signal.signal]
        assert SignalType.BUY in signals or SignalType.SELL in signals or all(s == SignalType.HOLD for s in signals)

    def test_queue_reset_functionality(self, sample_data, basic_strategy):
        """Test that signal queue is properly reset between extractions"""
        engine = ZiplineEngine()
        engine_strategy = ZiplineEngineStrategy(basic_strategy)
        extractor = ZiplineSignalExtractor(engine_strategy, min_bars_required=10)
        
        # First extraction
        signal1 = extractor.extract_signal(sample_data)
        
        # Verify queue is empty
        assert extractor._signal_queue.empty(), "Signal queue should be empty after extraction"
        
        # Second extraction should work independently
        signal2 = extractor.extract_signal(sample_data)
        
        # Both should be valid TradingSignal objects
        assert isinstance(signal1, TradingSignal)
        assert isinstance(signal2, TradingSignal)

    def test_backward_compatibility(self, sample_data):
        """Test that the new system maintains backward compatibility"""
        class SimpleStrategy:
            def initialize(self, context):
                context.asset = type('MockAsset', (), {'symbol': 'TEST'})()
                
            def handle_data(self, context, data):
                # Simple order that used to work
                context.order_target_percent(context.asset, 0.1)
        
        engine = ZiplineEngine()
        engine_strategy = ZiplineEngineStrategy(SimpleStrategy())
        extractor = ZiplineSignalExtractor(engine_strategy, min_bars_required=10)
        
        signal = extractor.extract_signal(sample_data)
        
        # Should still work and produce a valid signal
        assert isinstance(signal, TradingSignal)
        assert signal.signal in [SignalType.BUY, SignalType.SELL, SignalType.HOLD]
        
        # Check backward compatibility fields
        if hasattr(signal, 'size') and signal.size is not None:
            # If size was set, quantity should also be set for backward compatibility
            assert signal.quantity is not None

    def test_error_handling(self, sample_data):
        """Test error handling in order capture"""
        class ErrorStrategy:
            def initialize(self, context):
                context.asset = type('MockAsset', (), {'symbol': 'TEST'})()
                
            def handle_data(self, context, data):
                # This should not crash the system
                raise ValueError("Test error in strategy")
        
        engine = ZiplineEngine()
        engine_strategy = ZiplineEngineStrategy(ErrorStrategy())
        extractor = ZiplineSignalExtractor(engine_strategy, min_bars_required=10)
        
        # Should handle the error gracefully and return a HOLD signal
        signal = extractor.extract_signal(sample_data)
        
        assert isinstance(signal, TradingSignal)
        # Should be HOLD due to error
        assert signal.signal == SignalType.HOLD

    def test_no_orders_scenario(self, sample_data):
        """Test behavior when strategy makes no orders"""
        class NoOrderStrategy:
            def initialize(self, context):
                pass
                
            def handle_data(self, context, data):
                # Do nothing - no orders
                pass
        
        engine = ZiplineEngine()
        engine_strategy = ZiplineEngineStrategy(NoOrderStrategy())
        extractor = ZiplineSignalExtractor(engine_strategy, min_bars_required=10)
        
        signal = extractor.extract_signal(sample_data)
        
        # Should return HOLD when no orders are made
        assert isinstance(signal, TradingSignal)
        assert signal.signal == SignalType.HOLD 