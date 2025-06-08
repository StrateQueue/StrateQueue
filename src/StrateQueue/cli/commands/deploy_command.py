"""Deploy Command

Main deploy command implementation that orchestrates strategy deployment
including validation and trading system execution.
"""

import argparse
import asyncio
import logging
import math
import numpy as np
import os
import random, threading, socket
from argparse import Namespace

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from uvicorn import Config, Server
from ..formatters.base_formatter import BaseFormatter
from ..utils.deploy_utils import parse_symbols
from ..utils.logging_setup import setup_logging
from ..validators.deploy_validator import DeployValidator
from .base_command import BaseCommand

logger = logging.getLogger(__name__)


class DeployCommand(BaseCommand):
    """Deploy command for strategy execution"""

    def __init__(self):
        super().__init__()
        self.validator = DeployValidator()
        self.formatter = BaseFormatter()

    @property
    def name(self) -> str:
        """Command name"""
        return "deploy"

    @property
    def description(self) -> str:
        """Command description"""
        return "Deploy strategies for live trading"

    @property
    def aliases(self) -> list[str]:
        """Command aliases"""
        return ["run", "start"]

    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Setup the argument parser for deploy command"""

        # Strategy configuration
        strategy_group = parser.add_argument_group('Strategy Configuration')

        strategy_group.add_argument(
            '--strategy',
            required=True,
            help='Strategy file(s). Single or comma-separated list (e.g., sma.py or sma.py,momentum.py,random.py)'
        )

        strategy_group.add_argument(
            '--strategy-id',
            help='Strategy identifier(s). Optional - defaults to strategy filename(s). Single value or comma-separated list matching strategies.'
        )

        strategy_group.add_argument(
            '--allocation',
            help='Strategy allocation(s) as percentage (0-1) or dollar amount. Single value or comma-separated list (e.g., 0.4 or 0.4,0.35,0.25). Required for multi-strategy mode.'
        )

        # Trading configuration
        parser.add_argument(
            '--symbol',
            default='AAPL',
            help='Symbol(s) to trade. Single or comma-separated list (e.g., AAPL or ETH,BTC,AAPL). When number of symbols equals number of strategies, creates 1:1 mapping.'
        )

        parser.add_argument(
            '--data-source',
            default='demo',
            help='Data source(s). Single value applies to all, or comma-separated list matching strategies (e.g., demo or polygon,coinmarketcap)'
        )

        parser.add_argument(
            '--timeframe',
            dest='granularity',
            help='Timeframe(s). Single value applies to all, or comma-separated list matching strategies (e.g., 1m or 1m,5m,1h)'
        )

        parser.add_argument(
            '--broker',
            help='Broker(s) for trading. Single value applies to all, or comma-separated list matching strategies (e.g., alpaca or alpaca,kraken)'
        )

        # Get supported engines for autocomplete
        try:
            from ...engines import get_supported_engines
            supported_engines = get_supported_engines()
        except Exception:
            supported_engines = None  # Fallback if import fails
        
        parser.add_argument(
            '--engine',
            help='Trading engine to use (e.g., vectorbt, backtesting). If not specified, will auto-detect from strategy file'
        )

        from ...multi_strategy.strategy_config import DEFAULT_LOOKBACK_PERIOD

        parser.add_argument(
            '--lookback',
            type=lambda x: int(x) + 1,
            default=DEFAULT_LOOKBACK_PERIOD,
            help=f'Lookback period for historical data (default: {DEFAULT_LOOKBACK_PERIOD} bars)'
        )

        # Execution mode options
        execution_group = parser.add_argument_group('Execution Mode')

        # Create mutually exclusive group for trading modes
        mode_group = execution_group.add_mutually_exclusive_group()

        mode_group.add_argument(
            '--paper',
            action='store_true',
            help='Paper trading mode (fake money)'
        )

        mode_group.add_argument(
            '--live',
            action='store_true',
            help='Live trading mode (real money, use with caution!)'
        )

        mode_group.add_argument(
            '--no-trading',
            action='store_true',
            help='Signals only mode (no trading execution, default behavior)'
        )

        # System control options
        system_group = parser.add_argument_group('System Control')

        system_group.add_argument(
            '--duration',
            type=int,
            default=60,
            help='Runtime duration in minutes (default: 60)'
        )

        system_group.add_argument(
            '--stats-port',
            type=int,
            help='Optional port for the embedded statistics server (0 = auto)'
        )

        system_group.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose logging'
        )

        return parser

    def execute(self, args: Namespace) -> int:
        """
        Execute the deploy command

        Args:
            args: Parsed command arguments

        Returns:
            Exit code (0 for success, 1 for error)
        """
        # Setup logging if verbose mode
        if hasattr(args, 'verbose') and args.verbose:
            setup_logging(verbose=True, log_file='stratequeue.log')

        # Validate engine availability if specified
        if hasattr(args, 'engine') and args.engine:
            engine_error = self._validate_engine(args.engine)
            if engine_error:
                print(f"❌ Error: {engine_error}")
                return 1

        # Validate arguments
        is_valid, errors = self.validator.validate(args)
        if not is_valid:
            self._show_validation_errors(errors)
            self._show_quick_help()
            return 1

        # Run the trading system normally
        try:
            return asyncio.run(self._run_trading_system(args))
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            print(f"❌ Unexpected error: {e}")
            return 1

    def _show_validation_errors(self, errors: list[str]) -> None:
        """Show validation errors to user"""
        for error in errors:
            print(f"❌ Error: {error}")

    def _validate_engine(self, engine_name: str) -> str | None:
        """
        Validate that an engine is available
        
        Args:
            engine_name: Name of the engine to validate
            
        Returns:
            Error message if engine is not available, None if valid
        """
        try:
            from ...engines import (
                EngineFactory,
                get_supported_engines,
                get_unavailable_engines,
            )
            
            if not EngineFactory.is_engine_supported(engine_name):
                unavailable = get_unavailable_engines()
                if engine_name in unavailable:
                    return f"Engine '{engine_name}' is not available.\nHint: {unavailable[engine_name]}"
                else:
                    supported = get_supported_engines()
                    return f"Unknown engine '{engine_name}'. Available engines: {', '.join(supported)}"
            
            return None  # Engine is valid
            
        except Exception as e:
            return f"Error validating engine: {e}"

    def _show_quick_help(self) -> None:
        """Show quick help for common issues"""
        print("")
        print("💡 Quick Help:")
        print("  stratequeue list engines              # See supported engines")
        print("  stratequeue list brokers              # See supported brokers")
        print("  stratequeue status                    # Check broker credentials")
        print("  stratequeue setup broker <broker>     # Setup broker")
        print("  stratequeue deploy --help             # Detailed deployment help")
        print("")
        print("📖 Common Examples:")
        print("  # Test strategy (default mode)")
        print("  stratequeue deploy --strategy sma.py --symbol AAPL")
        print("")
        print("  # Paper trading (fake money)")
        print("  stratequeue deploy --strategy sma.py --symbol AAPL --paper")
        print("")
        print("  # Live trading (real money - be careful!)")
        print("  stratequeue deploy --strategy sma.py --symbol AAPL --live")

    async def _run_trading_system(self, args: Namespace) -> int:
        """
        Run trading system

        Args:
            args: Parsed command arguments

        Returns:
            Exit code
        """
        try:
            # Import here to avoid circular imports
            from ...live_system.orchestrator import LiveTradingSystem

            # Parse symbols
            symbols = parse_symbols(args.symbol)

            # Determine trading configuration
            enable_trading = args._enable_trading
            paper_trading = args._paper_trading

            # Determine if multi-strategy mode
            is_multi_strategy = hasattr(args, '_strategies') and len(args._strategies) > 1

            if is_multi_strategy:
                return await self._run_multi_strategy_system(args, symbols, enable_trading, paper_trading)
            else:
                return await self._run_single_strategy_system(args, symbols, enable_trading, paper_trading)

        except ImportError as e:
            logger.error(f"Trading system not available: {e}")
            print(f"❌ Trading system not available: {e}")
            print("💡 Please reinstall the package: pip install stratequeue")
            return 1
        except Exception as e:
            logger.error(f"Error running trading system: {e}")
            print(f"❌ Error running trading system: {e}")
            return 1

    async def _run_multi_strategy_system(self, args: Namespace, symbols: list[str],
                                        enable_trading: bool, paper_trading: bool) -> int:
        """Run multi-strategy system"""
        try:
            import tempfile

            from ...live_system.orchestrator import LiveTradingSystem
            from ..utils.deploy_utils import create_inline_strategy_config

            # Create temporary multi-strategy config
            temp_config_content = create_inline_strategy_config(args)
            if not temp_config_content:
                logger.error("Failed to create multi-strategy configuration")
                print("❌ Failed to create multi-strategy configuration")
                return 1

            # Create temporary config file
            temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
            try:
                temp_config.write(temp_config_content)
                temp_config.close()

                logger.info("Created temporary multi-strategy configuration")
                print("📊 Multi-strategy mode - temporary config created")

                # Initialize multi-strategy system
                system = LiveTradingSystem(
                    symbols=symbols,
                    data_source=args._data_sources[0],
                    granularity=args._granularities[0] if args._granularities else "1m",
                    enable_trading=enable_trading,
                    multi_strategy_config=temp_config.name,
                    broker_type=args._brokers[0] if args._brokers and args._brokers[0] != 'auto' else None,
                    paper_trading=paper_trading,
                    lookback_override=args.lookback
                )

                print(f"🚀 Starting multi-strategy system for {args.duration} minutes...")
                print(f"📈 Strategies: {len(args._strategies)}")
                print(f"💰 Trading mode: {'Paper' if paper_trading else 'Live' if enable_trading else 'Signals only'}")
                print("")

                # Start stats server
                port = args.stats_port if getattr(args, 'stats_port', None) else 0
                if not port:
                    port = _find_free_port()
                _start_stats_server(system.statistics_manager, port)
                print(f"📡 Statistics server listening on 127.0.0.1:{port}/stats")

                await system.run_live_system(args.duration)

                print("✅ Multi-strategy system completed successfully")
                return 0

            finally:
                # Clean up temporary file
                if os.path.exists(temp_config.name):
                    os.unlink(temp_config.name)

        except Exception as e:
            logger.error(f"Error running multi-strategy system: {e}")
            print(f"❌ Error running multi-strategy system: {e}")
            return 1

    async def _run_single_strategy_system(self, args: Namespace, symbols: list[str],
                                         enable_trading: bool, paper_trading: bool) -> int:
        """Run single strategy system"""
        try:
            from ...live_system.orchestrator import LiveTradingSystem

            strategy_path = args._strategies[0]

            # Get single values for single strategy
            data_source = args._data_sources[0] if args._data_sources else 'demo'
            granularity = args._granularities[0] if args._granularities else "1m"
            broker_type = args._brokers[0] if args._brokers and args._brokers[0] != 'auto' else None

            # Initialize single strategy system
            system = LiveTradingSystem(
                strategy_path=strategy_path,
                symbols=symbols,
                data_source=data_source,
                granularity=granularity,
                enable_trading=enable_trading,
                broker_type=broker_type,
                paper_trading=paper_trading,
                lookback_override=args.lookback,
                engine_type=getattr(args, 'engine', None)
            )

            print(f"🚀 Starting single strategy system for {args.duration} minutes...")
            print(f"📊 Strategy: {os.path.basename(strategy_path)}")
            print(f"💰 Trading mode: {'Paper' if paper_trading else 'Live' if enable_trading else 'Signals only'}")
            print(f"📈 Symbols: {', '.join(symbols)}")
            print("")

            # Start stats server
            port = args.stats_port if getattr(args, 'stats_port', None) else 0
            if not port:
                port = _find_free_port()
            _start_stats_server(system.statistics_manager, port)
            print(f"📡 Statistics server listening on 127.0.0.1:{port}/stats")

            await system.run_live_system(args.duration)

            print("✅ Single strategy system completed successfully")
            return 0

        except Exception as e:
            logger.error(f"Error running single strategy system: {e}")
            print(f"❌ Error running single strategy system: {e}")
            return 1

    def _send_to_daemon(self, args: Namespace) -> int:
        """Deprecated stub kept for backward compatibility – always informs user that daemon mode is no longer available."""
        print("❌ Daemon mode has been removed from StrateQueue. Please run strategies directly without the --daemon flag.")
        return 1

# Helper: find free TCP port

def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

# Helper: start stats FastAPI server in background thread

def _start_stats_server(stats_manager, port: int):
    """Expose statistics_manager.calc_summary_metrics() on /stats (JSON)."""
    app = FastAPI()

    # ------------------------------------------------------------------
    # Helper: convert NumPy / non-finite values so FastAPI can serialise
    # ------------------------------------------------------------------
    def _sanitize_metrics(metrics: dict) -> dict:
        cleaned: dict[str, object] = {}
        for k, v in metrics.items():
            # Convert NumPy scalars → builtin Python types
            if isinstance(v, np.generic):
                v = v.item()

            # Replace ±inf / nan with None (JSON does not allow them)
            if isinstance(v, float) and not math.isfinite(v):
                v = None

            cleaned[k] = v
        return cleaned

    @app.get('/stats')
    async def get_stats():
        try:
            raw = stats_manager.calc_summary_metrics()
            safe = _sanitize_metrics(raw)
            return JSONResponse(content=jsonable_encoder(safe))
        except Exception as e:
            return {'error': str(e)}

    cfg = Config(app, host='127.0.0.1', port=port, log_level='warning')
    thread = threading.Thread(target=Server(cfg).run, daemon=True)
    thread.start()
    return port
