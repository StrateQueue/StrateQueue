"""Global pytest configuration tweaks for the stubbed/offline test environment."""

import os
import pytest
import asyncio

# ---------------------------------------------------------------------------
# Skip *live* broker integration tests automatically – they require network
# connectivity and genuine broker back-ends.  We still collect them (so the
# test suite stays visible) but mark them as *skipped* at runtime.
# ---------------------------------------------------------------------------

def pytest_collection_modifyitems(config, items):
    skip_live = pytest.mark.skip(reason="Live integration tests are disabled in the offline test environment")
    for item in items:
        # custom markers defined in the relevant test modules
        if 'live_ibkr' in item.keywords or 'live_alpaca' in item.keywords or 'network' in item.keywords:
            item.add_marker(skip_live)

    # The *engine_parity* tests are computationally heavy and depend on optional
    # back-end libraries (Backtrader, etc.) not included in the lightweight CI
    # environment.  Skip them unless the user explicitly requests the
    # 'engine_parity' marker.
    skip_engine_parity = pytest.mark.skip(reason="Engine parity tests skipped in lightweight environment")
    for item in items:
        if 'engine_parity' in str(item.nodeid) or 'engine_parity' in str(getattr(item, 'fspath', '')):
            item.add_marker(skip_engine_parity)
    
    # Auto-mark async functions with asyncio marker if not already marked
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            if not any(marker.name == 'asyncio' for marker in item.iter_markers()):
                item.add_marker(pytest.mark.asyncio)

# ---------------------------------------------------------------------------
# Defensive per-test setup: re-assert critical stub symbols that *some* tests
# expect to be present (they may get monkey-patched away in previous tests).
# ---------------------------------------------------------------------------

def pytest_runtest_setup(item):
    import sys as _sys
    
    # Clean environment variables that might affect provider detection
    # This prevents CCXT credentials from interfering with tests that expect demo provider
    ccxt_env_vars = [
        'CCXT_EXCHANGE', 'CCXT_API_KEY', 'CCXT_SECRET_KEY', 'CCXT_PASSPHRASE',
        'CCXT_PAPER_TRADING', 'CCXT_SANDBOX'
    ]
    
    # Also clean exchange-specific CCXT variables
    ccxt_exchanges = ['BINANCE', 'COINBASE', 'KRAKEN', 'BYBIT', 'OKX', 'KUCOIN', 'HUOBI', 'BITFINEX', 'GATEIO', 'MEXC']
    for exchange in ccxt_exchanges:
        ccxt_env_vars.extend([
            f'CCXT_{exchange}_API_KEY',
            f'CCXT_{exchange}_SECRET_KEY', 
            f'CCXT_{exchange}_PASSPHRASE',
            f'CCXT_{exchange}_PAPER_TRADING'
        ])
    
    # Store original values and clear them for tests
    if not hasattr(item.session, '_original_env_vars'):
        item.session._original_env_vars = {}
        for var in ccxt_env_vars:
            if var in os.environ:
                item.session._original_env_vars[var] = os.environ[var]
                del os.environ[var]
    
    mod_name = "StrateQueue.brokers.Alpaca.alpaca_broker"
    # Lazily import the broker & stubs so that they are guaranteed present.
    try:
        import importlib
        _ab = importlib.import_module(mod_name)
        from tests.unit_tests.brokers.alpaca.alpaca_stubs import _FakeAlpacaClient, _FakeAPIError
    except Exception:
        return  # either broker or stubs unavailable – nothing to patch

    if not hasattr(_ab, "TradingClient"):
        setattr(_ab, "TradingClient", _FakeAlpacaClient)
    if not hasattr(_ab, "APIError"):
        setattr(_ab, "APIError", _FakeAPIError)

# ---------------------------------------------------------------------------
# Global fixtures for environment isolation and async support
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
def clean_ccxt_env():
    """Clean CCXT environment variables before each test to prevent interference."""
    ccxt_env_vars = [
        'CCXT_EXCHANGE', 'CCXT_API_KEY', 'CCXT_SECRET_KEY', 'CCXT_PASSPHRASE',
        'CCXT_PAPER_TRADING', 'CCXT_SANDBOX'
    ]
    
    # Also clean exchange-specific variables
    exchanges = ['BINANCE', 'COINBASE', 'KRAKEN', 'BYBIT', 'OKX', 'KUCOIN', 
                'HUOBI', 'BITFINEX', 'GATEIO', 'MEXC']
    
    for exchange in exchanges:
        ccxt_env_vars.extend([
            f'CCXT_{exchange}_API_KEY',
            f'CCXT_{exchange}_SECRET_KEY', 
            f'CCXT_{exchange}_PASSPHRASE',
            f'CCXT_{exchange}_PAPER_TRADING'
        ])
    
    # Store original values
    original_values = {}
    for var in ccxt_env_vars:
        if var in os.environ:
            original_values[var] = os.environ[var]
            del os.environ[var]
    
    yield
    
    # Restore original values
    for var, value in original_values.items():
        os.environ[var] = value 