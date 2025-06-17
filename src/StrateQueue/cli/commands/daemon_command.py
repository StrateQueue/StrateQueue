"""Daemon Command

Command for controlling the StrateQueue daemon process.
"""

import argparse
import logging
from argparse import Namespace
from typing import List, Dict, Any, Tuple

from .base_command import BaseCommand

logger = logging.getLogger(__name__)

# Constants
DEFAULT_DAEMON_HOST = "127.0.0.1"
DEFAULT_DAEMON_PORT = 8400
DEFAULT_LOG_FILE = "~/.stratequeue/daemon.log"
DAEMON_START_TIMEOUT = 2  # seconds
DAEMON_SHUTDOWN_TIMEOUT = 10  # seconds
DAEMON_REQUEST_TIMEOUT = 30  # seconds


class DaemonCommand(BaseCommand):
    """Daemon control command"""
    
    def __init__(self):
        super().__init__()
    
    @property
    def name(self) -> str:
        """Command name"""
        return "daemon"
    
    @property
    def description(self) -> str:
        """Command description"""
        return "Control the StrateQueue daemon process"
    
    @property
    def aliases(self) -> List[str]:
        """Command aliases"""
        return []
    
    def _call_daemon_api(self, endpoint: str, method: str = "GET", payload: Dict[str, Any] = None, 
                        timeout: int = DAEMON_REQUEST_TIMEOUT, port: int = DEFAULT_DAEMON_PORT) -> Tuple[bool, Dict[str, Any]]:
        """
        Consolidated method to call daemon API endpoints
        
        Args:
            endpoint: API endpoint (e.g. "/status", "/strategy/deploy")
            method: HTTP method ("GET" or "POST")
            payload: Request payload for POST requests
            timeout: Request timeout in seconds
            port: Daemon port
            
        Returns:
            Tuple of (success: bool, response_data: dict)
        """
        try:
            import requests
            
            url = f"http://{DEFAULT_DAEMON_HOST}:{port}{endpoint}"
            
            if method.upper() == "POST":
                response = requests.post(url, json=payload or {}, timeout=timeout)
            else:
                response = requests.get(url, timeout=timeout)
            
            if response.ok:
                try:
                    return True, response.json()
                except ValueError:
                    return True, {"message": response.text}
            else:
                try:
                    error_data = response.json()
                    return False, {"error": error_data.get("detail", f"HTTP {response.status_code}")}
                except ValueError:
                    return False, {"error": f"HTTP {response.status_code}: {response.text}"}
                    
        except ImportError:
            return False, {"error": "Daemon control requires 'requests' package. Install with: pip3.11 install requests"}
        except Exception as e:
            return False, {"error": str(e)}
    
    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Setup the argument parser for daemon command"""
        
        subparsers = parser.add_subparsers(
            dest='daemon_action',
            help='Daemon actions',
            metavar='action'
        )
        
        # Start daemon
        start_parser = subparsers.add_parser(
            'start',
            help='Start the daemon process'
        )
        start_parser.add_argument(
            '--bind',
            default=DEFAULT_DAEMON_HOST,
            help=f'IP address to bind to (default: {DEFAULT_DAEMON_HOST})'
        )
        start_parser.add_argument(
            '--port',
            type=int,
            default=DEFAULT_DAEMON_PORT,
            help=f'Port to listen on (default: {DEFAULT_DAEMON_PORT})'
        )
        start_parser.add_argument(
            '--log-file',
            default=DEFAULT_LOG_FILE,
            help=f'Log file path (default: {DEFAULT_LOG_FILE})'
        )
        
        # Stop daemon
        stop_parser = subparsers.add_parser(
            'stop',
            help='Stop the daemon process'
        )
        
        # Status
        status_parser = subparsers.add_parser(
            'status',
            help='Get daemon status'
        )
        
        # Strategy control subcommands
        strategy_parser = subparsers.add_parser(
            'strategy',
            help='Control strategies in the running daemon'
        )
        strategy_subparsers = strategy_parser.add_subparsers(
            dest='strategy_action',
            help='Strategy actions',
            metavar='strategy_action'
        )
        
        # Deploy strategy
        deploy_strategy_parser = strategy_subparsers.add_parser(
            'deploy',
            help='Deploy a new strategy to the running daemon'
        )
        deploy_strategy_parser.add_argument(
            '--strategy',
            required=True,
            help='Path to strategy file'
        )
        deploy_strategy_parser.add_argument(
            '--symbol',
            required=True,
            help='Trading symbol'
        )
        deploy_strategy_parser.add_argument(
            '--strategy-id',
            help='Custom strategy identifier'
        )
        deploy_strategy_parser.add_argument(
            '--allocation',
            type=float,
            default=0.1,
            help='Allocation percentage (default: 0.1)'
        )
        
        # Pause strategy
        pause_strategy_parser = strategy_subparsers.add_parser(
            'pause',
            help='Pause a running strategy'
        )
        pause_strategy_parser.add_argument(
            'strategy_id',
            help='Strategy identifier to pause'
        )
        
        # Resume strategy
        resume_strategy_parser = strategy_subparsers.add_parser(
            'resume',
            help='Resume a paused strategy'
        )
        resume_strategy_parser.add_argument(
            'strategy_id',
            help='Strategy identifier to resume'
        )
        
        # Undeploy strategy
        undeploy_strategy_parser = strategy_subparsers.add_parser(
            'undeploy',
            help='Remove a strategy from the daemon'
        )
        undeploy_strategy_parser.add_argument(
            'strategy_id',
            help='Strategy identifier to undeploy'
        )
        
        # Rebalance portfolio
        rebalance_parser = strategy_subparsers.add_parser(
            'rebalance',
            help='Rebalance strategy allocations'
        )
        rebalance_parser.add_argument(
            'allocations',
            help='Strategy allocations as JSON string, e.g. \'{"strategy1": 0.6, "strategy2": 0.4}\''
        )
        
        return parser
    
    def execute(self, args: Namespace) -> int:
        """
        Execute the daemon command
        
        Args:
            args: Parsed command arguments
            
        Returns:
            Exit code (0 for success, 1 for error)
        """
        action = getattr(args, 'daemon_action', None)
        
        if action == 'start':
            return self._start_daemon(args)
        elif action == 'stop':
            return self._stop_daemon(args)
        elif action == 'status':
            return self._daemon_status(args)
        elif action == 'strategy':
            return self._handle_strategy_command(args)
        else:
            print("❌ No action specified")
            print("💡 Available actions: start, stop, status, strategy")
            return 1
    
    def _start_daemon(self, args: Namespace) -> int:
        """Start the daemon process using the shared function"""
        from ...daemon import start_daemon_process
        
        bind = getattr(args, 'bind', DEFAULT_DAEMON_HOST)
        port = getattr(args, 'port', DEFAULT_DAEMON_PORT)
        log_file = getattr(args, 'log_file', DEFAULT_LOG_FILE)

        success, message = start_daemon_process(
            bind=bind,
            port=port,
            log_file=log_file,
            verbose=True  # Always show output for direct start command
        )

        if not success:
            print(f"❌ {message}")
            return 1
        
        return 0
    
    def _stop_daemon(self, args: Namespace) -> int:
        """Stop the daemon process"""
        print("🛑 Stopping daemon...")
        if not self._is_daemon_running():
            print("✅ Daemon is not running")
            return 0
        
        success, response = self._call_daemon_api(endpoint="/shutdown", method="POST")
        
        if success:
            print("✅ Daemon shutdown initiated")
        else:
            print(f"❌ Failed to stop daemon: {response.get('error', 'Unknown error')}")
            print("💡 It might not be running or is unresponsive.")
            return 1
        
        # Wait for daemon to stop
        import time
        
        for _ in range(DAEMON_SHUTDOWN_TIMEOUT):
            if not self._is_daemon_running():
                print("✅ Daemon stopped successfully")
                return 0
            time.sleep(1)
        
        print("❌ Daemon did not stop within the timeout period")
        return 1
    
    def _daemon_status(self, args: Namespace) -> int:
        """Get daemon status"""
        if not self._is_daemon_running():
            print("❌ Daemon is not running")
            return 1
        
        success, response = self._call_daemon_api("/status", timeout=3)
        if success:
            print("✅ Daemon is running")
            print(f"📊 Trading system running: {response.get('trading_system_running', False)}")
            
            strategies = response.get('strategies', [])
            if strategies:
                print(f"📈 Active strategies: {len(strategies)}")
                for strategy in strategies:
                    print(f"  - {strategy}")
            else:
                print("📈 No active strategies")
            
            status_data = response.get('status', {})
            print(f"    - Uptime: {status_data.get('uptime', 'N/A')}")
            
            return 0
        else:
            error_msg = response.get("error", "Unknown error")
            print(f"❌ Failed to get daemon status: {error_msg}")
            return 1
    
    def _is_daemon_running(self, port: int = DEFAULT_DAEMON_PORT) -> bool:
        """Check if daemon is running"""
        from ...daemon import is_daemon_running
        return is_daemon_running(port=port)
    
    def _handle_strategy_command(self, args: Namespace) -> int:
        """Handle strategy control commands"""
        strategy_action = getattr(args, 'strategy_action', None)
        
        if strategy_action == 'deploy':
            return self._deploy_strategy(args)
        elif strategy_action == 'pause':
            return self._pause_strategy(args)
        elif strategy_action == 'resume':
            return self._resume_strategy(args)
        elif strategy_action == 'undeploy':
            return self._undeploy_strategy(args)
        elif strategy_action == 'rebalance':
            return self._rebalance_portfolio(args)
        else:
            print("❌ No strategy action specified")
            print("💡 Available strategy actions: deploy, pause, resume, undeploy, rebalance")
            return 1
    
    def _deploy_strategy(self, args: Namespace) -> int:
        """Deploy a strategy to the running daemon"""
        if not self._is_daemon_running():
            print("❌ Daemon is not running")
            print("💡 Start daemon with: stratequeue daemon start")
            return 1
        
        strategy_path = args.strategy
        symbol = args.symbol
        strategy_id = getattr(args, 'strategy_id', None)
        allocation = getattr(args, 'allocation', 0.1)
        
        payload = {
            "strategy": strategy_path,
            "symbol": symbol,
            "allocation": allocation
        }
        
        if strategy_id:
            payload["strategy_id"] = strategy_id
        
        print(f"🚀 Deploying strategy {strategy_path} on {symbol}")
        
        success, response = self._call_daemon_api("/strategy/deploy", method="POST", payload=payload)
        if success:
            message = response.get('message', 'Strategy deployed successfully')
            print(f"✅ {message}")
            return 0
        else:
            error_msg = response.get("error", "Unknown error")
            print(f"❌ Failed to deploy strategy: {error_msg}")
            return 1
    
    def _pause_strategy(self, args: Namespace) -> int:
        """Pause a strategy"""
        if not self._is_daemon_running():
            print("❌ Daemon is not running")
            return 1
        
        strategy_id = args.strategy_id
        print(f"⏸️  Pausing strategy {strategy_id}")
        
        success, response = self._call_daemon_api("/strategy/pause", method="POST", 
                                                 payload={"strategy_id": strategy_id}, timeout=10)
        if success:
            message = response.get('message', 'Strategy paused successfully')
            print(f"✅ {message}")
            return 0
        else:
            error_msg = response.get("error", "Unknown error")
            print(f"❌ Failed to pause strategy: {error_msg}")
            return 1
    
    def _resume_strategy(self, args: Namespace) -> int:
        """Resume a strategy"""
        if not self._is_daemon_running():
            print("❌ Daemon is not running")
            return 1
        
        strategy_id = args.strategy_id
        print(f"▶️  Resuming strategy {strategy_id}")
        
        success, response = self._call_daemon_api("/strategy/resume", method="POST", 
                                                 payload={"strategy_id": strategy_id}, timeout=10)
        if success:
            message = response.get('message', 'Strategy resumed successfully')
            print(f"✅ {message}")
            return 0
        else:
            error_msg = response.get("error", "Unknown error")
            print(f"❌ Failed to resume strategy: {error_msg}")
            return 1
    
    def _undeploy_strategy(self, args: Namespace) -> int:
        """Undeploy a strategy"""
        if not self._is_daemon_running():
            print("❌ Daemon is not running")
            return 1
        
        strategy_id = args.strategy_id
        print(f"🗑️  Undeploying strategy {strategy_id}")
        
        success, response = self._call_daemon_api("/strategy/undeploy", method="POST", 
                                                 payload={"strategy_id": strategy_id}, timeout=10)
        if success:
            message = response.get('message', 'Strategy undeployed successfully')
            print(f"✅ {message}")
            return 0
        else:
            error_msg = response.get("error", "Unknown error")
            print(f"❌ Failed to undeploy strategy: {error_msg}")
            return 1

    def _rebalance_portfolio(self, args: Namespace) -> int:
        """Rebalance portfolio allocations"""
        if not self._is_daemon_running():
            print("❌ Daemon is not running")
            return 1
        
        # Parse JSON allocations
        try:
            import json
            allocations_dict = json.loads(args.allocations)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"❌ Invalid JSON format: {e}")
            print("💡 Example: '{\"strategy1\": 0.6, \"strategy2\": 0.4}'")
            return 1
        
        print(f"🔄 Rebalancing portfolio with allocations: {allocations_dict}")
        
        success, response = self._call_daemon_api("/portfolio/rebalance", method="POST", 
                                                 payload={"allocations": allocations_dict})
        if success:
            message = response.get('message', 'Portfolio rebalanced successfully')
            print(f"✅ {message}")
            return 0
        else:
            error_msg = response.get("error", "Unknown error")
            print(f"❌ Failed to rebalance portfolio: {error_msg}")
            return 1 