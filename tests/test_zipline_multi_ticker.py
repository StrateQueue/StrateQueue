"""
Test Zipline Multi-Ticker Signal Extraction

Tests the multi-ticker signal extraction functionality for Zipline strategies,
ensuring that strategies can process multiple symbols in one orchestrated call.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.StrateQueue.engines.zipline_engine import (
    ZiplineEngine, 
    ZiplineMultiTickerSignalExtractor,
    ZIPLINE_AVAILABLE
)
from src.StrateQueue.core.base_signal_extractor import SignalType, TradingSignal


@pytest.mark.skipif(not ZIPLINE_AVAILABLE, reason="Zipline-Reloaded not available")
class TestZiplineMultiTicker:
    """Test Zipline multi-ticker signal extraction"""

    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data for multiple symbols"""
        dates = pd.date_range(start='2023-01-01', periods=50, freq='1min')
        
        # Create data for AAPL
        aapl_data = pd.DataFrame({
            'Open': np.random.normal(150, 5, 50),
            'High': np.random.normal(152, 5, 50),
            'Low': np.random.normal(148, 5, 50),
            'Close': np.random.normal(150, 5, 50),
            'Volume': np.random.randint(1000, 10000, 50)
        }, index=dates)
        
        # Create data for MSFT - trending upward for testing
        msft_base = np.linspace(250, 270, 50)  # Upward trend
        msft_data = pd.DataFrame({
            'Open': msft_base + np.random.normal(0, 2, 50),
            'High': msft_base + np.random.normal(2, 2, 50),
            'Low': msft_base + np.random.normal(-2, 2, 50),
            'Close': msft_base + np.random.normal(0, 2, 50),
            'Volume': np.random.randint(1000, 10000, 50)
        }, index=dates)
        
        return {
            'AAPL': aapl_data,
            'MSFT': msft_data
        }

    @pytest.fixture
    def simple_strategy_module(self):
        """Create a simple Zipline strategy module for testing"""
        from types import ModuleType
        
        # Create a mock module
        module = ModuleType("test_strategy")
        
        # Add strategy functions
        def initialize(context):
            # Don't create assets in initialize - will be handled per symbol in multi-ticker mode
            context.lookback = 10
        
        def handle_data(context, data):
            # In multi-ticker mode, this gets called once per symbol
            # So we can just work with the current symbol directly
            try:
                # Simple moving average strategy
                hist = data.history(None, 'price', context.lookback, '1m')
                current_price = data.current(None, 'price')
                
                if len(hist) > 0:
                    sma = hist.mean()
                    
                    if current_price > sma * 1.01:  # 1% above SMA
                        context.order_target_percent(None, 0.5)  # Buy signal
                    elif current_price < sma * 0.99:  # 1% below SMA
                        context.order_target_percent(None, 0.0)  # Sell signal
            except Exception as e:
                # Ignore errors in test strategy
                pass
        
        module.initialize = initialize
        module.handle_data = handle_data
        module.__zipline_strategy__ = True
        
        return module

    def test_multi_ticker_extractor_creation(self, simple_strategy_module):
        """Test that multi-ticker extractor can be created"""
        engine = ZiplineEngine()
        engine_strategy = engine.create_engine_strategy(simple_strategy_module)
        
        symbols = ['AAPL', 'MSFT']
        extractor = engine.create_multi_ticker_signal_extractor(
            engine_strategy, 
            symbols=symbols,
            min_bars_required=10
        )
        
        assert isinstance(extractor, ZiplineMultiTickerSignalExtractor)
        assert extractor.symbols == symbols
        assert extractor.min_bars_required == 10

    def test_extract_signals_success(self, simple_strategy_module, sample_data):
        """Test successful signal extraction for multiple symbols"""
        engine = ZiplineEngine()
        engine_strategy = engine.create_engine_strategy(simple_strategy_module)
        
        extractor = engine.create_multi_ticker_signal_extractor(
            engine_strategy,
            symbols=['AAPL', 'MSFT'],
            min_bars_required=10
        )
        
        signals = extractor.extract_signals(sample_data)
        
        # Should return signals for both symbols
        assert 'AAPL' in signals
        assert 'MSFT' in signals
        
        # Each signal should be a TradingSignal
        assert isinstance(signals['AAPL'], TradingSignal)
        assert isinstance(signals['MSFT'], TradingSignal)
        
        # Signals should have valid types
        valid_signals = [SignalType.BUY, SignalType.SELL, SignalType.HOLD]
        assert signals['AAPL'].signal in valid_signals
        assert signals['MSFT'].signal in valid_signals

    def test_extract_signals_missing_symbols(self, simple_strategy_module, sample_data):
        """Test handling of missing symbol data"""
        engine = ZiplineEngine()
        engine_strategy = engine.create_engine_strategy(simple_strategy_module)
        
        extractor = engine.create_multi_ticker_signal_extractor(
            engine_strategy,
            symbols=['AAPL', 'MSFT', 'GOOGL'],  # GOOGL not in sample_data
            min_bars_required=10
        )
        
        signals = extractor.extract_signals(sample_data)
        
        # Should return HOLD signal for missing symbol
        assert 'GOOGL' in signals
        assert signals['GOOGL'].signal == SignalType.HOLD

    def test_extract_signals_insufficient_data(self, simple_strategy_module):
        """Test handling of insufficient data"""
        engine = ZiplineEngine()
        engine_strategy = engine.create_engine_strategy(simple_strategy_module)
        
        # Create minimal data (less than required)
        minimal_data = {
            'AAPL': pd.DataFrame({
                'Open': [100, 101],
                'High': [102, 103],
                'Low': [99, 100],
                'Close': [101, 102],
                'Volume': [1000, 1000]
            }, index=pd.date_range('2023-01-01', periods=2, freq='1min'))
        }
        
        extractor = engine.create_multi_ticker_signal_extractor(
            engine_strategy,
            symbols=['AAPL'],
            min_bars_required=10  # Require more data than available
        )
        
        signals = extractor.extract_signals(minimal_data)
        
        # Should return HOLD signal for insufficient data
        assert signals['AAPL'].signal == SignalType.HOLD

    def test_symbol_extractor_caching(self, simple_strategy_module, sample_data):
        """Test that symbol extractors are cached properly"""
        engine = ZiplineEngine()
        engine_strategy = engine.create_engine_strategy(simple_strategy_module)
        
        extractor = engine.create_multi_ticker_signal_extractor(
            engine_strategy,
            symbols=['AAPL', 'MSFT'],
            min_bars_required=10
        )
        
        # First extraction should create extractors
        assert len(extractor._symbol_extractors) == 0
        
        signals1 = extractor.extract_signals(sample_data)
        
        # After extraction, extractors should be cached
        assert len(extractor._symbol_extractors) == 2
        assert 'AAPL' in extractor._symbol_extractors
        assert 'MSFT' in extractor._symbol_extractors
        
        # Second extraction should reuse cached extractors
        extractors_before = extractor._symbol_extractors.copy()
        signals2 = extractor.extract_signals(sample_data)
        
        # Same extractor objects should be reused
        for symbol in ['AAPL', 'MSFT']:
            assert extractor._symbol_extractors[symbol] is extractors_before[symbol]

    def test_engine_info_multi_strategy_enabled(self):
        """Test that engine info shows multi-strategy support"""
        engine = ZiplineEngine()
        info = engine.get_engine_info()
        
        assert info.supported_features.get('multi_strategy') is True  # Should be enabled now

    def test_performance_timing(self, simple_strategy_module, sample_data):
        """Test that multi-ticker extraction completes in reasonable time"""
        import time
        
        engine = ZiplineEngine()
        engine_strategy = engine.create_engine_strategy(simple_strategy_module)
        
        extractor = engine.create_multi_ticker_signal_extractor(
            engine_strategy,
            symbols=['AAPL', 'MSFT'],
            min_bars_required=10
        )
        
        start_time = time.time()
        signals = extractor.extract_signals(sample_data)
        end_time = time.time()
        
        extraction_time = end_time - start_time
        
        # Should complete within reasonable time (< 1 second for 2 symbols)
        assert extraction_time < 1.0
        
        # Should return valid signals
        assert len(signals) == 2
        assert all(isinstance(signal, TradingSignal) for signal in signals.values())

    def test_reset_functionality(self, simple_strategy_module):
        """Test that reset clears all symbol extractors"""
        engine = ZiplineEngine()
        engine_strategy = engine.create_engine_strategy(simple_strategy_module)
        
        extractor = engine.create_multi_ticker_signal_extractor(
            engine_strategy,
            symbols=['AAPL', 'MSFT'],
            min_bars_required=10
        )
        
        # Create some cached extractors by accessing them
        extractor._get_symbol_extractor('AAPL')
        extractor._get_symbol_extractor('MSFT')
        
        assert len(extractor._symbol_extractors) == 2
        
        # Reset should clear internal state of extractors but keep the cache
        extractor.reset()
        
        # Cache should still exist but extractors should be reset
        assert len(extractor._symbol_extractors) == 2

    def test_get_stats(self, simple_strategy_module):
        """Test that stats are returned correctly"""
        engine = ZiplineEngine()
        engine_strategy = engine.create_engine_strategy(simple_strategy_module)
        
        extractor = engine.create_multi_ticker_signal_extractor(
            engine_strategy,
            symbols=['AAPL', 'MSFT', 'GOOGL'],
            min_bars_required=15
        )
        
        stats = extractor.get_stats()
        
        assert stats['zipline_available'] is True
        assert stats['symbols'] == ['AAPL', 'MSFT', 'GOOGL']
        assert stats['extractors_cached'] == 0  # No extractors created yet
        assert stats['min_bars_required'] == 15


if __name__ == "__main__":
    pytest.main([__file__]) 