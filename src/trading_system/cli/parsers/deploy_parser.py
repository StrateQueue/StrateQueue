"""Deploy Command Parser

Argument parser for the deploy command with comprehensive options for 
single and multi-strategy deployment.
"""

import argparse
from .base_parser import BaseParser


class DeployParser(BaseParser):
    """Parser for deploy command arguments"""
    
    def configure_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """
        Configure the deploy command parser
        
        Args:
            parser: ArgumentParser to configure
            
        Returns:
            Configured argument parser for deploy command
        """
        # Strategy configuration
        self._add_strategy_arguments(parser)
        
        # Trading configuration  
        self._add_trading_arguments(parser)
        
        # Execution mode options
        self._add_execution_arguments(parser)
        
        # System control options
        self._add_system_arguments(parser)
        
        return parser
    
    def create_parser(self, subparsers) -> argparse.ArgumentParser:
        """
        Create the deploy subcommand parser
        
        Args:
            subparsers: Parent subparsers object
            
        Returns:
            Configured argument parser for deploy command
        """
        deploy_parser = subparsers.add_parser(
            'deploy',
            help='Deploy strategies for live trading',
            aliases=['run', 'start'],
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=self._get_deploy_examples()
        )
        
        # Strategy configuration
        self._add_strategy_arguments(deploy_parser)
        
        # Trading configuration  
        self._add_trading_arguments(deploy_parser)
        
        # Execution mode options
        self._add_execution_arguments(deploy_parser)
        
        # System control options
        self._add_system_arguments(deploy_parser)
        
        return deploy_parser
    
    def _add_strategy_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add strategy configuration arguments"""
        strategy_group = parser.add_argument_group('Strategy Configuration')

        strategy_group.add_argument(
            '--strategy', 
            required=True,
            help='Strategy file(s). Single or comma-separated list (e.g., sma.py or sma.py,momentum.py,random.py)'
        )

        strategy_group.add_argument(
            '--strategy-id',
            help='Strategy identifier(s). Optional - defaults to strategy filename(s). Single value or comma-separated list matching strategies.'
        )

        strategy_group.add_argument(
            '--allocation',
            help='Strategy allocation(s) as percentage (0-1) or dollar amount. Single value or comma-separated list (e.g., 0.4 or 0.4,0.35,0.25). Required for multi-strategy mode.'
        )
    
    def _add_trading_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add trading configuration arguments"""
                parser.add_argument(
            '--symbol',
            default='AAPL',
            help='Symbol(s) to trade. Single or comma-separated list (e.g., AAPL or ETH,BTC,AAPL). When number of symbols equals number of strategies, creates 1:1 mapping.'
        )
        
        parser.add_argument(
            '--data-source', 
            default='demo',
            help='Data source(s). Single value applies to all, or comma-separated list matching strategies (e.g., demo or polygon,coinmarketcap)'
        )
        
        parser.add_argument(
            '--granularity', 
            help='Data granularity/granularities. Single value applies to all, or comma-separated list matching strategies (e.g., 1m or 1m,5m,1h)'
        )
        
        parser.add_argument(
            '--broker',
            help='Broker(s) for trading. Single value applies to all, or comma-separated list matching strategies (e.g., alpaca or alpaca,kraken)'
        )
        
        parser.add_argument(
            '--lookback', 
            type=int, 
            help='Override calculated lookback period'
        )
    
    def _add_execution_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add execution mode arguments"""
        execution_group = parser.add_argument_group('Execution Mode')
        
        # Create mutually exclusive group for trading modes
        mode_group = execution_group.add_mutually_exclusive_group()
        
        mode_group.add_argument(
            '--paper', 
            action='store_true', 
            default=True,
            help='Paper trading mode (fake money, default)'
        )
        
        mode_group.add_argument(
            '--live', 
            action='store_true',
            help='Live trading mode (real money, use with caution!)'
        )
        
        mode_group.add_argument(
            '--no-trading', 
            action='store_true',
            help='Signals only mode (no trading execution)'
        )
    
    def _add_system_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add system control arguments"""
        system_group = parser.add_argument_group('System Control')
        
        system_group.add_argument(
            '--duration', 
            type=int, 
            default=60,
            help='Runtime duration in minutes (default: 60)'
        )
        
        system_group.add_argument(
            '--daemon', 
            action='store_true',
            help='Run in background mode (enables hot swapping from same terminal)'
        )
        
        system_group.add_argument(
            '--pid-file', 
            help='PID file path for daemon mode (default: .stratequeue.pid)'
        )
        
        system_group.add_argument(
            '--verbose', 
            action='store_true',
            help='Enable verbose logging'
        )
    
    def _get_deploy_examples(self) -> str:
        """Get examples for deploy command"""
        return """
Examples:
  # Single strategy mode
  stratequeue deploy --strategy sma.py --symbols AAPL,MSFT --data-source demo
  
  # Multi-strategy mode (comma-separated values)
  stratequeue deploy --strategy sma.py,momentum.py,random.py --allocation 0.4,0.35,0.25 --symbols AAPL,MSFT --data-source demo
  
  # Multi-strategy with 1:1 strategy-symbol mapping
  stratequeue deploy --strategy sma.py,random.py --allocation 0.5,0.5 --symbols ETH,AAPL --data-source demo
  
  # Multi-strategy with custom strategy IDs
  stratequeue deploy --strategy sma.py,momentum.py --strategy-id sma_cross,momentum_trend --allocation 0.6,0.4 --symbols AAPL
  
  # Multi-strategy with dollar allocations
  stratequeue deploy --strategy sma.py,momentum.py --allocation 1000,500 --symbols AAPL --broker alpaca --paper
  
  # Multi-strategy with different granularities per strategy
  stratequeue deploy --strategy sma.py,momentum.py --allocation 0.6,0.4 --granularity 1m,5m --symbols ETH,BTC
  
  # Multi-strategy with different data sources per strategy  
  stratequeue deploy --strategy sma.py,momentum.py --allocation 0.6,0.4 --data-source polygon,coinmarketcap --symbols AAPL,ETH
  
  # Single value applies to all strategies
  stratequeue deploy --strategy sma.py,momentum.py --allocation 0.5,0.5 --granularity 1m --broker alpaca --symbols ETH
  
  # Run with real Polygon data
  stratequeue deploy --strategy sma.py --symbols AAPL --data-source polygon --lookback 50
  
  # Paper trading (default behavior)
  stratequeue deploy --strategy sma.py --symbols AAPL --paper
  
  # Live trading (use with caution!)
  stratequeue deploy --strategy sma.py --symbols AAPL --live
  
  # Disable trading execution (signals only)
  stratequeue deploy --strategy sma.py --symbols AAPL --no-trading
  
  # Multi-strategy with live trading
  stratequeue deploy --strategy sma.py,momentum.py --allocation 0.6,0.4 --symbols AAPL,MSFT --live
  
  # Daemon mode for background execution
  stratequeue deploy --strategy sma.py --symbols AAPL --daemon --duration 120
  
  # Verbose logging
  stratequeue deploy --strategy sma.py --symbols AAPL --verbose
        """ 