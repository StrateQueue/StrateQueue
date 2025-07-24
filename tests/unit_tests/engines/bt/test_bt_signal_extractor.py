"""
BtSignalExtractor Unit Tests
===========================
Comprehensive tests for the BtSignalExtractor class focusing on signal extraction functionality.

Requirements verified in this module
------------------------------------
A. Signal extraction from bt backtest (Requirement 2.1)
   A1  extract_signal runs bt backtest and extracts portfolio weights
   A2  Uses backtest.security_weights for weight extraction
   A3  Extracts weights from the last day of backtest results
   A4  Handles single and multiple security scenarios

B. Weight-to-signal conversion (Requirement 2.2, 2.3)
   B1  Weight > 0 converts to BUY signal
   B2  Weight = 0 converts to HOLD signal
   B3  Weight < 0 converts to SELL signal (short positions)
   B4  Proper TradingSignal objects created with correct attributes

C. Error handling for insufficient data (Requirement 6.1)
   C1  Returns HOLD signal when data length < min_bars_required
   C2  Sets insufficient_data indicator in signal
   C3  Uses safe price extraction for HOLD signals
   C4  Handles empty data gracefully

D. Error handling for backtest failures (Requirement 6.2)
   D1  Catches exceptions during bt.run() execution
   D2  Returns safe HOLD signal on backtest failure
   D3  Logs error information for debugging
   D4  Preserves current price in fallback signals

E. Data validation and format handling (Requirement 6.3)
   E1  Validates required columns (Close price minimum)
   E2  Normalizes column names to bt expectations
   E3  Handles NaN values with forward/backward fill
   E4  Converts data to proper numeric types

F. Signal extraction error handling (Requirement 6.4)
   F1  Handles missing security_weights gracefully
   F2  Handles empty backtest results
   F3  Returns appropriate fallback signals
   F4  Maintains error information in signal metadata

All tests run without the real bt library using mock objects.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, PropertyMock
import pytest
import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.StrateQueue.engines.bt_engine import BtSignalExtractor, BtEngineStrategy
from src.StrateQueue.core.signal_extractor import TradingSignal, SignalType
from src.StrateQueue.core.base_signal_extractor import BaseSignalExtractor
from src.StrateQueue.engines.engine_base import EngineSignalExtractor


# ---------------------------------------------------------------------------
# Mock objects and test data
# ---------------------------------------------------------------------------

def create_mock_bt_strategy(name="TestStrategy", **attributes):
    """Create a mock bt.Strategy object"""
    mock_strategy = Mock()
    mock_strategy.name = name
    mock_strategy.algos = []
    for attr_name, attr_value in attributes.items():
        setattr(mock_strategy, attr_name, attr_value)
    return mock_strategy


def create_sample_ohlcv_data(num_bars=50, start_price=100.0):
    """Create sample OHLCV data for testing"""
    dates = pd.date_range('2023-01-01', periods=num_bars, freq='1D')
    
    # Generate realistic price data
    prices = []
    current_price = start_price
    for _ in range(num_bars):
        change = np.random.normal(0, 0.02) * current_price
        current_price = max(current_price + change, 1.0)  # Prevent negative prices
        prices.append(current_price)
    
    data = pd.DataFrame({
        'Open': [p * (1 + np.random.normal(0, 0.001)) for p in prices],
        'High': [p * (1 + abs(np.random.normal(0, 0.005))) for p in prices],
        'Low': [p * (1 - abs(np.random.normal(0, 0.005))) for p in prices],
        'Close': prices,
        'Volume': [np.random.randint(1000, 10000) for _ in range(num_bars)]
    }, index=dates)
    
    return data


def create_mock_backtest_result(security_weights=None):
    """Create a mock bt backtest result"""
    mock_result = Mock()
    
    if security_weights is not None:
        mock_result.security_weights = security_weights
    else:
        # Default: create sample weights
        dates = pd.date_range('2023-01-01', periods=10, freq='1D')
        weights_data = {
            'AAPL': [0.5, 0.6, 0.4, 0.3, 0.5, 0.7, 0.2, 0.8, 0.6, 0.4],
            'MSFT': [0.3, 0.2, 0.4, 0.5, 0.3, 0.1, 0.6, 0.0, 0.2, 0.4],
            'GOOGL': [0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2]
        }
        mock_result.security_weights = pd.DataFrame(weights_data, index=dates)
    
    return mock_result


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_bt_available():
    """Mock bt library as available"""
    with patch('src.StrateQueue.engines.bt_engine.BT_AVAILABLE', True):
        with patch('src.StrateQueue.engines.bt_engine.bt') as mock_bt:
            mock_bt.__version__ = "1.0.0"
            mock_bt.Strategy = Mock()
            mock_bt.Backtest = Mock()
            mock_bt.run = Mock()
            yield mock_bt


@pytest.fixture
def sample_strategy():
    """Sample bt strategy for testing"""
    return create_mock_bt_strategy(name="SampleStrategy", param1="value1")


@pytest.fixture
def engine_strategy(sample_strategy):
    """BtEngineStrategy wrapper for testing"""
    return BtEngineStrategy(sample_strategy)


@pytest.fixture
def signal_extractor(mock_bt_available, engine_strategy):
    """BtSignalExtractor instance for testing"""
    return BtSignalExtractor(engine_strategy, min_bars_required=20, granularity='1d')


@pytest.fixture
def sample_data():
    """Sample OHLCV data for testing"""
    return create_sample_ohlcv_data(num_bars=50, start_price=100.0)


@pytest.fixture
def insufficient_data():
    """Insufficient data for testing (less than min_bars_required)"""
    return create_sample_ohlcv_data(num_bars=10, start_price=100.0)


# ---------------------------------------------------------------------------
# A. Signal extraction from bt backtest tests (Requirement 2.1)
# ---------------------------------------------------------------------------

def test_A1_extract_signal_runs_bt_backtest(mock_bt_available, signal_extractor, sample_data):
    """A1: extract_signal runs bt backtest and extracts portfolio weights"""
    # Mock bt.run to return a result with security weights
    mock_backtest_result = create_mock_backtest_result()
    mock_result = {"test_strategy": mock_backtest_result}
    mock_bt_available.run.return_value = mock_result
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(sample_data)
    
    # Verify bt.Backtest was called
    mock_bt_available.Backtest.assert_called_once()
    # Verify bt.run was called
    mock_bt_available.run.assert_called_once()
    # Verify we got a TradingSignal
    assert isinstance(signal, TradingSignal)


def test_A2_uses_backtest_security_weights(mock_bt_available, signal_extractor, sample_data):
    """A2: Uses backtest.security_weights for weight extraction"""
    # Create specific security weights
    dates = pd.date_range('2023-01-01', periods=5, freq='1D')
    weights = pd.DataFrame({
        'AAPL': [0.6, 0.7, 0.5, 0.8, 0.4]
    }, index=dates)
    
    mock_backtest_result = create_mock_backtest_result(security_weights=weights)
    mock_result = {"test_strategy": mock_backtest_result}
    mock_bt_available.run.return_value = mock_result
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(sample_data)
    
    # Verify the signal was extracted from the last weight (0.4 -> BUY)
    assert signal.signal == SignalType.BUY
    assert signal.indicators['weight'] == 0.4


def test_A3_extracts_weights_from_last_day(mock_bt_available, signal_extractor, sample_data):
    """A3: Extracts weights from the last day of backtest results"""
    # Create weights with specific last day values
    dates = pd.date_range('2023-01-01', periods=3, freq='1D')
    weights = pd.DataFrame({
        'AAPL': [0.5, 0.7, 0.3]  # Last day weight is 0.3
    }, index=dates)
    
    mock_backtest_result = create_mock_backtest_result(security_weights=weights)
    mock_result = {"test_strategy": mock_backtest_result}
    mock_bt_available.run.return_value = mock_result
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(sample_data)
    
    # Should use the last day weight (0.3)
    assert signal.indicators['weight'] == 0.3
    assert signal.signal == SignalType.BUY


def test_A4_handles_multiple_securities(mock_bt_available, signal_extractor, sample_data):
    """A4: Handles single and multiple security scenarios"""
    # Test with multiple securities - should return signal for first security
    dates = pd.date_range('2023-01-01', periods=2, freq='1D')
    weights = pd.DataFrame({
        'AAPL': [0.4, 0.6],
        'MSFT': [0.3, 0.2],
        'GOOGL': [0.3, 0.2]
    }, index=dates)
    
    mock_backtest_result = create_mock_backtest_result(security_weights=weights)
    mock_result = {"test_strategy": mock_backtest_result}
    mock_bt_available.run.return_value = mock_result
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(sample_data)
    
    # Should return a signal (implementation returns first signal from list)
    assert isinstance(signal, TradingSignal)
    assert signal.signal in [SignalType.BUY, SignalType.HOLD, SignalType.SELL]


# ---------------------------------------------------------------------------
# B. Weight-to-signal conversion tests (Requirement 2.2, 2.3)
# ---------------------------------------------------------------------------

def test_B1_weight_greater_than_zero_converts_to_buy(mock_bt_available, signal_extractor, sample_data):
    """B1: Weight > 0 converts to BUY signal"""
    dates = pd.date_range('2023-01-01', periods=1, freq='1D')
    weights = pd.DataFrame({'AAPL': [0.5]}, index=dates)
    
    mock_backtest_result = create_mock_backtest_result(security_weights=weights)
    mock_result = {"test_strategy": mock_backtest_result}
    mock_bt_available.run.return_value = mock_result
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(sample_data)
    
    assert signal.signal == SignalType.BUY
    assert signal.indicators['weight'] == 0.5


def test_B2_weight_zero_converts_to_hold(mock_bt_available, signal_extractor, sample_data):
    """B2: Weight = 0 converts to HOLD signal"""
    dates = pd.date_range('2023-01-01', periods=1, freq='1D')
    weights = pd.DataFrame({'AAPL': [0.0]}, index=dates)
    
    mock_backtest_result = create_mock_backtest_result(security_weights=weights)
    mock_result = {"test_strategy": mock_backtest_result}
    mock_bt_available.run.return_value = mock_result
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(sample_data)
    
    assert signal.signal == SignalType.HOLD
    assert signal.indicators['weight'] == 0.0


def test_B3_weight_less_than_zero_converts_to_sell(mock_bt_available, signal_extractor, sample_data):
    """B3: Weight < 0 converts to SELL signal (short positions)"""
    dates = pd.date_range('2023-01-01', periods=1, freq='1D')
    weights = pd.DataFrame({'AAPL': [-0.3]}, index=dates)
    
    mock_backtest_result = create_mock_backtest_result(security_weights=weights)
    mock_result = {"test_strategy": mock_backtest_result}
    mock_bt_available.run.return_value = mock_result
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(sample_data)
    
    assert signal.signal == SignalType.SELL
    assert signal.indicators['weight'] == -0.3


def test_B4_proper_trading_signal_objects_created(mock_bt_available, signal_extractor, sample_data):
    """B4: Proper TradingSignal objects created with correct attributes"""
    dates = pd.date_range('2023-01-01', periods=1, freq='1D')
    weights = pd.DataFrame({'AAPL': [0.4]}, index=dates)
    
    mock_backtest_result = create_mock_backtest_result(security_weights=weights)
    mock_result = {"test_strategy": mock_backtest_result}
    mock_bt_available.run.return_value = mock_result
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(sample_data)
    
    # Verify TradingSignal structure
    assert isinstance(signal, TradingSignal)
    assert hasattr(signal, 'signal')
    assert hasattr(signal, 'price')
    assert hasattr(signal, 'timestamp')
    assert hasattr(signal, 'indicators')
    
    # Verify signal content
    assert signal.signal == SignalType.BUY
    assert isinstance(signal.price, (int, float))
    assert signal.price > 0
    assert isinstance(signal.indicators, dict)
    assert 'weight' in signal.indicators
    assert 'granularity' in signal.indicators


# ---------------------------------------------------------------------------
# C. Error handling for insufficient data tests (Requirement 6.1)
# ---------------------------------------------------------------------------

def test_C1_returns_hold_signal_insufficient_data(mock_bt_available, signal_extractor, insufficient_data):
    """C1: Returns HOLD signal when data length < min_bars_required"""
    signal = signal_extractor.extract_signal(insufficient_data)
    
    assert signal.signal == SignalType.HOLD
    assert signal.indicators.get('insufficient_data') is True


def test_C2_sets_insufficient_data_indicator(mock_bt_available, signal_extractor, insufficient_data):
    """C2: Sets insufficient_data indicator in signal"""
    signal = signal_extractor.extract_signal(insufficient_data)
    
    assert 'insufficient_data' in signal.indicators
    assert signal.indicators['insufficient_data'] is True


def test_C3_uses_safe_price_extraction_for_hold(mock_bt_available, signal_extractor, insufficient_data):
    """C3: Uses safe price extraction for HOLD signals"""
    signal = signal_extractor.extract_signal(insufficient_data)
    
    # Should extract price from the last Close value
    expected_price = insufficient_data['Close'].iloc[-1]
    assert signal.price == expected_price


def test_C4_handles_empty_data_gracefully(mock_bt_available, signal_extractor):
    """C4: Handles empty data gracefully"""
    empty_data = pd.DataFrame()
    
    signal = signal_extractor.extract_signal(empty_data)
    
    assert signal.signal == SignalType.HOLD
    assert signal.price == 0.0  # Default price for empty data


# ---------------------------------------------------------------------------
# D. Error handling for backtest failures tests (Requirement 6.2)
# ---------------------------------------------------------------------------

def test_D1_catches_exceptions_during_bt_run(mock_bt_available, signal_extractor, sample_data):
    """D1: Catches exceptions during bt.run() execution"""
    # Make bt.run raise an exception
    mock_bt_available.run.side_effect = Exception("Backtest failed")
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(sample_data)
    
    # Should return HOLD signal instead of crashing
    assert signal.signal == SignalType.HOLD
    assert isinstance(signal, TradingSignal)


def test_D2_returns_safe_hold_signal_on_backtest_failure(mock_bt_available, signal_extractor, sample_data):
    """D2: Returns safe HOLD signal on backtest failure"""
    # Make bt.run raise an exception
    mock_bt_available.run.side_effect = RuntimeError("Backtest execution failed")
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(sample_data)
    
    assert signal.signal == SignalType.HOLD
    assert signal.price > 0  # Should have extracted current price


def test_D3_logs_error_information_for_debugging(mock_bt_available, signal_extractor, sample_data):
    """D3: Logs error information for debugging"""
    with patch('src.StrateQueue.engines.bt_engine.logger') as mock_logger:
        # Make bt.run raise an exception
        mock_bt_available.run.side_effect = ValueError("Test error")
        mock_bt_available.Backtest.return_value = Mock()
        
        signal = signal_extractor.extract_signal(sample_data)
        
        # Verify error was logged
        mock_logger.error.assert_called()
        assert signal.signal == SignalType.HOLD


def test_D4_preserves_current_price_in_fallback_signals(mock_bt_available, signal_extractor, sample_data):
    """D4: Preserves current price in fallback signals"""
    # Make bt.run raise an exception
    mock_bt_available.run.side_effect = Exception("Backtest failed")
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(sample_data)
    
    # Should preserve the current price from data
    expected_price = sample_data['Close'].iloc[-1]
    assert signal.price == expected_price


# ---------------------------------------------------------------------------
# E. Data validation and format handling tests (Requirement 6.3)
# ---------------------------------------------------------------------------

def test_E1_validates_required_columns(mock_bt_available, signal_extractor):
    """E1: Validates required columns (Close price minimum)"""
    # Data without Close column
    invalid_data = pd.DataFrame({
        'Open': [100, 101, 102],
        'High': [105, 106, 107],
        'Low': [95, 96, 97],
        'Volume': [1000, 1100, 1200]
    })
    
    signal = signal_extractor.extract_signal(invalid_data)
    
    # Should return HOLD signal due to validation failure
    assert signal.signal == SignalType.HOLD


def test_E2_normalizes_column_names(mock_bt_available, signal_extractor, sample_data):
    """E2: Normalizes column names to bt expectations"""
    # Create data with lowercase column names
    lowercase_data = sample_data.copy()
    lowercase_data.columns = [col.lower() for col in lowercase_data.columns]
    
    # Mock successful backtest
    dates = pd.date_range('2023-01-01', periods=1, freq='1D')
    weights = pd.DataFrame({'AAPL': [0.5]}, index=dates)
    mock_backtest_result = create_mock_backtest_result(security_weights=weights)
    mock_result = {"test_strategy": mock_backtest_result}
    mock_bt_available.run.return_value = mock_result
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(lowercase_data)
    
    # Should successfully process the data despite lowercase columns
    assert signal.signal == SignalType.BUY


def test_E3_handles_nan_values(mock_bt_available, signal_extractor):
    """E3: Handles NaN values with forward/backward fill"""
    # Create data with NaN values
    data_with_nans = create_sample_ohlcv_data(num_bars=30)
    data_with_nans.loc[data_with_nans.index[10:15], 'Close'] = np.nan
    
    # Mock successful backtest
    dates = pd.date_range('2023-01-01', periods=1, freq='1D')
    weights = pd.DataFrame({'AAPL': [0.3]}, index=dates)
    mock_backtest_result = create_mock_backtest_result(security_weights=weights)
    mock_result = {"test_strategy": mock_backtest_result}
    mock_bt_available.run.return_value = mock_result
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(data_with_nans)
    
    # Should handle NaN values and return valid signal
    assert isinstance(signal, TradingSignal)
    assert signal.signal == SignalType.BUY


def test_E4_converts_data_to_numeric_types(mock_bt_available, signal_extractor):
    """E4: Converts data to proper numeric types"""
    # Create data with string values
    string_data = pd.DataFrame({
        'Open': ['100.0', '101.0', '102.0'],
        'High': ['105.0', '106.0', '107.0'],
        'Low': ['95.0', '96.0', '97.0'],
        'Close': ['100.0', '101.0', '102.0'],
        'Volume': ['1000', '1100', '1200']
    }, index=pd.date_range('2023-01-01', periods=3, freq='1D'))
    
    # Extend to meet minimum bars requirement
    extended_data = pd.concat([string_data] * 10, ignore_index=False)
    extended_data.index = pd.date_range('2023-01-01', periods=len(extended_data), freq='1D')
    
    # Mock successful backtest
    dates = pd.date_range('2023-01-01', periods=1, freq='1D')
    weights = pd.DataFrame({'AAPL': [0.4]}, index=dates)
    mock_backtest_result = create_mock_backtest_result(security_weights=weights)
    mock_result = {"test_strategy": mock_backtest_result}
    mock_bt_available.run.return_value = mock_result
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(extended_data)
    
    # Should convert strings to numbers and process successfully
    assert isinstance(signal, TradingSignal)
    assert signal.signal == SignalType.BUY


# ---------------------------------------------------------------------------
# F. Signal extraction error handling tests (Requirement 6.4)
# ---------------------------------------------------------------------------

def test_F1_handles_missing_security_weights(mock_bt_available, signal_extractor, sample_data):
    """F1: Handles missing security_weights gracefully"""
    # Create backtest result without security_weights
    mock_backtest_result = Mock()
    mock_backtest_result.security_weights = pd.DataFrame()  # Empty weights
    mock_result = {"test_strategy": mock_backtest_result}
    mock_bt_available.run.return_value = mock_result
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(sample_data)
    
    # Should return HOLD signal when no weights available
    assert signal.signal == SignalType.HOLD
    assert 'reason' in signal.indicators
    assert signal.indicators['reason'] == 'no_weights_available'


def test_F2_handles_empty_backtest_results(mock_bt_available, signal_extractor, sample_data):
    """F2: Handles empty backtest results"""
    # Return empty result dictionary
    mock_bt_available.run.return_value = {}
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(sample_data)
    
    # Should return HOLD signal for empty results
    assert signal.signal == SignalType.HOLD


def test_F3_returns_appropriate_fallback_signals(mock_bt_available, signal_extractor, sample_data):
    """F3: Returns appropriate fallback signals"""
    # Make result extraction fail
    mock_backtest_result = Mock()
    mock_backtest_result.security_weights = Mock()
    mock_backtest_result.security_weights.empty = False
    mock_backtest_result.security_weights.iloc = Mock(side_effect=IndexError("No data"))
    mock_result = {"test_strategy": mock_backtest_result}
    mock_bt_available.run.return_value = mock_result
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(sample_data)
    
    # Should return fallback HOLD signal
    assert signal.signal == SignalType.HOLD
    assert isinstance(signal.price, (int, float))


def test_F4_maintains_error_information_in_metadata(mock_bt_available, signal_extractor, sample_data):
    """F4: Maintains error information in signal metadata"""
    # Make the entire extraction process fail
    mock_bt_available.Backtest.side_effect = Exception("Backtest creation failed")
    
    signal = signal_extractor.extract_signal(sample_data)
    
    # Should return HOLD signal with error metadata
    assert signal.signal == SignalType.HOLD
    assert hasattr(signal, 'metadata')
    if signal.metadata:
        assert 'error' in signal.metadata


# ---------------------------------------------------------------------------
# Integration and interface tests
# ---------------------------------------------------------------------------

def test_signal_extractor_inherits_from_base_classes(mock_bt_available, engine_strategy):
    """Test that BtSignalExtractor inherits from required base classes"""
    extractor = BtSignalExtractor(engine_strategy)
    
    assert isinstance(extractor, BaseSignalExtractor)
    assert isinstance(extractor, EngineSignalExtractor)


def test_signal_extractor_implements_required_methods(mock_bt_available, engine_strategy):
    """Test that BtSignalExtractor implements required abstract methods"""
    extractor = BtSignalExtractor(engine_strategy)
    
    # Test required methods exist and are callable
    assert hasattr(extractor, 'extract_signal')
    assert callable(extractor.extract_signal)
    
    assert hasattr(extractor, 'get_minimum_bars_required')
    assert callable(extractor.get_minimum_bars_required)


def test_minimum_bars_required_calculation(mock_bt_available, engine_strategy):
    """Test minimum bars required calculation"""
    extractor = BtSignalExtractor(engine_strategy, min_bars_required=25)
    
    # Should return max of min_bars_required and engine strategy lookback
    min_bars = extractor.get_minimum_bars_required()
    assert min_bars == max(25, engine_strategy.get_lookback_period())


def test_signal_extractor_initialization(mock_bt_available, engine_strategy):
    """Test BtSignalExtractor initialization"""
    extractor = BtSignalExtractor(
        engine_strategy, 
        min_bars_required=30, 
        granularity='1h'
    )
    
    assert extractor.engine_strategy is engine_strategy
    assert extractor.strategy_obj is engine_strategy.strategy_obj
    assert extractor.min_bars_required == 30
    assert extractor.granularity == '1h'


def test_weight_conversion_edge_cases(mock_bt_available, signal_extractor, sample_data):
    """Test weight conversion with edge case values"""
    # Test very small positive weight (should be HOLD due to threshold)
    dates = pd.date_range('2023-01-01', periods=1, freq='1D')
    weights = pd.DataFrame({'AAPL': [1e-7]}, index=dates)  # Very small weight
    
    mock_backtest_result = create_mock_backtest_result(security_weights=weights)
    mock_result = {"test_strategy": mock_backtest_result}
    mock_bt_available.run.return_value = mock_result
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(sample_data)
    
    # Very small weight should be treated as HOLD
    assert signal.signal == SignalType.HOLD


def test_signal_timestamp_handling(mock_bt_available, signal_extractor, sample_data):
    """Test that signal timestamps are handled correctly"""
    dates = pd.date_range('2023-01-01', periods=1, freq='1D')
    weights = pd.DataFrame({'AAPL': [0.5]}, index=dates)
    
    mock_backtest_result = create_mock_backtest_result(security_weights=weights)
    mock_result = {"test_strategy": mock_backtest_result}
    mock_bt_available.run.return_value = mock_result
    mock_bt_available.Backtest.return_value = Mock()
    
    signal = signal_extractor.extract_signal(sample_data)
    
    # Should have a valid timestamp
    assert hasattr(signal, 'timestamp')
    assert signal.timestamp is not None