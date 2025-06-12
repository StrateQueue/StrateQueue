"""Resume Command

Resumes a paused strategy in a daemon trading system.
The strategy will start generating new signals again.
"""

import argparse
from argparse import Namespace
from typing import List, Optional

from .base_command import BaseCommand
from ..utils.daemon_manager import DaemonManager, DaemonIPC


class ResumeCommand(BaseCommand):
    """Command for resuming a paused strategy"""
    
    def __init__(self):
        super().__init__()
        self.daemon_manager = DaemonManager()
    
    @property
    def name(self) -> str:
        """Command name"""
        return "resume"
    
    @property
    def description(self) -> str:
        """Command description"""
        return "Resume a paused strategy"
    
    @property
    def aliases(self) -> List[str]:
        """Command aliases"""
        return []
    
    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Setup command-specific arguments"""
        parser.add_argument(
            'strategy_id',
            help='Strategy identifier to resume'
        )
        
        parser.add_argument(
            '--config',
            help='Multi-strategy config file to identify the running system'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        
        return parser
    
    def validate_args(self, args: Namespace) -> Optional[List[str]]:
        """Validate command arguments"""
        errors = []
        
        if not args.strategy_id:
            errors.append("Strategy ID is required")
        
        return errors if errors else None
    
    def execute(self, args: Namespace) -> int:
        """
        Execute resume operation
        
        Args:
            args: Parsed command arguments
            
        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        try:
            print(f"▶️  Resuming strategy: {args.strategy_id}")
            
            # Load running daemon system
            success, system_info, error = self.daemon_manager.load_daemon_system(config_file=args.config)
            if not success:
                print(f"❌ {error}")
                print("💡 Make sure a trading system is running with daemon mode (--daemon)")
                return 1
            
            # Get LIVE strategy data via IPC to validate strategy exists
            ipc_command = {'type': 'get_status'}
            ipc_response = self.daemon_manager.ipc.send_command(ipc_command)
            
            if not ipc_response.get('success'):
                print(f"❌ Failed to get live strategy data: {ipc_response.get('error', 'Unknown IPC error')}")
                print("⚠️  Falling back to cached data (may be outdated)")
                strategies = system_info.get('strategies', {})
            else:
                live_status = ipc_response.get('status', {})
                strategies = live_status.get('strategies', {})
            
            # Validate strategy exists
            if args.strategy_id not in strategies:
                print(f"❌ Strategy '{args.strategy_id}' not found in the system")
                available_strategies = list(strategies.keys())
                if available_strategies:
                    print(f"📋 Available strategies: {', '.join(available_strategies)}")
                return 1
            
            if args.dry_run:
                print("🔍 DRY RUN - Would resume:")
                print(f"  Strategy ID: {args.strategy_id}")
                return 0
            
            # Resume strategy in live system
            success = self._resume_strategy_in_system(system_info, args.strategy_id)
            
            if success:
                print(f"✅ Successfully resumed strategy '{args.strategy_id}'")
                print("   Strategy will start generating signals again")
                
                # Update daemon info
                self.daemon_manager.store_daemon_system(system_info['system'])
                return 0
            else:
                print(f"❌ Failed to resume strategy '{args.strategy_id}'")
                return 1
                
        except Exception as e:
            print(f"❌ Error resuming strategy: {e}")
            return 1
    

    
    def _resume_strategy_in_system(self, system_info: dict, strategy_id: str) -> bool:
        """Resume strategy in live trading system"""
        try:
            print(f"🔧 Resuming strategy '{strategy_id}'")
            
            # Send resume command via IPC
            ipc = DaemonIPC()
            
            command = {
                'type': 'resume_strategy',
                'strategy_id': strategy_id
            }
            
            response = ipc.send_command(command)
            
            if response.get('success'):
                print(f"✅ Strategy '{strategy_id}' resumed successfully")
                print("   • Signal generation restarted")
                print("   • Strategy is now active")
                print(f"   • Pause again with: stratequeue pause {strategy_id}")
                return True
            else:
                error_msg = response.get('error', 'Unknown error')
                print(f"❌ Failed to resume strategy '{strategy_id}': {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ Error resuming strategy: {e}")
            return False 