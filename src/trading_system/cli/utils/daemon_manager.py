"""
Daemon Management Utilities

Provides daemon process management capabilities including:
- PID file management and process tracking
- Daemon lifecycle operations (start, stop, status)
- Inter-process communication for hotswap operations
"""

import os
import pickle
import signal
import time
import socket
import threading
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

logger = logging.getLogger(__name__)


class DaemonIPC:
    """Inter-process communication for daemon operations"""
    
    def __init__(self, daemon_id: str = "trading_system"):
        self.daemon_id = daemon_id
        self.socket_path = f"/tmp/stratequeue_{daemon_id}.sock"
        self.server_socket = None
        self.server_thread = None
        self.running = False
        self.system_instance = None
    
    def start_command_server(self, system_instance):
        """Start the IPC command server in daemon process"""
        self.system_instance = system_instance
        self.running = True
        
        # Clean up any existing socket
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        # Create Unix socket
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(self.socket_path)
        self.server_socket.listen(5)
        
        # Start server thread
        self.server_thread = threading.Thread(target=self._command_server_loop, daemon=True)
        self.server_thread.start()
        
        logger.info(f"IPC command server started at {self.socket_path}")
    
    def stop_command_server(self):
        """Stop the IPC command server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
    
    def _command_server_loop(self):
        """Main server loop for handling IPC commands"""
        while self.running:
            try:
                conn, _ = self.server_socket.accept()
                threading.Thread(target=self._handle_command, args=(conn,), daemon=True).start()
            except Exception as e:
                if self.running:  # Only log if we're supposed to be running
                    logger.error(f"Error in command server: {e}")
                break
    
    def _handle_command(self, conn):
        """Handle a single IPC command"""
        try:
            data = conn.recv(4096).decode('utf-8')
            if not data:
                return
            
            command = json.loads(data)
            response = self._execute_command(command)
            
            conn.send(json.dumps(response).encode('utf-8'))
        except Exception as e:
            logger.error(f"Error handling command: {e}")
            error_response = {'success': False, 'error': str(e)}
            try:
                conn.send(json.dumps(error_response).encode('utf-8'))
            except:
                pass
        finally:
            conn.close()
    
    def _execute_command(self, command: dict) -> dict:
        """Execute a command and return response"""
        cmd_type = command.get('type')
        
        if cmd_type == 'add_strategy':
            return self._handle_add_strategy(command)
        elif cmd_type == 'pause_strategy':
            return self._handle_pause_strategy(command)
        elif cmd_type == 'resume_strategy':
            return self._handle_resume_strategy(command)
        elif cmd_type == 'get_status':
            return self._handle_get_status(command)
        else:
            return {'success': False, 'error': f'Unknown command type: {cmd_type}'}
    
    def _handle_add_strategy(self, command: dict) -> dict:
        """Handle add strategy command"""
        try:
            strategy_path = command['strategy_path']
            strategy_id = command['strategy_id']
            allocation = command.get('allocation', 0.5)
            symbol = command.get('symbol')
            
            logger.info(f"Adding strategy {strategy_id} via IPC: path={strategy_path}, allocation={allocation}, symbol={symbol}")
            
            # Check if system supports runtime strategy addition
            if not hasattr(self.system_instance, 'deploy_strategy_runtime'):
                error_msg = 'System does not support runtime strategy addition'
                logger.error(error_msg)
                return {'success': False, 'error': error_msg}
            
            logger.info(f"System has deploy_strategy_runtime method, calling it...")
            
            # Deploy strategy
            result = self.system_instance.deploy_strategy_runtime(
                strategy_path=strategy_path,
                strategy_id=strategy_id,
                allocation_percentage=allocation,
                symbol=symbol
            )
            
            logger.info(f"deploy_strategy_runtime returned: {result}")
            
            return {
                'success': result,
                'message': f'Strategy {strategy_id} {"added" if result else "failed to add"}'
            }
            
        except Exception as e:
            error_msg = f"Exception in _handle_add_strategy: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'error': error_msg}
    
    def _handle_pause_strategy(self, command: dict) -> dict:
        """Handle pause strategy command"""
        try:
            strategy_id = command['strategy_id']
            
            if not hasattr(self.system_instance, 'pause_strategy_runtime'):
                return {
                    'success': False,
                    'error': 'System does not support strategy pausing'
                }
            
            result = self.system_instance.pause_strategy_runtime(strategy_id)
            return {
                'success': result,
                'message': f'Strategy {strategy_id} {"paused" if result else "failed to pause"}'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _handle_resume_strategy(self, command: dict) -> dict:
        """Handle resume strategy command"""
        try:
            strategy_id = command['strategy_id']
            
            if not hasattr(self.system_instance, 'resume_strategy_runtime'):
                return {
                    'success': False,
                    'error': 'System does not support strategy resuming'
                }
            
            result = self.system_instance.resume_strategy_runtime(strategy_id)
            return {
                'success': result,
                'message': f'Strategy {strategy_id} {"resumed" if result else "failed to resume"}'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _handle_get_status(self, command: dict) -> dict:
        """Handle get status command"""
        try:
            # Get basic system status
            status = {
                'mode': 'multi-strategy' if hasattr(self.system_instance, 'multi_strategy_runner') else 'single-strategy',
                'strategies': {},
                'running': True
            }
            
            # Try to get strategy information
            if hasattr(self.system_instance, 'get_deployed_strategies'):
                strategy_ids = self.system_instance.get_deployed_strategies()
                for sid in strategy_ids:
                    status['strategies'][sid] = {
                        'status': 'active',  # Could enhance this
                        'allocation': 1.0 / len(strategy_ids)  # Simplified
                    }
            
            return {'success': True, 'status': status}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def send_command(self, command: dict, timeout: int = 10) -> dict:
        """Send command to daemon via IPC"""
        try:
            # Connect to daemon socket
            client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client_socket.settimeout(timeout)
            client_socket.connect(self.socket_path)
            
            # Send command
            client_socket.send(json.dumps(command).encode('utf-8'))
            
            # Receive response
            response_data = client_socket.recv(4096).decode('utf-8')
            response = json.loads(response_data)
            
            client_socket.close()
            return response
            
        except FileNotFoundError:
            return {'success': False, 'error': 'Daemon IPC socket not found'}
        except socket.timeout:
            return {'success': False, 'error': 'Command timeout'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class DaemonManager:
    """Manages daemon processes and state"""
    
    def __init__(self, system_name: str = "trading_system"):
        """
        Initialize DaemonManager
        
        Args:
            system_name: Name prefix for daemon files
        """
        self.system_name = system_name
        self.pid_dir = Path.home() / '.stratequeue' / 'pids'
        self.pid_dir.mkdir(parents=True, exist_ok=True)
        self.ipc = DaemonIPC(system_name)  # Add IPC instance
    
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
    
    def store_daemon_system(self, system_info: Dict[str, Any], pid_file_path: Optional[Path] = None) -> bool:
        """
        Store daemon system info to PID file
        
        Args:
            system_info: System information dictionary (should not contain unpicklable objects)
            pid_file_path: Optional custom PID file path
            
        Returns:
            True if successful
        """
        try:
            if pid_file_path is None:
                pid_file_path = self.get_pid_file_path()
            
            # Create safe system info for pickling (avoid complex objects)
            safe_system_info = {
                'pid': system_info.get('pid', os.getpid()),
                'start_time': system_info.get('start_time', time.time()),
                'strategies': system_info.get('strategies', {}),
                'mode': system_info.get('mode', 'unknown'),
                'symbols': system_info.get('symbols', []),
                'args': system_info.get('args', {}),
                # Store system reference only for this process, not pickled
                '_system_ref': id(system_info.get('system')) if 'system' in system_info else None
            }
            
            # Store to file
            with open(pid_file_path, 'wb') as f:
                pickle.dump(safe_system_info, f)
            
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