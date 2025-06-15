"""
CLI module for the trading system.

Now provides a modular CLI architecture with separate components for:
- Commands: Individual command implementations
- Parsers: Argument parsing functionality  
- Validators: Input validation
- Formatters: Output formatting
- Utils: Common utilities

The old monolithic cli.py is replaced with a modular system using:
- BaseCommand: Abstract base for all commands
- CommandFactory: Factory for command registration and creation
- BaseParser: Common parsing patterns
- BaseValidator: Common validation patterns
- BaseFormatter: Consistent output formatting
"""

# New modular CLI entry point
from .cli import main as cli_main

# Core modular components
from .command_factory import CommandFactory, register_command, get_supported_commands, create_command
from .commands import BaseCommand, ListCommand, StatusCommand, SetupCommand
from .parsers import BaseParser
from .validators import BaseValidator
from .formatters import BaseFormatter, InfoFormatter
from .utils import setup_logging, get_cli_logger

# Import command registry to ensure commands are registered
from . import command_registry

# Legacy support - redirect old main to new cli_main
main = cli_main

__all__ = [
    # Main entry point (new and legacy)
    'cli_main',
    'main',
    
    # Command system
    'CommandFactory',
    'register_command', 
    'get_supported_commands',
    'create_command',
    'BaseCommand',
    'ListCommand',
    'StatusCommand', 
    'SetupCommand',
    
    # Modular components
    'BaseParser',
    'BaseValidator', 
    'BaseFormatter',
    'InfoFormatter',
    
    # Utilities
    'setup_logging',
    'get_cli_logger',
] 