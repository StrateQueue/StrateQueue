"""
Command Line Interface

This module handles:
1. Command-line argument parsing
2. Validation of user inputs
3. Configuration display
4. Main entry point coordination
"""

import argparse
import asyncio
import logging
from typing import List, Tuple, Dict, Any

from ..core.granularity import GranularityParser, validate_granularity
from ..live_system import LiveTradingSystem

logger = logging.getLogger(__name__)

def print_granularity_info():
    """Print information about supported granularities"""
    
    print("\nSupported granularities by data source:")
    print("=" * 50)
    
    for source in ["polygon", "coinmarketcap", "demo"]:
        granularities = GranularityParser.get_supported_granularities(source)
        print(f"\n{source.upper()}:")
        print(f"  Supported: {', '.join(granularities)}")
        if source == "polygon":
            print(f"  Default: 1m (very flexible with most timeframes)")
        elif source == "coinmarketcap":
            print(f"  Default: 1d (historical), supports intraday real-time simulation")
        elif source == "demo":
            print(f"  Default: 1m (can generate any granularity)")
    
    print("\nExample granularity formats:")
    print("  1s   = 1 second")
    print("  30s  = 30 seconds") 
    print("  1m   = 1 minute")
    print("  5m   = 5 minutes")
    print("  1h   = 1 hour")
    print("  1d   = 1 day")
    print()

def print_broker_info():
    """Print information about supported brokers"""
    
    print("\n🏦 Supported Brokers")
    print("=" * 50)
    
    try:
        from ..brokers import list_broker_features, get_supported_brokers
        
        supported_brokers = get_supported_brokers()
        broker_features = list_broker_features()
        
        if not supported_brokers:
            print("❌ No brokers available (missing dependencies)")
            print("\nInstall broker dependencies:")
            print("  pip install stratequeue[trading]  # For Alpaca")
            return
        
        for broker_type in supported_brokers:
            info = broker_features.get(broker_type)
            if info:
                print(f"\n{info.name.upper()} ({broker_type})")
                print(f"  Version: {info.version}")
                print(f"  Description: {info.description}")
                print(f"  Markets: {', '.join(info.supported_markets)}")
                print(f"  Paper Trading: {'✅' if info.paper_trading else '❌'}")
                
                # Show key features
                key_features = []
                for feature, supported in info.supported_features.items():
                    if supported and feature in ['market_orders', 'limit_orders', 'crypto_trading', 'multi_strategy']:
                        key_features.append(feature.replace('_', ' ').title())
                
                if key_features:
                    print(f"  Key Features: {', '.join(key_features)}")
            else:
                print(f"\n{broker_type.upper()}")
                print(f"  ⚠️  Info not available")
        
        print(f"\n📊 Total: {len(supported_brokers)} brokers supported")
        
    except ImportError:
        print("❌ Broker factory not available (missing dependencies)")
        print("\nInstall broker dependencies:")
        print("  pip install stratequeue[trading]")
    except Exception as e:
        print(f"❌ Error loading broker info: {e}")

def print_broker_status():
    """Print detailed broker environment status"""
    
    try:
        from ..brokers.utils import print_broker_environment_status
        print_broker_environment_status()
        
    except ImportError:
        print("❌ Broker utilities not available (missing dependencies)")
        print("\nInstall broker dependencies:")
        print("  pip install stratequeue[trading]")
    except Exception as e:
        print(f"❌ Error checking broker status: {e}")

def print_broker_setup_help(broker_type: str = None):
    """Print broker setup instructions"""
    
    try:
        from ..brokers.utils import suggest_environment_setup
        from ..brokers import get_supported_brokers
        
        if broker_type:
            # Show specific broker setup
            print(f"\n🔧 Setup Instructions for {broker_type.title()}")
            print("=" * 50)
            setup_text = suggest_environment_setup(broker_type)
            print(setup_text)
        else:
            # Show all supported brokers
            print("\n🔧 Broker Setup Instructions")
            print("=" * 50)
            
            supported_brokers = get_supported_brokers()
            for broker in supported_brokers:
                setup_text = suggest_environment_setup(broker)
                print(setup_text)
                print("-" * 30)
        
    except ImportError:
        print("❌ Broker utilities not available (missing dependencies)")
    except Exception as e:
        print(f"❌ Error loading setup instructions: {e}")

