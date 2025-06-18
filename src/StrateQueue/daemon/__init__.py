"""
StrateQueue Daemon Package

This package contains the trading daemon server and related utilities.
"""

import subprocess
import sys
import time
from typing import Tuple

import requests

from .server import DEFAULT_DAEMON_HOST, DEFAULT_DAEMON_PORT

DAEMON_START_TIMEOUT = 10  # seconds

def is_daemon_running(port: int = DEFAULT_DAEMON_PORT) -> bool:
    """Check if the trading daemon is running"""
    try:
        response = requests.get(f"http://{DEFAULT_DAEMON_HOST}:{port}/health", timeout=1)
        return response.status_code == 200 and response.json().get("status") == "ok"
    except requests.exceptions.ConnectionError:
        return False

def start_daemon_process(
    bind: str = DEFAULT_DAEMON_HOST,
    port: int = DEFAULT_DAEMON_PORT,
    log_file: str = "~/.stratequeue/daemon.log",
    verbose: bool = False
) -> tuple[bool, str]:
    """
    Start the daemon as a background process and wait for it to be healthy.

    Args:
        bind: IP address to bind to.
        port: Port to listen on.
        log_file: Path to the log file.
        verbose: If True, print detailed output.

    Returns:
        A tuple of (success, message).
    """
    if is_daemon_running(port):
        if verbose:
            print("✅ Daemon is already running.")
        return True, "Daemon is already running."

    if verbose:
        print(f"🚀 Starting daemon on {bind}:{port}...")
        print(f"📝 Logs will be written to: {log_file}")

    try:
        cmd = [
            sys.executable,
            "-m", "uvicorn",
            "StrateQueue.daemon.server:app",
            "--host", bind,
            "--port", str(port),
            "--lifespan", "on"
        ]

        # For background execution, redirect output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True  # Detach from the current terminal
        )

        # Wait for the daemon to become healthy
        start_time = time.time()
        while time.time() - start_time < DAEMON_START_TIMEOUT:
            if is_daemon_running(port):
                if verbose:
                    print("✅ Daemon started successfully.")
                return True, "Daemon started successfully."
            time.sleep(0.5)

        # If it times out, kill the process and report failure
        process.kill()
        return False, f"Daemon failed to start within {DAEMON_START_TIMEOUT} seconds."

    except Exception as e:
        return False, f"Failed to start daemon process: {e}"

__version__ = "0.0.1"
