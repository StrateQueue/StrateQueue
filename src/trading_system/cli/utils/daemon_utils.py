"""Daemon Utilities

Utilities for handling daemon mode deployment including background execution,
PID file management, and daemon system storage for hotswap functionality.
"""

import os
import time
import pickle
import threading
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from argparse import Namespace

from .deploy_utils import parse_symbols

logger = logging.getLogger(__name__)


class DaemonManager:
    """Manages daemon mode execution and state"""
    
    def __init__(self, pid_file: Optional[str] = None):
        """
        Initialize daemon manager
        
        Args:
            pid_file: Path to PID file (defaults to .stratequeue.pid)
        """
        self.pid_file = pid_file or ".stratequeue.pid"
        self.daemon_file = self.pid_file.replace('.pid', '.daemon')
        self._daemon_thread = None
    
    def start_daemon(self, args: Namespace) -> bool:
        """
        Start the trading system in daemon mode
        
        Args:
            args: Parsed command arguments
            
        Returns:
            True if daemon started successfully
        """
        print("🔄 Starting Stratequeue in daemon mode...")
        print("💡 You can now use 'stratequeue hotswap' commands in this terminal")
        print("")
        
        try:
            # Create daemon thread
            self._daemon_thread = threading.Thread(
                target=self._run_daemon_thread, 
                args=(args,), 
                daemon=True
            )
            
            print(f"🚀 Launching trading system in background...")
            print(f"📋 PID file: {self.pid_file}")
            
            # Store PID (using current process PID for simplicity)
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
            
            # Start daemon thread
            self._daemon_thread.start()
            
            # Wait for daemon to initialize
            time.sleep(1)
            
            print(f"✅ System started (PID: {os.getpid()})")
            print("")
            print("🔥 Hot swap commands now available:")
            print("  stratequeue hotswap deploy --strategy new.py --strategy-id new --allocation 0.2")
            print("  stratequeue hotswap pause --strategy-id momentum")  
            print("  stratequeue hotswap list")
            print("")
            print("To stop: kill -TERM $(cat .stratequeue.pid)")
            
            # Keep main process alive for demonstration
            print("📡 Daemon running... (Press Ctrl+C to stop)")
            try:
                while self._daemon_thread.is_alive():
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n👋 Daemon stopped")
                self.cleanup()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start daemon: {e}")
            print(f"❌ Failed to start daemon: {e}")
            return False
    
    def _run_daemon_thread(self, args: Namespace) -> None:
        """Function to run in daemon thread"""
        args_copy = Namespace(**vars(args))
        args_copy.daemon = False  # Prevent recursion
        
        try:
            # Create a mock trading system for demonstration
            # In production, this would run the actual trading system
            self._run_mock_trading_system(args_copy)
            
        except Exception as e:
            logger.error(f"Daemon thread error: {e}")
            print(f"[DAEMON] Error: {e}")
        finally:
            self.cleanup()
    
    def _run_mock_trading_system(self, args: Namespace) -> None:
        """Run mock trading system for demonstration"""
        # Parse symbols
        symbols = parse_symbols(args.symbols)
        
        # Determine trading configuration
        enable_trading = not args.no_trading
        paper_trading = args.paper or (not args.live and not args.no_trading)
        
        # Create mock system info
        if hasattr(args, '_strategies') and len(args._strategies) > 1:
            # Multi-strategy system placeholder
            print(f"[DAEMON] Multi-strategy system with {len(args._strategies)} strategies")
            system = {
                'strategies': {
                    args._strategy_ids[i]: {
                        'state': 'active',
                        'allocation': float(args._allocations[i]),
                        'symbols': symbols
                    } for i in range(len(args._strategies))
                },
                'total_allocation': sum(float(a) for a in args._allocations)
            }
        else:
            # Single strategy system  
            strategy_id = os.path.basename(args._strategies[0]).replace('.py', '')
            print(f"[DAEMON] Single strategy system: {strategy_id}")
            system = {
                'strategies': {
                    strategy_id: {
                        'state': 'active', 
                        'allocation': float(args._allocations[0]) if args._allocations else 1.0,
                        'symbols': symbols
                    }
                },
                'total_allocation': float(args._allocations[0]) if args._allocations else 1.0
            }
        
        # Store daemon info for hotswap
        self.store_daemon_info(system)
        
        print(f"[DAEMON] System running for {args.duration} minutes...")
        
        # Simulate running for specified duration
        time.sleep(args.duration * 60)
        
        print(f"[DAEMON] System stopped after {args.duration} minutes")
    
    def store_daemon_info(self, system: Dict[str, Any]) -> None:
        """Store daemon info for hotswap commands"""
        daemon_info = {
            'pid': os.getpid(),
            'system': system,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            with open(self.daemon_file, 'wb') as f:
                pickle.dump(daemon_info, f)
            
            print(f"📋 Daemon info stored: {self.daemon_file}")
            print(f"🔥 Hot swap commands available while system runs")
            
        except Exception as e:
            logger.warning(f"Could not store daemon info: {e}")
    
    def load_daemon_info(self) -> Optional[Dict[str, Any]]:
        """Load daemon info for hotswap commands"""
        try:
            if not os.path.exists(self.daemon_file):
                return None
                
            with open(self.daemon_file, 'rb') as f:
                daemon_info = pickle.load(f)
            
            # Check if process is still running
            pid = daemon_info['pid']
            try:
                os.kill(pid, 0)  # Check if process exists
            except OSError:
                # Process is dead, clean up
                self.cleanup()
                return None
            
            return daemon_info
            
        except Exception as e:
            logger.warning(f"Could not load daemon info: {e}")
            return None
    
    def cleanup(self) -> None:
        """Clean up daemon files"""
        try:
            if os.path.exists(self.daemon_file):
                os.unlink(self.daemon_file)
            if os.path.exists(self.pid_file):
                os.unlink(self.pid_file)
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
    
    def is_running(self) -> bool:
        """Check if daemon is currently running"""
        if not os.path.exists(self.pid_file):
            return False
        
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process exists
            os.kill(pid, 0)
            return True
        except (OSError, ValueError):
            # Process is dead or PID file is invalid
            self.cleanup()
            return False


# Standalone functions for backward compatibility
def store_daemon_system(system: Any, pid_file_path: Optional[str] = None) -> None:
    """Store running system info for daemon mode (legacy function)"""
    manager = DaemonManager(pid_file_path)
    manager.store_daemon_info(system)


def load_daemon_system(pid_file_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Load running system info for hot swap commands (legacy function)"""
    manager = DaemonManager(pid_file_path)
    return manager.load_daemon_info() 