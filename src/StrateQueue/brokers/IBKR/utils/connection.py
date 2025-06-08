"""
Connection Manager for IBKR

Handles connection management, reconnection logic, and connection health monitoring.
"""

import logging
import time
from typing import Any, Dict, Optional

try:
    from ib_insync import IB, util
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False
    
    class IB:
        pass
    class util:
        @staticmethod
        def startLoop():
            pass

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages IB connection with automatic reconnection and health monitoring.
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        """
        Initialize connection manager
        
        Args:
            host: TWS/Gateway host
            port: TWS/Gateway port
            client_id: Client ID for connection
        """
        if not IB_INSYNC_AVAILABLE:
            raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
        
        self.host = host
        self.port = port
        self.client_id = client_id
        
        self.ib = IB()
        self.logger = logging.getLogger(f"{__name__}.ConnectionManager")
        
        # Connection state
        self._is_connected = False
        self._connection_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 5  # seconds
        
        # Health monitoring
        self._last_heartbeat = None
        self._heartbeat_interval = 30  # seconds
        
        # Setup event handlers
        self._setup_event_handlers()
    
    def _setup_event_handlers(self) -> None:
        """Setup IB event handlers for connection monitoring"""
        try:
            self.ib.connectedEvent += self._on_connected
            self.ib.disconnectedEvent += self._on_disconnected
            self.ib.errorEvent += self._on_error
            
        except Exception as e:
            self.logger.error(f"Error setting up event handlers: {e}")
    
    def _on_connected(self) -> None:
        """Handle connection established event"""
        self._is_connected = True
        self._connection_attempts = 0
        self._last_heartbeat = time.time()
        self.logger.info(f"✅ Connected to IBKR at {self.host}:{self.port}")
    
    def _on_disconnected(self) -> None:
        """Handle disconnection event"""
        self._is_connected = False
        self.logger.warning(f"❌ Disconnected from IBKR at {self.host}:{self.port}")
    
    def _on_error(self, reqId: int, errorCode: int, errorString: str) -> None:
        """
        Handle IB error events
        
        Args:
            reqId: Request ID
            errorCode: Error code
            errorString: Error message
        """
        # Log different error levels based on error code
        if errorCode in [2104, 2106, 2158]:  # Market data farm connection warnings
            self.logger.debug(f"IB Info ({errorCode}): {errorString}")
        elif errorCode in [502, 504]:  # Connection errors
            self.logger.error(f"IB Connection Error ({errorCode}): {errorString}")
        elif errorCode >= 2000:  # System messages
            self.logger.info(f"IB System ({errorCode}): {errorString}")
        else:  # Other errors
            self.logger.warning(f"IB Error ({errorCode}): {errorString}")
    
    def connect(self, timeout: int = 10) -> bool:
        """
        Establish connection to TWS/Gateway
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            True if connection successful
        """
        try:
            # Attempt connection
            self.logger.info(f"Connecting to IBKR at {self.host}:{self.port} (client_id={self.client_id})")
            
            self.ib.connect(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
                timeout=timeout
            )
            
            # Verify connection
            if self.ib.isConnected():
                self._is_connected = True
                self._last_heartbeat = time.time()
                return True
            else:
                self.logger.error("Connection failed - not connected after connect() call")
                return False
                
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self._is_connected = False
            return False
    
    def disconnect(self) -> None:
        """Disconnect from TWS/Gateway"""
        try:
            if self.ib.isConnected():
                self.ib.disconnect()
                self.logger.info("Disconnected from IBKR")
            
            self._is_connected = False
            
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
    
    def reconnect(self) -> bool:
        """
        Attempt to reconnect to TWS/Gateway
        
        Returns:
            True if reconnection successful
        """
        if self._connection_attempts >= self._max_reconnect_attempts:
            self.logger.error(f"Max reconnection attempts ({self._max_reconnect_attempts}) reached")
            return False
        
        self._connection_attempts += 1
        
        self.logger.info(f"Reconnection attempt {self._connection_attempts}/{self._max_reconnect_attempts}")
        
        # Disconnect first if partially connected
        try:
            self.disconnect()
            time.sleep(self._reconnect_delay)
        except Exception:
            pass
        
        return self.connect()
    
    def is_connected(self) -> bool:
        """
        Check if connected to TWS/Gateway
        
        Returns:
            True if connected
        """
        try:
            return self.ib.isConnected() and self._is_connected
        except Exception:
            return False
    
    def check_health(self) -> bool:
        """
        Perform health check on the connection
        
        Returns:
            True if connection is healthy
        """
        try:
            if not self.is_connected():
                return False
            
            # Check if we can get account summary (basic API call)
            try:
                self.ib.accountSummary()
                self._last_heartbeat = time.time()
                return True
            except Exception as e:
                self.logger.warning(f"Health check failed: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error during health check: {e}")
            return False
    
    def ensure_connected(self) -> bool:
        """
        Ensure connection is established, reconnect if necessary
        
        Returns:
            True if connected (or successfully reconnected)
        """
        if self.is_connected():
            return True
        
        self.logger.info("Connection lost, attempting to reconnect...")
        return self.reconnect()
    
    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get connection information
        
        Returns:
            Dictionary with connection details
        """
        return {
            'host': self.host,
            'port': self.port,
            'client_id': self.client_id,
            'connected': self.is_connected(),
            'connection_attempts': self._connection_attempts,
            'last_heartbeat': self._last_heartbeat,
            'accounts': getattr(self.ib.wrapper, 'accounts', []) if self.is_connected() else []
        }
    
    def wait_for_connection(self, timeout: int = 30) -> bool:
        """
        Wait for connection to be established
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if connection established within timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.is_connected():
                return True
            
            time.sleep(0.5)  # Check every 500ms
        
        return False
    
    def set_reconnect_config(self, max_attempts: int = 5, delay: int = 5) -> None:
        """
        Configure reconnection behavior
        
        Args:
            max_attempts: Maximum reconnection attempts
            delay: Delay between attempts in seconds
        """
        self._max_reconnect_attempts = max_attempts
        self._reconnect_delay = delay
        
        self.logger.debug(f"Reconnect config: max_attempts={max_attempts}, delay={delay}s")
    
    def __enter__(self):
        """Context manager entry"""
        if not self.connect():
            raise ConnectionError("Failed to establish IBKR connection")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect() 