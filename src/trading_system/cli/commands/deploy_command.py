"""Deploy Command

Main deploy command implementation that orchestrates strategy deployment
including validation, daemon mode, and trading system execution.
"""

import asyncio
import argparse
import logging
import tempfile
import os
import signal
import threading
import time
from argparse import Namespace
from typing import List

from .base_command import BaseCommand
from ..validators.deploy_validator import DeployValidator
from ..formatters.base_formatter import BaseFormatter
from ..utils.deploy_utils import setup_logging, create_inline_strategy_config, parse_symbols
from ..utils.daemon_manager import DaemonManager

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
        
        # Check for existing daemon first
        daemon_manager = DaemonManager()
        success, existing_system, error = daemon_manager.load_daemon_system()
        
        if success and existing_system:
            if args.daemon:
                # Add strategy to existing daemon (hotswap functionality)
                print(f"🔗 Found existing daemon (PID: {existing_system.get('pid')})")
                return self._add_strategy_to_existing_daemon(args, existing_system, daemon_manager)
            else:
                # Warn user about existing daemon
                print("⚠️  A daemon is already running!")
                print(f"   PID: {existing_system.get('pid')}")
                strategies = existing_system.get('strategies', {})
                print(f"   Strategies: {len(strategies)} active")
                for strategy_id, info in strategies.items():
                    status = info.get('status', 'unknown')
                    print(f"     • {strategy_id} ({status})")
                print("")
                print("💡 Options:")
                print("   --daemon           Add strategy to existing daemon")
                print("   stratequeue stop   Stop existing daemon first")
                return 1
        
        # Handle daemon mode (no existing daemon)
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
        print("  # Test strategy (default mode)")
        print("  stratequeue deploy --strategy sma.py --symbol AAPL")
        print("")
        print("  # Paper trading (fake money)")  
        print("  stratequeue deploy --strategy sma.py --symbol AAPL --paper")
        print("")
        print("  # Live trading (real money - be careful!)")
        print("  stratequeue deploy --strategy sma.py --symbol AAPL --live")
    
    def _handle_daemon_mode(self, args: Namespace) -> int:
        """Handle daemon mode execution"""
        daemon_manager = DaemonManager()
        
        print("🔄 Starting Stratequeue in daemon mode...")
        print("💡 You can now use pause/resume/stop commands in this terminal")
        print("")
        
        try:
            # Setup signal handlers for graceful shutdown
            def signal_handler(signum, frame):
                print(f"\n📡 Received signal {signum}, shutting down gracefully...")
                daemon_manager.ipc.stop_command_server()  # Stop IPC server
                daemon_manager.cleanup_daemon_files()
                exit(0)
            
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
            
            # Get PID file path for later use
            pid_file_path = daemon_manager.get_pid_file_path()
            
            print(f"🚀 Launching trading system in background...")
            print(f"✅ System started (PID: {os.getpid()})")
            print("")
            print("🔥 Management commands now available:")
            print("  stratequeue pause <strategy_id>")
            print("  stratequeue resume <strategy_id>")
            print("  stratequeue stop")
            print("")
            
            # Run the trading system in a separate thread
            system_thread = threading.Thread(
                target=self._run_trading_system_in_thread,
                args=(args, daemon_manager),
                daemon=True
            )
            system_thread.start()
            
            print("📡 Daemon running... (Press Ctrl+C to stop)")
            
            # Keep main process alive
            try:
                while system_thread.is_alive():
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n👋 Daemon stopped")
                daemon_manager.cleanup_daemon_files()
            
            return 0
            
        except Exception as e:
            print(f"❌ Failed to start daemon: {e}")
            daemon_manager.cleanup_daemon_files()
            return 1
    
    def _add_strategy_to_existing_daemon(self, args: Namespace, system_info: dict, daemon_manager: DaemonManager) -> int:
        """
        Add strategy to existing daemon (hotswap deploy functionality)
        
        Args:
            args: Parsed command arguments
            system_info: Existing daemon system information
            daemon_manager: Daemon manager instance
            
        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            # Parse new strategy info
            strategy_path = args._strategies[0]
            base_strategy_id = os.path.basename(strategy_path).replace('.py', '')
            symbols = parse_symbols(args.symbol)
            
            # Check if strategy already exists and generate unique ID if needed
            existing_strategies = system_info.get('strategies', {})
            strategy_id = self._generate_unique_strategy_id(base_strategy_id, symbols, existing_strategies)
            
            # Show strategy ID information
            if strategy_id != base_strategy_id:
                print(f"🔄 Strategy ID auto-generated: '{strategy_id}' (base: '{base_strategy_id}')")
                print(f"💡 This avoids conflicts with existing strategies")
            else:
                print(f"📝 Using strategy ID: '{strategy_id}'")
            
            # Use specified allocation from command line arguments
            num_existing = len(existing_strategies)
            if hasattr(args, '_allocations') and args._allocations:
                new_allocation = float(args._allocations[0])
                allocation_description = f"specified allocation"
            else:
                # Fallback to equal weight if no allocation specified
                new_allocation = 1.0 / (num_existing + 1)
                allocation_description = f"equal weight with {num_existing} existing"
            
            print(f"🚀 Adding strategy '{strategy_id}' to daemon...")
            print(f"📊 New allocation: {new_allocation:.1%} ({allocation_description})")
            print(f"📈 Symbols: {', '.join(symbols)}")
            
            # Use symbol for 1:1 mapping if single symbol, None for all symbols
            target_symbol = symbols[0] if len(symbols) == 1 else None
            
            # Send hotswap command via IPC
            command = {
                'type': 'add_strategy',
                'strategy_path': strategy_path,
                'strategy_id': strategy_id,
                'allocation': new_allocation,
                'symbol': target_symbol
            }
            
            response = daemon_manager.ipc.send_command(command)
            
            if response.get('success'):
                print(f"✅ Successfully added strategy '{strategy_id}' to daemon")
                print("🔄 Portfolio automatically rebalanced to accommodate new strategy")
                print("")
                print("🔥 Strategy now active in daemon! Available commands:")
                print(f"  stratequeue pause {strategy_id}")
                print(f"  stratequeue resume {strategy_id}")
                print("  stratequeue stop")
                return 0
            else:
                error_msg = response.get('error', 'Unknown error')
                print(f"❌ Failed to add strategy '{strategy_id}': {error_msg}")
                return 1
                
        except Exception as e:
            logger.error(f"Error adding strategy to daemon: {e}")
            print(f"❌ Error adding strategy to daemon: {e}")
            return 1
    
    def _generate_unique_strategy_id(self, base_strategy_id: str, symbols: list, existing_strategies: dict) -> str:
        """
        Generate a unique strategy ID by appending symbol and timestamp if needed
        
        Args:
            base_strategy_id: Base strategy ID from filename
            symbols: List of symbols for this strategy
            existing_strategies: Dictionary of existing strategy IDs
            
        Returns:
            Unique strategy ID
        """
        # First, try the base strategy ID
        if base_strategy_id not in existing_strategies:
            return base_strategy_id
        
        # If conflict, generate unique ID with symbol and timestamp
        import time
        from datetime import datetime
        
        # Use first symbol for naming
        symbol = symbols[0] if symbols else "MULTI"
        
        # Generate timestamp (compact format: YYMMDD_HHMM)
        timestamp = datetime.now().strftime("%y%m%d_%H%M")
        
        # Create enhanced strategy ID: base_symbol_timestamp
        unique_id = f"{base_strategy_id}_{symbol}_{timestamp}"
        
        # Final safety check - if somehow this still conflicts, add a counter
        counter = 1
        original_unique_id = unique_id
        while unique_id in existing_strategies:
            unique_id = f"{original_unique_id}_{counter}"
            counter += 1
        
        return unique_id
    
    def _create_daemon_system_info(self, args: Namespace) -> dict:
        """Create basic system info for daemon storage"""
        # Parse symbols to get strategy info
        symbols = parse_symbols(args.symbol)
        
        # Determine if multi-strategy mode - force it for daemon mode to enable hotswap
        is_multi_strategy = (hasattr(args, '_strategies') and len(args._strategies) > 1) or args.daemon
        
        if is_multi_strategy:
            strategies = {}
            for i, strategy_path in enumerate(args._strategies):
                strategy_id = args._strategy_ids[i] if args._strategy_ids else os.path.basename(strategy_path).replace('.py', '')
                strategies[strategy_id] = {
                    'class': strategy_id,
                    'status': 'active',
                    'allocation': float(args._allocations[i]) if args._allocations else None,
                    'symbols': symbols,
                    'path': strategy_path
                }
        else:
            strategy_path = args._strategies[0]
            strategy_id = os.path.basename(strategy_path).replace('.py', '')
            strategies = {
                strategy_id: {
                    'class': strategy_id,
                    'status': 'active',
                    'allocation': 1.0,
                    'symbols': symbols,
                    'path': strategy_path
                }
            }
        
        return {
            'strategies': strategies,
            'mode': 'multi-strategy' if is_multi_strategy else 'single-strategy',
            'args': vars(args)
        }
    
    def _create_daemon_system_info_from_system(self, trading_system: any, original_info: dict) -> dict:
        """
        Create updated daemon system info from running trading system
        
        Args:
            trading_system: Running trading system instance
            original_info: Original daemon info to preserve
            
        Returns:
            Updated system info dictionary
        """
        try:
            # Preserve original system instance and metadata
            updated_info = original_info.copy()
            updated_info['system'] = trading_system
            
            # Update strategies info if possible
            if hasattr(trading_system, 'get_deployed_strategies'):
                strategy_ids = trading_system.get_deployed_strategies()
                strategies = {}
                
                for strategy_id in strategy_ids:
                    # Get strategy status and allocation
                    status = getattr(trading_system, 'get_strategy_status', lambda x: 'active')(strategy_id)
                    
                    # Try to get allocation from portfolio manager
                    allocation = 1.0 / len(strategy_ids)  # Default equal allocation
                    if hasattr(trading_system, 'multi_strategy_runner'):
                        runner = trading_system.multi_strategy_runner
                        if hasattr(runner, 'get_strategy_allocation'):
                            allocation = runner.get_strategy_allocation(strategy_id)
                    
                    strategies[strategy_id] = {
                        'class': strategy_id,
                        'status': status,
                        'allocation': allocation,
                        'symbols': updated_info.get('args', {}).get('symbol', ['AAPL']),
                        'path': f"{strategy_id}.py"  # Approximation
                    }
                
                updated_info['strategies'] = strategies
            
            return updated_info
            
        except Exception as e:
            logger.warning(f"Could not update daemon system info: {e}")
            # Return original with updated system instance
            updated_info = original_info.copy()
            updated_info['system'] = trading_system
            return updated_info
    
    def _run_trading_system_in_thread(self, args: Namespace, daemon_manager: DaemonManager) -> None:
        """Run trading system in background thread"""
        try:
            # Setup logging in daemon thread
            from ..utils.deploy_utils import setup_logging
            setup_logging(verbose=getattr(args, 'verbose', False))
            
            # Remove daemon flag to prevent recursion
            args_copy = Namespace(**vars(args))
            args_copy.daemon = False
            
            # Run trading system with daemon storage
            result = asyncio.run(self._run_trading_system_with_daemon_storage(args_copy, daemon_manager))
            
        except Exception as e:
            print(f"[DAEMON] Error: {e}")
        finally:
            # Cleanup when system stops
            daemon_manager.cleanup_daemon_files()
    
    async def _run_trading_system_with_daemon_storage(self, args: Namespace, daemon_manager: DaemonManager) -> int:
        """
        Run trading system and store in daemon manager for hotswap support
        
        Args:
            args: Parsed command arguments
            daemon_manager: Daemon manager instance
            
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
            
            # Force multi-strategy mode for daemon to enable hotswap
            # Create a simple multi-strategy config
            import tempfile
            temp_config_content = self._create_daemon_multi_strategy_config(args)
            temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
            try:
                temp_config.write(temp_config_content)
                temp_config.close()
                
                # Initialize multi-strategy system for daemon
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
                
                # Store essential daemon info for hotswap (avoid pickling issues)
                strategies_info = self._extract_strategies_from_system(system, args)
                daemon_info = {
                    'pid': os.getpid(),
                    'system': system,  # Store reference for this process (not pickled)
                    'start_time': time.time(),
                    'strategies': strategies_info,
                    'mode': 'multi-strategy',
                    'symbols': symbols,
                    'args': vars(args)
                }
                daemon_manager.store_daemon_system(daemon_info)
                
                # Start IPC command server for hotswap operations
                daemon_manager.ipc.start_command_server(system)
                
                print(f"[DAEMON] System stored for hotswap operations")
                print(f"[DAEMON] IPC command server started")
                
                print(f"🚀 Starting daemon system for {args.duration} minutes...")
                print(f"📊 Mode: Multi-strategy (hotswap enabled)")
                print(f"💰 Trading mode: {'Paper' if paper_trading else 'Live'}")
                print("")
                
                # Run the system
                await system.run_live_system(args.duration)
                
                print("✅ Daemon system completed successfully")
                return 0
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_config.name):
                    os.unlink(temp_config.name)
                    
        except ImportError as e:
            logger.error(f"Trading system not available: {e}")
            print(f"❌ Trading system not available: {e}")
            print("💡 Install with: pip install stratequeue[trading]")
            return 1
        except Exception as e:
            logger.error(f"Error running daemon system: {e}")
            print(f"❌ Error running daemon system: {e}")
            return 1
    
    def _create_daemon_multi_strategy_config(self, args: Namespace) -> str:
        """Create multi-strategy config for daemon mode"""
        # Extract strategy info
        strategy_path = args._strategies[0]
        strategy_id = os.path.basename(strategy_path).replace('.py', '')
        allocation = args._allocations[0] if args._allocations else 1.0
        
        # Get the symbol for this strategy
        symbols = parse_symbols(args.symbol)
        symbol = symbols[0] if symbols else 'AAPL'
        
        # Create CSV content for single strategy in multi-strategy format
        # Format: filename,strategy_id,allocation_percentage,symbol (1:1 mapping)
        content = f"{strategy_path},{strategy_id},{allocation},{symbol}\n"
        
        return content
    
    def _extract_strategies_from_system(self, system: any, args: Namespace) -> dict:
        """Extract strategy information safely for daemon storage"""
        try:
            strategies = {}
            
            # Extract from multi-strategy runner if available
            if hasattr(system, 'multi_strategy_runner'):
                runner = system.multi_strategy_runner
                
                print(f"🔍 Extracting strategies from multi-strategy runner...")
                
                # Use proper API methods instead of direct attribute access
                try:
                    # Get strategy configs using proper API
                    strategy_configs = runner.get_strategy_configs()
                    strategy_statuses = runner.get_all_strategy_statuses()
                    
                    print(f"📋 Found {len(strategy_configs)} strategy configs")
                    
                    for strategy_id, config in strategy_configs.items():
                        # Get real status from signal coordinator
                        status = strategy_statuses.get(strategy_id, 'active')
                        
                        # Get current allocation from portfolio manager
                        try:
                            allocation = runner.get_strategy_allocation(strategy_id)
                        except:
                            allocation = getattr(config, 'allocation', 1.0)
                        
                        # Get symbols for this strategy
                        if hasattr(config, 'symbol') and config.symbol:
                            symbols = [config.symbol]
                        elif hasattr(runner, 'symbols') and runner.symbols:
                            symbols = runner.symbols
                        else:
                            symbols = args.symbol.split(',') if isinstance(args.symbol, str) else [args.symbol]
                        
                        strategies[strategy_id] = {
                            'class': strategy_id,
                            'status': status,
                            'allocation': allocation,
                            'symbols': symbols,
                            'path': getattr(config, 'file_path', 'unknown')
                        }
                        print(f"   📋 {strategy_id}: {status}, {allocation:.1%}, {symbols}")
                        
                except Exception as api_error:
                    print(f"⚠️  Failed to use API methods, falling back to direct access: {api_error}")
                    # Fallback to direct access if API methods fail
                    if hasattr(runner, 'config_manager'):
                        config_manager = runner.config_manager
                        if hasattr(config_manager, 'strategy_configs'):
                            for strategy_id, config in config_manager.strategy_configs.items():
                                strategies[strategy_id] = {
                                    'class': strategy_id,
                                    'status': 'active',
                                    'allocation': getattr(config, 'allocation', 1.0),
                                    'symbols': args.symbol.split(',') if isinstance(args.symbol, str) else [args.symbol],
                                    'path': getattr(config, 'file_path', 'unknown')
                                }
            
            # Fallback: single strategy from args
            if not strategies:
                print("🔍 No multi-strategy runner found, using single strategy from args")
                strategy_path = args._strategies[0]
                strategy_id = os.path.basename(strategy_path).replace('.py', '')
                strategies[strategy_id] = {
                    'class': strategy_id,
                    'status': 'active',
                    'allocation': 1.0,
                    'symbols': args.symbol.split(',') if isinstance(args.symbol, str) else [args.symbol],
                    'path': strategy_path
                }
                print(f"   📋 {strategy_id}: active, 100%, {strategies[strategy_id]['symbols']}")
            
            print(f"✅ Successfully extracted {len(strategies)} strategies for daemon storage")
            return strategies
            
        except Exception as e:
            logger.warning(f"Could not extract strategy info: {e}")
            print(f"⚠️  Warning: Could not extract strategy info: {e}")
            # Return basic info from args as final fallback
            strategy_path = args._strategies[0]
            strategy_id = os.path.basename(strategy_path).replace('.py', '')
            fallback_strategy = {
                strategy_id: {
                    'class': strategy_id,
                    'status': 'active',
                    'allocation': 1.0,
                    'symbols': [args.symbol],
                    'path': strategy_path
                }
            }
            print(f"   📋 Fallback: {strategy_id}: active, 100%, {fallback_strategy[strategy_id]['symbols']}")
            return fallback_strategy
    
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
            symbols = parse_symbols(args.symbol)
            
            # Determine trading configuration
            enable_trading = args._enable_trading
            paper_trading = args._paper_trading
            
            # Determine if multi-strategy mode - force it for daemon mode to enable hotswap
            is_multi_strategy = (hasattr(args, '_strategies') and len(args._strategies) > 1) or args.daemon
            
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
            if os.path.exists(temp_config.name):
                os.unlink(temp_config.name)
    
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