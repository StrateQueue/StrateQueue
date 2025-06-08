"""
Daemon Command

Command for running the StrateQueue REST daemon server.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from .base_command import BaseCommand


class DaemonCommand(BaseCommand):
    """
    Daemon command implementation
    
    Starts the StrateQueue REST API daemon server using uvicorn.
    """

    @property
    def name(self) -> str:
        return "daemon"

    @property
    def description(self) -> str:
        return "Run the StrateQueue REST daemon server"

    @property
    def aliases(self) -> list[str]:
        return ["server", "api"]

    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Configure daemon command arguments"""
        parser.add_argument(
            "--port",
            "-p",
            type=int,
            default=8400,
            help="Port to bind the server to (default: 8400)"
        )
        parser.add_argument(
            "--host",
            default="0.0.0.0",
            help="Host to bind the server to (default: 0.0.0.0)"
        )
        parser.add_argument(
            "--reload",
            action="store_true",
            help="Enable auto-reload for development"
        )
        return parser

    def execute(self, args: argparse.Namespace) -> int:
        """Execute daemon command"""
        print(f"🚀 Starting StrateQueue daemon on {args.host}:{args.port}")
        
        # Build uvicorn command
        cmd = [
            sys.executable, "-m", "uvicorn",
            "StrateQueue.api.daemon:app",
            "--host", args.host,
            "--port", str(args.port)
        ]
        
        if args.reload:
            cmd.append("--reload")
            
        # Run uvicorn - this will block until Ctrl+C
        try:
            return subprocess.call(cmd)
        except KeyboardInterrupt:
            print("\n🛑 Daemon stopped")
            return 0 