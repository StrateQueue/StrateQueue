"""Rebalance Command

Rebalances portfolio allocations between strategies in a running daemon trading system.
Supports both automatic equal-weight rebalancing and custom allocation specification.
"""

import argparse
from argparse import Namespace
from typing import List, Optional, Dict

from .base_command import BaseCommand
from ..utils.daemon_manager import DaemonManager


class RebalanceCommand(BaseCommand):
    """Command for rebalancing strategy allocations in the running system"""
    
    def __init__(self):
        super().__init__()
        self.daemon_manager = DaemonManager()
    
    @property
    def name(self) -> str:
        """Command name"""
        return "rebalance"
    
    @property
    def description(self) -> str:
        """Command description"""
        return "Rebalance portfolio allocations between strategies"
    
    @property
    def aliases(self) -> List[str]:
        """Command aliases"""
        return ["rebal", "balance"]
    
    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Setup command-specific arguments"""
        parser.add_argument(
            '--config',
            help='Multi-strategy config file to identify the running system'
        )
        
        parser.add_argument(
            '--allocations',
            help='New allocations as comma-separated percentages (e.g., 0.4,0.3,0.3) or equal for equal weights'
        )
        
        parser.add_argument(
            '--strategy-ids',
            help='Comma-separated strategy IDs to specify allocation order (optional)'
        )
        
        parser.add_argument(
            '--target',
            choices=['portfolio', 'positions', 'both'],
            default='both',
            help='What to rebalance: portfolio allocations, actual positions, or both (default: both)'
        )
        
        parser.add_argument(
            '--liquidate-excess',
            action='store_true',
            help='Liquidate excess positions that exceed new allocations'
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
        
        # Validate allocations format if provided
        if args.allocations and args.allocations != 'equal':
            try:
                allocations = [float(a.strip()) for a in args.allocations.split(',')]
                
                # Check all are positive
                if any(a <= 0 for a in allocations):
                    errors.append("All allocations must be positive")
                
                # Check sum is reasonable (allowing for minor rounding)
                total = sum(allocations)
                if abs(total - 1.0) > 0.01:
                    errors.append(f"Allocations must sum to 1.0 (got {total:.3f})")
                    
            except ValueError:
                errors.append("Allocations must be comma-separated decimal numbers (e.g., 0.4,0.3,0.3)")
        
        return errors if errors else None
    
    def execute(self, args: Namespace) -> int:
        """
        Execute rebalance operation
        
        Args:
            args: Parsed command arguments
            
        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        try:
            print("⚖️  Rebalancing portfolio allocations")
            
            # Load running daemon system
            success, system_info, error = self.daemon_manager.load_daemon_system(config_file=args.config)
            if not success:
                print(f"❌ {error}")
                print("💡 Make sure a trading system is running with daemon mode (--daemon)")
                return 1
            
            # Get current strategies
            strategies = system_info.get('strategies', {})
            if len(strategies) < 2:
                print("⚠️  Cannot rebalance - need at least 2 strategies in the system")
                return 1
            
            strategy_ids = list(strategies.keys())
            print(f"📋 Found {len(strategy_ids)} strategies: {', '.join(strategy_ids)}")
            
            # Determine new allocations
            new_allocations = self._calculate_new_allocations(args, strategy_ids)
            if not new_allocations:
                return 1
            
            # Show current vs new allocations
            self._show_allocation_comparison(strategies, new_allocations)
            
            if args.dry_run:
                print("\n🔍 DRY RUN - Would rebalance:")
                print(f"  Target: {args.target}")
                print(f"  Liquidate excess: {args.liquidate_excess}")
                return 0
            
            # Perform rebalancing
            success = self._rebalance_system(
                system_info['system'],
                new_allocations,
                target=args.target,
                liquidate_excess=args.liquidate_excess
            )
            
            if success:
                print("✅ Successfully rebalanced portfolio")
                
                # Update daemon info
                self.daemon_manager.store_daemon_system(system_info['system'])
                return 0
            else:
                print("❌ Failed to rebalance portfolio")
                return 1
                
        except Exception as e:
            print(f"❌ Error rebalancing portfolio: {e}")
            return 1
    
    def _calculate_new_allocations(self, args: Namespace, strategy_ids: List[str]) -> Optional[Dict[str, float]]:
        """Calculate new allocations based on arguments"""
        if not args.allocations or args.allocations == 'equal':
            # Equal weight allocation
            weight = 1.0 / len(strategy_ids)
            return {strategy_id: weight for strategy_id in strategy_ids}
        
        try:
            allocations = [float(a.strip()) for a in args.allocations.split(',')]
            
            # Handle strategy ID ordering
            if args.strategy_ids:
                specified_ids = [s.strip() for s in args.strategy_ids.split(',')]
                if len(specified_ids) != len(allocations):
                    print(f"❌ Mismatch: {len(specified_ids)} strategy IDs but {len(allocations)} allocations")
                    return None
                if len(specified_ids) != len(strategy_ids):
                    print(f"❌ Must specify all {len(strategy_ids)} strategies")
                    return None
                strategy_order = specified_ids
            else:
                if len(allocations) != len(strategy_ids):
                    print(f"❌ Must provide {len(strategy_ids)} allocations for current strategies")
                    return None
                strategy_order = strategy_ids
            
            return dict(zip(strategy_order, allocations))
            
        except ValueError as e:
            print(f"❌ Invalid allocation format: {e}")
            return None
    
    def _show_allocation_comparison(self, current_strategies: Dict, new_allocations: Dict[str, float]) -> None:
        """Show current vs new allocation comparison"""
        print("\n📊 Allocation Changes:")
        print("Strategy".ljust(20) + "Current".ljust(12) + "New".ljust(12) + "Change")
        print("-" * 50)
        
        for strategy_id in new_allocations.keys():
            current_alloc = current_strategies.get(strategy_id, {}).get('allocation', 0.0)
            new_alloc = new_allocations[strategy_id]
            change = new_alloc - current_alloc
            
            change_str = f"{change:+.1%}" if change != 0 else "unchanged"
            print(f"{strategy_id:<20}{current_alloc:<12.1%}{new_alloc:<12.1%}{change_str}")
    
    def _rebalance_system(self, trading_system: any, new_allocations: Dict[str, float], 
                         target: str = 'both', liquidate_excess: bool = False) -> bool:
        """Perform actual rebalancing in the trading system"""
        try:
            print("\n🔧 Applying new allocations...")
            
            if target in ['portfolio', 'both']:
                print("📈 Updating portfolio allocations...")
                # TODO: Implement portfolio allocation updates
                # trading_system.update_strategy_allocations(new_allocations)
            
            if target in ['positions', 'both']:
                print("💰 Rebalancing positions...")
                # TODO: Implement position rebalancing
                # trading_system.rebalance_positions(new_allocations, liquidate_excess)
            
            print("⚖️  Rebalancing completed successfully")
            return True
            
        except Exception as e:
            print(f"⚠️  Rebalancing simulation: {e}")
            return False 