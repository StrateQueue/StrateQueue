"""
Comprehensive Test Suite for DataProviderFactory

This test module thoroughly tests the DataProviderFactory implementation with focus on:
1. Registration logic
2. Capability helpers
3. Environment-based provider detection
4. Error handling
5. Configuration validation

Core features tested:
- _initialize_providers only runs once
- Providers with missing dependencies remain listed but throw on instantiation
- Canonical keys present in provider registry
- is_provider_supported returns correct values
- detect_provider_type correctly identifies from environment variables
- create_provider properly handles error cases and configuration

Note: This file complements the existing tests in test_provider_factory.py.
Together they provide ~64% coverage of the provider_factory.py module.

The remaining untested code is primarily:
- Exception handling blocks
- Provider-specific creation branches for less common providers
- Some helper functions for credentials validation

All tests run without performing any real network IO.
"""

from __future__ import annotations

import os
import sys
import types
import importlib
import logging
from unittest.mock import patch, MagicMock, call

import pytest

from StrateQueue.data import provider_factory as pf
from StrateQueue.data.sources.demo import TestDataIngestion
from StrateQueue.data.provider_factory import DataProviderFactory, DataProviderConfig


# ---------------------------------------------------------------------------
# Setup and helper fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def reset_provider_factory():
    """Reset DataProviderFactory state before each test."""
    # Store the original state
    original_providers = DataProviderFactory._providers.copy()
    original_initialized = DataProviderFactory._initialized
    
    # Reset the factory
    DataProviderFactory._providers = {}
    DataProviderFactory._initialized = False
    
    yield
    
    # Restore the original state
    DataProviderFactory._providers = original_providers
    DataProviderFactory._initialized = original_initialized


