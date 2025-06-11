"""Deploy Command

Main deploy command implementation that orchestrates strategy deployment
including validation, daemon mode, and trading system execution.
"""

import asyncio
import argparse
import logging
import tempfile
import os
from argparse import Namespace
from typing import List

from .base_command import BaseCommand
from ..validators.deploy_validator import DeployValidator
from ..formatters.base_formatter import BaseFormatter
from ..utils.deploy_utils import setup_logging, create_inline_strategy_config, parse_symbols
from ..utils.daemon_utils import DaemonManager

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
    def aliases(self) -> List[str]:
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
            '--symbols', 
            default='AAPL', 
            help='Symbol(s) to trade. Single or comma-separated list (e.g., AAPL or ETH,BTC,AAPL). When number of symbols equals number of strategies, creates 1:1 mapping.'
        )
        
        parser.add_argument(
            '--data-source', 
            default='demo',
            help='Data source(s). Single value applies to all, or comma-separated list matching strategies (e.g., demo or polygon,coinmarketcap)'
        )
        
        parser.add_argument(
            '--granularity', 
            help='Data granularity/granularities. Single value applies to all, or comma-separated list matching strategies (e.g., 1m or 1m,5m,1h)'
        )
        
        parser.add_argument(
            '--broker',
            help='Broker(s) for trading. Single value applies to all, or comma-separated list matching strategies (e.g., alpaca or alpaca,kraken)'
        )
        
        parser.add_argument(
            '--lookback', 
            type=int, 
            help='Override calculated lookback period'
        )
        
        # Execution mode options
        execution_group = parser.add_argument_group('Execution Mode')
        
        # Create mutually exclusive group for trading modes
        mode_group = execution_group.add_mutually_exclusive_group()
        
        mode_group.add_argument(
            '--paper', 
            action='store_true', 
            help='Paper trading mode (fake money, default behavior)'
        )
        
        mode_group.add_argument(
            '--live', 
            action='store_true',
            help='Live trading mode (real money, use with caution!)'
        )
        
        mode_group.add_argument(
            '--no-trading', 
            action='store_true',
            help='Signals only mode (no trading execution)'
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
            '--daemon', 
            action='store_true',
            help='Run in background mode (enables hot swapping from same terminal)'
        )
        
        system_group.add_argument(
            '--pid-file', 
            help='PID file path for daemon mode (default: .stratequeue.pid)'
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
            setup_logging(verbose=True)
        
        # Validate arguments
        is_valid, errors = self.validator.validate(args)
        if not is_valid:
            self._show_validation_errors(errors)
            self._show_quick_help()
            return 1
        
        # Handle daemon mode
        if args.daemon:
            return self._handle_daemon_mode(args)
        
        # Run the trading system normally (blocking mode)
        try:
            return asyncio.run(self._run_trading_system(args))
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            print(f"❌ Unexpected error: {e}")
            return 1
    
    def _show_validation_errors(self, errors: List[str]) -> None:
        """Show validation errors to user"""
        for error in errors:
            print(f"❌ Error: {error}")
    
    def _show_quick_help(self) -> None:
        """Show quick help for common issues"""
        print("")
        print("💡 Quick Help:")
        print("  stratequeue list brokers              # See supported brokers")
        print("  stratequeue status                    # Check broker credentials")
        print("  stratequeue setup broker <broker>     # Setup broker")
        print("  stratequeue deploy --help             # Detailed deployment help")
        print("")
        print("📖 Common Examples:")
        print("  # Test strategy (no trading)")
        print("  stratequeue deploy --strategy sma.py --symbol AAPL --no-trading")
        print("")
        print("  # Paper trading (fake money)")  
        print("  stratequeue deploy --strategy sma.py --symbol AAPL --paper")
        print("")
        print("  # Live trading (real money - be careful!)")
        print("  stratequeue deploy --strategy sma.py --symbol AAPL --live")
    
    def _handle_daemon_mode(self, args: Namespace) -> int:
        """Handle daemon mode execution"""
        daemon_manager = DaemonManager(args.pid_file)
        
        if daemon_manager.start_daemon(args):
            return 0
        else:
            return 1
    
    async def _run_trading_system(self, args: Namespace) -> int:
        """
        Run the trading system with given arguments
        
        Args:
            args: Parsed command arguments
            
        Returns:
            Exit code
        """
        try:
            # Import here to avoid circular imports
            from ...live_system.orchestrator import LiveTradingSystem
            
            # Parse symbols
            symbols = parse_symbols(args.symbols)
            
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
            print("💡 Install with: pip install stratequeue[trading]")
            return 1
        except Exception as e:
            logger.error(f"Error running trading system: {e}")
            print(f"❌ Error running trading system: {e}")
            return 1
    
    async def _run_multi_strategy_system(self, args: Namespace, symbols: List[str], 
                                        enable_trading: bool, paper_trading: bool) -> int:
        """Run multi-strategy trading system"""
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
            
            # Import here to avoid circular imports
            from ...live_system.orchestrator import LiveTradingSystem
            
            # Initialize multi-strategy system
            system = LiveTradingSystem(
                symbols=symbols,
                data_source=args._data_sources[0],
                granularity=args._granularities[0] if args._granularities else None,
                enable_trading=enable_trading,
                multi_strategy_config=temp_config.name,
                broker_type=args._brokers[0] if args._brokers and args._brokers[0] != 'auto' else None,
                paper_trading=paper_trading,
                lookback_override=args.lookback
            )
            
            print(f"🚀 Starting multi-strategy system for {args.duration} minutes...")
            print(f"📈 Strategies: {len(args._strategies)}")
            print(f"💰 Trading mode: {'Paper' if paper_trading else 'Live'}")
            print("")
            
            # Run the system
            await system.run_live_system(args.duration)
            
            print("✅ Multi-strategy system completed successfully")
            return 0
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_config.name)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file: {e}")
    
    async def _run_single_strategy_system(self, args: Namespace, symbols: List[str], 
                                         enable_trading: bool, paper_trading: bool) -> int:
        """Run single strategy trading system"""
        strategy_path = args._strategies[0]
        
        # Get single values for single strategy
        data_source = args._data_sources[0] if args._data_sources else 'demo'
        granularity = args._granularities[0] if args._granularities else None
        broker_type = args._brokers[0] if args._brokers and args._brokers[0] != 'auto' else None
        
        # Import here to avoid circular imports
        from ...live_system.orchestrator import LiveTradingSystem
        
        system = LiveTradingSystem(
            strategy_path=strategy_path,
            symbols=symbols,
            data_source=data_source,
            granularity=granularity,
            enable_trading=enable_trading,
            broker_type=broker_type,
            paper_trading=paper_trading,
            lookback_override=args.lookback
        )
        
        print(f"🚀 Starting single strategy system for {args.duration} minutes...")
        print(f"📊 Strategy: {os.path.basename(strategy_path)}")
        print(f"💰 Trading mode: {'Paper' if paper_trading else 'Live'}")
        print(f"📈 Symbols: {', '.join(symbols)}")
        print("")
        
        # Run the system
        await system.run_live_system(args.duration)
        
        print("✅ Single strategy system completed successfully")
        return 0 