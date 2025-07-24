"""
BtEngineStrategy Unit Tests
==========================
Comprehensive tests for the BtEngineStrategy wrapper class.

Requirements verified in this module
------------------------------------
A. Strategy parameter extraction (Requirement 5.1)
   A1  Parameters extracted from bt.Strategy object attributes
   A2  Constructor strategy_params override object attributes
   A3  Private attributes excluded from parameters
   A4  Complex objects excluded from parameters
   A5  Only simple types included (str, int, float, bool, list, dict)

B. Strategy name generation (Requirement 5.2)
   B1  Uses strategy.name if available and not empty
   B2  Falls back to BtStrategy_{id} format when name unavailable
   B3  Falls back to BtStrategy_{id} format when name is empty

C. Lookback period calculation (Requirement 5.3)
   C1  Returns minimum 20 bars for bt strategies
   C2  Consistent lookback period for same strategy

D. Standard EngineStrategy interface (Requirement 5.3)
   D1  Inherits from EngineStrategy base class
   D2  Implements all required abstract methods
   D3  Maintains strategy object reference
   D4  Supports strategy_params in constructor

All tests run without the real bt library using mock objects.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.StrateQueue.engines.bt_engine import BtEngineStrategy
from src.StrateQueue.engines.engine_base import EngineStrategy


# ---------------------------------------------------------------------------
# Mock bt.Strategy objects for testing
# ---------------------------------------------------------------------------

def create_mock_bt_strategy(name=None, **attributes):
    """Create a mock bt.Strategy object with specified attributes"""
    mock_strategy = Mock()
    mock_strategy.name = name
    mock_strategy.algos = []  # bt strategies have algos attribute
    
    # Add custom attributes
    for attr_name, attr_value in attributes.items():
        setattr(mock_strategy, attr_name, attr_value)
    
    return mock_strategy


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_bt_strategy():
    """Simple bt strategy with basic attributes"""
    return create_mock_bt_strategy(
        name="TestStrategy",
        param1="value1",
        param2=42,
        param3=3.14,
        param4=True,
        param5=[1, 2, 3],
        param6={"key": "value"}
    )


@pytest.fixture
def bt_strategy_with_private_attrs():
    """bt strategy with private attributes that should be excluded"""
    strategy = create_mock_bt_strategy(name="PrivateAttrsStrategy")
    strategy._private_attr = "should_be_excluded"
    strategy.__dunder_attr = "should_be_excluded"
    strategy.public_attr = "should_be_included"
    return strategy


@pytest.fixture
def bt_strategy_with_complex_objects():
    """bt strategy with complex objects that should be excluded"""
    strategy = create_mock_bt_strategy(name="ComplexObjectsStrategy")
    strategy.simple_param = "included"
    strategy.callable_param = lambda x: x  # Should be excluded
    strategy.complex_object = Mock()  # Should be excluded
    return strategy


@pytest.fixture
def bt_strategy_no_name():
    """bt strategy without a name"""
    return create_mock_bt_strategy(name=None, param1="value1")


@pytest.fixture
def bt_strategy_empty_name():
    """bt strategy with empty name"""
    return create_mock_bt_strategy(name="", param1="value1")


# ---------------------------------------------------------------------------
# A. Strategy parameter extraction tests (Requirement 5.1)
# ---------------------------------------------------------------------------

def test_A1_parameters_extracted_from_strategy_object(simple_bt_strategy):
    """A1: Parameters extracted from bt.Strategy object attributes"""
    strategy = BtEngineStrategy(simple_bt_strategy)
    params = strategy.get_parameters()
    
    assert params["param1"] == "value1"
    assert params["param2"] == 42
    assert params["param3"] == 3.14
    assert params["param4"] is True
    assert params["param5"] == [1, 2, 3]
    assert params["param6"] == {"key": "value"}


def test_A2_constructor_params_override_object_attributes(simple_bt_strategy):
    """A2: Constructor strategy_params override object attributes"""
    override_params = {"param1": "overridden", "new_param": "new_value"}
    strategy = BtEngineStrategy(simple_bt_strategy, strategy_params=override_params)
    params = strategy.get_parameters()
    
    assert params["param1"] == "overridden"  # Overridden
    assert params["param2"] == 42  # Original value
    assert params["new_param"] == "new_value"  # New parameter


def test_A3_private_attributes_excluded(bt_strategy_with_private_attrs):
    """A3: Private attributes excluded from parameters"""
    strategy = BtEngineStrategy(bt_strategy_with_private_attrs)
    params = strategy.get_parameters()
    
    assert "_private_attr" not in params
    assert "__dunder_attr" not in params
    assert params["public_attr"] == "should_be_included"


def test_A4_complex_objects_excluded(bt_strategy_with_complex_objects):
    """A4: Complex objects excluded from parameters"""
    strategy = BtEngineStrategy(bt_strategy_with_complex_objects)
    params = strategy.get_parameters()
    
    assert params["simple_param"] == "included"
    assert "callable_param" not in params
    assert "complex_object" not in params


def test_A5_only_simple_types_included():
    """A5: Only simple types included (str, int, float, bool, list, dict)"""
    mock_strategy = create_mock_bt_strategy(
        name="TypeTestStrategy",
        str_param="string",
        int_param=123,
        float_param=45.67,
        bool_param=False,
        list_param=[1, 2, 3],
        dict_param={"a": 1},
        none_param=None,  # Should be excluded
        tuple_param=(1, 2),  # Should be excluded
        set_param={1, 2, 3}  # Should be excluded
    )
    
    strategy = BtEngineStrategy(mock_strategy)
    params = strategy.get_parameters()
    
    # Simple types should be included
    assert params["str_param"] == "string"
    assert params["int_param"] == 123
    assert params["float_param"] == 45.67
    assert params["bool_param"] is False
    assert params["list_param"] == [1, 2, 3]
    assert params["dict_param"] == {"a": 1}
    
    # Complex types should be excluded
    assert "none_param" not in params
    assert "tuple_param" not in params
    assert "set_param" not in params


# ---------------------------------------------------------------------------
# B. Strategy name generation tests (Requirement 5.2)
# ---------------------------------------------------------------------------

def test_B1_uses_strategy_name_when_available(simple_bt_strategy):
    """B1: Uses strategy.name if available and not empty"""
    strategy = BtEngineStrategy(simple_bt_strategy)
    assert strategy.get_strategy_name() == "TestStrategy"


def test_B2_fallback_when_name_unavailable(bt_strategy_no_name):
    """B2: Falls back to BtStrategy_{id} format when name unavailable"""
    strategy = BtEngineStrategy(bt_strategy_no_name)
    name = strategy.get_strategy_name()
    
    assert name.startswith("BtStrategy_")
    assert len(name) > len("BtStrategy_")


def test_B3_fallback_when_name_empty(bt_strategy_empty_name):
    """B3: Falls back to BtStrategy_{id} format when name is empty"""
    strategy = BtEngineStrategy(bt_strategy_empty_name)
    name = strategy.get_strategy_name()
    
    assert name.startswith("BtStrategy_")
    assert len(name) > len("BtStrategy_")


def test_B4_consistent_name_for_same_strategy(simple_bt_strategy):
    """B4: Same strategy object produces consistent name"""
    strategy1 = BtEngineStrategy(simple_bt_strategy)
    strategy2 = BtEngineStrategy(simple_bt_strategy)
    
    assert strategy1.get_strategy_name() == strategy2.get_strategy_name()


# ---------------------------------------------------------------------------
# C. Lookback period calculation tests (Requirement 5.3)
# ---------------------------------------------------------------------------

def test_C1_returns_minimum_20_bars(simple_bt_strategy):
    """C1: Returns minimum 20 bars for bt strategies"""
    strategy = BtEngineStrategy(simple_bt_strategy)
    assert strategy.get_lookback_period() == 20


def test_C2_consistent_lookback_period(simple_bt_strategy):
    """C2: Consistent lookback period for same strategy"""
    strategy1 = BtEngineStrategy(simple_bt_strategy)
    strategy2 = BtEngineStrategy(simple_bt_strategy)
    
    assert strategy1.get_lookback_period() == strategy2.get_lookback_period()


def test_C3_lookback_period_independent_of_parameters():
    """C3: Lookback period is independent of strategy parameters"""
    strategy1 = create_mock_bt_strategy(name="Strategy1", param1="value1")
    strategy2 = create_mock_bt_strategy(name="Strategy2", param2="value2")
    
    wrapper1 = BtEngineStrategy(strategy1)
    wrapper2 = BtEngineStrategy(strategy2)
    
    assert wrapper1.get_lookback_period() == wrapper2.get_lookback_period() == 20


# ---------------------------------------------------------------------------
# D. Standard EngineStrategy interface tests (Requirement 5.3)
# ---------------------------------------------------------------------------

def test_D1_inherits_from_engine_strategy(simple_bt_strategy):
    """D1: Inherits from EngineStrategy base class"""
    strategy = BtEngineStrategy(simple_bt_strategy)
    assert isinstance(strategy, EngineStrategy)


def test_D2_implements_required_abstract_methods(simple_bt_strategy):
    """D2: Implements all required abstract methods"""
    strategy = BtEngineStrategy(simple_bt_strategy)
    
    # Test that all abstract methods are implemented and callable
    assert callable(strategy.get_lookback_period)
    assert callable(strategy.get_strategy_name)
    assert callable(strategy.get_parameters)
    
    # Test that methods return expected types
    assert isinstance(strategy.get_lookback_period(), int)
    assert isinstance(strategy.get_strategy_name(), str)
    assert isinstance(strategy.get_parameters(), dict)


def test_D3_maintains_strategy_object_reference(simple_bt_strategy):
    """D3: Maintains strategy object reference"""
    strategy = BtEngineStrategy(simple_bt_strategy)
    
    assert hasattr(strategy, 'strategy_obj')
    assert strategy.strategy_obj is simple_bt_strategy


def test_D4_supports_strategy_params_in_constructor(simple_bt_strategy):
    """D4: Supports strategy_params in constructor"""
    params = {"custom_param": "custom_value"}
    strategy = BtEngineStrategy(simple_bt_strategy, strategy_params=params)
    
    assert strategy.strategy_params == params
    assert strategy.get_parameters()["custom_param"] == "custom_value"


# ---------------------------------------------------------------------------
# Edge cases and error handling
# ---------------------------------------------------------------------------

def test_strategy_object_without_dict_attribute():
    """Handle strategy objects without __dict__ attribute"""
    # Create a mock that doesn't have __dict__
    mock_strategy = Mock()
    mock_strategy.name = "TestStrategy"
    mock_strategy.algos = []
    del mock_strategy.__dict__  # Remove __dict__ to test edge case
    
    strategy = BtEngineStrategy(mock_strategy)
    params = strategy.get_parameters()
    
    # Should not crash and should return empty dict (or only strategy_params)
    assert isinstance(params, dict)


def test_strategy_params_none():
    """Handle None strategy_params in constructor"""
    mock_strategy = create_mock_bt_strategy(name="TestStrategy", param1="value1")
    strategy = BtEngineStrategy(mock_strategy, strategy_params=None)
    
    params = strategy.get_parameters()
    assert params["param1"] == "value1"
    assert strategy.strategy_params == {}


def test_empty_strategy_params():
    """Handle empty strategy_params dict"""
    mock_strategy = create_mock_bt_strategy(name="TestStrategy", param1="value1")
    strategy = BtEngineStrategy(mock_strategy, strategy_params={})
    
    params = strategy.get_parameters()
    assert params["param1"] == "value1"


def test_strategy_with_property_attributes():
    """Handle strategy objects with property attributes"""
    class MockStrategyWithProperty:
        def __init__(self):
            self.name = "PropertyStrategy"
            self.algos = []
            self._internal_value = "internal"
        
        @property
        def computed_param(self):
            return "computed_value"
        
        @property
        def error_property(self):
            raise ValueError("Property access error")
    
    mock_strategy = MockStrategyWithProperty()
    strategy = BtEngineStrategy(mock_strategy)
    params = strategy.get_parameters()
    
    # Should handle properties gracefully
    assert isinstance(params, dict)
    # Properties might or might not be included depending on implementation
    # The important thing is that it doesn't crash


def test_strategy_name_with_special_characters():
    """Handle strategy names with special characters"""
    mock_strategy = create_mock_bt_strategy(name="Strategy-With_Special.Chars!")
    strategy = BtEngineStrategy(mock_strategy)
    
    assert strategy.get_strategy_name() == "Strategy-With_Special.Chars!"


def test_large_parameter_values():
    """Handle large parameter values"""
    mock_strategy = create_mock_bt_strategy(
        name="LargeParamsStrategy",
        large_int=999999999999999,
        large_float=1.23456789e10,
        large_list=list(range(1000)),
        large_dict={f"key_{i}": f"value_{i}" for i in range(100)}
    )
    
    strategy = BtEngineStrategy(mock_strategy)
    params = strategy.get_parameters()
    
    assert params["large_int"] == 999999999999999
    assert params["large_float"] == 1.23456789e10
    assert len(params["large_list"]) == 1000
    assert len(params["large_dict"]) == 100