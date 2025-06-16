"""
Test suite for StrateQueue Daemon API

Tests all HTTP endpoints including concurrency safety and lifecycle management.
"""

import pytest
import pytest_asyncio
import asyncio
import tempfile
from pathlib import Path
from httpx import AsyncClient

from StrateQueue.daemon.server import app, daemon


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    # Ensure clean state between tests
    if daemon.running:
        await daemon.shutdown()


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Test health endpoint always responds"""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["daemon_running"] is True


@pytest.mark.asyncio
async def test_status_before_deployment(client):
    """Test status when no trading system is running"""
    response = await client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["daemon_running"] is True
    assert data["trading_system_running"] is False
    assert data["strategies"] == []


@pytest.mark.asyncio
async def test_deploy_invalid_strategy(client):
    """Test deployment with invalid strategy path"""
    response = await client.post("/deploy", json={
        "strategy": "nonexistent/strategy.py",
        "symbol": "DOGE"
    })
    assert response.status_code == 500  # Should fail gracefully


@pytest.mark.asyncio
async def test_full_lifecycle(client):
    """Test complete strategy lifecycle: deploy → status → pause → resume → undeploy"""
    strategy_path = "examples/strategies/simple_sma.py"
    
    # 1. Deploy initial strategy
    response = await client.post("/deploy", json={
        "strategy": strategy_path,
        "symbol": "DOGE",
        "allocation": 0.7
    })
    assert response.status_code == 200
    assert "success" in response.json()["status"]
    
    # 2. Check status - should show trading system running
    response = await client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["trading_system_running"] is True
    assert len(data["strategies"]) == 1
    strategy_id = data["strategies"][0]
    
    # 3. Deploy second strategy
    response = await client.post("/strategy/deploy", json={
        "strategy": strategy_path,
        "symbol": "BTC",
        "strategy_id": "sma_btc",
        "allocation": 0.2
    })
    assert response.status_code == 200
    assert "sma_btc deployed successfully" in response.json()["message"]
    
    # 4. Check status again - should show 2 strategies
    response = await client.get("/status")
    data = response.json()
    assert len(data["strategies"]) == 2
    assert "sma_btc" in data["strategies"]
    
    # 5. Pause one strategy
    response = await client.post("/strategy/pause", json={
        "strategy_id": "sma_btc"
    })
    assert response.status_code == 200
    assert "sma_btc paused" in response.json()["message"]
    
    # 6. Resume the strategy
    response = await client.post("/strategy/resume", json={
        "strategy_id": "sma_btc"
    })
    assert response.status_code == 200
    assert "sma_btc resumed" in response.json()["message"]
    
    # 7. Rebalance portfolio
    response = await client.post("/portfolio/rebalance", json={
        "allocations": {strategy_id: 0.6, "sma_btc": 0.4}
    })
    assert response.status_code == 200
    assert "rebalanced successfully" in response.json()["message"]
    
    # 8. Undeploy one strategy
    response = await client.post("/strategy/undeploy", json={
        "strategy_id": "sma_btc"
    })
    assert response.status_code == 200
    assert "sma_btc undeployed" in response.json()["message"]
    
    # 9. Check final status
    response = await client.get("/status")
    data = response.json()
    assert len(data["strategies"]) == 1
    assert "sma_btc" not in data["strategies"]


@pytest.mark.asyncio
async def test_allocation_limits(client):
    """Test allocation limit enforcement"""
    strategy_path = "examples/strategies/simple_sma.py"
    
    # Deploy strategy with 100% allocation
    response = await client.post("/deploy", json={
        "strategy": strategy_path,
        "symbol": "DOGE",
        "allocation": 1.0
    })
    assert response.status_code == 200
    
    # Try to deploy another strategy - should fail due to allocation limit
    response = await client.post("/strategy/deploy", json={
        "strategy": strategy_path,
        "symbol": "BTC",
        "allocation": 0.1
    })
    assert response.status_code == 500
    assert "Allocation limit exceeded" in response.json()["detail"]


@pytest.mark.asyncio
async def test_concurrent_deployments(client):
    """Test async lock protection during concurrent strategy deployments"""
    strategy_path = "examples/strategies/simple_sma.py"
    
    # First deploy a strategy with 90% allocation
    response = await client.post("/deploy", json={
        "strategy": strategy_path,
        "symbol": "DOGE",
        "allocation": 0.9
    })
    assert response.status_code == 200
    
    # Fire two concurrent deployment requests that each want 10%
    # Only one should succeed due to allocation limits
    responses = await asyncio.gather(
        client.post("/strategy/deploy", json={
            "strategy": strategy_path,
            "symbol": "BTC",
            "strategy_id": "concurrent1",
            "allocation": 0.1
        }),
        client.post("/strategy/deploy", json={
            "strategy": strategy_path,
            "symbol": "ETH", 
            "strategy_id": "concurrent2",
            "allocation": 0.1
        }),
        return_exceptions=True
    )
    
    # Count successful vs failed responses
    success_count = sum(1 for r in responses if r.status_code == 200)
    error_count = sum(1 for r in responses if r.status_code == 500)
    
    # Exactly one should succeed, one should fail
    assert success_count == 1
    assert error_count == 1


@pytest.mark.asyncio
async def test_strategy_control_without_system(client):
    """Test strategy control endpoints when trading system not running"""
    endpoints_to_test = [
        ("/strategy/deploy", {"strategy": "test.py", "symbol": "DOGE"}),
        ("/strategy/pause", {"strategy_id": "test"}),
        ("/strategy/resume", {"strategy_id": "test"}),
        ("/strategy/undeploy", {"strategy_id": "test"}),
        ("/portfolio/rebalance", {"allocations": {"test": 0.5}})
    ]
    
    for endpoint, payload in endpoints_to_test:
        response = await client.post(endpoint, json=payload)
        assert response.status_code == 503
        assert "Trading system not running" in response.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_payloads(client):
    """Test endpoints with missing or invalid parameters"""
    strategy_path = "examples/strategies/simple_sma.py"
    
    # Deploy system first
    await client.post("/deploy", json={
        "strategy": strategy_path,
        "symbol": "DOGE"
    })
    
    # Test missing required fields
    invalid_requests = [
        ("/strategy/deploy", {}),  # missing strategy and symbol
        ("/strategy/deploy", {"strategy": strategy_path}),  # missing symbol
        ("/strategy/pause", {}),  # missing strategy_id
        ("/strategy/resume", {}),  # missing strategy_id
        ("/strategy/undeploy", {}),  # missing strategy_id
        ("/portfolio/rebalance", {}),  # missing allocations
        ("/portfolio/rebalance", {"allocations": "invalid"}),  # invalid allocations type
    ]
    
    for endpoint, payload in invalid_requests:
        response = await client.post(endpoint, json=payload)
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_shutdown_endpoint(client):
    """Test graceful shutdown endpoint"""
    response = await client.post("/shutdown")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "shutting down" in data["message"]


@pytest.mark.asyncio
async def test_async_lock_behavior():
    """Test that asyncio.Lock doesn't block the event loop"""
    # Create a new daemon instance for isolated testing
    from StrateQueue.daemon.server import TradingDaemon
    test_daemon = TradingDaemon()
    
    # Verify lock is asyncio.Lock
    assert isinstance(test_daemon._lock, asyncio.Lock)
    
    # Test that lock can be acquired asynchronously
    async with test_daemon._lock:
        # Simulate some async work
        await asyncio.sleep(0.001)
        
        # While holding the lock, try to acquire it again (should work with asyncio)
        lock_acquired = False
        
        async def try_acquire():
            nonlocal lock_acquired
            # This should wait, not block the event loop
            async with test_daemon._lock:
                lock_acquired = True
        
        # Start the task but don't wait for it
        task = asyncio.create_task(try_acquire())
        
        # Give it a moment to try acquiring
        await asyncio.sleep(0.001)
        
        # Lock should not be acquired yet (we're holding it)
        assert not lock_acquired
        
    # Now the lock is released, task should complete
    await task
    assert lock_acquired


@pytest.mark.asyncio
async def test_smart_strategy_id_generation():
    """Test the smart strategy ID generation with timestamps"""
    from StrateQueue.daemon.server import generate_strategy_id
    import re
    
    # Test with symbol
    id_with_symbol = generate_strategy_id("examples/strategies/simple_sma.py", "ETH")
    assert re.match(r"simple_sma_ETH_\d{8}_\d{6}", id_with_symbol)
    
    # Test without symbol
    id_without_symbol = generate_strategy_id("examples/strategies/simple_sma.py")
    assert re.match(r"simple_sma_\d{8}_\d{6}", id_without_symbol)
    
    # Test user-provided ID takes precedence
    custom_id = generate_strategy_id("examples/strategies/simple_sma.py", "ETH", "my_custom_id")
    assert custom_id == "my_custom_id"
    
    # Test uniqueness - two calls should produce different IDs
    import time
    id1 = generate_strategy_id("test.py", "BTC")
    time.sleep(1.1)  # Ensure different second
    id2 = generate_strategy_id("test.py", "BTC")
    assert id1 != id2


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_daemon_api.py -v
    pytest.main([__file__, "-v"]) 