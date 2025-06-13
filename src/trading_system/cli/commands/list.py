"""
List Command

Command for listing available options and resources.
This includes brokers, granularities, and strategies.
"""

import argparse
from typing import Optional, List

from .base_command import BaseCommand
from ..formatters.info_formatter import InfoFormatter


class ListCommand(BaseCommand):
    """
    List command implementation
    
    Handles listing of various system resources and options.
    """
    
    def __init__(self):
        super().__init__()
    
    @property
    def name(self) -> str:
        return "list"
    
    @property
    def description(self) -> str:
        return "List available options and resources"
    
    @property
    def aliases(self) -> List[str]:
        return ["ls"]
    
    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Configure list command arguments"""
        
        parser.add_argument(
            'list_type',
            nargs='?',
            choices=['brokers', 'granularities', 'strategies', 'strategy'],
            help='Type of resource to list'
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
            return self._list_strategies(args)
            
        else:
            # This shouldn't happen due to choices constraint, but handle gracefully
            print(InfoFormatter.format_error(f"Unknown list type: {args.list_type}"))
            print("💡 Available options: brokers, granularities, strategies")
            return 1
    
    def _list_strategies(self, args: argparse.Namespace) -> int:
        """List strategies (simplified version)"""
        print("📊 Strategy Listing")
        print("")
        print("Strategy listing is not available in this simplified version.")
        print("Previously this required daemon mode, which has been removed.")
        print("")
        print("💡 To see your strategies:")
        print("  • Check your strategy files directory")
        print("  • Use 'stratequeue deploy --strategy <file>' to run strategies")
        print("")
        return 0 