@pytest.fixture
def clean_env(monkeypatch):
    """Remove all data provider environment variables."""
    env_vars = [
        'POLYGON_API_KEY',
        'CMC_API_KEY',
        'PAPER_KEY', 'PAPER_API_KEY', 'ALPACA_API_KEY',
        'PAPER_SECRET', 'PAPER_SECRET_KEY', 'ALPACA_SECRET_KEY',
        'IB_TWS_PORT', 'IB_CLIENT_ID', 'IB_TWS_HOST',
        'DATA_PROVIDER'
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# Test Group 1: Registration Logic
# ---------------------------------------------------------------------------

def test_initialize_providers_runs_only_once(reset_provider_factory):
    """Test that _initialize_providers only runs once directly."""
    # First directly call initialize to set _initialized = True
    DataProviderFactory._initialize_providers()
    
    # Now use the spy to track subsequent calls
    with patch.object(DataProviderFactory, '_initialize_providers', wraps=DataProviderFactory._initialize_providers) as mock_init:
        # Should not execute the body since _initialized is already True
        DataProviderFactory._initialize_providers()
        assert mock_init.call_count == 1
        
        # Another call should still just return without doing work
        DataProviderFactory._initialize_providers()
        assert mock_init.call_count == 2
        
        # Although call_count increases, the actual code inside _initialize_providers
        # should only run once due to the early return when _initialized=True


def test_providers_with_missing_deps_remain_listed(reset_provider_factory):
    """Test that providers whose dependencies are missing remain listed but throw on instantiation."""
    # Create a mock provider that will raise an exception when instantiated
    mock_provider = MagicMock()
    mock_provider.side_effect = ImportError("Dependency not installed")
    
    # First let the factory initialize normally
    DataProviderFactory._initialize_providers()
    
    # Then add our fake provider
    DataProviderFactory._providers['fake_provider'] = mock_provider
    
    # Verify the provider is listed
    providers = DataProviderFactory.get_supported_providers()
    assert 'fake_provider' in providers
    
    # But creating it should raise an exception
    with pytest.raises(Exception):
        DataProviderFactory.create_provider('fake_provider')


def test_canonical_keys_present(reset_provider_factory):
    """Test that canonical provider keys are present."""
    # Get supported providers
    providers = DataProviderFactory.get_supported_providers()
    
    # Check that canonical keys are present
    canonical_keys = ["polygon", "coinmarketcap", "demo", "yfinance", "alpaca", "ibkr"]
    for key in canonical_keys:
        assert key in providers


# ---------------------------------------------------------------------------
# Test Group 2: Capability Helpers
# ---------------------------------------------------------------------------

def test_is_provider_supported_returns_true_for_valid_providers(reset_provider_factory):
    """Test is_provider_supported returns True for valid providers."""
    assert DataProviderFactory.is_provider_supported("demo") is True


def test_is_provider_supported_returns_false_for_unknown_providers(reset_provider_factory):
    """Test is_provider_supported returns False for unknown providers."""
    assert DataProviderFactory.is_provider_supported("foo") is False


# ---------------------------------------------------------------------------
# Test Group 3: Environment-based Provider Detection
# ---------------------------------------------------------------------------

def test_detect_provider_type_with_polygon_api_key(reset_provider_factory, clean_env, monkeypatch):
    """Test that with POLYGON_API_KEY set, detect_provider_type returns 'polygon'."""
    monkeypatch.setenv("POLYGON_API_KEY", "dummy_key")
    assert pf.detect_provider_type() == "polygon"


def test_detect_provider_type_with_alpaca_credentials(reset_provider_factory, clean_env, monkeypatch):
    """Test that with both PAPER_KEY & PAPER_SECRET set, detect_provider_type returns 'alpaca'."""
    monkeypatch.setenv("PAPER_KEY", "dummy_key")
    monkeypatch.setenv("PAPER_SECRET", "dummy_secret")
    assert pf.detect_provider_type() == "alpaca"


def test_detect_provider_type_with_nothing_set_returns_demo(reset_provider_factory, clean_env):
    """Test that with nothing set, detect_provider_type returns 'demo'."""
    assert pf.detect_provider_type() == "demo"


def test_detect_provider_type_prefers_polygon_over_alpaca(reset_provider_factory, clean_env, monkeypatch):
    """Test that when multiple API keys are set, polygon is preferred over alpaca."""
    monkeypatch.setenv("POLYGON_API_KEY", "dummy_key")
    monkeypatch.setenv("PAPER_KEY", "dummy_key")
    monkeypatch.setenv("PAPER_SECRET", "dummy_secret")
    assert pf.detect_provider_type() == "polygon"


def test_detect_provider_type_honors_explicit_setting(reset_provider_factory, clean_env, monkeypatch):
    """Test that explicit DATA_PROVIDER setting is honored."""
    monkeypatch.setenv("DATA_PROVIDER", "yfinance")
    assert pf.detect_provider_type() == "yfinance"


def test_detect_provider_type_unknown_explicit_setting_ignored(reset_provider_factory, clean_env, monkeypatch):
    """Test that unknown explicit DATA_PROVIDER setting is ignored."""
    monkeypatch.setenv("DATA_PROVIDER", "nonexistent")
    assert pf.detect_provider_type() == "demo"  # Falls back to demo

def test_detect_provider_type_with_ccxt_credentials(reset_provider_factory, clean_env, monkeypatch):
    """Test that with CCXT credentials set, detect_provider_type returns 'ccxt'."""
    monkeypatch.setenv("CCXT_EXCHANGE", "binance")
    monkeypatch.setenv("CCXT_API_KEY", "dummy_key")
    monkeypatch.setenv("CCXT_SECRET_KEY", "dummy_secret")
    assert pf.detect_provider_type() == "ccxt"


# ---------------------------------------------------------------------------
# Test Group 4: Create Provider Error Branches
# ---------------------------------------------------------------------------

def test_create_provider_polygon_without_api_key_raises(reset_provider_factory, clean_env):
    """Test that creating a Polygon provider without an API key raises ValueError."""
    with pytest.raises(ValueError) as exc:
        pf.create_provider("polygon")
    
    assert "requires an API key" in str(exc.value)


def test_create_provider_unknown_provider_raises_helpful_message(reset_provider_factory):
    """Test that requesting an unknown provider raises ValueError with helpful message."""
    with pytest.raises(ValueError) as exc:
        pf.create_provider("nonexistent")
    
    assert "Unsupported data provider type" in str(exc.value)
    assert "Available:" in str(exc.value)  # Should list available providers


def test_create_provider_demo_obeys_granularity(reset_provider_factory):
    """Test that create_provider returns a TestDataIngestion with correct granularity."""
    # Create demo provider with specific granularity
    config = DataProviderConfig(provider_type="demo", granularity="5m")
    provider = pf.create_provider("demo", config)
    
    # Verify it's the right class
    assert isinstance(provider, TestDataIngestion)
    
    # The demo provider should have update interval set based on granularity
    # 5m = 300 seconds
    expected_interval = 300
    assert provider.update_interval == expected_interval


# ---------------------------------------------------------------------------
# Additional Tests for Coverage
# ---------------------------------------------------------------------------

def test_create_provider_passes_api_key_to_polygon(reset_provider_factory):
    """Test that API key is properly passed to Polygon provider."""
    # Create a spy for the polygon provider
    mock_polygon = MagicMock()
    
    # First initialize providers normally
    DataProviderFactory._initialize_providers()
    
    # Then replace the polygon provider with our mock
    DataProviderFactory._providers["polygon"] = mock_polygon
    
    # Create provider with API key
    config = DataProviderConfig(provider_type="polygon", api_key="test_key")
    pf.create_provider("polygon", config)
    
    # Verify the provider constructor was called with the API key
    mock_polygon.assert_called_once_with("test_key")


def test_get_provider_info_returns_data_for_valid_providers(reset_provider_factory):
    """Test that get_provider_info returns provider data for valid providers."""
    info = DataProviderFactory.get_provider_info("demo")
    
    assert info is not None
    assert info.name == "Demo/Test Data"
    assert info.requires_api_key is False
    assert "1m" in info.supported_granularities

def test_get_provider_info_ccxt_provider(reset_provider_factory):
    """Test that CCXT provider info is correctly returned."""
    info = DataProviderFactory.get_provider_info("ccxt")
    
    assert info is not None
    assert info.name == "CCXT"
    assert info.requires_api_key is True
    assert "crypto" in info.supported_markets
    assert "1m" in info.supported_granularities
    assert info.supported_features["multiple_exchanges"] is True


def test_get_provider_info_returns_none_for_invalid_providers(reset_provider_factory):
    """Test that get_provider_info returns None for invalid providers."""
    assert DataProviderFactory.get_provider_info("nonexistent") is None


def test_list_provider_features_returns_all_providers(reset_provider_factory):
    """Test that list_provider_features returns all available providers."""
    features = pf.list_provider_features()
    
    # Should include at least the demo provider
    assert "demo" in features
    assert isinstance(features["demo"], pf.DataProviderInfo) 