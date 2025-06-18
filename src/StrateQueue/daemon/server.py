"""
StrateQueue Trading Daemon Server

Background daemon that manages a single LiveTradingSystem instance and exposes
HTTP endpoints for remote control via CLI commands.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import Body, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from StrateQueue.live_system.orchestrator import LiveTradingSystem

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
SHUTDOWN_DELAY_SECONDS = 0.1
DEFAULT_DAEMON_PORT = 8400
DEFAULT_DAEMON_HOST = "127.0.0.1"

app = FastAPI(title="StrateQueue Daemon", version="0.0.1")

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def generate_strategy_id(strategy_path: str, symbol: str = None, user_id: str = None) -> str:
    """
    Generate a unique strategy ID with timestamp

    Format: {strategy_name}_{symbol}_{timestamp}
    Example: sma_ETH_20250616_164530

    Args:
        strategy_path: Path to strategy file
        symbol: Trading symbol (optional)
        user_id: User-provided ID (optional, takes precedence)

    Returns:
        Unique strategy identifier
    """
    if user_id:
        return user_id

    # Extract strategy name from file path
    strategy_name = Path(strategy_path).stem.lower()

    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Build ID components
    if symbol:
        return f"{strategy_name}_{symbol.upper()}_{timestamp}"
    else:
        return f"{strategy_name}_{timestamp}"


class TradingDaemon:
    """Main daemon class that manages the LiveTradingSystem"""

    def __init__(self):
        self.system: LiveTradingSystem | None = None
        self.system_task: asyncio.Task | None = None
        self.running = False
        self._lock: asyncio.Lock = asyncio.Lock()  # Non-blocking protection against concurrent API calls

    async def deploy(self, cli_args: dict[str, Any]) -> dict[str, Any]:
        """
        Deploy a strategy to the trading system

        Args:
            cli_args: CLI arguments as dictionary

        Returns:
            Response dictionary
        """
        try:
            if self.system is None:
                # First deployment - create and start the trading system
                await self._create_trading_system(cli_args)
                return {"success": True, "message": "Trading system started and strategy deployed"}
            else:
                # Add strategy to existing system
                success = await self._add_strategy_to_system(cli_args)
                if success:
                    return {"success": True, "message": "Strategy added to running system"}
                else:
                    return {"success": False, "message": "Failed to add strategy to system"}

        except Exception as e:
            logger.error(f"Failed to deploy strategy: {e}")
            return {"success": False, "message": f"Deployment failed: {str(e)}"}

    async def _create_trading_system(self, cli_args: dict[str, Any]) -> None:
        """Create and start the initial trading system"""
        try:

            # Parse arguments
            symbols = self._parse_symbols(cli_args.get("symbol", "AAPL"))
            data_source = cli_args.get("data_source", "demo")
            granularity = cli_args.get("granularity", "1m")
            # Handle cases where granularity might be None or empty
            if not granularity:
                granularity = "1m"
            lookback = cli_args.get("lookback", 3)
            enable_trading = cli_args.get("_enable_trading", False)
            paper_trading = cli_args.get("_paper_trading", True)
            broker_type = cli_args.get("broker")
            duration_minutes = cli_args.get("duration", 60)

            # Always use multi-strategy mode for runtime flexibility
            cli_args.get("_strategies", [cli_args.get("strategy")])

            # Create temporary multi-strategy config
            temp_config_content = self._create_multi_strategy_config(cli_args)
            if not temp_config_content:
                raise ValueError("Failed to create multi-strategy configuration")

            # Write to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
                f.write(temp_config_content)
                temp_config_path = f.name

            try:
                self.system = LiveTradingSystem(
                    strategy_path=None,
                    symbols=symbols,
                    data_source=data_source,
                    granularity=granularity,
                    lookback_override=lookback,
                    enable_trading=enable_trading,
                    multi_strategy_config=temp_config_path,
                    broker_type=broker_type,
                    paper_trading=paper_trading
                )
            finally:
                # Clean up temp file
                os.unlink(temp_config_path)

            # Start the trading system in background
            self.system_task = asyncio.create_task(
                self.system.run_live_system(duration_minutes=duration_minutes)
            )
            self.running = True

            logger.info(f"Trading system started with strategy: {cli_args.get('strategy', 'multi-strategy')}")

        except Exception as e:
            logger.error(f"Failed to create trading system: {e}")
            raise

    def _parse_symbols(self, symbols_str: str) -> list[str]:
        """Parse symbols string into list"""
        return [s.strip().upper() for s in symbols_str.split(',') if s.strip()]

    def _create_multi_strategy_config(self, cli_args: dict[str, Any]) -> str | None:
        """Create multi-strategy configuration content"""
        strategies = cli_args.get("_strategies", [])
        if not strategies:
            return None

        # Parse symbols for potential 1:1 mapping
        symbols = self._parse_symbols(cli_args.get("symbol", ""))
        strategy_ids = cli_args.get("_strategy_ids", [])
        allocations = cli_args.get("_allocations", [])

        # Check if we have 1:1 strategy-to-symbol mapping
        if len(strategies) == len(symbols):
            config_lines = [
                "# Auto-generated multi-strategy configuration from CLI arguments",
                "# Format: filename,strategy_id,allocation_percentage,symbol",
                "# 1:1 Strategy-to-Symbol mapping mode",
                ""
            ]

            for i, strategy_path in enumerate(strategies):
                # Use provided ID or generate smart ID with symbol
                user_id = strategy_ids[i] if i < len(strategy_ids) else None
                strategy_id = generate_strategy_id(strategy_path, symbols[i], user_id)
                allocation = allocations[i] if i < len(allocations) else ("1.0" if len(strategies) == 1 else "0.1")
                symbol = symbols[i]
                config_lines.append(f"{strategy_path},{strategy_id},{allocation},{symbol}")
        else:
            # Traditional multi-strategy mode (all strategies on all symbols)
            config_lines = [
                "# Auto-generated multi-strategy configuration from CLI arguments",
                "# Format: filename,strategy_id,allocation_percentage",
                ""
            ]

            for i, strategy_path in enumerate(strategies):
                # Use provided ID or generate smart ID without symbol
                user_id = strategy_ids[i] if i < len(strategy_ids) else None
                strategy_id = generate_strategy_id(strategy_path, None, user_id)
                allocation = allocations[i] if i < len(allocations) else ("1.0" if len(strategies) == 1 else "0.1")
                config_lines.append(f"{strategy_path},{strategy_id},{allocation}")

        return "\n".join(config_lines)

    async def _add_strategy_to_system(self, cli_args: dict[str, Any]) -> bool:
        """Add a strategy to the running system"""
        try:
            if not self.system or not self.running:
                return False

            strategy_path = cli_args.get("strategy")
            user_strategy_id = cli_args.get("strategy_id")  # User-provided ID (optional)
            allocation = float(cli_args.get("allocation", 0.1))
            symbol = cli_args.get("symbol")

            # Generate unique strategy ID
            strategy_id = generate_strategy_id(strategy_path, symbol, user_strategy_id)

            success = self.system.deploy_strategy_runtime(
                strategy_path=strategy_path,
                strategy_id=strategy_id,
                allocation_percentage=allocation,
                symbol=symbol
            )

            if success:
                logger.info(f"Added strategy {strategy_id} to running system")
            else:
                logger.warning(f"Failed to add strategy {strategy_id} to system")

            return success

        except Exception as e:
            logger.error(f"Failed to add strategy to system: {e}")
            return False

    def get_status(self) -> dict[str, Any]:
        """Get daemon and system status"""
        if not self.system or not self.running:
            return {
                "daemon_running": True,
                "trading_system_running": False,
                "strategies": []
            }

        try:
            strategies = self.system.get_deployed_strategies()
            system_status = self.system.get_system_status()

            # Get detailed strategy information if available
            strategy_details = []
            if self.system.is_multi_strategy and hasattr(self.system, 'multi_strategy_runner'):
                strategy_configs = self.system.multi_strategy_runner.get_strategy_configs()
                strategy_statuses = self.system.multi_strategy_runner.get_all_strategy_statuses()

                for strategy_id in strategies:
                    config = strategy_configs.get(strategy_id)
                    status = strategy_statuses.get(strategy_id, "unknown")

                    strategy_detail = {
                        "id": strategy_id,
                        "status": status,
                        "allocation": config.allocation if config else 0.0,
                        "symbols": [config.symbol] if config and config.symbol else system_status.get("symbols", []),
                        "file_path": config.file_path if config else None
                    }
                    strategy_details.append(strategy_detail)
            else:
                # Single strategy mode - use system-wide symbols
                if strategies:
                    strategy_detail = {
                        "id": strategies[0] if strategies else "unknown",
                        "status": "running",
                        "allocation": 1.0,
                        "symbols": system_status.get("symbols", []),
                        "file_path": getattr(self.system, 'strategy_path', None)
                    }
                    strategy_details.append(strategy_detail)

            return {
                "daemon_running": True,
                "trading_system_running": True,
                "strategies": strategies,  # Keep for backward compatibility
                "strategy_details": strategy_details,  # New detailed information
                "system_status": system_status
            }
        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return {
                "daemon_running": True,
                "trading_system_running": False,
                "error": str(e),
                "strategies": []
            }

    async def shutdown(self) -> dict[str, Any]:
        """Shutdown the trading system and daemon"""
        try:
            if self.system_task and not self.system_task.done():
                self.system_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self.system_task

            self.system = None
            self.system_task = None
            self.running = False

            logger.info("Trading system shut down successfully")
            return {"success": True, "message": "Daemon shutting down"}

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            return {"success": False, "message": f"Shutdown error: {str(e)}"}


# Global daemon instance
daemon = TradingDaemon()


def _normalise_deploy_payload(cli_args: dict[str, Any]) -> None:
    """
    Normalises a raw REST/UI payload by creating the private, list-based
    arguments (`_strategies`, `_allocations`, etc.) that the daemon's core logic expects.
    """
    # Ensure private list-based arguments exist for the core logic
    if not cli_args.get("_strategies"):
        strategy = cli_args.get("strategy")
        if strategy:
            cli_args["_strategies"] = [strategy]

    if not cli_args.get("_allocations"):
        allocation = cli_args.get("allocation")
        if allocation is not None:
            cli_args["_allocations"] = [str(allocation)]

    if not cli_args.get("_symbols"):
        symbol = cli_args.get("symbol")
        if symbol:
            cli_args["_symbols"] = [symbol]

    if not cli_args.get("_strategy_ids"):
        strategy_id = cli_args.get("strategy_id")
        if strategy_id:
            cli_args["_strategy_ids"] = [strategy_id]


@app.post("/deploy")
async def deploy_endpoint(payload: dict[str, Any] = Body(...)):
    """Deploy a strategy to the trading system"""

    _normalise_deploy_payload(payload)

    # Use a lock to prevent race conditions during deployment
    async with daemon._lock:
        if daemon.system is not None:
            return {"status": "error", "message": "Trading system is already running"}, 400

    return await daemon.deploy(payload)


@app.get("/status")
async def status_endpoint():
    """Get daemon and trading system status"""
    return daemon.get_status()


@app.post("/shutdown")
async def shutdown_endpoint():
    """Shutdown the trading daemon"""
    return await daemon.shutdown()


@app.get("/health")
async def health_endpoint():
    """Health check endpoint"""
    return {"status": "ok", "daemon_running": True}


@app.post("/strategy/upload")
async def upload_strategy_endpoint(file: UploadFile):
    """Saves an uploaded strategy file to a temporary location and returns the path."""
    try:
        # Create a temporary file with the same suffix
        suffix = Path(file.filename).suffix or ".py"
        with tempfile.NamedTemporaryFile(mode="wb", suffix=suffix, prefix="uploaded_", delete=False) as tmp:
            # Write the uploaded file's content to the temporary file
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        logger.info(f"Uploaded strategy '{file.filename}' saved to temporary file: {tmp_path}")
        return {"status": "success", "file_path": tmp_path}
    except Exception as e:
        logger.error(f"Failed to upload strategy file: {e}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")


# Strategy runtime control endpoints
@app.post("/strategy/deploy")
async def deploy_strategy_endpoint(payload: dict[str, Any] = Body(...)):
    """Deploy a new strategy to the running system"""
    try:
        _normalise_deploy_payload(payload)

        async with daemon._lock:  # Non-blocking protection against concurrent modifications
            if not daemon.system or not daemon.running:
                raise HTTPException(status_code=503, detail="Trading system not running")

            # Extract required parameters
            strategy_path = payload.get("strategy")
            symbol = payload.get("symbol")
            user_strategy_id = payload.get("strategy_id")  # User-provided ID (optional)
            allocation = float(payload.get("allocation", 0.1))

            if not strategy_path or not symbol:
                raise HTTPException(status_code=400, detail="strategy and symbol are required")

            # Generate unique strategy ID
            strategy_id = generate_strategy_id(strategy_path, symbol, user_strategy_id)

            # Call runtime deploy
            success = daemon.system.deploy_strategy_runtime(
                strategy_path=strategy_path,
                symbol=symbol,
                strategy_id=strategy_id,
                allocation_percentage=allocation
            )

            if success:
                return {"status": "success", "message": f"Strategy {strategy_id} deployed successfully"}
            else:
                # Try to get more specific error information
                error_detail = "Failed to deploy strategy"

                # Check for common failure reasons
                try:
                    portfolio_status = daemon.system.get_system_status().get("portfolio_health", [True, "OK"])
                    if not portfolio_status[0]:
                        error_detail = f"Portfolio issue: {portfolio_status[1]}"

                    # Check allocation limits
                    strategies = daemon.system.get_deployed_strategies()
                    if strategies:
                        error_detail = f"Allocation limit exceeded. Current strategies: {', '.join(strategies)}. Consider adjusting allocations or undeploying existing strategies."
                except Exception:
                    pass  # Fall back to generic error

                raise HTTPException(status_code=500, detail=error_detail)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/strategy/pause")
async def pause_strategy_endpoint(payload: dict[str, Any] = Body(...)):
    """Pause a strategy"""
    try:
        async with daemon._lock:  # Non-blocking protection against concurrent modifications
            if not daemon.system or not daemon.running:
                raise HTTPException(status_code=503, detail="Trading system not running")

            strategy_id = payload.get("strategy_id")
            if not strategy_id:
                raise HTTPException(status_code=400, detail="strategy_id is required")

            success = daemon.system.pause_strategy_runtime(strategy_id)
            if success:
                return {"status": "success", "message": f"Strategy {strategy_id} paused"}
            else:
                raise HTTPException(status_code=500, detail=f"Failed to pause strategy {strategy_id}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/strategy/resume")
async def resume_strategy_endpoint(payload: dict[str, Any] = Body(...)):
    """Resume a paused strategy"""
    try:
        async with daemon._lock:  # Non-blocking protection against concurrent modifications
            if not daemon.system or not daemon.running:
                raise HTTPException(status_code=503, detail="Trading system not running")

            strategy_id = payload.get("strategy_id")
            if not strategy_id:
                raise HTTPException(status_code=400, detail="strategy_id is required")

            success = daemon.system.resume_strategy_runtime(strategy_id)
            if success:
                return {"status": "success", "message": f"Strategy {strategy_id} resumed"}
            else:
                raise HTTPException(status_code=500, detail=f"Failed to resume strategy {strategy_id}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/strategy/undeploy")
async def undeploy_strategy_endpoint(payload: dict[str, Any] = Body(...)):
    """Remove a strategy from the running system"""
    try:
        async with daemon._lock:  # Non-blocking protection against concurrent modifications
            if not daemon.system or not daemon.running:
                raise HTTPException(status_code=503, detail="Trading system not running")

            strategy_id = payload.get("strategy_id")
            if not strategy_id:
                raise HTTPException(status_code=400, detail="strategy_id is required")

            success = daemon.system.undeploy_strategy_runtime(strategy_id)
            if success:
                return {"status": "success", "message": f"Strategy {strategy_id} undeployed"}
            else:
                raise HTTPException(status_code=500, detail=f"Failed to undeploy strategy {strategy_id}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/portfolio/rebalance")
async def rebalance_portfolio_endpoint(payload: dict[str, Any] = Body(...)):
    """Rebalance strategy allocations"""
    try:
        async with daemon._lock:  # Non-blocking protection against concurrent modifications
            if not daemon.system or not daemon.running:
                raise HTTPException(status_code=503, detail="Trading system not running")

            new_allocations = payload.get("allocations")
            if not new_allocations or not isinstance(new_allocations, dict):
                raise HTTPException(status_code=400, detail="allocations dictionary is required")

            success = daemon.system.rebalance_portfolio_runtime(new_allocations)
            if success:
                return {"status": "success", "message": "Portfolio rebalanced successfully"}
            else:
                raise HTTPException(status_code=500, detail="Failed to rebalance portfolio")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(daemon.shutdown())
        os._exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


def run_daemon(bind: str = DEFAULT_DAEMON_HOST, port: int = DEFAULT_DAEMON_PORT, log_file: str | None = None):
    """
    Run the daemon server

    Args:
        bind: IP address to bind to
        port: Port to listen on
        log_file: Optional log file path
    """
    # Setup logging to file if specified
    if log_file:
        log_path = Path(log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Only add file handler if not already present
        handler_exists = any(isinstance(h, logging.FileHandler) and h.baseFilename == str(log_path)
                           for h in logger.handlers)

        if not handler_exists:
            file_handler = logging.FileHandler(log_path)
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            logger.addHandler(file_handler)

            # Also log to file for uvicorn
            uvicorn_logger = logging.getLogger("uvicorn")
            uvicorn_handler_exists = any(isinstance(h, logging.FileHandler) and h.baseFilename == str(log_path)
                                       for h in uvicorn_logger.handlers)
            if not uvicorn_handler_exists:
                uvicorn_logger.addHandler(file_handler)

    # Setup signal handlers
    setup_signal_handlers()

    logger.info(f"Starting StrateQueue daemon on {bind}:{port}")

    # Run the server
    uvicorn.run(
        "StrateQueue.daemon.server:app",
        host=bind,
        port=port,
        log_level="info",
        access_log=False,
        lifespan="off"
    )


if __name__ == "__main__":
    # Allow running as module: python -m StrateQueue.daemon.server
    import argparse

    parser = argparse.ArgumentParser(description="StrateQueue Daemon Server")
    parser.add_argument("--bind", default="127.0.0.1", help="IP address to bind to")
    parser.add_argument("--port", type=int, default=8400, help="Port to listen on")
    parser.add_argument("--log-file", help="Log file path")

    args = parser.parse_args()
    run_daemon(bind=args.bind, port=args.port, log_file=args.log_file)