def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser"""
    
    parser = argparse.ArgumentParser(
        description='Live Trading System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single strategy mode (paper trading by default)
  python3 main.py --strategy sma.py --symbols AAPL,MSFT --data-source demo
  
  # Multi-strategy mode
  python3 main.py --strategies strategies.txt --symbols AAPL,MSFT --data-source demo
  
  # Run with real Polygon data
  python3 main.py --strategy sma.py --symbols AAPL --data-source polygon --lookback 50
  
  # Paper trading (default behavior)
  python3 main.py --strategy sma.py --symbols AAPL --paper
  
  # Live trading (use with caution!)
  python3 main.py --strategy sma.py --symbols AAPL --live
  
  # Disable trading execution (signals only)
  python3 main.py --strategy sma.py --symbols AAPL --no-trading
  
  # Specify broker explicitly
  python3 main.py --strategy sma.py --symbols AAPL --broker alpaca --paper
  
  # Multi-strategy with live trading
  python3 main.py --strategies strategies.txt --symbols AAPL,MSFT --live
  
  # Information commands
  python3 main.py --list-granularities
  python3 main.py --list-brokers
  python3 main.py --broker-status
  python3 main.py --broker-setup alpaca
        """
    )
    
    # Strategy configuration
    parser.add_argument('--strategy', 
                       help='Path to strategy file for single-strategy mode (e.g., sma.py)')
    
    parser.add_argument('--strategies', 
                       help='Path to multi-strategy configuration file (e.g., strategies.txt)')
    
    # Trading configuration
    parser.add_argument('--symbols', default='AAPL', 
                       help='Comma-separated list of symbols (e.g., AAPL,MSFT)')
    
    parser.add_argument('--data-source', 
                       choices=['demo', 'polygon', 'coinmarketcap'], 
                       default='demo', 
                       help='Data source to use')
    
    parser.add_argument('--granularity', type=str, 
                       help='Data granularity (e.g., 1s, 1m, 5m, 1h, 1d)')
    
    parser.add_argument('--lookback', type=int, 
                       help='Override calculated lookback period')
    
    parser.add_argument('--duration', type=int, default=60, 
                       help='Duration to run in minutes')
    
    # Trading mode configuration
    trading_group = parser.add_mutually_exclusive_group()
    trading_group.add_argument('--paper', action='store_true', default=True,
                              help='Use paper trading (default)')
    trading_group.add_argument('--live', action='store_true',
                              help='Use live trading (requires live credentials)')
    trading_group.add_argument('--no-trading', action='store_true',
                              help='Disable trading execution (signals only)')
    
    # Broker configuration
    parser.add_argument('--broker', type=str,
                       help='Broker to use for trading (auto-detected if not specified)')
    
    # Legacy support (deprecated but maintained for backward compatibility)
    parser.add_argument('--enable-trading', action='store_true',
                       help='(Deprecated) Use --paper or --live instead')
    
    # Information commands
    parser.add_argument('--list-granularities', action='store_true',
                       help='List supported granularities for each data source')
    
    parser.add_argument('--list-brokers', action='store_true',
                       help='List supported brokers and their features')
    
    parser.add_argument('--broker-status', action='store_true',
                       help='Show broker environment variable status')
    
    parser.add_argument('--broker-setup', type=str, nargs='?', const='all',
                       help='Show broker setup instructions (specify broker type or "all")')
    
    # Logging
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Enable verbose logging')
    
    return parser

