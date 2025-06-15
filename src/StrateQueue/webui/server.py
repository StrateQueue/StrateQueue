#!/usr/bin/env python3

"""
Stratequeue Web UI Server

This module provides a local web server that serves the React frontend
and bridges communication between the web interface and the CLI commands.
"""

import os
import sys
import subprocess
import threading
import time
import webbrowser
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware


def get_webui_path() -> Path:
    """Get the path to the webui directory."""
    return Path(__file__).parent


def get_frontend_path() -> Path:
    """Get the path to the frontend directory."""
    return get_webui_path() / "frontend"


def get_strategies_from_cli() -> Dict[str, Any]:
    """
    Get strategies from the CLI command 'stratequeue list strategy'.
    
    Returns:
        Dictionary containing strategies data or error information
    """
    try:
        # Run the CLI command to get strategies
        result = subprocess.run(
            ["stratequeue", "list", "strategy"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Check if command succeeded
        if result.returncode != 0:
            # No trading system running or other error
            return {
                "success": False,
                "error": "No trading system is currently running",
                "message": result.stderr.strip() if result.stderr else "Unknown error",
                "strategies": []
            }
        
        # Parse the CLI output to extract strategy information
        # The CLI output is text-based, so we need to parse it
        output_lines = result.stdout.strip().split('\n')
        
        # Look for strategy information in the output
        strategies = []
        current_strategy = None
        
        for line in output_lines:
            line = line.strip()
            
            # Skip empty lines and headers
            if not line or line.startswith('📋') or line.startswith('=') or line.startswith('🔗') or line.startswith('📊') or line.startswith('✅') or line.startswith('🎯') or line.startswith('💰') or line.startswith('🔧') or line.startswith('INFO:'):
                continue
            
            # Strategy entry starts with an emoji indicator
            if line.startswith('🟢') or line.startswith('⏸️') or line.startswith('🔴') or line.startswith('🟡') or line.startswith('⚪'):
                # New strategy found
                if current_strategy:
                    strategies.append(current_strategy)
                
                # Extract strategy name (after the emoji and space)
                strategy_name = line.split(' ', 1)[1] if ' ' in line else line[2:]
                current_strategy = {
                    "id": len(strategies) + 1,
                    "name": strategy_name,
                    "file": "unknown",
                    "symbols": [],
                    "status": "unknown",
                    "pnl": 0.0,
                    "pnlPercent": 0.0,
                    "trades": 0,
                    "winRate": 0.0,
                    "lastUpdate": "unknown",
                    "allocation": 0.0
                }
                
                # Determine status from emoji
                if line.startswith('🟢'):
                    current_strategy["status"] = "running"
                elif line.startswith('⏸️'):
                    current_strategy["status"] = "paused"
                elif line.startswith('🔴'):
                    current_strategy["status"] = "error"
                elif line.startswith('🟡'):
                    current_strategy["status"] = "initialized"
                
            elif current_strategy and ':' in line:
                # Parse strategy details
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                if key == "Status":
                    current_strategy["status"] = value.lower()
                elif key == "Allocation":
                    try:
                        # Convert percentage to decimal (e.g., "40%" -> 0.4)
                        allocation_str = value.replace('%', '')
                        current_strategy["allocation"] = float(allocation_str) / 100
                    except ValueError:
                        current_strategy["allocation"] = 0.0
                elif key == "Symbols":
                    current_strategy["symbols"] = [s.strip() for s in value.split(',')]
                elif key == "Path":
                    current_strategy["file"] = value
        
        # Add the last strategy if exists
        if current_strategy:
            strategies.append(current_strategy)
        
        return {
            "success": True,
            "strategies": strategies,
            "total": len(strategies)
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Command timeout",
            "message": "CLI command took too long to respond",
            "strategies": []
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "CLI not found",
            "message": "Could not find stratequeue CLI command",
            "strategies": []
        }
    except Exception as e:
        return {
            "success": False,
            "error": "Unexpected error",
            "message": str(e),
            "strategies": []
        }


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
        process = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", "3000"],
            cwd=frontend_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a moment for the server to start
        time.sleep(3)
        
        if process.poll() is None:  # Process is still running
            print("✅ Next.js development server started on port 3000")
            return process
        else:
            print("❌ Failed to start Next.js development server")
            return None
            
    except Exception as e:
        print(f"❌ Error starting Next.js server: {e}")
        return None


# FastAPI app for API endpoints
app = FastAPI(title="Stratequeue Web UI", version="0.0.1")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "message": "Stratequeue Web UI is running"}


@app.get("/api/status")
async def get_status():
    """Get the current system status."""
    return {
        "webui_running": True,
        "frontend_connected": True,
        "version": "0.0.1"
    }


@app.get("/api/strategies")
async def get_strategies():
    """Get live strategies from the CLI command."""
    try:
        result = get_strategies_from_cli()
        
        if not result["success"]:
            # Return error but don't raise HTTP exception for better UX
            return {
                "success": False,
                "error": result["error"],
                "message": result["message"],
                "strategies": [],
                "fallback_available": True  # Frontend can show a message about starting system
            }
        
        return {
            "success": True,
            "strategies": result["strategies"],
            "total": result["total"],
            "last_updated": time.time()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": "Server error",
            "message": f"Failed to fetch strategies: {str(e)}",
            "strategies": []
        }


def start_webui_server(port: int = 8080, open_browser: bool = True):
    """
    Start the Stratequeue Web UI server.
    
    Args:
        port: Port to run the server on (default: 8080)
        open_browser: Whether to automatically open the browser (default: True)
    """
    print("🚀 Starting Stratequeue Web UI...")
    print(f"📂 Frontend path: {get_frontend_path()}")
    
    # Start the Next.js development server
    next_process = start_next_dev_server()
    
    if not next_process:
        print("❌ Failed to start frontend server")
        return
    
    try:
        # Start the FastAPI server for API endpoints
        print(f"🌐 Starting API server on port {port}...")
        
        if open_browser:
            # Open browser after a short delay
            def open_browser_delayed():
                time.sleep(2)
                webbrowser.open(f"http://localhost:3000")
            
            threading.Thread(target=open_browser_delayed, daemon=True).start()
        
        print("✅ Stratequeue Web UI is running!")
        print(f"🌐 Frontend: http://localhost:3000")
        print(f"🔌 API: http://localhost:{port}")
        print("📝 Press Ctrl+C to stop")
        
        # Run the FastAPI server
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=port,
            log_level="info",
            access_log=False
        )
        
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