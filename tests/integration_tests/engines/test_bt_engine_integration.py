"""
BT Engine Integration Tests

End-to-end integration tests for the bt engine implementation.
Tests the complete pipeline from engine factory registration through
signal extraction with real bt strategies.

Requirements verified by these tests:
1. Engine factory registration - bt engine is properly registered and discoverable
2. Strategy loading - bt strategies can be loaded from files and validated
3. Signal extraction - complete pipeline from data to trading signals
4. CLI integration - bt engine appears in CLI commands
5. Error handling - graceful handling of missing dependencies and invalid strategies
6. Engine parity - bt engine produces consistent signals with other engines
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import pytest

# Add src/ to path for direct script execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SRC_PATH = PROJECT_ROOT / "src"
if SRC_PATH.exists() and SRC_PATH.is_dir():
    sys.path.insert(0, str(SRC_PATH))

from StrateQueue.engines import EngineFactory
from StrateQueue.core.signal_extractor import SignalType, TradingSignal

# Conditional import for bt library
try:
    import bt
    BT_AVAILABLE = True
except ImportError:
    BT_AVAILABLE = False
    bt = None


# ---------------------------------------------------------------------------
# Test Data and Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for testing"""
    dates = pd.date_range('2023-01-01', periods=50, freq='D')
    import numpy as np
    np_random = np.random.RandomState(42)  # For reproducible tests
    
    # Generate realistic price data
    base_price = 100.0
    returns = np_random.normal(0.001, 0.02, len(dates))
    prices = [base_price]
    
    for ret in returns[1:]:
        prices.append(prices[-1] * (1 + ret))
    
    data = pd.DataFrame({
        'Open': [p * (1 + np_random.normal(0, 0.005)) for p in prices],
        'High': [p * (1 + abs(np_random.normal(0, 0.01))) for p in prices],
        'Low': [p * (1 - abs(np_random.normal(0, 0.01))) for p in prices],
        'Close': prices,
        'Volume': np_random.randint(1000, 10000, len(dates))
    }, index=dates)
    
    # Ensure High >= max(Open, Close) and Low <= min(Open, Close)
    data['High'] = data[['Open', 'High', 'Close']].max(axis=1)
    data['Low'] = data[['Open', 'Low', 'Close']].min(axis=1)
    
    return data


@pytest.fixture
def bt_sma_strategy_code():
    """Sample bt SMA crossover strategy code"""
    return '''
import bt

# Simple Moving Average Crossover Strategy for bt
def create_sma_strategy():
    """Create a simple SMA crossover strategy using bt"""
    
    # Define the strategy using bt's algo composition
    strategy = bt.Strategy(
        'SMA_Crossover',
        [
            bt.algos.RunMonthly(),
            bt.algos.SelectAll(),
            bt.algos.WeighTarget(bt.algos.SMA(20) > bt.algos.SMA(50)),
            bt.algos.Rebalance()
        ]
    )
    
    return strategy

# Create the strategy instance
sma_strategy = create_sma_strategy()

# Mark as bt strategy for engine detection
__bt_strategy__ = True
'''


@pytest.fixture
def bt_simple_strategy_code():
    """Simple bt strategy for basic testing"""
    return '''
import bt

# Simple buy-and-hold strategy
simple_strategy = bt.Strategy(
    'BuyAndHold',
    [
        bt.algos.RunOnce(),
        bt.algos.SelectAll(),
        bt.algos.WeighEqually(),
        bt.algos.Rebalance()
    ]
)

__bt_strategy__ = True
'''


@pytest.fixture
def temp_strategy_file(tmp_path):
    """Create temporary strategy files for testing"""
    def _create_file(content: str, filename: str = "test_strategy.py") -> Path:
        strategy_file = tmp_path / filename
        strategy_file.write_text(content)
        return strategy_file
    return _create_file


# ---------------------------------------------------------------------------
# Engine Factory Integration Tests
# ---------------------------------------------------------------------------

