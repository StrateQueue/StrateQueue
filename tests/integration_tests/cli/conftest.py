"""
CLI Integration Test Fixtures and Helpers

Provides fixtures and helper functions for testing the CLI end-to-end
by spawning real subprocess calls to the stratequeue command.
"""

import os
import sys
import subprocess
import pytest
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

# Add debug helper to check environment in CI
@pytest.fixture(scope="session", autouse=True)
def debug_test_env():
    """Debug helper to print environment information for CI debugging"""
    print("\n--- Test Environment Info ---")
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    
    # Check key package versions
    packages = ["python-dotenv", "pexpect", "pytest"]
    for pkg in packages:
        try:
            __import__(pkg)
            mod = sys.modules[pkg]
            version = getattr(mod, "__version__", "unknown")
            print(f"{pkg} version: {version}")
        except (ImportError, AttributeError):
            print(f"{pkg} not found or version unknown")
    
    # Check if HOME is set
    print(f"HOME env: {os.environ.get('HOME', 'Not set')}")
    print("--- End Environment Info ---\n")


@pytest.fixture
def tmp_working_dir(tmp_path):
    """
    Provide a temporary working directory for CLI tests.
    
    This ensures each test runs in isolation with its own
    temporary directory for any files created.
    """
    return tmp_path


def run_cli(*args, stdin: str = "", env: Optional[Dict[str, str]] = None, 
            timeout: int = 30, cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    """
    Spawn `stratequeue` in a real subprocess and return results.
    
    Args:
        *args: Command line arguments to pass to stratequeue
        stdin: Input to send to stdin (default: empty string)
        env: Environment variables to set (merged with current env)
        timeout: Maximum time to wait for command completion (seconds)
        cwd: Working directory for the command (default: current directory)
        
    Returns:
        Tuple of (exit_code, stdout, stderr)
        
    Example:
        exit_code, stdout, stderr = run_cli("--help")
        assert exit_code == 0
        assert "StrateQueue" in stdout
    """
    # Build the command to run the CLI module
    cmd = [sys.executable, "-m", "StrateQueue.cli.cli"] + list(args)
    
    # Merge environment variables
    test_env = os.environ.copy()  # Start with current environment
    if env:
        test_env.update(env)
    
    # Add src directory to PYTHONPATH so subprocess can find StrateQueue module
    if cwd:
        src_path = cwd / "src"
        if src_path.exists():
            current_pythonpath = test_env.get("PYTHONPATH", "")
            if current_pythonpath:
                test_env["PYTHONPATH"] = f"{src_path}{os.pathsep}{current_pythonpath}"
            else:
                test_env["PYTHONPATH"] = str(src_path)
    
    for var in ("PAPER_KEY","PAPER_SECRET","ALPACA_API_KEY","ALPACA_SECRET_KEY",
                "IB_TWS_PORT","IB_CLIENT_ID","IB_TWS_HOST"):
        test_env[var] = ""
    
    try:
        result = subprocess.run(
            cmd,
            input=stdin.encode() if stdin else None,
            capture_output=True,
            env=test_env,
            timeout=timeout,
            cwd=cwd
        )
        
        return (
            result.returncode,
            result.stdout.decode('utf-8', errors='replace'),
            result.stderr.decode('utf-8', errors='replace')
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"Command timed out after {timeout} seconds: {' '.join(cmd)}")
    except Exception as e:
        pytest.fail(f"Failed to run command {' '.join(cmd)}: {e}")


# Automatically inject offline/test environment variables so that the spawned
# subprocess uses the same lightweight stub environment as the current test
# process.  This guarantees that the CLI output (which runs in a fresh Python
# interpreter) matches the expectations computed inside the test process
# (e.g. InfoFormatter outputs built from the in-process Broker stubs).

# Stub registration is now handled in the main conftest.py
# No need for additional stub registration here

@pytest.fixture
def cli_runner(tmp_working_dir, mock_offline_env):
    """
    Provide a CLI runner fixture that runs commands in a temporary directory.
    
    Returns a function that can be called like:
        exit_code, stdout, stderr = cli_runner("--help")
    """
    def _run_cli(*args, **kwargs):
        # Run CLI subprocess from project root
        project_root = Path(__file__).resolve().parents[3]  # Go up from tests/integration_tests/cli/
        kwargs.setdefault('cwd', project_root)

        # Merge/append environment variables so the child process inherits the
        # *offline* settings (no real network/Broker SDK imports) unless the
        # caller explicitly overrides them.
        extra_env = kwargs.pop('env', {}) or {}
        # Child-env gets the offline defaults first, then any explicit overrides
        merged_env = {
            **mock_offline_env,  # SQ_OFFLINE / SQ_LIGHT_IMPORTS, etc.
            **extra_env,
            "SQ_TEST_STUB_BROKERS": "1",
        }

        return run_cli(*args, env=merged_env, **kwargs)
    
    return _run_cli


def strip_ansi(text: str) -> str:
    """
    Remove ANSI color codes from text for easier testing.
    
    Args:
        text: Text that may contain ANSI escape sequences
        
    Returns:
        Text with ANSI codes removed
    """
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def normalize_output(text: str) -> str:
    """
    Normalize output text for cross-platform testing.
    
    Args:
        text: Raw output text
        
    Returns:
        Normalized text with consistent line endings and stripped ANSI codes
    """
    # Remove ANSI codes
    text = strip_ansi(text)
    
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Strip trailing whitespace from each line
    lines = [line.rstrip() for line in text.split('\n')]
    
    return '\n'.join(lines)


@pytest.fixture
def mock_offline_env():
    """
    Provide environment variables that put StrateQueue in offline mode.
    
    This prevents network calls during integration tests.
    """
    return {
        'SQ_OFFLINE': '1',
        'SQ_LIGHT_IMPORTS': '1',
        'IBKR_PORT': '4000',  # Force IBKR tests to skip in CI
    }


@pytest.fixture
def temp_env_file(tmp_working_dir):
    """
    Create a temporary .env file for testing configuration.
    
    Returns a function that creates an .env file with given content.
    """
    def _create_env_file(content: str) -> Path:
        env_file = tmp_working_dir / '.env'
        env_file.write_text(content)
        return env_file
    
    return _create_env_file


# Mark all tests in this directory as integration tests
pytestmark = pytest.mark.integration 