#!/usr/bin/env python3

"""
Stratequeue Web UI Server

This module provides a local web server that serves the React frontend
which communicates directly with the StrateQueue daemon on port 8400.
"""

import subprocess
import threading
import time
import webbrowser
import socket
from pathlib import Path
from typing import Optional


def get_webui_path() -> Path:
    """Get the path to the webui directory."""
    return Path(__file__).parent


def get_frontend_path() -> Path:
    """Get the path to the frontend directory."""
    return get_webui_path() / "frontend"


def build_frontend() -> bool:
    """Build the Next.js frontend for production."""
    frontend_path = get_frontend_path()
    
    if not frontend_path.exists():
        print("❌ Frontend directory not found!")
        return False
    
    print("🔨 Building frontend...")
    try:
        # Build the Next.js app
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=frontend_path,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )
        
        if result.returncode != 0:
            print(f"❌ Frontend build failed: {result.stderr}")
            return False
            
        print("✅ Frontend built successfully!")
        return True
        
    except subprocess.TimeoutExpired:
        print("❌ Frontend build timed out!")
        return False
    except Exception as e:
        print(f"❌ Frontend build error: {e}")
        return False


def start_next_dev_server() -> Optional[subprocess.Popen]:
    """Start the Next.js development server."""
    frontend_path = get_frontend_path()
    
    if not frontend_path.exists():
        print("❌ Frontend directory not found!")
        return None
    
    print("🚀 Starting Next.js development server...")
    try:
        # Start Next.js dev server on port 3000
        # Don't capture stdout/stderr to avoid process hanging
        process = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", "3000"],
            cwd=frontend_path,
            stdout=subprocess.DEVNULL,  # Redirect to avoid buffer filling
            stderr=subprocess.DEVNULL,  # Redirect to avoid buffer filling
            text=True
        )
        
        # Wait for the server to be ready by checking if port 3000 is listening
        max_attempts = 15  # 15 seconds timeout
        
        for attempt in range(max_attempts):
            time.sleep(1)
            
            # Check if process is still running
            if process.poll() is not None:
                print("❌ Next.js process exited unexpectedly")
                return None
            
            # Check if port 3000 is listening
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex(('localhost', 3000))
                    if result == 0:
                        print("✅ Next.js development server started on port 3000")
                        return process
            except Exception:
                pass  # Continue trying
        
        # If we get here, the server didn't start in time
        print("❌ Next.js server failed to start within timeout")
        if process.poll() is None:
            process.terminate()
            process.wait()
        return None
            
    except Exception as e:
        print(f"❌ Error starting Next.js server: {e}")
        return None


def check_daemon_connection() -> bool:
    """Check if the daemon is running and accessible."""
    try:
        import requests
        response = requests.get("http://127.0.0.1:8400/health", timeout=2)
        return response.ok
    except:
        return False


def start_webui_server(open_browser: bool = True):
    """
    Start the Stratequeue Web UI server.
    
    Args:
        open_browser: Whether to automatically open the browser (default: True)
    """
    print("🚀 Starting Stratequeue Web UI...")
    print(f"📂 Frontend path: {get_frontend_path()}")
    
    # Check daemon connection
    daemon_connected = check_daemon_connection()
    if daemon_connected:
        print("✅ Connected to StrateQueue daemon on port 8400")
    else:
        print("⚠️  StrateQueue daemon not detected on port 8400")
        print("💡 To get live data, start daemon with: stratequeue daemon start")
    
    # Start the Next.js development server
    next_process = start_next_dev_server()
    
    if not next_process:
        print("❌ Failed to start frontend server")
        return
    
    try:
        if open_browser:
            # Open browser after a short delay
            def open_browser_delayed():
                time.sleep(2)
                webbrowser.open(f"http://localhost:3000")
            
            threading.Thread(target=open_browser_delayed, daemon=True).start()
        
        print("✅ Stratequeue Web UI is running!")
        print(f"🌐 Frontend: http://localhost:3000")
        if daemon_connected:
            print(f"🔌 Daemon API: http://localhost:8400")
        print("📝 Press Ctrl+C to stop")
        
        # Keep the process alive
        try:
            while next_process.poll() is None:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Shutting down Web UI...")
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down Web UI...")
    finally:
        # Clean up the Next.js process
        if next_process and next_process.poll() is None:
            print("🧹 Stopping Next.js server...")
            next_process.terminate()
            next_process.wait()
        
        print("✅ Web UI stopped")


if __name__ == "__main__":
    start_webui_server() 