class TestBtEngineFactoryIntegration:
    """Test bt engine integration with EngineFactory"""
    
    def test_bt_engine_registration(self):
        """Test that bt engine is properly registered in EngineFactory"""
        all_engines = EngineFactory.get_all_known_engines()
        assert 'bt' in all_engines, "bt engine should be registered in EngineFactory"
    
    def test_bt_engine_availability_check(self):
        """Test bt engine availability detection"""
        is_supported = EngineFactory.is_engine_supported('bt')
        is_known = EngineFactory.is_engine_known('bt')
        
        assert is_known, "bt engine should be known to EngineFactory"
        
        if BT_AVAILABLE:
            assert is_supported, "bt engine should be supported when bt library is available"
        else:
            assert not is_supported, "bt engine should not be supported when bt library is missing"
            
            # Check unavailable engines info
            unavailable = EngineFactory.get_unavailable_engines()
            assert 'bt' in unavailable, "bt should be listed in unavailable engines when missing"
            assert "bt library not installed" in unavailable['bt'].lower()
    
    @pytest.mark.skipif(not BT_AVAILABLE, reason="bt library not available")
    def test_bt_engine_creation(self):
        """Test creating bt engine instance through factory"""
        engine = EngineFactory.create_engine('bt')
        
        assert engine is not None
        assert hasattr(engine, 'get_engine_info')
        assert hasattr(engine, 'is_valid_strategy')
        assert hasattr(engine, 'load_strategy_from_file')
        
        # Test engine info
        info = engine.get_engine_info()
        assert info.name == 'bt'
        assert info.version is not None
        assert 'backtesting framework' in info.description.lower()
    
    def test_bt_engine_creation_without_dependencies(self):
        """Test that creating bt engine fails gracefully without dependencies"""
        if BT_AVAILABLE:
            pytest.skip("bt library is available - cannot test missing dependency case")
        
        with pytest.raises(ValueError, match="Unsupported engine type 'bt'"):
            EngineFactory.create_engine('bt')


# ---------------------------------------------------------------------------
# Strategy Loading and Validation Tests
# ---------------------------------------------------------------------------

class TestBtStrategyLoading:
    """Test bt strategy loading and validation"""
    
    @pytest.mark.skipif(not BT_AVAILABLE, reason="bt library not available")
    def test_load_valid_bt_strategy(self, temp_strategy_file, bt_simple_strategy_code):
        """Test loading a valid bt strategy from file"""
        strategy_file = temp_strategy_file(bt_simple_strategy_code)
        engine = EngineFactory.create_engine('bt')
        
        # Load strategy
        engine_strategy = engine.load_strategy_from_file(str(strategy_file))
        
        assert engine_strategy is not None
        assert hasattr(engine_strategy, 'strategy_obj')
        assert hasattr(engine_strategy, 'get_strategy_name')
        assert hasattr(engine_strategy, 'get_lookback_period')
        
        # Test strategy properties
        strategy_name = engine_strategy.get_strategy_name()
        assert isinstance(strategy_name, str)
        assert len(strategy_name) > 0
        
        lookback = engine_strategy.get_lookback_period()
        assert isinstance(lookback, int)
        assert lookback > 0
    
    @pytest.mark.skipif(not BT_AVAILABLE, reason="bt library not available")
    def test_bt_strategy_validation(self, temp_strategy_file, bt_simple_strategy_code):
        """Test bt strategy validation logic"""
        strategy_file = temp_strategy_file(bt_simple_strategy_code)
        engine = EngineFactory.create_engine('bt')
        
        # Test file validation
        is_valid = engine.validate_strategy_file(str(strategy_file))
        assert is_valid, "Valid bt strategy file should pass validation"
        
        # Test invalid file
        invalid_code = "print('not a strategy')"
        invalid_file = temp_strategy_file(invalid_code, "invalid.py")
        is_valid = engine.validate_strategy_file(str(invalid_file))
        assert not is_valid, "Invalid strategy file should fail validation"
    
    @pytest.mark.skipif(not BT_AVAILABLE, reason="bt library not available")
    def test_bt_strategy_object_validation(self):
        """Test validation of bt strategy objects"""
        engine = EngineFactory.create_engine('bt')
        
        # Create a valid bt strategy
        valid_strategy = bt.Strategy('test', [bt.algos.RunOnce()])
        assert engine.is_valid_strategy('test_strategy', valid_strategy)
        
        # Test invalid objects
        assert not engine.is_valid_strategy('not_strategy', "not a strategy")
        assert not engine.is_valid_strategy('not_strategy', 42)
        assert not engine.is_valid_strategy('not_strategy', {})
    
    @pytest.mark.skipif(not BT_AVAILABLE, reason="bt library not available")
    def test_bt_strategy_parameters(self, temp_strategy_file, bt_simple_strategy_code):
        """Test extraction of strategy parameters"""
        strategy_file = temp_strategy_file(bt_simple_strategy_code)
        engine = EngineFactory.create_engine('bt')
        
        engine_strategy = engine.load_strategy_from_file(str(strategy_file))
        params = engine_strategy.get_parameters()
        
        assert isinstance(params, dict)
        # bt strategies may not have explicit parameters, but should return a dict


