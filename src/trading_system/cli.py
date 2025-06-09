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

from .granularity import GranularityParser, validate_granularity
from .live_trading_system import LiveTradingSystem

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

def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser"""
    
    parser = argparse.ArgumentParser(
        description='Live Trading System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with SMA strategy on demo data
  python3 main.py --strategy sma.py --symbols AAPL,MSFT --data-source demo
  
  # Run with real Polygon data
  python3 main.py --strategy sma.py --symbols AAPL --data-source polygon --lookback 50
  
  # Enable paper trading via Alpaca
  python3 main.py --strategy sma.py --symbols AAPL --enable-trading
  
  # Show granularity options
  python3 main.py --list-granularities
        """
    )
    
    parser.add_argument('--strategy', 
                       help='Path to strategy file (e.g., sma.py)')
    
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
    
    parser.add_argument('--list-granularities', action='store_true',
                       help='List supported granularities for each data source')
    
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Enable verbose logging')
    
    parser.add_argument('--enable-trading', action='store_true', 
                       help='Enable actual trading execution via Alpaca (requires .env setup)')
    
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
    
    # Handle granularity info request
    if args.list_granularities:
        return True, []  # No validation needed for info request
    
    # Strategy is required for normal operation
    if not args.strategy:
        errors.append("--strategy is required when not using --list-granularities")
    
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
        
        # Create and run the trading system
        system = LiveTradingSystem(
            strategy_path=args.strategy,
            symbols=symbols,
            data_source=args.data_source,
            granularity=granularity,
            lookback_override=args.lookback,
            enable_trading=args.enable_trading
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
    
    # Handle granularity info request
    if args.list_granularities:
        print_granularity_info()
        return 0
    
    # Validate arguments
    is_valid, errors = validate_arguments(args)
    if not is_valid:
        for error in errors:
            print(f"Error: {error}")
        print(f"\nUse --list-granularities to see supported options.")
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