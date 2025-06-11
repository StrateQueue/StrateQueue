"""Daemon Management Utilities

Handles PID files, daemon communication, and system state management
for hotswap operations.
"""

import os
import pickle
import signal
import time
import threading
from typing import Dict, Any, Optional, Tuple
from pathlib import Path


class DaemonManager:
    """Manages daemon processes and system state for hotswap operations"""
    
    def __init__(self, system_name: str = "trading_system"):
        """
        Initialize daemon manager
        
        Args:
            system_name: Name of the trading system
        """
        self.system_name = system_name
        self.pid_dir = Path.home() / ".stratequeue" / "pids"
        self.pid_dir.mkdir(parents=True, exist_ok=True)
    
    def get_pid_file_path(self, config_file: Optional[str] = None) -> Path:
        """
        Get PID file path for the system
        
        Args:
            config_file: Optional config file to identify specific system
            
        Returns:
            Path to PID file
        """
        if config_file:
            # Use config file name as part of PID file name
            config_name = Path(config_file).stem
            pid_file = f"{self.system_name}_{config_name}.pid"
        else:
            pid_file = f"{self.system_name}.pid"
        
        return self.pid_dir / pid_file
    
    def store_daemon_system(self, system: Any, pid_file_path: Optional[Path] = None) -> bool:
        """
        Store daemon system info to PID file
        
        Args:
            system: Trading system instance
            pid_file_path: Optional custom PID file path
            
        Returns:
            True if successful
        """
        try:
            if pid_file_path is None:
                pid_file_path = self.get_pid_file_path()
            
            # Create system info
            system_info = {
                'pid': os.getpid(),
                'system': system,
                'start_time': time.time(),
                'strategies': self._extract_strategy_info(system),
            }
            
            # Store to file
            with open(pid_file_path, 'wb') as f:
                pickle.dump(system_info, f)
            
            print(f"💾 Daemon info stored to {pid_file_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error storing daemon info: {e}")
            return False
    
    def load_daemon_system(self, pid_file_path: Optional[Path] = None, config_file: Optional[str] = None) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Load daemon system info from PID file
        
        Args:
            pid_file_path: Optional custom PID file path
            config_file: Optional config file to identify system
            
        Returns:
            Tuple of (success, system_info, error_message)
        """
        try:
            if pid_file_path is None:
                pid_file_path = self.get_pid_file_path(config_file)
            
            if not pid_file_path.exists():
                return False, None, f"No daemon found at {pid_file_path}"
            
            # Load system info
            with open(pid_file_path, 'rb') as f:
                system_info = pickle.load(f)
            
            # Check if process is still running
            pid = system_info.get('pid')
            if not self._is_process_running(pid):
                # Clean up stale PID file
                pid_file_path.unlink(missing_ok=True)
                return False, None, f"Daemon process {pid} is no longer running"
            
            return True, system_info, ""
            
        except Exception as e:
            return False, None, f"Error loading daemon info: {e}"
    
    def cleanup_daemon_files(self, pid_file_path: Optional[Path] = None, config_file: Optional[str] = None) -> bool:
        """
        Clean up daemon PID files
        
        Args:
            pid_file_path: Optional custom PID file path
            config_file: Optional config file to identify system
            
        Returns:
            True if successful
        """
        try:
            if pid_file_path is None:
                pid_file_path = self.get_pid_file_path(config_file)
            
            if pid_file_path.exists():
                pid_file_path.unlink()
                print(f"🧹 Cleaned up daemon file {pid_file_path}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error cleaning up daemon files: {e}")
            return False
    
    def list_running_daemons(self) -> Dict[str, Dict[str, Any]]:
        """
        List all running daemon processes
        
        Returns:
            Dictionary mapping PID file names to system info
        """
        running_daemons = {}
        
        for pid_file in self.pid_dir.glob("*.pid"):
            success, system_info, error = self.load_daemon_system(pid_file)
            if success and system_info:
                running_daemons[pid_file.name] = system_info
        
        return running_daemons
    
    def _extract_strategy_info(self, system: Any) -> Dict[str, Any]:
        """
        Extract strategy information from trading system
        
        Args:
            system: Trading system instance
            
        Returns:
            Dictionary of strategy information
        """
        try:
            strategies = {}
            
            # Try to get strategies from system
            if hasattr(system, 'strategies'):
                for strategy_id, strategy in system.strategies.items():
                    strategies[strategy_id] = {
                        'class': strategy.__class__.__name__,
                        'status': getattr(strategy, 'status', 'active'),
                        'allocation': getattr(strategy, 'allocation', None),
                        'symbols': getattr(strategy, 'symbols', []),
                    }
            
            return strategies
            
        except Exception as e:
            print(f"⚠️  Warning: Could not extract strategy info: {e}")
            return {}
    
    def _is_process_running(self, pid: int) -> bool:
        """
        Check if a process is still running
        
        Args:
            pid: Process ID to check
            
        Returns:
            True if process is running
        """
        try:
            # Send signal 0 to check if process exists
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
    
    def send_signal_to_daemon(self, signal_type: int = signal.SIGTERM, 
                             pid_file_path: Optional[Path] = None,
                             config_file: Optional[str] = None) -> Tuple[bool, str]:
        """
        Send signal to daemon process
        
        Args:
            signal_type: Signal to send (default: SIGTERM)
            pid_file_path: Optional custom PID file path
            config_file: Optional config file to identify system
            
        Returns:
            Tuple of (success, message)
        """
        try:
            success, system_info, error = self.load_daemon_system(pid_file_path, config_file)
            if not success:
                return False, error
            
            pid = system_info['pid']
            os.kill(pid, signal_type)
            
            signal_name = {
                signal.SIGTERM: "TERM",
                signal.SIGINT: "INT",
                signal.SIGKILL: "KILL",
                signal.SIGUSR1: "USR1",
                signal.SIGUSR2: "USR2",
            }.get(signal_type, str(signal_type))
            
            return True, f"Sent {signal_name} signal to process {pid}"
            
        except Exception as e:
            return False, f"Error sending signal: {e}" 