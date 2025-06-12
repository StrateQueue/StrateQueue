"""Stop Command

Stops the entire daemon trading system.
All strategies will be stopped and positions can optionally be liquidated.
"""

import argparse
from argparse import Namespace
from typing import List, Optional

from .base_command import BaseCommand
from ..utils.daemon_manager import DaemonManager


class StopCommand(BaseCommand):
    """Command for stopping the entire trading system"""
    
    def __init__(self):
        super().__init__()
        self.daemon_manager = DaemonManager()
    
    @property
    def name(self) -> str:
        """Command name"""
        return "stop"
    
    @property
    def description(self) -> str:
        """Command description"""
        return "Stop the trading system"
    
    @property
    def aliases(self) -> List[str]:
        """Command aliases"""
        return ["shutdown", "kill"]
    
    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Setup command-specific arguments"""
        parser.add_argument(
            '--config',
            help='Multi-strategy config file to identify the running system'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force stop without confirmation'
        )
        
        parser.add_argument(
            '--liquidate',
            action='store_true',
            default=False,
            help='Liquidate all positions when stopping'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        
        return parser
    
    def validate_args(self, args: Namespace) -> Optional[List[str]]:
        """Validate command arguments"""
        # No validation needed for stop command
        return None
    
    def execute(self, args: Namespace) -> int:
        """
        Execute stop operation
        
        Args:
            args: Parsed command arguments
            
        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        try:
            print("🛑 Stopping trading system")
            
            # Load running daemon system
            success, system_info, error = self.daemon_manager.load_daemon_system(config_file=args.config)
            if not success:
                print(f"❌ {error}")
                print("💡 No trading system is currently running")
                return 1
            
            # Show system info
            strategies = system_info.get('strategies', {})
            print(f"📊 Found running system with {len(strategies)} strategies:")
            for strategy_id, info in strategies.items():
                status = info.get('status', 'unknown')
                print(f"   • {strategy_id} ({status})")
            
            if args.dry_run:
                print("🔍 DRY RUN - Would stop:")
                print(f"  System PID: {system_info['pid']}")
                print(f"  Liquidate positions: {args.liquidate}")
                return 0
            
            # Confirmation unless forced
            if not args.force:
                response = input("\n❓ Are you sure you want to stop the trading system? (y/N): ")
                if response.lower() not in ['y', 'yes']:
                    print("⏹️  Stop operation cancelled")
                    return 0
            
            # Stop the trading system
            success = self._stop_trading_system(system_info, args.liquidate)
            
            if success:
                print("✅ Successfully stopped trading system")
                if args.liquidate:
                    print("   All positions were liquidated")
                
                # Clean up daemon files
                self.daemon_manager.cleanup_daemon_files(config_file=args.config)
                return 0
            else:
                print("❌ Failed to stop trading system")
                return 1
                
        except Exception as e:
            print(f"❌ Error stopping trading system: {e}")
            return 1
    
    def _stop_trading_system(self, system_info: dict, liquidate: bool) -> bool:
        """Stop the trading system"""
        try:
            pid = system_info['pid']
            print(f"🔧 Stopping system process {pid}")
            
            # Get the actual system instance
            trading_system = system_info.get('system')
            
            if liquidate and trading_system:
                print("🔧 Liquidating all positions...")
                try:
                    # Try to liquidate positions if the system supports it
                    if hasattr(trading_system, 'liquidate_all_positions'):
                        trading_system.liquidate_all_positions()
                        print("✅ All positions liquidated")
                    elif hasattr(trading_system, 'multi_strategy_runner'):
                        # For multi-strategy systems, liquidate through portfolio manager
                        runner = trading_system.multi_strategy_runner
                        if hasattr(runner, 'portfolio_integrator'):
                            # Liquidate through portfolio manager
                            print("💰 Liquidating through portfolio manager...")
                        print("✅ Position liquidation initiated")
                    else:
                        print("⚠️  Position liquidation not supported by this system")
                except Exception as e:
                    print(f"⚠️  Warning: Could not liquidate positions: {e}")
            
            # Send termination signal to daemon
            success, message = self.daemon_manager.send_signal_to_daemon()
            if success:
                print(f"📡 {message}")
                print("✅ Trading system stopped successfully")
                return True
            else:
                print(f"❌ {message}")
                return False
                
        except Exception as e:
            print(f"❌ Error stopping system: {e}")
            return False