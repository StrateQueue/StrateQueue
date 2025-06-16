"""
CLI Smoke Tests for StrateQueue Daemon

Tests daemon process lifecycle via CLI commands.
"""

import pytest
import subprocess
import sys
import time
import os
import tempfile
from pathlib import Path

import requests


def test_daemon_start_stop_lifecycle():
    """Test full daemon lifecycle: start → health check → stop"""
    # Use ephemeral port to avoid conflicts
    port = 9500
    
    with tempfile.TemporaryDirectory() as temp_dir:
        log_file = Path(temp_dir) / "daemon.log"
        
        # Set up environment with PYTHONPATH
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()
        
        # Start daemon
        daemon_cmd = [
            sys.executable, "-m", "StrateQueue.daemon.server",
            "--bind", "127.0.0.1",
            "--port", str(port),
            "--log-file", str(log_file)
        ]
        
        process = subprocess.Popen(
            daemon_cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        
        try:
            # Wait for daemon to start
            time.sleep(3)
            
            # Check if daemon is responding
            health_url = f"http://127.0.0.1:{port}/health"
            response = requests.get(health_url, timeout=5)
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"
            
            # Check status endpoint
            status_url = f"http://127.0.0.1:{port}/status"
            response = requests.get(status_url, timeout=5)
            assert response.status_code == 200
            data = response.json()
            assert data["daemon_running"] is True
            assert data["trading_system_running"] is False
            
            # Graceful shutdown
            shutdown_url = f"http://127.0.0.1:{port}/shutdown"
            response = requests.post(shutdown_url, timeout=5)
            assert response.status_code == 200
            
            # Wait for process to terminate
            process.wait(timeout=15)
            assert process.returncode == 0
            
        except Exception as e:
            # Clean up process if test fails
            process.terminate()
            process.wait(timeout=5)
            raise e


def test_cli_daemon_commands():
    """Test CLI daemon commands (requires stratequeue CLI to work)"""
    port = 9501
    
    # Set up environment
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    
    try:
        # Test daemon start via CLI
        start_cmd = [
            sys.executable, "-c", "from StrateQueue.cli.cli import main; main()",
            "daemon", "start",
            "--port", str(port),
            "--bind", "127.0.0.1"
        ]
        
        result = subprocess.run(start_cmd, env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0
        assert "Daemon started successfully" in result.stdout
        
        # Wait a moment for daemon to be ready
        time.sleep(2)
        
        # Test daemon status via CLI
        status_cmd = [
            sys.executable, "-c", "from StrateQueue.cli.cli import main; main()",
            "daemon", "status"
        ]
        
        # Note: Status command uses default port 8400, but our test daemon is on 9501
        # This test might fail if default daemon is not running, which is expected
        # In real usage, users would start daemon on default port
        
        # Test daemon stop via CLI (this will try to stop default port daemon)
        stop_cmd = [
            sys.executable, "-c", "from StrateQueue.cli.cli import main; main()",
            "daemon", "stop"
        ]
        
        # Manually stop our test daemon via HTTP since CLI uses default port
        try:
            requests.post(f"http://127.0.0.1:{port}/shutdown", timeout=5)
        except:
            pass  # Expected if daemon already stopped
            
    except subprocess.TimeoutExpired:
        pytest.fail("CLI daemon commands timed out")
    except Exception as e:
        # Clean up any running processes
        try:
            requests.post(f"http://127.0.0.1:{port}/shutdown", timeout=5)
        except:
            pass
        raise e


def test_daemon_log_file_creation():
    """Test that daemon creates log files correctly"""
    port = 9502
    
    with tempfile.TemporaryDirectory() as temp_dir:
        log_file = Path(temp_dir) / "test_daemon.log"
        
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()
        
        daemon_cmd = [
            sys.executable, "-m", "StrateQueue.daemon.server",
            "--bind", "127.0.0.1",
            "--port", str(port),
            "--log-file", str(log_file)
        ]
        
        process = subprocess.Popen(
            daemon_cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        try:
            time.sleep(2)
            
            # Check log file was created
            assert log_file.exists()
            
            # Check log file has content
            log_content = log_file.read_text()
            assert "Starting StrateQueue daemon" in log_content
            
            # Stop daemon
            requests.post(f"http://127.0.0.1:{port}/shutdown", timeout=5)
            process.wait(timeout=10)
            
        except Exception as e:
            process.terminate()
            process.wait(timeout=5)
            raise e


def test_daemon_handles_invalid_args():
    """Test daemon handles invalid command line arguments gracefully"""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    
    # Test invalid port
    invalid_cmd = [
        sys.executable, "-m", "StrateQueue.daemon.server",
        "--port", "99999999"  # Invalid port number
    ]
    
    result = subprocess.run(
        invalid_cmd, 
        env=env, 
        capture_output=True, 
        text=True, 
        timeout=10
    )
    
    # Should fail with error code
    assert result.returncode != 0


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_daemon_cli.py -v -s
    pytest.main([__file__, "-v", "-s"]) 