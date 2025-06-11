"""
Status Command

Command for checking system and broker environment status.
"""

import argparse
from typing import Optional, List

from .base_command import BaseCommand
from ..formatters import InfoFormatter


class StatusCommand(BaseCommand):
    """
    Status command implementation
    
    Checks system and broker environment status, including credential validation.
    """
    
    @property
    def name(self) -> str:
        return "status"
    
    @property
    def description(self) -> str:
        return "Check system and broker status"
    
    @property
    def aliases(self) -> List[str]:
        return ["check", "health"]
    
    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Configure status command arguments"""
        
        parser.add_argument(
            'status_type',
            nargs='?',
            default='broker',
            choices=['broker', 'system'],
            help='Type of status to check (default: broker)'
        )
        
        parser.add_argument(
            '--detailed', '-d',
            action='store_true',
            help='Show detailed status information'
        )
        
        return parser
    
    def validate_args(self, args: argparse.Namespace) -> Optional[List[str]]:
        """Validate status command arguments"""
        # No validation needed - all arguments are optional with choices
        return None
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute status command"""
        
        if args.status_type == 'broker':
            print(InfoFormatter.format_broker_status())
            return 0
            
        elif args.status_type == 'system':
            # For now, system status is the same as broker status
            # In the future, this could include more system checks
            print(InfoFormatter.format_broker_status())
            
            # Could add additional system checks here:
            # - Check if trading system is running
            # - Check data source connectivity
            # - Check log file status
            # - etc.
            
            return 0
            
        else:
            # This shouldn't happen due to choices constraint, but handle gracefully
            print(InfoFormatter.format_error(f"Unknown status type: {args.status_type}"))
            print("💡 Available options: broker, system")
            print("💡 Try: stratequeue status broker")
            return 1 