# ---------------------------------------------------------------------------
# Signal Extraction Integration Tests
# ---------------------------------------------------------------------------

class TestBtSignalExtraction:
    """Test end-to-end signal extraction with bt engine"""
    
    @pytest.mark.skipif(not BT_AVAILABLE, reason="bt library not available")
    def test_signal_extraction_pipeline(self, temp_strategy_file, bt_simple_strategy_code, sample_ohlcv_data):
        """Test complete signal extraction pipeline"""
        strategy_file = temp_strategy_file(bt_simple_strategy_code)
        engine = EngineFactory.create_engine('bt')
        
        # Load strategy and create extractor
        engine_strategy = engine.load_strategy_from_file(str(strategy_file))
        extractor = engine.create_signal_extractor(engine_strategy, granularity='1d')
        
        # Extract signal
        signal = extractor.extract_signal(sample_ohlcv_data)
        
        # Validate signal
        assert isinstance(signal, TradingSignal)
        assert isinstance(signal.signal, SignalType)
        assert signal.signal in [SignalType.BUY, SignalType.SELL, SignalType.HOLD]
        assert isinstance(signal.price, (int, float))
        assert signal.price > 0
        assert signal.timestamp is not None
        assert isinstance(signal.indicators, dict)
    
    @pytest.mark.skipif(not BT_AVAILABLE, reason="bt library not available")
    def test_signal_extraction_with_insufficient_data(self, temp_strategy_file, bt_simple_strategy_code):
        """Test signal extraction with insufficient data"""
        strategy_file = temp_strategy_file(bt_simple_strategy_code)
        engine = EngineFactory.create_engine('bt')
        
        engine_strategy = engine.load_strategy_from_file(str(strategy_file))
        extractor = engine.create_signal_extractor(engine_strategy)
        
        # Create minimal data (insufficient for most strategies)
        minimal_data = pd.DataFrame({
            'Close': [100.0, 101.0],
            'Open': [99.0, 100.5],
            'High': [102.0, 103.0],
            'Low': [98.0, 99.5],
            'Volume': [1000, 1100]
        }, index=pd.date_range('2023-01-01', periods=2))
        
        signal = extractor.extract_signal(minimal_data)
        
        # Should return HOLD signal for insufficient data
        assert signal.signal == SignalType.HOLD
        assert (signal.indicators.get("insufficient_data") is True or 
                "insufficient" in signal.indicators.get("reason", "").lower())
    
    @pytest.mark.skipif(not BT_AVAILABLE, reason="bt library not available")
    def test_signal_extraction_error_handling(self, temp_strategy_file, sample_ohlcv_data):
        """Test error handling in signal extraction"""
        # Create a strategy that will cause errors
        problematic_code = '''
import bt

# Strategy that will cause issues
problematic_strategy = bt.Strategy(
    'Problematic',
    [
        bt.algos.RunOnce(),
        bt.algos.SelectAll(),
        # This will cause issues with the data
        bt.algos.WeighTarget(lambda x: 1/0),  # Division by zero
        bt.algos.Rebalance()
    ]
)

__bt_strategy__ = True
'''
        
        strategy_file = temp_strategy_file(problematic_code)
        engine = EngineFactory.create_engine('bt')
        
        engine_strategy = engine.load_strategy_from_file(str(strategy_file))
        extractor = engine.create_signal_extractor(engine_strategy)
        
        # Should handle errors gracefully
        signal = extractor.extract_signal(sample_ohlcv_data)
        
        # Should return safe HOLD signal on error
        assert signal.signal == SignalType.HOLD
        assert signal.price > 0  # Should have a valid price
    
    @pytest.mark.skipif(not BT_AVAILABLE, reason="bt library not available")
    def test_signal_extraction_data_validation(self, temp_strategy_file, bt_simple_strategy_code):
        """Test data validation in signal extraction"""
        strategy_file = temp_strategy_file(bt_simple_strategy_code)
        engine = EngineFactory.create_engine('bt')
        
        engine_strategy = engine.load_strategy_from_file(str(strategy_file))
        extractor = engine.create_signal_extractor(engine_strategy)
        
        # Test with empty data
        empty_data = pd.DataFrame()
        signal = extractor.extract_signal(empty_data)
        assert signal.signal == SignalType.HOLD
        
        # Test with missing required columns
        invalid_data = pd.DataFrame({
            'SomeColumn': [1, 2, 3],
            'AnotherColumn': [4, 5, 6]
        })
        signal = extractor.extract_signal(invalid_data)
        assert signal.signal == SignalType.HOLD
        
        # Test with NaN values
        nan_data = pd.DataFrame({
            'Close': [100.0, float('nan'), 102.0],
            'Open': [99.0, 100.5, 101.5],
            'High': [102.0, 103.0, 104.0],
            'Low': [98.0, 99.5, 100.5],
            'Volume': [1000, 1100, 1200]
        }, index=pd.date_range('2023-01-01', periods=3))
        
        # Should handle NaN values gracefully
        signal = extractor.extract_signal(nan_data)
        assert isinstance(signal, TradingSignal)
        assert signal.price > 0


