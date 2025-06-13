"""
List Command

Command for listing available options like brokers, granularities, strategies, etc.
"""

import argparse
from typing import Optional, List

from .base_command import BaseCommand
from ..formatters import InfoFormatter


class ListCommand(BaseCommand):
    """
    List command implementation
    
    Shows available options like supported brokers, data granularities, and live strategies.
    """
    
    def __init__(self):
        super().__init__()
    
    @property
    def name(self) -> str:
        return "list"
    
    @property
    def description(self) -> str:
        return "List available options (brokers, granularities, strategies, etc.)"
    
    @property
    def aliases(self) -> List[str]:
        return ["ls", "show"]
    
    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Configure list command arguments"""
        
        parser.add_argument(
            'list_type',
            nargs='?',
            choices=['brokers', 'granularities', 'strategies', 'strategy'],
            help='Type of information to list'
        )
        
        parser.add_argument(
            '--verbose', '-v',
            action='store_true',
            help='Show detailed information'
        )
        
        parser.add_argument(
            '--config',
            help='Multi-strategy config file to identify the running system'
        )
        
        return parser
    
    def validate_args(self, args: argparse.Namespace) -> Optional[List[str]]:
        """Validate list command arguments"""
        # No validation needed - all arguments are optional with choices
        return None
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute list command"""
        
        if not hasattr(args, 'list_type') or args.list_type is None:
            # No list type provided, show available options
            print(InfoFormatter.format_command_help())
            return 0
        
        if args.list_type == 'brokers':
            print(InfoFormatter.format_broker_info())
            return 0
            
        elif args.list_type == 'granularities':
            print(InfoFormatter.format_granularity_info())
            return 0
            
        elif args.list_type in ['strategies', 'strategy']:
            print("❌ Listing live strategies is no longer supported (daemon mode removed).")
            return 1
            
        else:
            # This shouldn't happen due to choices constraint, but handle gracefully
            print(InfoFormatter.format_error(f"Unknown list type: {args.list_type}"))
            print("💡 Available options: brokers, granularities, strategies")
            print("💡 Try: stratequeue list strategies")
            return 1 