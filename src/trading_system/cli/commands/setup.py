"""
Setup Command

Command for configuring broker credentials and system settings.
"""

import argparse
from typing import Optional, List

from .base_command import BaseCommand
from ..formatters import InfoFormatter


class SetupCommand(BaseCommand):
    """
    Setup command implementation
    
    Provides setup instructions for brokers and system configuration.
    """
    
    @property
    def name(self) -> str:
        return "setup"
    
    @property
    def description(self) -> str:
        return "Configure brokers and system settings"
    
    @property
    def aliases(self) -> List[str]:
        return ["config", "configure"]
    
    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Configure setup command arguments"""
        
        parser.add_argument(
            'setup_type',
            nargs='?',
            choices=['broker'],
            help='Type of setup to perform'
        )
        
        parser.add_argument(
            'broker_name',
            nargs='?',
            help='Specific broker to setup (or "all" for all brokers)'
        )
        
        parser.add_argument(
            '--interactive', '-i',
            action='store_true',
            help='Interactive setup mode (future feature)'
        )
        
        return parser
    
    def validate_args(self, args: argparse.Namespace) -> Optional[List[str]]:
        """Validate setup command arguments"""
        errors = []
        
        # If setup_type is provided, validate broker_name
        if hasattr(args, 'setup_type') and args.setup_type == 'broker':
            if hasattr(args, 'broker_name') and args.broker_name:
                # Validate broker name against supported brokers
                valid_brokers = ['alpaca', 'interactive_brokers', 'td_ameritrade', 'all']
                if args.broker_name not in valid_brokers:
                    errors.append(f"Unknown broker: {args.broker_name}")
                    errors.append(f"Valid brokers: {', '.join(valid_brokers[:-1])}")
        
        return errors if errors else None
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute setup command"""
        
        if not hasattr(args, 'setup_type') or args.setup_type is None:
            # No setup type provided, show help
            self._show_setup_help()
            return 0
        
        if args.setup_type == 'broker':
            broker_name = getattr(args, 'broker_name', None)
            
            if args.interactive:
                print(InfoFormatter.format_warning("Interactive setup mode not yet implemented"))
                print("💡 For now, follow the setup instructions below:")
                print()
            
            print(InfoFormatter.format_broker_setup_instructions(broker_name))
            return 0
            
        else:
            # This shouldn't happen due to choices constraint, but handle gracefully
            print(InfoFormatter.format_error(f"Unknown setup type: {args.setup_type}"))
            print("💡 Try: stratequeue setup broker")
            return 1
    
    def _show_setup_help(self) -> None:
        """Show setup command help"""
        output = []
        output.append("🔧 StrateQueue Setup")
        output.append("=" * 50)
        output.append("Available setup options:")
        output.append("  broker    Configure broker credentials")
        output.append("")
        output.append("Usage:")
        output.append("  stratequeue setup broker           # Show all broker setup instructions")
        output.append("  stratequeue setup broker alpaca    # Show Alpaca setup instructions")
        output.append("  stratequeue setup broker all       # Show all broker instructions")
        output.append("")
        output.append("Examples:")
        output.append("  stratequeue setup broker alpaca")
        output.append("  stratequeue setup broker interactive_brokers")
        
        print("\n".join(output)) 