def validate_arguments(args: argparse.Namespace) -> Tuple[bool, List[str]]:
    """
    Validate parsed arguments
    
    Args:
        args: Parsed arguments
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    # Handle info requests (no validation needed)
    if any([args.list_granularities, args.list_brokers, args.broker_status, args.broker_setup]):
        return True, []
    
    # Handle legacy --enable-trading flag
    if args.enable_trading:
        print("⚠️  WARNING: --enable-trading is deprecated. Use --paper or --live instead.")
        if not (args.paper or args.live or args.no_trading):
            # Default to paper trading for legacy compatibility
            args.paper = True
    
    # Determine trading mode
    enable_trading = not args.no_trading
    paper_trading = args.paper or (not args.live and not args.no_trading)  # Default to paper
    
    # Either strategy or strategies is required, but not both
    if not args.strategy and not args.strategies:
        errors.append("Either --strategy (single-strategy mode) or --strategies (multi-strategy mode) is required")
    elif args.strategy and args.strategies:
        errors.append("Cannot use both --strategy and --strategies. Choose single-strategy or multi-strategy mode.")
    
    # Validate strategy file exists (single-strategy mode)
    if args.strategy:
        import os
        if not os.path.exists(args.strategy):
            errors.append(f"Strategy file not found: {args.strategy}")
    
    # Validate strategies config file exists (multi-strategy mode)
    if args.strategies:
        import os
        if not os.path.exists(args.strategies):
            errors.append(f"Multi-strategy config file not found: {args.strategies}")
    
    # Validate granularity for the chosen data source
    if args.granularity:
        is_valid, error_msg = validate_granularity(args.granularity, args.data_source)
        if not is_valid:
            errors.append(f"Invalid granularity: {error_msg}")
    
    # Validate symbols format
    try:
        symbols = [s.strip().upper() for s in args.symbols.split(',')]
        if not symbols or any(not s for s in symbols):
            errors.append("Invalid symbols format. Use comma-separated list like 'AAPL,MSFT'")
    except Exception:
        errors.append("Error parsing symbols")
    
    # Validate duration
    if args.duration <= 0:
        errors.append("Duration must be a positive number")
    
    # Validate lookback
    if args.lookback is not None and args.lookback <= 0:
        errors.append("Lookback period must be a positive number")
    
    # Validate broker if specified
    if args.broker:
        try:
            from ..brokers import get_supported_brokers
            supported = get_supported_brokers()
            if args.broker not in supported:
                errors.append(f"Unsupported broker '{args.broker}'. Supported: {', '.join(supported)}")
        except ImportError:
            errors.append("Broker functionality not available (missing dependencies)")
    
    # Validate trading requirements
    if enable_trading:
        try:
            from ..brokers import detect_broker_type, validate_broker_credentials
            
            # If broker specified, validate it
            if args.broker:
                if not validate_broker_credentials(args.broker):
                    trading_mode = "paper" if paper_trading else "live"
                    errors.append(f"Invalid {trading_mode} trading credentials for broker '{args.broker}'. Check environment variables.")
            else:
                # Auto-detect broker
                detected_broker = detect_broker_type()
                if detected_broker == 'unknown':
                    trading_mode = "paper" if paper_trading else "live"
                    errors.append(f"No broker detected from environment for {trading_mode} trading. Set up broker credentials or use --broker to specify.")
                elif not validate_broker_credentials(detected_broker):
                    trading_mode = "paper" if paper_trading else "live"
                    errors.append(f"Invalid {trading_mode} trading credentials for detected broker '{detected_broker}'. Check environment variables.")
            
            # Special validation for live trading
            if args.live:
                print("🚨 LIVE TRADING MODE ENABLED")
                print("⚠️  You are about to trade with real money!")
                print("💰 Please ensure you have tested your strategy thoroughly in paper trading first.")
                
        except ImportError:
            errors.append("Trading functionality not available (missing dependencies). Install with: pip install stratequeue[trading]")
    
    # Store computed values in args for later use
    args._enable_trading = enable_trading
    args._paper_trading = paper_trading
    
    return len(errors) == 0, errors

def determine_granularity(args: argparse.Namespace) -> str:
    """
    Determine the granularity to use based on args and defaults
    
    Args:
        args: Parsed arguments
        
    Returns:
        Granularity string to use
    """
    if args.granularity:
        return args.granularity
    
    # Use defaults based on data source
    defaults = {
        "polygon": "1m",
        "coinmarketcap": "1d", 
        "demo": "1m"
    }
    
    granularity = defaults.get(args.data_source, "1m")
    logger.info(f"Using default granularity {granularity} for {args.data_source}")
    
    return granularity

def determine_broker(args: argparse.Namespace) -> str:
    """
    Determine the broker to use based on args and auto-detection
    
    Args:
        args: Parsed arguments
        
    Returns:
        Broker type string
    """
    if args.broker:
        logger.info(f"Using specified broker: {args.broker}")
        return args.broker
    
    # Auto-detect broker based on trading mode
    try:
        from ..brokers import detect_broker_type
        detected = detect_broker_type()
        if detected != 'unknown':
            trading_mode = "paper" if args._paper_trading else "live"
            logger.info(f"Auto-detected broker: {detected} ({trading_mode} trading)")
            return detected
        else:
            trading_mode = "paper" if args._paper_trading else "live"
            logger.warning(f"No broker auto-detected from environment for {trading_mode} trading")
            return 'unknown'
    except ImportError:
        logger.error("Broker detection not available (missing dependencies)")
        return 'unknown'

def parse_symbols(symbols_str: str) -> List[str]:
    """
    Parse symbols string into list
    
    Args:
        symbols_str: Comma-separated symbols string
        
    Returns:
        List of symbol strings
    """
    return [s.strip().upper() for s in symbols_str.split(',')]

def setup_logging(verbose: bool = False):
    """
    Setup logging configuration
    
    Args:
        verbose: Enable verbose (DEBUG) logging
    """
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('trading_system.log')
        ]
    )

async def run_trading_system(args: argparse.Namespace) -> int:
    """
    Run the trading system with parsed arguments
    
    Args:
        args: Parsed and validated arguments
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Determine granularity and parse symbols
        granularity = determine_granularity(args)
        symbols = parse_symbols(args.symbols)
        
        # Get trading configuration
        enable_trading = args._enable_trading
        paper_trading = args._paper_trading
        
        # Determine broker if trading is enabled
        broker_type = None
        if enable_trading:
            broker_type = determine_broker(args)
            if broker_type == 'unknown':
                trading_mode = "paper" if paper_trading else "live"
                logger.error(f"No valid broker found for {trading_mode} trading")
                return 1
        
        # Log trading configuration
        if enable_trading:
            trading_mode = "paper" if paper_trading else "live"
            logger.info(f"Trading enabled: {trading_mode.upper()} mode via {broker_type}")
        else:
            logger.info("Trading disabled: signals only mode")
        
        # Determine mode and create trading system
        if args.strategies:
            # Multi-strategy mode
            system = LiveTradingSystem(
                symbols=symbols,
                data_source=args.data_source,
                granularity=granularity,
                lookback_override=args.lookback,
                enable_trading=enable_trading,
                multi_strategy_config=args.strategies,
                broker_type=broker_type,
                paper_trading=paper_trading
            )
        else:
            # Single-strategy mode
            system = LiveTradingSystem(
                strategy_path=args.strategy,
                symbols=symbols,
                data_source=args.data_source,
                granularity=granularity,
                lookback_override=args.lookback,
                enable_trading=enable_trading,
                broker_type=broker_type,
                paper_trading=paper_trading
            )
        
        # Run the system
        await system.run_live_system(duration_minutes=args.duration)
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to start system: {e}")
        print(f"\n❌ Error: {e}")
        return 1

def main() -> int:
    """
    Main CLI entry point
    
    Returns:
        Exit code
    """
    # Create and parse arguments
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Handle information requests
    if args.list_granularities:
        print_granularity_info()
        return 0
    
    if args.list_brokers:
        print_broker_info()
        return 0
    
    if args.broker_status:
        print_broker_status()
        return 0
    
    if args.broker_setup:
        if args.broker_setup == 'all':
            print_broker_setup_help()
        else:
            print_broker_setup_help(args.broker_setup)
        return 0
    
    # Validate arguments
    is_valid, errors = validate_arguments(args)
    if not is_valid:
        for error in errors:
            print(f"Error: {error}")
        print(f"\nUse --list-brokers to see supported brokers.")
        print(f"Use --broker-status to check your broker setup.")
        print(f"Use --broker-setup <broker> for setup instructions.")
        return 1
    
    # Run the trading system
    try:
        return asyncio.run(run_trading_system(args))
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"❌ Unexpected error: {e}")
        return 1 