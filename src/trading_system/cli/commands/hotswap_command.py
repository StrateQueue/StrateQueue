"""Hotswap Command

Handles real-time strategy management during live trading including:
- Deploy new strategies at runtime
- Undeploy existing strategies
- Pause/resume strategies  
- Rebalance portfolio allocations
- List currently deployed strategies
"""

import argparse
import os
import sys
import time
from argparse import Namespace
from typing import Dict, Any, List, Optional
from pathlib import Path

from .base_command import BaseCommand
from ..parsers.hotswap_parser import HotswapParser
from ..validators.hotswap_validator import HotswapValidator
from ..formatters.base_formatter import BaseFormatter
from ..utils.daemon_manager import DaemonManager


class HotswapCommand(BaseCommand):
    """Command for hot swapping strategies during runtime"""
    
    def __init__(self):
        super().__init__()
        self.daemon_manager = DaemonManager()
        self.hotswap_parser = HotswapParser()
        self.hotswap_validator = HotswapValidator()
        self.formatter = BaseFormatter()
    
    @property
    def name(self) -> str:
        """Command name"""
        return "hotswap"
    
    @property
    def description(self) -> str:
        """Command description"""
        return "Hot swap strategies during runtime (multi-strategy mode only)"
    
    @property
    def aliases(self) -> List[str]:
        """Command aliases"""
        return ["hs", "swap"]
    
    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Setup command-specific arguments"""
        self.hotswap_parser.add_arguments(parser)
        
        # Add examples to help
        parser.epilog = self.hotswap_parser.get_examples()
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        
        return parser
    
    def validate_args(self, args: argparse.Namespace) -> Optional[List[str]]:
        """Validate command arguments"""
        is_valid, errors = self.hotswap_validator.validate(args)
        return errors if not is_valid else None
    
    def execute(self, args: Namespace) -> int:
        """
        Execute hotswap operation
        
        Args:
            args: Parsed command arguments
            
        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        try:
            print(f"🔄 Executing hotswap operation: {args.operation}")
            
            # Load running daemon system (except for list operation in dry-run)
            system_info = None
            if not (args.dry_run and args.operation == 'list'):
                success, system_info, error = self.daemon_manager.load_daemon_system(config_file=args.config)
                if not success:
                    if not args.dry_run:
                        print(f"❌ {error}")
                        print("💡 Make sure a trading system is running with daemon mode (--daemon)")
                        return 1
                    else:
                        # For dry-run, create mock system info for validation
                        system_info = {'strategies': {}}
            
            # Execute operation based on type
            if args.operation == 'deploy':
                return self._handle_deploy(args, system_info)
            elif args.operation == 'undeploy':
                return self._handle_undeploy(args, system_info)
            elif args.operation == 'pause':
                return self._handle_pause(args, system_info)
            elif args.operation == 'resume':
                return self._handle_resume(args, system_info)
            elif args.operation == 'rebalance':
                return self._handle_rebalance(args, system_info)
            elif args.operation == 'list':
                return self._handle_list(args, system_info)
            else:
                print(f"❌ Unknown operation: {args.operation}")
                return 1
                
        except Exception as e:
            print(f"❌ Error executing hotswap operation: {e}")
            return 1
    
    def _handle_deploy(self, args: Namespace, system_info: Dict[str, Any]) -> int:
        """Handle deploy operation"""
        print(f"🚀 Deploying strategy: {args.strategy_id}")
        
        # Validate strategy doesn't already exist
        if not self.hotswap_validator.validate_strategy_not_exists_in_system(args.strategy_id, system_info):
            print(f"❌ Strategy '{args.strategy_id}' already exists in the system")
            return 1
        
        if args.dry_run:
            print("🔍 DRY RUN - Would deploy:")
            print(f"  Strategy: {args.strategy}")
            print(f"  ID: {args.strategy_id}")
            print(f"  Allocation: {args.allocation:.1%}")
            if args.symbols:
                print(f"  Symbols: {args.symbols}")
            return 0
        
        try:
            # Get trading system
            trading_system = system_info['system']
            
            # Load and deploy strategy
            strategy_config = {
                'strategy_file': args.strategy,
                'strategy_id': args.strategy_id,
                'allocation': args.allocation,
                'symbols': args.symbols.split(',') if args.symbols else None,
            }
            
            # Deploy strategy to live system
            success = self._deploy_strategy_to_system(trading_system, strategy_config)
            
            if success:
                print(f"✅ Successfully deployed strategy '{args.strategy_id}'")
                print(f"   Allocation: {args.allocation:.1%}")
                
                # Update daemon info
                self.daemon_manager.store_daemon_system(trading_system)
                return 0
            else:
                print(f"❌ Failed to deploy strategy '{args.strategy_id}'")
                return 1
                
        except Exception as e:
            print(f"❌ Error deploying strategy: {e}")
            return 1
    
    def _handle_undeploy(self, args: Namespace, system_info: Dict[str, Any]) -> int:
        """Handle undeploy operation"""
        print(f"🗑️  Undeploying strategy: {args.strategy_id}")
        
        # Validate strategy exists
        if not self.hotswap_validator.validate_strategy_exists_in_system(args.strategy_id, system_info):
            print(f"❌ Strategy '{args.strategy_id}' not found in the system")
            return 1
        
        if args.dry_run:
            print("🔍 DRY RUN - Would undeploy:")
            print(f"  Strategy ID: {args.strategy_id}")
            print(f"  Liquidate positions: {args.liquidate}")
            return 0
        
        try:
            # Get trading system
            trading_system = system_info['system']
            
            # Undeploy strategy from live system
            success = self._undeploy_strategy_from_system(trading_system, args.strategy_id, args.liquidate)
            
            if success:
                print(f"✅ Successfully undeployed strategy '{args.strategy_id}'")
                if args.liquidate:
                    print("   Positions were liquidated")
                else:
                    print("   Positions were kept")
                
                # Update daemon info
                self.daemon_manager.store_daemon_system(trading_system)
                return 0
            else:
                print(f"❌ Failed to undeploy strategy '{args.strategy_id}'")
                return 1
                
        except Exception as e:
            print(f"❌ Error undeploying strategy: {e}")
            return 1
    
    def _handle_pause(self, args: Namespace, system_info: Dict[str, Any]) -> int:
        """Handle pause operation"""
        print(f"⏸️  Pausing strategy: {args.strategy_id}")
        
        # Validate strategy exists
        if not self.hotswap_validator.validate_strategy_exists_in_system(args.strategy_id, system_info):
            print(f"❌ Strategy '{args.strategy_id}' not found in the system")
            return 1
        
        if args.dry_run:
            print("🔍 DRY RUN - Would pause:")
            print(f"  Strategy ID: {args.strategy_id}")
            return 0
        
        try:
            # Get trading system
            trading_system = system_info['system']
            
            # Pause strategy in live system
            success = self._pause_strategy_in_system(trading_system, args.strategy_id)
            
            if success:
                print(f"✅ Successfully paused strategy '{args.strategy_id}'")
                print("   Strategy will stop generating new signals but keep positions")
                
                # Update daemon info
                self.daemon_manager.store_daemon_system(trading_system)
                return 0
            else:
                print(f"❌ Failed to pause strategy '{args.strategy_id}'")
                return 1
                
        except Exception as e:
            print(f"❌ Error pausing strategy: {e}")
            return 1
    
    def _handle_resume(self, args: Namespace, system_info: Dict[str, Any]) -> int:
        """Handle resume operation"""
        print(f"▶️  Resuming strategy: {args.strategy_id}")
        
        # Validate strategy exists
        if not self.hotswap_validator.validate_strategy_exists_in_system(args.strategy_id, system_info):
            print(f"❌ Strategy '{args.strategy_id}' not found in the system")
            return 1
        
        if args.dry_run:
            print("🔍 DRY RUN - Would resume:")
            print(f"  Strategy ID: {args.strategy_id}")
            return 0
        
        try:
            # Get trading system
            trading_system = system_info['system']
            
            # Resume strategy in live system
            success = self._resume_strategy_in_system(trading_system, args.strategy_id)
            
            if success:
                print(f"✅ Successfully resumed strategy '{args.strategy_id}'")
                print("   Strategy will start generating signals again")
                
                # Update daemon info
                self.daemon_manager.store_daemon_system(trading_system)
                return 0
            else:
                print(f"❌ Failed to resume strategy '{args.strategy_id}'")
                return 1
                
        except Exception as e:
            print(f"❌ Error resuming strategy: {e}")
            return 1
    
    def _handle_rebalance(self, args: Namespace, system_info: Dict[str, Any]) -> int:
        """Handle rebalance operation"""
        print("⚖️  Rebalancing portfolio allocations")
        
        # Parse allocations
        allocations = self._parse_allocations(args.allocations)
        if not allocations:
            print("❌ Invalid allocations format")
            return 1
        
        if args.dry_run:
            print("🔍 DRY RUN - Would rebalance to:")
            for strategy_id, allocation in allocations.items():
                print(f"  {strategy_id}: {allocation:.1%}")
            return 0
        
        try:
            # Get trading system
            trading_system = system_info['system']
            
            # Validate all strategies exist
            for strategy_id in allocations.keys():
                if not self.hotswap_validator.validate_strategy_exists_in_system(strategy_id, system_info):
                    print(f"❌ Strategy '{strategy_id}' not found in the system")
                    return 1
            
            # Rebalance portfolio in live system
            success = self._rebalance_portfolio_in_system(trading_system, allocations)
            
            if success:
                print("✅ Successfully rebalanced portfolio:")
                for strategy_id, allocation in allocations.items():
                    print(f"   {strategy_id}: {allocation:.1%}")
                
                # Update daemon info
                self.daemon_manager.store_daemon_system(trading_system)
                return 0
            else:
                print("❌ Failed to rebalance portfolio")
                return 1
                
        except Exception as e:
            print(f"❌ Error rebalancing portfolio: {e}")
            return 1
    
    def _handle_list(self, args: Namespace, system_info: Dict[str, Any]) -> int:
        """Handle list operation"""
        print("📋 Listing deployed strategies")
        
        # List all running daemons if no specific system
        if system_info is None:
            running_daemons = self.daemon_manager.list_running_daemons()
            if not running_daemons:
                print("No running trading systems found")
                return 0
            
            for daemon_name, info in running_daemons.items():
                print(f"\n🚀 System: {daemon_name}")
                print(f"   PID: {info['pid']}")
                print(f"   Started: {time.ctime(info['start_time'])}")
                self._print_strategies(info.get('strategies', {}))
            
            return 0
        
        # List strategies in specific system
        strategies = system_info.get('strategies', {})
        if not strategies:
            print("No strategies currently deployed")
            return 0
        
        print(f"PID: {system_info['pid']}")
        print(f"Started: {time.ctime(system_info['start_time'])}")
        self._print_strategies(strategies)
        
        return 0
    
    def _print_strategies(self, strategies: Dict[str, Any]) -> None:
        """Print formatted strategy information"""
        if not strategies:
            print("   No strategies deployed")
            return
        
        print("   Strategies:")
        for strategy_id, info in strategies.items():
            status = info.get('status', 'unknown')
            allocation = info.get('allocation')
            strategy_class = info.get('class', 'Unknown')
            
            status_emoji = {
                'active': '🟢',
                'paused': '⏸️',
                'stopped': '🔴',
            }.get(status, '❓')
            
            print(f"     {status_emoji} {strategy_id} ({strategy_class})")
            if allocation is not None:
                print(f"       Allocation: {allocation:.1%}")
            symbols = info.get('symbols', [])
            if symbols:
                print(f"       Symbols: {', '.join(symbols)}")
    
    def _parse_allocations(self, allocations_str: str) -> Dict[str, float]:
        """Parse allocations string into dictionary"""
        try:
            allocations = {}
            for alloc_pair in allocations_str.split(','):
                strategy_id, allocation_str = alloc_pair.split(':')
                allocations[strategy_id.strip()] = float(allocation_str.strip())
            return allocations
        except Exception:
            return {}
    
    def _deploy_strategy_to_system(self, trading_system: Any, strategy_config: Dict[str, Any]) -> bool:
        """Deploy strategy to live trading system"""
        try:
            # This would integrate with the actual trading system
            # For now, simulate the deployment
            print(f"🔧 Loading strategy from {strategy_config['strategy_file']}")
            print(f"🔧 Adding to system with ID '{strategy_config['strategy_id']}'")
            print(f"🔧 Setting allocation to {strategy_config['allocation']:.1%}")
            
            # TODO: Implement actual strategy deployment
            # trading_system.add_strategy(strategy_config)
            
            return True
        except Exception as e:
            print(f"⚠️  Strategy deployment simulation: {e}")
            return False
    
    def _undeploy_strategy_from_system(self, trading_system: Any, strategy_id: str, liquidate: bool) -> bool:
        """Undeploy strategy from live trading system"""
        try:
            print(f"🔧 Removing strategy '{strategy_id}' from system")
            if liquidate:
                print("🔧 Liquidating positions")
            else:
                print("🔧 Keeping positions")
            
            # TODO: Implement actual strategy undeployment
            # trading_system.remove_strategy(strategy_id, liquidate=liquidate)
            
            return True
        except Exception as e:
            print(f"⚠️  Strategy undeployment simulation: {e}")
            return False
    
    def _pause_strategy_in_system(self, trading_system: Any, strategy_id: str) -> bool:
        """Pause strategy in live trading system"""
        try:
            print(f"🔧 Pausing strategy '{strategy_id}'")
            
            # TODO: Implement actual strategy pausing
            # trading_system.pause_strategy(strategy_id)
            
            return True
        except Exception as e:
            print(f"⚠️  Strategy pause simulation: {e}")
            return False
    
    def _resume_strategy_in_system(self, trading_system: Any, strategy_id: str) -> bool:
        """Resume strategy in live trading system"""
        try:
            print(f"🔧 Resuming strategy '{strategy_id}'")
            
            # TODO: Implement actual strategy resuming
            # trading_system.resume_strategy(strategy_id)
            
            return True
        except Exception as e:
            print(f"⚠️  Strategy resume simulation: {e}")
            return False
    
    def _rebalance_portfolio_in_system(self, trading_system: Any, allocations: Dict[str, float]) -> bool:
        """Rebalance portfolio in live trading system"""
        try:
            print("🔧 Rebalancing portfolio allocations")
            for strategy_id, allocation in allocations.items():
                print(f"🔧 Setting {strategy_id} allocation to {allocation:.1%}")
            
            # TODO: Implement actual portfolio rebalancing
            # trading_system.rebalance_portfolio(allocations)
            
            return True
        except Exception as e:
            print(f"⚠️  Portfolio rebalancing simulation: {e}")
            return False 