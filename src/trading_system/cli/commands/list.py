"""
List Command

Command for listing available options like brokers, granularities, etc.
"""

import argparse
from typing import Optional, List

from .base_command import BaseCommand
from ..formatters import InfoFormatter


class ListCommand(BaseCommand):
    """
    List command implementation
    
    Shows available options like supported brokers, data granularities, etc.
    """
    
    @property
    def name(self) -> str:
        return "list"
    
    @property
    def description(self) -> str:
        return "List available options (brokers, granularities, etc.)"
    
    @property
    def aliases(self) -> List[str]:
        return ["ls", "show"]
    
    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Configure list command arguments"""
        
        parser.add_argument(
            'list_type',
            nargs='?',
            choices=['brokers', 'granularities'],
            help='Type of information to list'
        )
        
        parser.add_argument(
            '--verbose', '-v',
            action='store_true',
            help='Show detailed information'
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
            
        else:
            # This shouldn't happen due to choices constraint, but handle gracefully
            print(InfoFormatter.format_error(f"Unknown list type: {args.list_type}"))
            print("💡 Available options: brokers, granularities")
            print("💡 Try: stratequeue list brokers")
            return 1 