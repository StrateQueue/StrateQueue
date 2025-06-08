from __future__ import annotations

import argparse
import logging
import os
import subprocess
import time
import requests
from pathlib import Path

from .base_command import BaseCommand

logger = logging.getLogger(__name__)


class WebUICommand(BaseCommand):
    """Launch the StrateQueue Web UI (dashboard) in development mode."""

    @property
    def name(self) -> str:  # noqa: D401, D403
        return "webui"

    @property
    def description(self) -> str:  # noqa: D401
        return "Start the StrateQueue Web UI (dashboard) using `npm run dev`."

    @property
    def aliases(self) -> list[str]:  # noqa: D401
        # Provide additional, more user-friendly aliases.
        return ["ui", "dashboard"]

    # ---------------------------------------------------------------------
    # Parser / Argument handling
    # ---------------------------------------------------------------------
    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:  # noqa: D401
        parser.description = (
            "Launches the Web UI dev server (vite) so you can interact with "
            "StrateQueue in the browser. If this is the first time you run "
            "the command, the necessary npm dependencies will automatically "
            "be installed."
        )
        parser.add_argument(
            "--port",
            "-p",
            default=5173,
            type=int,
            help="Port number for the dev server (default: 5173)",
        )
        return parser

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def execute(self, args: argparse.Namespace) -> int:  # noqa: D401
        """Run `npm run dev` inside the *webui* directory.

        If *node_modules* are missing, `npm install` will be executed first so
        the user does not have to worry about doing that manually.
        """
        project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        webui_dir = project_root / "webui"

        if not webui_dir.exists():
            self.logger.error("WebUI directory not found at %s", webui_dir)
            print(
                f"❌ WebUI directory was not found at {webui_dir}. Did you forget to initialise the frontend?"
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

        # Launch the dev server ------------------------------------------------------------------
        env = os.environ.copy()
        env["PORT"] = str(args.port)

        print("🚀 Launching StrateQueue Web UI at http://localhost:" + str(args.port))
        print(f"🔗 API backend available at http://localhost:{daemon_port}")
        # Pass the port through to vite so it binds to the correct port.
        process = subprocess.run(["npm", "run", "dev", "--", "--port", str(args.port)], cwd=webui_dir, env=env)
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