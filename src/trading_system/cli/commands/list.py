"""
List Command

Command for listing available options like brokers, granularities, strategies, etc.
"""

import argparse
from typing import Optional, List

from .base_command import BaseCommand
from ..formatters import InfoFormatter
from ..utils.daemon_manager import DaemonManager


class ListCommand(BaseCommand):
    """
    List command implementation
    
    Shows available options like supported brokers, data granularities, and live strategies.
    """
    
    def __init__(self):
        super().__init__()
        self.daemon_manager = DaemonManager()
    
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
            return self._list_strategies(args)
            
        else:
            # This shouldn't happen due to choices constraint, but handle gracefully
            print(InfoFormatter.format_error(f"Unknown list type: {args.list_type}"))
            print("💡 Available options: brokers, granularities, strategies")
            print("💡 Try: stratequeue list strategies")
            return 1
    
    def _list_strategies(self, args: argparse.Namespace) -> int:
        """List currently running strategies using live IPC data"""
        try:
            print("📋 Current Strategy Status:")
            
            # First verify daemon exists using pickled data
            success, system_info, error = self.daemon_manager.load_daemon_system(config_file=args.config)
            if not success:
                print(f"❌ {error}")
                print("💡 No trading system is currently running")
                print("💡 Start a system in daemon mode first:")
                print("   stratequeue deploy --strategy sma.py --symbol AAPL --daemon")
                return 1
            
            # Show basic system info from cached data
            print(f"🔗 Connected to running system (PID: {system_info.get('pid', 'unknown')})")
            print(f"📊 Mode: {system_info.get('mode', 'unknown')}")
            print("")
            
            # Now get LIVE strategy data via IPC instead of stale pickled data
            print("🔍 Retrieving live strategy data via IPC...")
            ipc_command = {
                'type': 'get_status',
                'include_statistics': True  # Get stats for more complete view
            }
            
            ipc_response = self.daemon_manager.ipc.send_command(ipc_command)
            
            if ipc_response.get('success'):
                live_status = ipc_response.get('status', {})
                live_strategies = live_status.get('strategies', {})
                
                print(f"✅ Retrieved live data: {len(live_strategies)} strategies")
                
                if not live_strategies:
                    print("   No strategies currently deployed")
                    return 0
                
                print(f"🎯 Found {len(live_strategies)} strategies:")
                print("")
                
                total_allocation = 0.0
                for strategy_id, info in live_strategies.items():
                    status = info.get('status', 'unknown')
                    allocation = info.get('allocation', 0.0)
                    
                    # Get symbols from cached data if not in live data
                    symbols = info.get('symbols', [])
                    if not symbols:
                        cached_strategy = system_info.get('strategies', {}).get(strategy_id, {})
                        symbols = cached_strategy.get('symbols', ['unknown'])
                    
                    # Convert symbols list to string if needed
                    if isinstance(symbols, list):
                        symbols_str = ', '.join(symbols)
                    else:
                        symbols_str = str(symbols)
                    
                    status_emoji = {
                        'active': '🟢',
                        'paused': '⏸️',
                        'error': '🔴',
                        'initialized': '🟡',
                        'running': '🟢'
                    }.get(status, '⚪')
                    
                    print(f"   {status_emoji} {strategy_id}")
                    print(f"      Status: {status}")
                    print(f"      Allocation: {allocation:.1%}")
                    print(f"      Symbols: {symbols_str}")
                    
                    if args.verbose:
                        # Try to get path from cached data
                        cached_strategy = system_info.get('strategies', {}).get(strategy_id, {})
                        strategy_path = cached_strategy.get('path', 'unknown')
                        print(f"      Path: {strategy_path}")
                    print("")
                    
                    if isinstance(allocation, (int, float)):
                        total_allocation += allocation
                
                print(f"💰 Total allocation: {total_allocation:.1%}")
                
                # Show statistics if available
                stats = live_status.get('statistics', {})
                if stats and args.verbose:
                    print("")
                    print("📊 Live Statistics:")
                    if 'pnl' in stats:
                        pnl_stats = stats['pnl']
                        print(f"   P&L: ${pnl_stats.get('total_pnl', 0):.2f}")
                        print(f"   Trades: {pnl_stats.get('total_trades', 0)}")
                    if 'winloss' in stats:
                        wl_stats = stats['winloss']
                        print(f"   Win Rate: {wl_stats.get('win_rate', 0):.1%}")
                
            else:
                # Fallback to cached data if IPC fails
                print("⚠️  IPC connection failed, showing cached data (may be outdated)")
                print(f"   Error: {ipc_response.get('error', 'Unknown IPC error')}")
                
                strategies = system_info.get('strategies', {})
                if not strategies:
                    print("   No strategies in cached data")
                    return 0
                
                print(f"🎯 Found {len(strategies)} strategies (cached):")
                print("")
                
                total_allocation = 0.0
                for strategy_id, info in strategies.items():
                    status = info.get('status', 'unknown')
                    allocation = info.get('allocation', 0.0)
                    symbols = info.get('symbols', [])
                    strategy_path = info.get('path', 'unknown')
                    
                    # Convert symbols list to string if needed
                    if isinstance(symbols, list):
                        symbols_str = ', '.join(symbols)
                    else:
                        symbols_str = str(symbols)
                    
                    status_emoji = {
                        'active': '🟢',
                        'paused': '⏸️',
                        'error': '🔴',
                        'initialized': '🟡',
                        'running': '🟢'
                    }.get(status, '⚪')
                    
                    print(f"   {status_emoji} {strategy_id}")
                    print(f"      Status: {status}")
                    print(f"      Allocation: {allocation:.1%}")
                    print(f"      Symbols: {symbols_str}")
                    if args.verbose:
                        print(f"      Path: {strategy_path}")
                    print("")
                    
                    if isinstance(allocation, (int, float)):
                        total_allocation += allocation
                
                print(f"💰 Total allocation: {total_allocation:.1%}")
            
            # Show available management commands
            print("")
            print("🔧 Available management commands:")
            print("  stratequeue pause <strategy_id>    # Pause a strategy")
            print("  stratequeue resume <strategy_id>   # Resume a paused strategy")
            print("  stratequeue remove <strategy_id>   # Remove a strategy")
            print("  stratequeue stop                   # Stop entire system")
            
            return 0
            
        except Exception as e:
            print(f"❌ Error listing strategies: {e}")
            return 1 