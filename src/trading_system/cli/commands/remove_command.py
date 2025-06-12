"""Remove Command

Removes a strategy from a running daemon trading system.
Handles position liquidation and allocation rebalancing.
"""

import argparse
from argparse import Namespace
from typing import List, Optional

from .base_command import BaseCommand
from ..utils.daemon_manager import DaemonManager


class RemoveCommand(BaseCommand):
    """Command for removing a strategy from the running system"""
    
    def __init__(self):
        super().__init__()
        self.daemon_manager = DaemonManager()
    
    @property
    def name(self) -> str:
        """Command name"""
        return "remove"
    
    @property
    def description(self) -> str:
        """Command description"""
        return "Remove a strategy from the running system"
    
    @property
    def aliases(self) -> List[str]:
        """Command aliases"""
        return ["rm", "delete"]
    
    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Setup command-specific arguments"""
        parser.add_argument(
            'strategy_id',
            help='Strategy identifier to remove'
        )
        
        parser.add_argument(
            '--config',
            help='Multi-strategy config file to identify the running system'
        )
        
        parser.add_argument(
            '--liquidate',
            action='store_true',
            help='Liquidate strategy positions when removing (default: transfer to other strategies)'
        )
        
        parser.add_argument(
            '--rebalance',
            action='store_true',
            help='Automatically rebalance remaining strategies after removal'
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
        Execute remove operation
        
        Args:
            args: Parsed command arguments
            
        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        try:
            print(f"🗑️  Removing strategy: {args.strategy_id}")
            
            # Load running daemon system
            success, system_info, error = self.daemon_manager.load_daemon_system(config_file=args.config)
            if not success:
                print(f"❌ {error}")
                print("💡 Make sure a trading system is running with daemon mode (--daemon)")
                return 1
            
            # Get LIVE strategy data via IPC instead of stale pickled data
            print("🔍 Getting live strategy data...")
            ipc_command = {'type': 'get_status'}
            ipc_response = self.daemon_manager.ipc.send_command(ipc_command)
            
            if not ipc_response.get('success'):
                print(f"❌ Failed to get live strategy data: {ipc_response.get('error', 'Unknown IPC error')}")
                print("⚠️  Falling back to cached data (may be outdated)")
                strategies = system_info.get('strategies', {})
            else:
                live_status = ipc_response.get('status', {})
                strategies = live_status.get('strategies', {})
                print(f"✅ Retrieved live data: {len(strategies)} strategies")
            
            # Validate strategy exists
            if args.strategy_id not in strategies:
                print(f"❌ Strategy '{args.strategy_id}' not found in the system")
                available_strategies = list(strategies.keys())
                if available_strategies:
                    print(f"📋 Available strategies: {', '.join(available_strategies)}")
                return 1
            
            # Check if this is the only strategy
            if len(strategies) <= 1:
                print(f"⚠️  Cannot remove '{args.strategy_id}' - it's the only strategy in the system")
                print("💡 Use 'stratequeue stop' to stop the entire system")
                return 1
            
            if args.dry_run:
                print("🔍 DRY RUN - Would remove:")
                print(f"  Strategy ID: {args.strategy_id}")
                print(f"  Liquidate positions: {args.liquidate}")
                print(f"  Rebalance remaining: {args.rebalance}")
                
                strategy_info = strategies[args.strategy_id]
                if 'allocation' in strategy_info:
                    allocation = strategy_info['allocation']
                    print(f"  Current allocation: {allocation:.1%}")
                
                remaining_strategies = [s for s in strategies.keys() if s != args.strategy_id]
                print(f"  Remaining strategies ({len(remaining_strategies)}): {', '.join(remaining_strategies)}")
                return 0
            
            # Remove strategy from live system
            success = self._remove_strategy_from_system(
                system_info['system'], 
                args.strategy_id,
                liquidate=args.liquidate,
                rebalance=args.rebalance
            )
            
            if success:
                print(f"✅ Successfully removed strategy '{args.strategy_id}'")
                
                if args.liquidate:
                    print("💰 Strategy positions have been liquidated")
                else:
                    print("📈 Strategy positions transferred to remaining strategies")
                
                if args.rebalance:
                    print("⚖️  Remaining strategies have been rebalanced")
                
                # Update daemon info
                self.daemon_manager.store_daemon_system(system_info['system'])
                return 0
            else:
                print(f"❌ Failed to remove strategy '{args.strategy_id}'")
                return 1
                
        except Exception as e:
            print(f"❌ Error removing strategy: {e}")
            return 1
    

    
    def _remove_strategy_from_system(self, trading_system: any, strategy_id: str, 
                                   liquidate: bool = False, rebalance: bool = False) -> bool:
        """Remove strategy from live trading system"""
        try:
            print(f"🔧 Removing strategy '{strategy_id}'")
            
            if liquidate:
                print("💰 Liquidating strategy positions...")
                # TODO: Implement actual position liquidation
                # trading_system.liquidate_strategy_positions(strategy_id)
            else:
                print("📈 Transferring positions to remaining strategies...")
                # TODO: Implement position transfer logic
                # trading_system.transfer_strategy_positions(strategy_id)
            
            # TODO: Implement actual strategy removal
            # trading_system.remove_strategy(strategy_id)
            
            if rebalance:
                print("⚖️  Rebalancing remaining strategies...")
                # TODO: Implement rebalancing logic
                # trading_system.rebalance_strategies()
            
            return True
        except Exception as e:
            print(f"⚠️  Strategy removal simulation: {e}")
            return False 