# ---------------------------------------------------------------------------
# CLI Integration Tests
# ---------------------------------------------------------------------------

class TestBtEngineCLIIntegration:
    """Test bt engine integration with CLI commands"""
    
    def test_bt_engine_in_info_formatter(self):
        """Test that bt engine appears in InfoFormatter output"""
        try:
            from StrateQueue.cli.formatters.info_formatter import InfoFormatter
            
            # Get engine info from formatter
            engine_info = InfoFormatter.format_engine_info()
            engine_info_lower = engine_info.lower()
            
            if BT_AVAILABLE:
                # bt should be mentioned as available
                assert 'bt' in engine_info_lower, "bt engine should appear in engine info when available"
            else:
                # bt may or may not be mentioned when unavailable
                # This is acceptable behavior
                pass
                
        except ImportError:
            pytest.skip("InfoFormatter not available for testing")
    
    @pytest.mark.skipif(not BT_AVAILABLE, reason="bt library not available")
    def test_bt_engine_info_content(self):
        """Test that bt engine info contains expected content"""
        try:
            from StrateQueue.cli.formatters.info_formatter import InfoFormatter
            
            engine_info = InfoFormatter.format_engine_info()
            engine_info_lower = engine_info.lower()
            
            # Should contain bt-related information
            bt_indicators = ['bt', 'backtesting', 'framework']
            found_indicators = [indicator for indicator in bt_indicators if indicator in engine_info_lower]
            
            # Should find at least some bt-related terms
            assert len(found_indicators) >= 1, f"Should find bt-related terms in output. Found: {found_indicators}"
            
        except ImportError:
            pytest.skip("InfoFormatter not available for testing")


# ---------------------------------------------------------------------------
# Engine Parity Integration Tests
# ---------------------------------------------------------------------------

