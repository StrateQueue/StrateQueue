"""WebUI Command

Command for starting the web interface with integrated Next.js frontend and FastAPI backend.
"""

import argparse
from argparse import Namespace
from typing import List

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
    def aliases(self) -> List[str]:
        """Command aliases"""
        return ["web", "ui"]
    
    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Setup the argument parser for webui command"""
        
        parser.add_argument(
            '--port', 
            type=int, 
            default=8080,
            help='Port to run the API server on (default: 8080)'
        )
        
        parser.add_argument(
            '--host', 
            default='localhost',
            help='Host to bind the API server to (default: localhost)'
        )
        
        parser.add_argument(
            '--dev', 
            action='store_true',
            help='Start in development mode (disables auto-opening browser)'
        )
        
        parser.add_argument(
            '--config-dir', 
            help='Directory to store web UI configurations'
        )
        
        parser.add_argument(
            '--no-browser',
            action='store_true',
            help='Don\'t automatically open browser'
        )
        
        parser.add_argument(
            '--verbose', 
            action='store_true',
            help='Enable verbose logging'
        )
        
        return parser
    
    def execute(self, args: Namespace) -> int:
        """
        Execute the webui command
        
        Args:
            args: Parsed command arguments
            
        Returns:
            Exit code (0 for success, 1 for error)
        """
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
            
            # Start the web UI server
            start_webui_server(
                port=args.port,
                open_browser=open_browser
            )
            
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
        print("🔧 To enable the Web UI, install the required dependencies:")
        print("")
        print("  # Install web UI dependencies")
        print("  pip3.10 install fastapi uvicorn")
        print("")
        print("  # Or install with all optional dependencies")
        print("  pip3.10 install stratequeue[all]")
        print("")
        print("🏗️  Frontend setup (if missing):")
        print("  cd src/trading_system/webui/frontend")
        print("  npm install")
        print("")
        print("💡 After installation, try again:")
        print("  stratequeue webui")
        print("")
        print(f"📝 Error details: {error}") 