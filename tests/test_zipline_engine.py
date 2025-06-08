"""
Tests for Zipline Engine Implementation
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from StrateQueue.engines.zipline_engine import (
        ZiplineEngine, ZiplineEngineStrategy, ZiplineSignalExtractor,
        ZIPLINE_AVAILABLE
    )
    from StrateQueue.core.signal_extractor import SignalType, TradingSignal
    from StrateQueue.engines.engine_factory import EngineFactory
except ImportError as e:
    pytest.skip(f"StrateQueue not available: {e}", allow_module_level=True)


class TestZiplineEngine:
    """Test the ZiplineEngine class"""

    @pytest.mark.skipif(not ZIPLINE_AVAILABLE, reason="Zipline not available")
    def test_engine_creation(self):
        """Test that we can create a Zipline engine instance"""
        engine = ZiplineEngine()
        assert engine is not None
        
        # Test engine info
        info = engine.get_engine_info()
        assert info.name == "zipline"
        assert info.vectorized_backtesting is False
        assert info.live_trading is True
        assert info.pandas_integration is True

    def test_dependencies_available(self):
        """Test dependency checking"""
        # This will depend on whether zipline is actually installed
        available = ZiplineEngine.dependencies_available()
        assert isinstance(available, bool)
        assert available == ZIPLINE_AVAILABLE

    @pytest.mark.skipif(not ZIPLINE_AVAILABLE, reason="Zipline not available")
    def test_explicit_marker(self):
        """Test the explicit strategy marker"""
        engine = ZiplineEngine()
        marker = engine.get_explicit_marker()
        assert marker == '__zipline_strategy__'

    @pytest.mark.skipif(not ZIPLINE_AVAILABLE, reason="Zipline not available")
    def test_strategy_validation(self):
        """Test strategy validation logic"""
        engine = ZiplineEngine()
        
        # Test with function (should return True for initialize/handle_data)
        mock_initialize = Mock()
        mock_initialize.__name__ = 'initialize'
        assert engine.is_valid_strategy('initialize', mock_initialize)
        
        mock_handle_data = Mock() 
        mock_handle_data.__name__ = 'handle_data'
        assert engine.is_valid_strategy('handle_data', mock_handle_data)
        
        # Test with mock module that has both functions
        mock_module = Mock()
        mock_module.initialize = Mock()
        mock_module.handle_data = Mock()
        assert engine.is_valid_strategy('strategy', mock_module)
        
        # Test with invalid object
        assert not engine.is_valid_strategy('invalid', Mock())


class TestZiplineEngineStrategy:
    """Test the ZiplineEngineStrategy wrapper"""

    def test_creation(self):
        """Test creating a strategy wrapper"""
        mock_strategy = Mock()
        wrapper = ZiplineEngineStrategy(mock_strategy)
        
        assert wrapper.strategy_class == mock_strategy
        assert wrapper.get_lookback_period() == 300  # Default for Zipline


class TestZiplineSignalExtractor:
    """Test the ZiplineSignalExtractor"""

    def test_creation(self):
        """Test creating a signal extractor"""
        mock_strategy = Mock()
        wrapper = ZiplineEngineStrategy(mock_strategy)
        extractor = ZiplineSignalExtractor(wrapper)
        
        assert extractor.strategy_obj == mock_strategy
        assert extractor.min_bars_required == 2  # default

    def test_data_preparation(self):
        """Test data preparation for Zipline"""
        mock_strategy = Mock()
        wrapper = ZiplineEngineStrategy(mock_strategy)
        extractor = ZiplineSignalExtractor(wrapper)
        
        # Create test data with various column names
        data = pd.DataFrame({
            'Open': [100, 101, 102],
            'High': [105, 106, 107], 
            'Low': [99, 100, 101],
            'Close': [103, 104, 105],
            'Volume': [1000, 1100, 1200]
        }, index=pd.date_range('2023-01-01', periods=3))
        
        prepared = extractor._prepare_data_for_zipline(data)
        
        # Check that columns are correctly mapped
        assert 'open' in prepared.columns
        assert 'high' in prepared.columns
        assert 'low' in prepared.columns
        assert 'close' in prepared.columns
        assert 'volume' in prepared.columns
        
        # Check data types are numeric
        for col in prepared.columns:
            assert pd.api.types.is_numeric_dtype(prepared[col])

    def test_frequency_detection(self):
        """Test data frequency detection"""
        mock_strategy = Mock()
        wrapper = ZiplineEngineStrategy(mock_strategy)
        extractor = ZiplineSignalExtractor(wrapper)
        
        # Daily data
        daily_data = pd.DataFrame({
            'close': [100, 101, 102]
        }, index=pd.date_range('2023-01-01', periods=3, freq='D'))
        
        assert extractor._determine_data_frequency(daily_data) == 'daily'
        
        # Minute data
        minute_data = pd.DataFrame({
            'close': [100, 101]
        }, index=pd.date_range('2023-01-01 09:30:00', periods=2, freq='1min'))
        
        assert extractor._determine_data_frequency(minute_data) == 'minute'

    @pytest.mark.skipif(not ZIPLINE_AVAILABLE, reason="Zipline not available")
    def test_signal_extraction_insufficient_data(self):
        """Test signal extraction with insufficient data"""
        mock_strategy = Mock()
        wrapper = ZiplineEngineStrategy(mock_strategy)
        extractor = ZiplineSignalExtractor(wrapper, min_bars_required=10)
        
        # Create insufficient data
        data = pd.DataFrame({
            'close': [100, 101]
        }, index=pd.date_range('2023-01-01', periods=2))
        
        signal = extractor.extract_signal(data)
        
        # Should return HOLD signal for insufficient data
        assert signal.signal == SignalType.HOLD
        assert 'insufficient_data' in signal.indicators

    def test_reset(self):
        """Test extractor reset functionality"""
        mock_strategy = Mock()
        wrapper = ZiplineEngineStrategy(mock_strategy)
        extractor = ZiplineSignalExtractor(wrapper)
        
        # Add some signals to the queue
        extractor._signal_queue.put(SignalType.BUY)
        extractor._signal_queue.put(SignalType.SELL)
        
        assert not extractor._signal_queue.empty()
        
        extractor.reset()
        
        assert extractor._signal_queue.empty()

    def test_get_stats(self):
        """Test getting extractor statistics"""
        mock_strategy = Mock()
        wrapper = ZiplineEngineStrategy(mock_strategy)
        extractor = ZiplineSignalExtractor(wrapper, min_bars_required=5)
        
        stats = extractor.get_stats()
        
        assert 'zipline_available' in stats
        assert 'signal_queue_size' in stats
        assert 'min_bars_required' in stats
        assert stats['min_bars_required'] == 5
        assert stats['zipline_available'] == ZIPLINE_AVAILABLE


class TestEngineFactoryIntegration:
    """Test Zipline engine integration with the factory"""

    def test_engine_registration(self):
        """Test that Zipline engine is properly registered"""
        # Force factory initialization
        EngineFactory._initialize_engines()
        
        all_engines = EngineFactory.get_all_known_engines()
        assert 'zipline' in all_engines
        
        if ZIPLINE_AVAILABLE:
            supported_engines = EngineFactory.get_supported_engines()
            assert 'zipline' in supported_engines
            
            # Test creating engine
            engine = EngineFactory.create_engine('zipline')
            assert isinstance(engine, ZiplineEngine)
        else:
            unavailable_engines = EngineFactory.get_unavailable_engines()
            assert 'zipline' in unavailable_engines

    def test_engine_detection(self):
        """Test that Zipline strategies are properly detected"""
        from StrateQueue.engines.engine_helpers import analyze_strategy_file, detect_engine_from_analysis
        
        # Test with our example strategy
        strategy_path = 'examples/strategies/zipline/dual_moving_avg.py'
        if os.path.exists(strategy_path):
            analysis = analyze_strategy_file(strategy_path)
            detected_engine = detect_engine_from_analysis(analysis)
            
            assert detected_engine == 'zipline'
            assert len(analysis['engine_indicators']['zipline']) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 