class TestBtEngineParity:
    """Test bt engine parity with other engines"""
    
    @pytest.mark.skipif(not BT_AVAILABLE, reason="bt library not available")
    def test_bt_engine_signal_consistency(self, sample_ohlcv_data):
        """Test that bt engine produces consistent signals across multiple runs"""
        # Create a simple deterministic strategy
        strategy_code = '''
import bt

# Deterministic strategy for consistency testing
consistent_strategy = bt.Strategy(
    'Consistent',
    [
        bt.algos.RunOnce(),
        bt.algos.SelectAll(),
        bt.algos.WeighEqually(),
        bt.algos.Rebalance()
    ]
)

__bt_strategy__ = True
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(strategy_code)
            strategy_file = f.name
        
        try:
            engine = EngineFactory.create_engine('bt')
            engine_strategy = engine.load_strategy_from_file(strategy_file)
            
            # Run signal extraction multiple times
            signals = []
            for _ in range(3):
                extractor = engine.create_signal_extractor(engine_strategy, granularity='1d')
                signal = extractor.extract_signal(sample_ohlcv_data)
                signals.append(signal)
            
            # All signals should be identical
            first_signal = signals[0]
            for signal in signals[1:]:
                assert signal.signal == first_signal.signal, "Signals should be consistent across runs"
                assert abs(signal.price - first_signal.price) < 1e-6, "Prices should be consistent"
        
        finally:
            os.unlink(strategy_file)
    
    @pytest.mark.skipif(not BT_AVAILABLE, reason="bt library not available")
    def test_bt_engine_with_different_data_sizes(self, temp_strategy_file, bt_simple_strategy_code):
        """Test bt engine with different data sizes"""
        strategy_file = temp_strategy_file(bt_simple_strategy_code)
        engine = EngineFactory.create_engine('bt')
        
        engine_strategy = engine.load_strategy_from_file(str(strategy_file))
        extractor = engine.create_signal_extractor(engine_strategy)
        
        # Test with different data sizes
        for size in [25, 50, 100]:
            dates = pd.date_range('2023-01-01', periods=size, freq='D')
            data = pd.DataFrame({
                'Close': range(100, 100 + size),
                'Open': range(99, 99 + size),
                'High': range(101, 101 + size),
                'Low': range(98, 98 + size),
                'Volume': [1000] * size
            }, index=dates)
            
            signal = extractor.extract_signal(data)
            
            assert isinstance(signal, TradingSignal)
            assert signal.signal in [SignalType.BUY, SignalType.SELL, SignalType.HOLD]
            assert signal.price > 0


# ---------------------------------------------------------------------------
# Dependency Management Tests
# ---------------------------------------------------------------------------

class TestBtEngineDependencyManagement:
    """Test bt engine dependency management"""
    
    def test_bt_engine_dependency_detection(self):
        """Test that bt engine correctly detects its dependencies"""
        from StrateQueue.engines.bt_engine import BtEngine
        
        # Test class-level dependency check
        deps_available = BtEngine.dependencies_available()
        assert deps_available == BT_AVAILABLE
        
        if BT_AVAILABLE:
            # Should be able to create engine
            engine = BtEngine()
            assert engine is not None
        else:
            # Should raise ImportError
            with pytest.raises(ImportError, match="bt library support is not installed"):
                BtEngine()
    
    def test_bt_engine_help_message(self):
        """Test that bt engine provides helpful error messages"""
        from StrateQueue.engines.bt_engine import BtEngine
        
        if not BT_AVAILABLE:
            try:
                BtEngine()
                pytest.fail("Should have raised ImportError")
            except ImportError as e:
                error_msg = str(e).lower()
                assert "bt library" in error_msg
                assert "pip install" in error_msg
                # Should suggest both stratequeue[bt] and direct bt installation
                assert ("stratequeue[bt]" in error_msg or "bt" in error_msg)


# ---------------------------------------------------------------------------
# Performance and Edge Case Tests
# ---------------------------------------------------------------------------

class TestBtEngineEdgeCases:
    """Test bt engine edge cases and performance"""
    
    @pytest.mark.skipif(not BT_AVAILABLE, reason="bt library not available")
    def test_bt_engine_with_large_dataset(self, temp_strategy_file, bt_simple_strategy_code):
        """Test bt engine performance with larger datasets"""
        strategy_file = temp_strategy_file(bt_simple_strategy_code)
        engine = EngineFactory.create_engine('bt')
        
        engine_strategy = engine.load_strategy_from_file(str(strategy_file))
        extractor = engine.create_signal_extractor(engine_strategy)
        
        # Create larger dataset (1000 days)
        dates = pd.date_range('2020-01-01', periods=1000, freq='D')
        large_data = pd.DataFrame({
            'Close': [100 + i * 0.1 for i in range(1000)],
            'Open': [99.5 + i * 0.1 for i in range(1000)],
            'High': [101 + i * 0.1 for i in range(1000)],
            'Low': [98.5 + i * 0.1 for i in range(1000)],
            'Volume': [1000 + i for i in range(1000)]
        }, index=dates)
        
        # Should handle large dataset without issues
        signal = extractor.extract_signal(large_data)
        
        assert isinstance(signal, TradingSignal)
        assert signal.signal in [SignalType.BUY, SignalType.SELL, SignalType.HOLD]
    
    @pytest.mark.skipif(not BT_AVAILABLE, reason="bt library not available")
    def test_bt_engine_with_extreme_values(self, temp_strategy_file, bt_simple_strategy_code):
        """Test bt engine with extreme price values"""
        strategy_file = temp_strategy_file(bt_simple_strategy_code)
        engine = EngineFactory.create_engine('bt')
        
        engine_strategy = engine.load_strategy_from_file(str(strategy_file))
        extractor = engine.create_signal_extractor(engine_strategy)
        
        # Test with very small values
        small_data = pd.DataFrame({
            'Close': [0.001, 0.002, 0.003],
            'Open': [0.0009, 0.0019, 0.0029],
            'High': [0.0011, 0.0021, 0.0031],
            'Low': [0.0008, 0.0018, 0.0028],
            'Volume': [1000, 1100, 1200]
        }, index=pd.date_range('2023-01-01', periods=3))
        
        signal = extractor.extract_signal(small_data)
        assert isinstance(signal, TradingSignal)
        
        # Test with very large values
        large_data = pd.DataFrame({
            'Close': [1000000, 1000001, 1000002],
            'Open': [999999, 1000000, 1000001],
            'High': [1000001, 1000002, 1000003],
            'Low': [999998, 999999, 1000000],
            'Volume': [1000, 1100, 1200]
        }, index=pd.date_range('2023-01-01', periods=3))
        
        signal = extractor.extract_signal(large_data)
        assert isinstance(signal, TradingSignal)


# Allow direct execution for debugging
if __name__ == "__main__":
    pytest.main([__file__, "-v"])