"""
Async Helpers for IBKR

Provides asyncio-compatible helpers for IB operations.
"""

import asyncio
import logging
from typing import Any, Callable, Optional, Union

try:
    from ib_insync import IB, Trade
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False
    
    class IB:
        pass
    class Trade:
        pass

logger = logging.getLogger(__name__)


class AsyncHelper:
    """
    Helper class for async operations with ib_insync.
    
    Provides utilities for waiting on order completion, timeouts, and event handling.
    """
    
    def __init__(self, ib_client: IB):
        """
        Initialize async helper
        
        Args:
            ib_client: Connected ib_insync IB client
        """
        if not IB_INSYNC_AVAILABLE:
            raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
        
        self.ib = ib_client
        self.logger = logging.getLogger(f"{__name__}.AsyncHelper")
    
    async def wait_for_order_completion(
        self, 
        trade: Trade, 
        timeout: float = 30.0
    ) -> bool:
        """
        Wait for an order to complete (fill or cancel)
        
        Args:
            trade: IB Trade object to monitor
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if order completed successfully
        """
        try:
            start_time = asyncio.get_event_loop().time()
            
            while asyncio.get_event_loop().time() - start_time < timeout:
                # Check if trade is done
                if trade.isDone():
                    status = trade.orderStatus.status
                    if status == 'Filled':
                        self.logger.debug(f"Order {trade.order.orderId} filled")
                        return True
                    elif status in ['Cancelled', 'ApiCancelled']:
                        self.logger.warning(f"Order {trade.order.orderId} cancelled")
                        return False
                    else:
                        self.logger.warning(f"Order {trade.order.orderId} completed with status: {status}")
                        return False
                
                # Wait for next update
                await self._wait_for_update()
            
            # Timeout reached
            self.logger.warning(f"Timeout waiting for order {trade.order.orderId} completion")
            return False
            
        except Exception as e:
            self.logger.error(f"Error waiting for order completion: {e}")
            return False
    
    async def wait_for_fill(
        self, 
        trade: Trade, 
        timeout: float = 30.0,
        partial_fill_ok: bool = False
    ) -> bool:
        """
        Wait for an order to be filled
        
        Args:
            trade: IB Trade object to monitor
            timeout: Maximum time to wait in seconds
            partial_fill_ok: Accept partial fills as success
            
        Returns:
            True if order was filled (fully or partially if allowed)
        """
        try:
            start_time = asyncio.get_event_loop().time()
            
            while asyncio.get_event_loop().time() - start_time < timeout:
                status = trade.orderStatus.status
                filled = trade.orderStatus.filled
                remaining = trade.orderStatus.remaining
                
                # Check for full fill
                if status == 'Filled' or remaining == 0:
                    self.logger.debug(f"Order {trade.order.orderId} fully filled")
                    return True
                
                # Check for partial fill if allowed
                if partial_fill_ok and filled > 0:
                    self.logger.debug(f"Order {trade.order.orderId} partially filled: {filled}")
                    return True
                
                # Check for cancellation
                if status in ['Cancelled', 'ApiCancelled']:
                    self.logger.warning(f"Order {trade.order.orderId} cancelled")
                    return False
                
                # Wait for next update
                await self._wait_for_update()
            
            # Timeout reached
            self.logger.warning(f"Timeout waiting for order {trade.order.orderId} fill")
            return False
            
        except Exception as e:
            self.logger.error(f"Error waiting for order fill: {e}")
            return False
    
    async def wait_for_condition(
        self, 
        condition: Callable[[], bool], 
        timeout: float = 30.0,
        check_interval: float = 0.1
    ) -> bool:
        """
        Wait for a custom condition to be met
        
        Args:
            condition: Callable that returns True when condition is met
            timeout: Maximum time to wait in seconds
            check_interval: How often to check condition in seconds
            
        Returns:
            True if condition was met within timeout
        """
        try:
            start_time = asyncio.get_event_loop().time()
            
            while asyncio.get_event_loop().time() - start_time < timeout:
                if condition():
                    return True
                
                await asyncio.sleep(check_interval)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error waiting for condition: {e}")
            return False
    
    async def _wait_for_update(self, timeout: float = 1.0) -> None:
        """
        Wait for next IB update
        
        Args:
            timeout: Maximum time to wait for update
        """
        try:
            # Create a future that will be resolved on next update
            future = asyncio.Future()
            
            def on_update():
                if not future.done():
                    future.set_result(None)
            
            # Subscribe to updates
            self.ib.updateEvent += on_update
            
            try:
                # Wait for update or timeout
                await asyncio.wait_for(future, timeout=timeout)
            except asyncio.TimeoutError:
                pass  # Timeout is expected behavior
            finally:
                # Unsubscribe from updates
                self.ib.updateEvent -= on_update
                
        except Exception as e:
            self.logger.debug(f"Error waiting for update: {e}")
    
    async def execute_with_timeout(
        self, 
        operation: Callable, 
        timeout: float = 30.0,
        *args, 
        **kwargs
    ) -> Any:
        """
        Execute an operation with timeout
        
        Args:
            operation: Function to execute
            timeout: Maximum time to wait
            *args: Arguments for operation
            **kwargs: Keyword arguments for operation
            
        Returns:
            Result of operation or None if timeout
        """
        try:
            # Run operation in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, operation, *args, **kwargs),
                timeout=timeout
            )
            return result
            
        except asyncio.TimeoutError:
            self.logger.warning(f"Operation timed out after {timeout} seconds")
            return None
        except Exception as e:
            self.logger.error(f"Error executing operation: {e}")
            return None
    
    async def wait_for_account_update(self, timeout: float = 10.0) -> bool:
        """
        Wait for account information to be updated
        
        Args:
            timeout: Maximum time to wait
            
        Returns:
            True if account update received
        """
        try:
            # Get initial account summary count
            initial_summary = self.ib.accountSummary()
            initial_count = len(initial_summary)
            
            def account_updated():
                current_summary = self.ib.accountSummary()
                return len(current_summary) >= initial_count
            
            return await self.wait_for_condition(account_updated, timeout)
            
        except Exception as e:
            self.logger.error(f"Error waiting for account update: {e}")
            return False
    
    async def wait_for_position_update(self, timeout: float = 10.0) -> bool:
        """
        Wait for position information to be updated
        
        Args:
            timeout: Maximum time to wait
            
        Returns:
            True if position update received
        """
        try:
            # Request position updates
            self.ib.reqPositions()
            
            # Wait for positions to be populated
            def positions_available():
                positions = self.ib.positions()
                return len(positions) >= 0  # Even empty list is valid
            
            result = await self.wait_for_condition(positions_available, timeout)
            
            # Cancel position updates to avoid spam
            self.ib.cancelPositions()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error waiting for position update: {e}")
            return False
    
    async def batch_execute(
        self, 
        operations: list, 
        max_concurrent: int = 5,
        timeout_per_operation: float = 30.0
    ) -> list:
        """
        Execute multiple operations concurrently with limits
        
        Args:
            operations: List of (function, args, kwargs) tuples
            max_concurrent: Maximum concurrent operations
            timeout_per_operation: Timeout for each operation
            
        Returns:
            List of results (None for failed operations)
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def execute_single(operation_tuple):
            func, args, kwargs = operation_tuple
            async with semaphore:
                return await self.execute_with_timeout(
                    func, timeout_per_operation, *args, **kwargs
                )
        
        try:
            tasks = [execute_single(op) for op in operations]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Convert exceptions to None
            return [None if isinstance(r, Exception) else r for r in results]
            
        except Exception as e:
            self.logger.error(f"Error in batch execution: {e}")
            return [None] * len(operations)
    
    def run_sync(self, coro, timeout: float = 30.0):
        """
        Run an async coroutine synchronously
        
        Args:
            coro: Coroutine to run
            timeout: Maximum time to wait
            
        Returns:
            Result of coroutine
        """
        try:
            # Try to get existing event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, we can't use run_until_complete
                # This shouldn't happen in normal ib_insync usage
                self.logger.warning("Event loop already running, cannot run sync operation")
                return None
            else:
                return loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(asyncio.wait_for(coro, timeout=timeout))
        except asyncio.TimeoutError:
            self.logger.warning(f"Sync operation timed out after {timeout} seconds")
            return None
        except Exception as e:
            self.logger.error(f"Error running sync operation: {e}")
            return None 