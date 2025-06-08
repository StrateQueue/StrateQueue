"""
IBKR Credential Validation

Lightweight credential testing that doesn't interfere with the main trading connection.
"""

import logging

try:
    from ib_insync import IB, util
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False
    
    class IB:
        def __init__(self, *args, **kwargs):
            raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
    
    class util:
        @staticmethod
        def startLoop():
            raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")

logger = logging.getLogger(__name__)


def test_ibkr_credentials(host: str = "127.0.0.1", port: int = 7497, client_id: int = 1, timeout: int = 5) -> bool:
    """
    Light-weight connectivity test that does NOT affect the trading connection
    
    Args:
        host: TWS/Gateway host
        port: TWS/Gateway port  
        client_id: Client ID for connection
        timeout: Connection timeout in seconds
        
    Returns:
        True if credentials are valid and connection works
    """
    if not IB_INSYNC_AVAILABLE:
        logger.error("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
        return False
    
    # Use a separate IB instance for testing
    test_ib = IB()
    
    try:
        # Test connection
        logger.debug(f"Testing IBKR credentials at {host}:{port} (client_id={client_id})")
        
        test_ib.connect(
            host=host,
            port=port,
            clientId=client_id,
            timeout=timeout
        )
        
        if not test_ib.isConnected():
            logger.error("Failed to connect to IBKR for credential test")
            return False
        
        # Test basic API access by getting account summary
        try:
            summary = test_ib.accountSummary()
            is_valid = len(summary) > 0
            
            if is_valid:
                logger.debug("IBKR credential test successful")
            else:
                logger.error("IBKR credential test failed - no account data")
                
            return is_valid
            
        except Exception as e:
            logger.error(f"IBKR credential test failed during account summary: {e}")
            return False
            
    except Exception as e:
        logger.error(f"IBKR credential test failed: {e}")
        return False
        
    finally:
        # Always clean up the test connection
        try:
            if test_ib.isConnected():
                test_ib.disconnect()
                logger.debug("Cleaned up IBKR credential test connection")
        except Exception as e:
            logger.warning(f"Error cleaning up IBKR test connection: {e}")


def get_ibkr_connection_info(host: str = "127.0.0.1", port: int = 7497, client_id: int = 1) -> dict:
    """
    Get connection information without establishing a persistent connection
    
    Args:
        host: TWS/Gateway host
        port: TWS/Gateway port
        client_id: Client ID for connection
        
    Returns:
        Dictionary with connection details
    """
    if not IB_INSYNC_AVAILABLE:
        return {"error": "ib_insync not installed"}
    
    test_ib = IB()
    
    try:
        test_ib.connect(host=host, port=port, clientId=client_id, timeout=5)
        
        if not test_ib.isConnected():
            return {"connected": False, "error": "Connection failed"}
        
        # Get basic info
        info = {
            "connected": True,
            "host": host,
            "port": port,
            "client_id": client_id,
            "accounts": getattr(test_ib.wrapper, 'accounts', []),
        }
        
        # Try to get server version
        try:
            info["server_version"] = test_ib.client.serverVersion()
        except:
            pass
            
        return info
        
    except Exception as e:
        return {"connected": False, "error": str(e)}
        
    finally:
        try:
            if test_ib.isConnected():
                test_ib.disconnect()
        except:
            pass 