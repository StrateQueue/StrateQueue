"""WebUI Command

Command for starting the web interface with Next.js frontend that communicates with the daemon.
"""

import argparse
from argparse import Namespace

from ...daemon import start_daemon_process
from .base_command import BaseCommand


class WebuiCommand(BaseCommand):
    """WebUI command for starting the web interface"""

    @property
    def name(self) -> str:
        """Command name"""
        return "webui"

    @property
    def description(self) -> str:
        """Command description"""
        return "Start the web interface"

    @property
    def aliases(self) -> list[str]:
        """Command aliases"""
        return ["web", "ui"]

    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Setup the argument parser for webui command"""

        parser.add_argument(
            "--dev",
            action="store_true",
            help="Start in development mode (disables auto-opening browser)",
        )

        parser.add_argument(
            "--no-browser", action="store_true", help="Don't automatically open browser"
        )

        parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

        return parser

    def execute(self, args: Namespace) -> int:
        """
        Execute the webui command

        Args:
            args: Parsed command arguments

        Returns:
            Exit code (0 for success, 1 for error)
        """
        # First, ensure the daemon is running
        print("🔍 Ensuring the trading daemon is running...")
        success, message = start_daemon_process(verbose=args.verbose)

        if not success:
            print(f"\n❌ Could not start the trading daemon: {message}")
            print("   The Web UI requires the daemon to be active to function correctly.")
            return 1

        print("✅ Daemon is running. Starting Web UI...\n")

        try:
            # Try to import the webui module
            from ...webui import start_webui_server

            print("🚀 Starting Stratequeue Web UI...")
            print("")
            print("🎯 Features:")
            print("  • Strategy deployment and monitoring")
            print("  • Real-time performance tracking")
            print("  • Portfolio management")
            print("  • Live trading controls")
            print("")

            # Determine whether to open browser
            open_browser = not (args.dev or args.no_browser)

            # Start the web UI server (no port needed, just Next.js frontend)
            start_webui_server(open_browser=open_browser)

            return 0

        except ImportError as e:
            self._show_dependency_error(e)
            return 1
        except Exception as e:
            print(f"❌ Failed to start Web UI: {e}")
            print("")
            print("💡 Try running with --verbose for more details")
            return 1

    def _show_dependency_error(self, error: Exception) -> None:
        """Show helpful error message when dependencies are missing"""
        print("❌ Web UI dependencies not available!")
        print("")
        print("🔧 To enable the Web UI, make sure Next.js dependencies are installed:")
        print("")
        print("  # Navigate to frontend directory and install dependencies")
        print("  cd src/StrateQueue/webui/frontend")
        print("  npm install")
        print("")
        print("🏗️  For daemon functionality, ensure daemon is running:")
        print("  stratequeue daemon start")
        print("")
        print("💡 After setup, try again:")
        print("  stratequeue webui")
        print("")
        print(f"📝 Error details: {error}")
