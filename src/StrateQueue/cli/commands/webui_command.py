from __future__ import annotations

import argparse
import logging
import os
import subprocess
import time
import requests
import http.server
import socketserver
import threading
from pathlib import Path

from .base_command import BaseCommand

logger = logging.getLogger(__name__)


class WebUICommand(BaseCommand):
    """Launch the StrateQueue Web UI (dashboard)."""

    @property
    def name(self) -> str:  # noqa: D401, D403
        return "webui"

    @property
    def description(self) -> str:  # noqa: D401
        return "Start the StrateQueue Web UI (dashboard)."

    @property
    def aliases(self) -> list[str]:  # noqa: D401
        # Provide additional, more user-friendly aliases.
        return ["ui", "dashboard"]

    # ---------------------------------------------------------------------
    # Parser / Argument handling
    # ---------------------------------------------------------------------
    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:  # noqa: D401
        parser.description = (
            "Launches the StrateQueue Web UI. By default serves the built production "
            "version. Use --dev for development mode with hot reload."
        )
        parser.add_argument(
            "--dev",
            action="store_true",
            help="Run in development mode with hot reload (requires npm)",
        )
        parser.add_argument(
            "--port",
            "-p",
            default=5173,
            type=int,
            help="Port number for the web server (default: 5173)",
        )
        return parser

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def execute(self, args: argparse.Namespace) -> int:  # noqa: D401
        """Launch the Web UI in production or development mode."""
        
        # Check and start daemon if needed --------------------------------------------------------
        daemon_port = 8400
        if not self._check_daemon_running(daemon_port):
            print("🔍 No daemon detected, starting background daemon...")
            daemon_process = self._start_daemon(daemon_port)
            if not daemon_process:
                print("⚠️  Warning: Failed to start daemon. Some Web UI features may not work.")
                print("💡 You can manually start the daemon with: stratequeue daemon")
        else:
            print(f"✅ Daemon already running on port {daemon_port}")

        if args.dev:
            return self._run_development_mode(args.port, daemon_port)
        else:
            return self._run_production_mode(args.port, daemon_port)

    def _run_production_mode(self, port: int, daemon_port: int) -> int:
        """Serve the built static files."""
        # Find the webui_static directory in the package
        package_root = Path(__file__).resolve().parent.parent.parent
        webui_static_dir = package_root / "webui_static"
        
        if not webui_static_dir.exists():
            self.logger.error("WebUI static directory not found at %s", webui_static_dir)
            print(
                f"❌ WebUI static directory was not found at {webui_static_dir}. "
                "The frontend may not have been built during package installation."
            )
            return 1

        print(f"🚀 Launching StrateQueue Web UI (production) at http://localhost:{port}")
        print(f"🔗 API backend available at http://localhost:{daemon_port}")
        
        # Change to the static directory and start HTTP server
        os.chdir(webui_static_dir)
        
        try:
            with socketserver.TCPServer(("", port), http.server.SimpleHTTPRequestHandler) as httpd:
                print(f"📁 Serving static files from {webui_static_dir}")
                print(f"🌐 Web UI available at http://localhost:{port}")
                print("Press Ctrl+C to stop the server")
                httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Web UI server stopped")
            return 0
        except OSError as e:
            if e.errno == 48:  # Address already in use
                print(f"❌ Port {port} is already in use. Try a different port with --port")
            else:
                print(f"❌ Failed to start server: {e}")
            return 1

    def _run_development_mode(self, port: int, daemon_port: int) -> int:
        """Run the development server with npm."""
        project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        webui_dir = project_root / "webui"

        if not webui_dir.exists():
            self.logger.error("WebUI directory not found at %s", webui_dir)
            print(
                f"❌ WebUI directory was not found at {webui_dir}. "
                "Development mode requires the source code to be available."
            )
            return 1

        # Install dependencies on first run ------------------------------------------------------
        node_modules_dir = webui_dir / "node_modules"
        if not node_modules_dir.exists():
            print("📦 Installing WebUI dependencies (npm install – this might take a minute)…")
            result = subprocess.run(["npm", "install"], cwd=webui_dir)
            if result.returncode != 0:
                self.logger.error("npm install failed with exit code %s", result.returncode)
                return result.returncode

        # Launch the dev server ------------------------------------------------------------------
        env = os.environ.copy()
        env["PORT"] = str(port)

        print(f"🚀 Launching StrateQueue Web UI (development) at http://localhost:{port}")
        print(f"🔗 API backend available at http://localhost:{daemon_port}")
        print("🔄 Development mode with hot reload enabled")
        
        # Pass the port through to vite so it binds to the correct port.
        process = subprocess.run(["npm", "run", "dev", "--", "--port", str(port)], cwd=webui_dir, env=env)
        return process.returncode

    def _check_daemon_running(self, port: int = 8400) -> bool:
        """Check if daemon is already running on the specified port."""
        try:
            response = requests.get(f"http://localhost:{port}/health", timeout=2)
            return response.status_code == 200
        except (requests.exceptions.RequestException, requests.exceptions.ConnectionError):
            return False

    def _start_daemon(self, port: int = 8400) -> subprocess.Popen | None:
        """Start the daemon in the background."""
        try:
            print(f"🔧 Starting StrateQueue daemon on port {port}...")
            # Start daemon in background (detached process)
            daemon_process = subprocess.Popen(
                ["stratequeue", "daemon", "--port", str(port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True  # Detach from parent process
            )
            
            # Wait a moment for daemon to start
            max_wait = 10  # seconds
            waited = 0
            while waited < max_wait:
                if self._check_daemon_running(port):
                    print(f"✅ Daemon started successfully on port {port}")
                    return daemon_process
                time.sleep(1)
                waited += 1

            # If we get here the daemon never came up
            print(f"❌ Failed to start daemon on port {port} after {max_wait}s")
            daemon_process.terminate()
            return None
                
        except Exception as e:
            self.logger.error(f"Failed to start daemon: {e}")
            print(f"❌ Failed to start daemon: {e}")
            return None 