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
  # Single strategy mode
  python3 main.py --strategy sma.py --symbols AAPL,MSFT --data-source demo
  
  # Multi-strategy mode (comma-separated values)
  python3 main.py --strategy sma.py,momentum.py,random.py --allocation 0.4,0.35,0.25 --symbols AAPL,MSFT --data-source demo
  
  # Multi-strategy with 1:1 strategy-symbol mapping
  python3 main.py --strategy sma.py,random.py --allocation 0.5,0.5 --symbols ETH,AAPL --data-source demo
  
  # Multi-strategy with custom strategy IDs
  python3 main.py --strategy sma.py,momentum.py --strategy-id sma_cross,momentum_trend --allocation 0.6,0.4 --symbols AAPL
  
  # Multi-strategy with dollar allocations
  python3 main.py --strategy sma.py,momentum.py --allocation 1000,500 --symbols AAPL --broker alpaca --paper
  
  # Multi-strategy with different granularities per strategy
  python3 main.py --strategy sma.py,momentum.py --allocation 0.6,0.4 --granularity 1m,5m --symbols ETH,BTC
  
  # Multi-strategy with different data sources per strategy  
  python3 main.py --strategy sma.py,momentum.py --allocation 0.6,0.4 --data-source polygon,coinmarketcap --symbols AAPL,ETH
  
  # Single value applies to all strategies
  python3 main.py --strategy sma.py,momentum.py --allocation 0.5,0.5 --granularity 1m --broker alpaca --symbols ETH
  
  # Run with real Polygon data
  python3 main.py --strategy sma.py --symbols AAPL --data-source polygon --lookback 50
  
  # Paper trading (default behavior)
  python3 main.py --strategy sma.py --symbols AAPL --paper
  
  # Live trading (use with caution!)
  python3 main.py --strategy sma.py --symbols AAPL --live
  
  # Disable trading execution (signals only)
  python3 main.py --strategy sma.py --symbols AAPL --no-trading
  
  # Multi-strategy with live trading
  python3 main.py --strategy sma.py,momentum.py --allocation 0.6,0.4 --symbols AAPL,MSFT --live
  
  # Information commands
  python3 main.py --list-granularities
  python3 main.py --list-brokers
  python3 main.py --broker-status
  python3 main.py --broker-setup alpaca
        """
    )
    
    # Strategy configuration
    strategy_group = parser.add_argument_group('Strategy Configuration')

    # All arguments now use comma-separated values for consistency
    strategy_group.add_argument('--strategy', required=True,
                       help='Strategy file(s). Single or comma-separated list (e.g., sma.py or sma.py,momentum.py,random.py)')

    strategy_group.add_argument('--strategy-id',
                       help='Strategy identifier(s). Optional - defaults to strategy filename(s). Single value or comma-separated list matching strategies.')

    strategy_group.add_argument('--allocation',
                       help='Strategy allocation(s) as percentage (0-1) or dollar amount. Single value or comma-separated list (e.g., 0.4 or 0.4,0.35,0.25). Required for multi-strategy mode.')

    # Trading configuration - now supports multiple values with smart defaulting
    parser.add_argument('--symbols', default='AAPL', 
                       help='Symbol(s) to trade. Single or comma-separated list (e.g., AAPL or ETH,BTC,AAPL). When number of symbols equals number of strategies, creates 1:1 mapping.')
    
    parser.add_argument('--data-source', default='demo',
                       help='Data source(s). Single value applies to all, or comma-separated list matching strategies (e.g., demo or polygon,coinmarketcap)')
    
    parser.add_argument('--granularity', 
                       help='Data granularity/granularities. Single value applies to all, or comma-separated list matching strategies (e.g., 1m or 1m,5m,1h)')
    
    parser.add_argument('--broker',
                       help='Broker(s) for trading. Single value applies to all, or comma-separated list matching strategies (e.g., alpaca or alpaca,kraken)')
    
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
    
    # Validate strategy configuration
    if args.strategy:
        import os
        
        # Parse comma-separated strategies
        strategies = parse_comma_separated(args.strategy)
        if not strategies:
            errors.append("At least one strategy is required")
            return False, errors
        
        # Validate all strategy files exist
        for strategy in strategies:
            if not os.path.exists(strategy):
                errors.append(f"Strategy file not found: {strategy}")
        
        # Parse other comma-separated arguments
        strategy_ids = parse_comma_separated(args.strategy_id) if args.strategy_id else []
        allocations = parse_comma_separated(args.allocation) if args.allocation else []
        data_sources = parse_comma_separated(args.data_source) if args.data_source else ['demo']
        granularities = parse_comma_separated(args.granularity) if args.granularity else []
        brokers = parse_comma_separated(args.broker) if args.broker else []
        
        # Apply smart defaults for multi-value arguments
        try:
            if len(strategies) > 1:
                # Multi-strategy validation
                if not allocations:
                    errors.append("--allocation is required for multi-strategy mode")
                else:
                    allocations = apply_smart_defaults(allocations, len(strategies), "--allocation")
                
                # Apply smart defaults for other arguments
                data_sources = apply_smart_defaults(data_sources, len(strategies), "--data-source")
                if granularities:
                    granularities = apply_smart_defaults(granularities, len(strategies), "--granularity")
                if brokers:
                    brokers = apply_smart_defaults(brokers, len(strategies), "--broker")
                if strategy_ids:
                    strategy_ids = apply_smart_defaults(strategy_ids, len(strategies), "--strategy-id")
            else:
                # Single strategy - ensure single values
                data_sources = data_sources[:1] if data_sources else ['demo']
                granularities = granularities[:1] if granularities else []
                brokers = brokers[:1] if brokers else []
                if not allocations:
                    allocations = ['1.0']
                else:
                    allocations = allocations[:1]
                
        except ValueError as e:
            errors.append(str(e))
        
        # Validate allocation values if we have them
        if allocations:
            total_percentage_allocation = 0.0
            total_dollar_allocation = 0.0
            has_percentage = False
            has_dollar = False
            
            for i, allocation_str in enumerate(allocations):
                try:
                    allocation_value = float(allocation_str)
                    
                    if allocation_value <= 0:
                        errors.append(f"Allocation {i+1} must be positive, got {allocation_value}")
                        continue
                    
                    # Determine if this is percentage (0-1) or dollar amount (>1)
                    if allocation_value <= 1:
                        # Percentage allocation
                        has_percentage = True
                        total_percentage_allocation += allocation_value
                    else:
                        # Dollar allocation
                        has_dollar = True
                        total_dollar_allocation += allocation_value
                        
                except ValueError:
                    errors.append(f"Invalid allocation value: {allocation_str}. Must be a number.")
            
            # Check for mixing allocation types
            if has_percentage and has_dollar:
                errors.append("Cannot mix percentage (0-1) and dollar (>1) allocations. Use one type consistently.")
            
            # Validate percentage allocations sum to reasonable amount
            if has_percentage and total_percentage_allocation > 1.01:  # Allow small rounding errors
                errors.append(f"Total percentage allocation is {total_percentage_allocation:.1%}, which exceeds 100%")
            elif has_percentage and total_percentage_allocation < 0.01:
                errors.append(f"Total percentage allocation is {total_percentage_allocation:.1%}, which is too small")
        
        # Generate strategy IDs if not provided
        if not strategy_ids:
            strategy_ids = []
            for strategy_path in strategies:
                # Use filename without extension as default strategy ID
                strategy_filename = os.path.basename(strategy_path)
                strategy_id = os.path.splitext(strategy_filename)[0]
                strategy_ids.append(strategy_id)
        
        # Store parsed values back to args for later use
        args._strategies = strategies
        args._strategy_ids = strategy_ids
        args._allocations = allocations
        args._data_sources = data_sources
        args._granularities = granularities
        args._brokers = brokers
    
    # Validate granularity for the chosen data source(s)
    if hasattr(args, '_granularities') and args._granularities:
        for i, granularity in enumerate(args._granularities):
            data_source = args._data_sources[i] if i < len(args._data_sources) else args._data_sources[0]
            is_valid, error_msg = validate_granularity(granularity, data_source)
            if not is_valid:
                errors.append(f"Invalid granularity '{granularity}' for data source '{data_source}': {error_msg}")
    
    # Validate symbols format
    try:
        symbols = parse_symbols(args.symbols)
        if not symbols or any(not s for s in symbols):
            errors.append("Invalid symbols format. Use comma-separated list like 'AAPL,MSFT'")
    except Exception:
        errors.append("Error parsing symbols")
    
    # Validate 1:1 strategy-symbol mapping if applicable
    if hasattr(args, '_strategies') and len(args._strategies) > 1:
        try:
            if len(args._strategies) == len(symbols):
                print(f"📌 1:1 Strategy-Symbol mapping detected:")
                for i, (strategy, symbol) in enumerate(zip(args._strategies, symbols)):
                    strategy_name = os.path.basename(strategy).replace('.py', '')
                    print(f"   {strategy_name} → {symbol}")
                print()
        except:
            pass  # symbols might not be parsed yet, ignore validation here
    
    # Validate duration
    if args.duration <= 0:
        errors.append("Duration must be a positive number")
    
    # Validate lookback
    if args.lookback is not None and args.lookback <= 0:
        errors.append("Lookback period must be a positive number")
    
    # Validate broker(s) if specified
    if hasattr(args, '_brokers') and args._brokers and args._brokers[0]:  # Check if first broker is not empty
        try:
            from ..brokers import get_supported_brokers
            supported = get_supported_brokers()
            for broker in args._brokers:
                if broker and broker not in supported:
                    errors.append(f"Unsupported broker '{broker}'. Supported: {', '.join(supported)}")
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

def determine_granularity(args: argparse.Namespace, strategy_index: int = 0) -> str:
    """
    Determine the granularity to use for a specific strategy
    
    Args:
        args: Parsed arguments
        strategy_index: Index of the strategy (for multi-strategy mode)
        
    Returns:
        Granularity string to use
    """
    # Use parsed granularities if available
    if hasattr(args, '_granularities') and args._granularities:
        return args._granularities[strategy_index]
    
    # Use defaults based on data source
    data_source = args._data_sources[strategy_index] if hasattr(args, '_data_sources') and args._data_sources else args.data_source
    defaults = {
        "polygon": "1m",
        "coinmarketcap": "1d", 
        "demo": "1m"
    }
    
    granularity = defaults.get(data_source, "1m")
    logger.info(f"Using default granularity {granularity} for {data_source}")
    
    return granularity

def determine_broker(args: argparse.Namespace, strategy_index: int = 0) -> str:
    """
    Determine the broker to use for a specific strategy
    
    Args:
        args: Parsed arguments
        strategy_index: Index of the strategy (for multi-strategy mode)
        
    Returns:
        Broker type string
    """
    # Use parsed brokers if available
    if hasattr(args, '_brokers') and args._brokers and args._brokers[strategy_index]:
        broker = args._brokers[strategy_index]
        logger.info(f"Using specified broker: {broker}")
        return broker
    
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

def parse_comma_separated(value: str) -> List[str]:
    """
    Parse comma-separated string into list of strings
    
    Args:
        value: Comma-separated string
        
    Returns:
        List of strings with whitespace stripped
    """
    if not value:
        return []
    return [s.strip() for s in value.split(',') if s.strip()]

def apply_smart_defaults(values: List[str], target_count: int, arg_name: str) -> List[str]:
    """
    Apply smart defaulting logic: single value applies to all, multiple values must match count
    
    Args:
        values: List of values
        target_count: Target count (usually number of strategies)
        arg_name: Argument name for error messages
        
    Returns:
        List with proper count
        
    Raises:
        ValueError: If count doesn't match and isn't 1
    """
    if not values:
        return []
    
    if len(values) == 1:
        # Single value applies to all
        return values * target_count
    elif len(values) == target_count:
        # Perfect match
        return values
    else:
        # Mismatch
        raise ValueError(f"{arg_name}: expected 1 value (applies to all) or {target_count} values (one per strategy), got {len(values)}")

def parse_symbols(symbols_str: str) -> List[str]:
    """
    Parse symbols string into list
    
    Args:
        symbols_str: Comma-separated symbols string
        
    Returns:
        List of symbol strings
    """
    return [s.strip().upper() for s in symbols_str.split(',') if s.strip()]

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

def create_inline_strategy_config(args: argparse.Namespace) -> str:
    """
    Create a temporary multi-strategy configuration from inline arguments
    
    Args:
        args: Parsed arguments with inline strategy configuration
        
    Returns:
        Temporary config content as string
    """
    if not hasattr(args, '_strategies') or len(args._strategies) <= 1:
        return None
    
    # Parse symbols for potential 1:1 mapping
    symbols = parse_symbols(args.symbols)
    
    # Check if we have 1:1 strategy-to-symbol mapping
    if len(args._strategies) == len(symbols):
        config_lines = [
            "# Auto-generated multi-strategy configuration from CLI arguments",
            "# Format: filename,strategy_id,allocation_percentage,symbol",
            "# 1:1 Strategy-to-Symbol mapping mode",
            ""
        ]
        
        for i, strategy_path in enumerate(args._strategies):
            strategy_id = args._strategy_ids[i]
            allocation = args._allocations[i]
            symbol = symbols[i]
            
            config_lines.append(f"{strategy_path},{strategy_id},{allocation},{symbol}")
        
    else:
        # Traditional multi-strategy mode (all strategies on all symbols)
        config_lines = [
            "# Auto-generated multi-strategy configuration from CLI arguments",
            "# Format: filename,strategy_id,allocation_percentage",
            ""
        ]
        
        for i, strategy_path in enumerate(args._strategies):
            strategy_id = args._strategy_ids[i]
            allocation = args._allocations[i]
            
            config_lines.append(f"{strategy_path},{strategy_id},{allocation}")
    
    return "\n".join(config_lines)

async def run_trading_system(args: argparse.Namespace) -> int:
    """
    Run the trading system with parsed arguments
    
    Args:
        args: Parsed and validated arguments
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Parse symbols
        symbols = parse_symbols(args.symbols)
        
        # Get trading configuration
        enable_trading = args._enable_trading
        paper_trading = args._paper_trading
        
        # Determine if this is multi-strategy mode
        is_multi_strategy = hasattr(args, '_strategies') and len(args._strategies) > 1
        
        if is_multi_strategy:
            # Multi-strategy mode
            import tempfile
            import os
            
            # For multi-strategy, we need to determine primary broker for trading system setup
            broker_type = None
            if enable_trading:
                # Use first broker as primary (or auto-detect if none specified)
                broker_type = determine_broker(args, 0)
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
            
            # Create temporary config file from inline arguments
            config_content = create_inline_strategy_config(args)
            
            # Write to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                temp_file.write(config_content)
                temp_config_path = temp_file.name
            
            try:
                # For multi-strategy, use first data source and granularity as primary
                data_source = args._data_sources[0]
                granularity = determine_granularity(args, 0)
                
                system = LiveTradingSystem(
                    symbols=symbols,
                    data_source=data_source,
                    granularity=granularity,
                    lookback_override=args.lookback,
                    enable_trading=enable_trading,
                    multi_strategy_config=temp_config_path,
                    broker_type=broker_type,
                    paper_trading=paper_trading
                )
                
                # Run the system
                await system.run_live_system(duration_minutes=args.duration)
                
            finally:
                # Clean up temporary file
                os.unlink(temp_config_path)
            
            return 0
        else:
            # Single-strategy mode
            strategy_path = args._strategies[0]
            data_source = args._data_sources[0] 
            granularity = determine_granularity(args, 0)
            
            # Determine broker if trading is enabled
            broker_type = None
            if enable_trading:
                broker_type = determine_broker(args, 0)
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
            
            system = LiveTradingSystem(
                strategy_path=strategy_path,
                symbols=symbols,
                data_source=data_source,
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