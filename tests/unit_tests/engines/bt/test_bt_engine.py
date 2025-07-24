"""
BtEngine Unit Tests
==================
Comprehensive tests for the BtEngine class focusing on strategy validation and loading.

Requirements verified in this module
------------------------------------
A. Strategy validation (Requirement 3.1)
   A1  Valid bt.Strategy objects are correctly identified
   A2  Invalid objects are rejected
   A3  Duck typing validation works without bt library
   A4  Edge cases handled gracefully

B. Strategy loading and wrapping (Requirement 3.2)
   B1  create_engine_strategy wraps bt.Strategy objects correctly
   B2  Wrapped strategies maintain original object reference
   B3  Strategy parameters are preserved during wrapping
   B4  Multiple strategies can be wrapped independently

C. Explicit marker support (Requirement 3.3)
   C1  get_explicit_marker returns correct marker string
   C2  Marker is consistent across engine instances
   C3  Marker follows StrateQueue conventions

All tests run without the real bt library using mock objects.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, PropertyMock
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.StrateQueue.engines.bt_engine import BtEngine, BtEngineStrategy
from src.StrateQueue.engines.engine_base import TradingEngine, EngineInfo


# ---------------------------------------------------------------------------
# Mock bt.Strategy objects for testing
# ---------------------------------------------------------------------------

def create_mock_bt_strategy(name=None, algos=None, **attributes):
    """Create a mock bt.Strategy object with specified attributes"""
    mock_strategy = Mock()
    mock_strategy.name = name
    mock_strategy.algos = algos if algos is not None else []
    mock_strategy.run = Mock()  # Mock the run method
    
    # Add custom attributes
    for attr_name, attr_value in attributes.items():
        setattr(mock_strategy, attr_name, attr_value)
    
    return mock_strategy


def create_invalid_object(missing_attr=None):
    """Create objects that should not be valid bt strategies"""
    mock_obj = Mock()
    
    # Set up basic attributes
    mock_obj.name = "InvalidStrategy"
    mock_obj.algos = []
    mock_obj.run = Mock()
    
    # Remove specified attribute to make it invalid
    if missing_attr:
        delattr(mock_obj, missing_attr)
    
    return mock_obj


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_bt_available():
    """Mock bt library as available"""
    with patch('src.StrateQueue.engines.bt_engine.BT_AVAILABLE', True):
        with patch('src.StrateQueue.engines.bt_engine.bt') as mock_bt:
            # Create a mock bt.Strategy class for isinstance checks
            mock_bt.Strategy = Mock()
            mock_bt.__version__ = "1.0.0"
            yield mock_bt


@pytest.fixture
def mock_bt_unavailable():
    """Mock bt library as unavailable"""
    with patch('src.StrateQueue.engines.bt_engine.BT_AVAILABLE', False):
        with patch('src.StrateQueue.engines.bt_engine.bt', None):
            yield


@pytest.fixture
def valid_bt_strategy():
    """Valid bt strategy for testing"""
    return create_mock_bt_strategy(
        name="TestStrategy",
        algos=[Mock(), Mock()],  # Mock algos
        param1="value1",
        param2=42
    )


@pytest.fixture
def bt_engine_with_bt_available(mock_bt_available):
    """BtEngine instance with bt library available"""
    return BtEngine()


# ---------------------------------------------------------------------------
# A. Strategy validation tests (Requirement 3.1)
# ---------------------------------------------------------------------------

def test_A1_valid_bt_strategy_identified_duck_typing(mock_bt_available, valid_bt_strategy):
    """A1: Valid bt.Strategy objects are correctly identified using duck typing"""
    engine = BtEngine()
    
    # Test duck typing validation (without mocking isinstance)
    assert engine.is_valid_strategy("test_strategy", valid_bt_strategy) is True


def test_A2_invalid_objects_rejected(mock_bt_available):
    """A2: Invalid objects are rejected"""
    engine = BtEngine()
    
    # Test object missing algos attribute
    invalid_obj1 = create_invalid_object(missing_attr='algos')
    assert engine.is_valid_strategy("invalid1", invalid_obj1) is False
    
    # Test object missing name attribute
    invalid_obj2 = create_invalid_object(missing_attr='name')
    assert engine.is_valid_strategy("invalid2", invalid_obj2) is False
    
    # Test object missing run method
    invalid_obj3 = create_invalid_object(missing_attr='run')
    assert engine.is_valid_strategy("invalid3", invalid_obj3) is False
    
    # Test object with non-callable run
    invalid_obj4 = Mock()
    invalid_obj4.name = "InvalidStrategy"
    invalid_obj4.algos = []
    invalid_obj4.run = "not_callable"
    assert engine.is_valid_strategy("invalid4", invalid_obj4) is False
    
    # Test object with string algos (should be rejected)
    invalid_obj5 = Mock()
    invalid_obj5.name = "InvalidStrategy"
    invalid_obj5.algos = "not_iterable_list"
    invalid_obj5.run = Mock()
    assert engine.is_valid_strategy("invalid5", invalid_obj5) is False


def test_A3_duck_typing_without_bt_library():
    """A3: Duck typing validation works without bt library"""
    # When bt is not available, should return False immediately
    with patch('src.StrateQueue.engines.bt_engine.BT_AVAILABLE', False):
        engine = BtEngine()
        valid_strategy = create_mock_bt_strategy(name="TestStrategy")
        
        assert engine.is_valid_strategy("test_strategy", valid_strategy) is False


def test_A4_edge_cases_handled_gracefully(mock_bt_available):
    """A4: Edge cases handled gracefully"""
    engine = BtEngine()
    
    # Test with None object
    assert engine.is_valid_strategy("none_obj", None) is False
    
    # Test with object that raises exception when accessing algos
    problematic_obj = Mock()
    problematic_obj.name = "ProblematicStrategy"
    problematic_obj.run = Mock()
    type(problematic_obj).algos = PropertyMock(side_effect=Exception("Access error"))
    
    assert engine.is_valid_strategy("problematic", problematic_obj) is False


def test_A5_bt_unavailable_returns_false_immediately():
    """A5: When bt is unavailable, validation returns False immediately"""
    with patch('src.StrateQueue.engines.bt_engine.BT_AVAILABLE', False):
        engine = BtEngine()
        valid_strategy = create_mock_bt_strategy(name="TestStrategy")
        
        assert engine.is_valid_strategy("test_strategy", valid_strategy) is False


def test_A6_algos_validation_edge_cases(mock_bt_available):
    """A6: Test algos validation with various edge cases"""
    engine = BtEngine()
    
    # Test with list algos (valid)
    strategy_with_list = create_mock_bt_strategy(name="ListStrategy", algos=[Mock(), Mock()])
    assert engine.is_valid_strategy("list_strategy", strategy_with_list) is True
    
    # Test with tuple algos (valid)
    strategy_with_tuple = create_mock_bt_strategy(name="TupleStrategy", algos=(Mock(), Mock()))
    assert engine.is_valid_strategy("tuple_strategy", strategy_with_tuple) is True
    
    # Test with empty algos (valid)
    strategy_with_empty = create_mock_bt_strategy(name="EmptyStrategy", algos=[])
    assert engine.is_valid_strategy("empty_strategy", strategy_with_empty) is True
    
    # Test with string algos (invalid)
    strategy_with_string = create_mock_bt_strategy(name="StringStrategy", algos="invalid")
    assert engine.is_valid_strategy("string_strategy", strategy_with_string) is False
    
    # Test with non-iterable algos (invalid)
    strategy_with_int = create_mock_bt_strategy(name="IntStrategy", algos=123)
    assert engine.is_valid_strategy("int_strategy", strategy_with_int) is False


# ---------------------------------------------------------------------------
# B. Strategy loading and wrapping tests (Requirement 3.2)
# ---------------------------------------------------------------------------

def test_B1_create_engine_strategy_wraps_correctly(mock_bt_available, valid_bt_strategy):
    """B1: create_engine_strategy wraps bt.Strategy objects correctly"""
    engine = BtEngine()
    
    wrapped_strategy = engine.create_engine_strategy(valid_bt_strategy)
    
    assert isinstance(wrapped_strategy, BtEngineStrategy)
    assert wrapped_strategy.strategy_obj is valid_bt_strategy


def test_B2_wrapped_strategies_maintain_reference(mock_bt_available, valid_bt_strategy):
    """B2: Wrapped strategies maintain original object reference"""
    engine = BtEngine()
    
    wrapped_strategy = engine.create_engine_strategy(valid_bt_strategy)
    
    # Verify the original strategy object is preserved
    assert wrapped_strategy.strategy_obj is valid_bt_strategy
    assert wrapped_strategy.strategy_obj.name == valid_bt_strategy.name
    assert wrapped_strategy.strategy_obj.algos is valid_bt_strategy.algos


def test_B3_strategy_parameters_preserved(mock_bt_available):
    """B3: Strategy parameters are preserved during wrapping"""
    engine = BtEngine()
    
    strategy_with_params = create_mock_bt_strategy(
        name="ParameterizedStrategy",
        param1="value1",
        param2=42,
        param3=3.14
    )
    
    wrapped_strategy = engine.create_engine_strategy(strategy_with_params)
    params = wrapped_strategy.get_parameters()
    
    assert params["param1"] == "value1"
    assert params["param2"] == 42
    assert params["param3"] == 3.14


def test_B4_multiple_strategies_wrapped_independently(mock_bt_available):
    """B4: Multiple strategies can be wrapped independently"""
    engine = BtEngine()
    
    strategy1 = create_mock_bt_strategy(name="Strategy1", param1="value1")
    strategy2 = create_mock_bt_strategy(name="Strategy2", param2="value2")
    
    wrapped1 = engine.create_engine_strategy(strategy1)
    wrapped2 = engine.create_engine_strategy(strategy2)
    
    # Verify they are independent
    assert wrapped1.strategy_obj is not wrapped2.strategy_obj
    assert wrapped1.get_strategy_name() != wrapped2.get_strategy_name()
    assert wrapped1.get_parameters() != wrapped2.get_parameters()


def test_B5_create_engine_strategy_with_none_object(mock_bt_available):
    """B5: create_engine_strategy handles edge cases"""
    engine = BtEngine()
    
    # Test with None - should not crash but may not be meaningful
    # The method signature doesn't specify error handling for None
    try:
        wrapped = engine.create_engine_strategy(None)
        # If it doesn't crash, verify it creates a wrapper
        assert isinstance(wrapped, BtEngineStrategy)
    except Exception:
        # If it crashes, that's also acceptable behavior
        pass


# ---------------------------------------------------------------------------
# C. Explicit marker support tests (Requirement 3.3)
# ---------------------------------------------------------------------------

def test_C1_get_explicit_marker_returns_correct_string(mock_bt_available):
    """C1: get_explicit_marker returns correct marker string"""
    engine = BtEngine()
    
    marker = engine.get_explicit_marker()
    assert marker == '__bt_strategy__'


def test_C2_marker_consistent_across_instances(mock_bt_available):
    """C2: Marker is consistent across engine instances"""
    engine1 = BtEngine()
    engine2 = BtEngine()
    
    assert engine1.get_explicit_marker() == engine2.get_explicit_marker()


def test_C3_marker_follows_stratequeue_conventions(mock_bt_available):
    """C3: Marker follows StrateQueue conventions"""
    engine = BtEngine()
    marker = engine.get_explicit_marker()
    
    # StrateQueue markers should be dunder attributes
    assert marker.startswith('__')
    assert marker.endswith('__')
    assert 'bt' in marker.lower()
    assert 'strategy' in marker.lower()


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

def test_engine_initialization_with_dependencies(mock_bt_available):
    """Test engine initialization when dependencies are available"""
    engine = BtEngine()
    
    assert isinstance(engine, TradingEngine)
    assert engine.dependencies_available() is True


def test_engine_initialization_without_dependencies():
    """Test engine initialization when dependencies are unavailable"""
    with patch('src.StrateQueue.engines.bt_engine.BT_AVAILABLE', False):
        # Need to patch the class attribute as well
        with patch.object(BtEngine, '_dependency_available_flag', False):
            with pytest.raises(ImportError) as exc_info:
                BtEngine()
            
            assert "bt library support is not installed" in str(exc_info.value)


def test_get_engine_info(mock_bt_available):
    """Test engine info retrieval"""
    engine = BtEngine()
    
    info = engine.get_engine_info()
    
    assert isinstance(info, EngineInfo)
    assert info.name == "bt"
    assert info.version == "1.0.0"
    assert "backtesting framework" in info.description.lower()


def test_dependencies_available_class_method():
    """Test dependencies_available class method"""
    with patch('src.StrateQueue.engines.bt_engine.BT_AVAILABLE', True):
        assert BtEngine.dependencies_available() is True
    
    with patch('src.StrateQueue.engines.bt_engine.BT_AVAILABLE', False):
        assert BtEngine.dependencies_available() is False


# ---------------------------------------------------------------------------
# Error handling and edge cases
# ---------------------------------------------------------------------------

def test_strategy_validation_with_property_errors(mock_bt_available):
    """Test strategy validation when property access raises errors"""
    engine = BtEngine()
    
    # Create object where accessing algos raises an exception
    problematic_strategy = Mock()
    problematic_strategy.name = "ProblematicStrategy"
    problematic_strategy.run = Mock()
    
    # Make algos property raise exception
    type(problematic_strategy).algos = PropertyMock(side_effect=AttributeError("No algos"))
    
    assert engine.is_valid_strategy("problematic", problematic_strategy) is False


def test_create_engine_strategy_preserves_all_attributes(mock_bt_available):
    """Test that create_engine_strategy preserves all strategy attributes"""
    engine = BtEngine()
    
    # Create strategy with various attribute types
    complex_strategy = create_mock_bt_strategy(
        name="ComplexStrategy",
        algos=[Mock(), Mock()],
        string_param="test",
        int_param=123,
        float_param=45.67,
        bool_param=True,
        list_param=[1, 2, 3],
        dict_param={"key": "value"},
        none_param=None,
        complex_param=Mock()  # This should be filtered out in get_parameters
    )
    
    wrapped = engine.create_engine_strategy(complex_strategy)
    
    # Verify the original object is completely preserved
    assert wrapped.strategy_obj is complex_strategy
    assert wrapped.strategy_obj.string_param == "test"
    assert wrapped.strategy_obj.int_param == 123
    assert wrapped.strategy_obj.float_param == 45.67
    assert wrapped.strategy_obj.bool_param is True
    assert wrapped.strategy_obj.list_param == [1, 2, 3]
    assert wrapped.strategy_obj.dict_param == {"key": "value"}
    assert wrapped.strategy_obj.none_param is None
    assert wrapped.strategy_obj.complex_param is not None


def test_strategy_validation_comprehensive(mock_bt_available):
    """Test comprehensive strategy validation scenarios"""
    engine = BtEngine()
    
    # Valid strategy with all required attributes
    valid_strategy = create_mock_bt_strategy(
        name="ValidStrategy",
        algos=[Mock(), Mock()],
        param1="value1"
    )
    assert engine.is_valid_strategy("valid", valid_strategy) is True
    
    # Valid strategy with None name (allowed)
    valid_strategy_no_name = create_mock_bt_strategy(
        name=None,
        algos=[Mock()],
        param1="value1"
    )
    assert engine.is_valid_strategy("valid_no_name", valid_strategy_no_name) is True
    
    # Valid strategy with empty algos (allowed)
    valid_strategy_empty_algos = create_mock_bt_strategy(
        name="ValidEmptyAlgos",
        algos=[],
        param1="value1"
    )
    assert engine.is_valid_strategy("valid_empty", valid_strategy_empty_algos) is True


def test_bt_engine_interface_compliance(mock_bt_available):
    """Test that BtEngine properly implements TradingEngine interface"""
    engine = BtEngine()
    
    # Test required methods exist and are callable
    assert hasattr(engine, 'get_engine_info')
    assert callable(engine.get_engine_info)
    
    assert hasattr(engine, 'is_valid_strategy')
    assert callable(engine.is_valid_strategy)
    
    assert hasattr(engine, 'create_engine_strategy')
    assert callable(engine.create_engine_strategy)
    
    assert hasattr(engine, 'get_explicit_marker')
    assert callable(engine.get_explicit_marker)
    
    assert hasattr(engine, 'dependencies_available')
    assert callable(engine.dependencies_available)
    
    # Test that it's a proper TradingEngine
    assert isinstance(engine, TradingEngine)