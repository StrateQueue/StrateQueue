"""
Main CLI Entry Point

Lightweight CLI entry point that uses the modular command system.
This replaces the monolithic cli.py with a clean, modular approach.
"""

import argparse
import sys
from typing import List, Optional

from .command_factory import CommandFactory, get_supported_commands, create_command
from .utils import setup_logging, get_cli_logger

# Import command registry to ensure commands are registered
from . import command_registry

logger = get_cli_logger('main')


def create_main_parser() -> argparse.ArgumentParser:
    """
    Create the main argument parser with subcommands
    
    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog='stratequeue',
        description='StrateQueue - Transform your backtesting strategies into live trading',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=create_help_epilog()
    )
    
    # Global arguments
    parser.add_argument(
        '--verbose', '-v', 
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--version', 
        action='version',
        version='%(prog)s 1.0.0'
    )
    
    # Create subparsers for commands
    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands',
        metavar='COMMAND'
    )
    
    # Register command parsers
    register_command_parsers(subparsers)
    
    return parser


def register_command_parsers(subparsers) -> None:
    """
    Register parsers for all available commands
    
    Args:
        subparsers: Subparsers object to add command parsers to
    """
    supported_commands = get_supported_commands()
    
    for command_name, description in supported_commands.items():
        command = create_command(command_name)
        if command:
            # Create subparser for this command with aliases
            aliases = command.aliases if hasattr(command, 'aliases') else []
            subparser = subparsers.add_parser(
                command_name,
                aliases=aliases,
                help=description,
                description=description
            )
            
            # Let the command configure its parser
            command.setup_parser(subparser)


def create_help_epilog() -> str:
    """
    Create help epilog with examples and available commands
    
    Returns:
        Help epilog string
    """
    epilog = """
Available Commands:
"""
    
    supported_commands = get_supported_commands()
    for command_name, description in supported_commands.items():
        epilog += f"  {command_name:<12} {description}\n"
    
    epilog += """
Examples:
  # Deploy a single strategy
  stratequeue deploy --strategy sma.py --symbols AAPL --paper
  
  # Check system status
  stratequeue status
  
  # List available brokers
  stratequeue list brokers
  
  # Setup broker credentials
  stratequeue setup broker alpaca

For command-specific help:
  stratequeue COMMAND --help
"""
    
    return epilog


def show_welcome_message() -> None:
    """Show welcome message when no command is provided"""
    print("🚀 StrateQueue - Live Trading System")
    print("=" * 50)
    print("Transform your backtesting strategies into live trading!")
    print("")
    
    supported_commands = get_supported_commands()
    if supported_commands:
        print("Available Commands:")
        for command_name, description in supported_commands.items():
            print(f"  {command_name:<12} {description}")
        print("")
    
    print("Quick Start:")
    print("  stratequeue deploy --strategy sma.py --symbol AAPL --paper")
    print("")
    print("Get Help:")
    print("  stratequeue --help           # Show detailed help")
    print("  stratequeue COMMAND --help   # Help for specific command")


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main CLI entry point
    
    Args:
        argv: Command line arguments (default: sys.argv[1:])
        
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        # Parse arguments
        parser = create_main_parser()
        args = parser.parse_args(argv)
        
        # Setup logging
        setup_logging(args.verbose)
        logger.debug(f"CLI started with args: {args}")
        
        # Handle no command provided
        if not args.command:
            show_welcome_message()
            return 0
        
        # Get and execute command
        command = create_command(args.command)
        if not command:
            print(f"❌ Unknown command: {args.command}")
            print(f"💡 Available commands: {', '.join(get_supported_commands().keys())}")
            return 1
        
        # Execute command
        return command.run(args)
        
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        return 130  # Standard exit code for SIGINT
    
    except Exception as e:
        logger.exception(f"Unexpected error in main CLI: {e}")
        print(f"❌ Unexpected error: {e}")
        print("💡 Run with --verbose for detailed error information")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 