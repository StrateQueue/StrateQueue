#!/usr/bin/env python3

"""
Stratequeue Web UI Server

This module starts the Next.js frontend for the StrateQueue Web UI.
It communicates directly with the StrateQueue daemon on port 8400.
"""

import subprocess
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path


def tee_subprocess_output(process, log_file_path):
    """
    Reads a process's stdout line by line, printing each line to the console
    and writing it to a log file.
    """
    try:
        with open(log_file_path, "a") as log_file:
            log_file.write(f"--- Log started at {datetime.now().isoformat()} ---\n")
            for line in iter(process.stdout.readline, ""):
                print(line, end="")  # Print to console
                log_file.write(line)  # Write to log file
    except Exception as e:
        print(f"Error in logging thread: {e}")
    finally:
        process.stdout.close()


def get_frontend_path() -> Path:
    """Get the path to the frontend directory."""
    return Path(__file__).parent / "frontend"


def open_browser_after_delay(url: str, delay: int = 2):
    """Open a web browser after a specified delay."""

    def _open():
        time.sleep(delay)
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()


def start_webui_server(open_browser: bool = True):
    """
    Start the Stratequeue Next.js Web UI server.

    Args:
        open_browser: Whether to automatically open the browser.
    """
    frontend_path = get_frontend_path()

    if not (frontend_path / "node_modules").exists():
        print("❌ Frontend dependencies are not installed.")
        print("💡 Please run 'npm install' in the frontend directory:")
        print(f"   cd {frontend_path}")
        print("   npm install")
        return

    print("🚀 Starting Stratequeue Web UI...")
    print("🌐 URL: http://localhost:3000")
    print("📝 Press Ctrl+C to stop the server.")

    if open_browser:
        open_browser_after_delay("http://localhost:3000")

    # Create logs directory if it doesn't exist
    log_dir = Path.home() / ".stratequeue" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Generate a timestamped log file name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_path = log_dir / f"webui_{timestamp}.log"

    print(f"📝 Frontend logs will be written to: {log_file_path}")

    process = None
    try:
        # Start the Next.js dev server as a subprocess
        process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=frontend_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        # Create a thread to tee the output to console and log file
        log_thread = threading.Thread(
            target=tee_subprocess_output, args=(process, log_file_path), daemon=True
        )
        log_thread.start()

        # Wait for the process to complete (it will run until Ctrl+C)
        process.wait()

    except FileNotFoundError:
        print("❌ 'npm' command not found. Please ensure Node.js and npm are installed.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Frontend server failed to start or exited with an error: {e}")
    except KeyboardInterrupt:
        print("\n✅ Web UI stopped gracefully.")
    finally:
        if process and process.poll() is None:
            print("🛑 Stopping frontend server...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        print("🛑 Server has been shut down.")


if __name__ == "__main__":
    start_webui_server()
