"""Hotswap Command Parser

Handles complex argument parsing for hotswap command operations including
strategy deployment, management, and portfolio rebalancing.
"""

import argparse
from .base_parser import BaseParser


class HotswapParser(BaseParser):
    """Parser for hotswap command arguments"""
    
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add hotswap-specific arguments to parser"""
        
        # Hot swap operation (positional argument)
        parser.add_argument(
            'operation', 
            choices=['deploy', 'undeploy', 'pause', 'resume', 'rebalance', 'list'],
            help='Hot swap operation to perform'
        )
        
        # Strategy deployment options
        parser.add_argument(
            '--strategy', 
            help='Strategy file path (required for deploy operation)'
        )
        
        parser.add_argument(
            '--strategy-id', 
            help='Strategy identifier (required for deploy/undeploy/pause/resume)'
        )
        
        parser.add_argument(
            '--allocation', 
            type=float,
            help='Allocation percentage 0.0-1.0 (required for deploy operation)'
        )
        
        parser.add_argument(
            '--symbols',
            help='Symbol for 1:1 mapping (optional for deploy operation)'
        )
        
        # Undeploy options
        parser.add_argument(
            '--liquidate', 
            action='store_true', 
            default=True,
            help='Liquidate positions when undeploying (default: true)'
        )
        
        parser.add_argument(
            '--no-liquidate', 
            dest='liquidate', 
            action='store_false',
            help='Keep positions when undeploying'
        )
        
        # Rebalancing options
        parser.add_argument(
            '--allocations',
            help='New allocations in format "strategy1:0.4,strategy2:0.6" (required for rebalance)'
        )
        
        # System identification (to find running instance)
        parser.add_argument(
            '--config',
            help='Multi-strategy config file to identify the running system'
        )
        
        # Standard options
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
    
    def get_examples(self) -> str:
        """Get usage examples for hotswap command"""
        return """
Examples:
  # Deploy a new strategy at runtime
  stratequeue hotswap deploy --strategy sma.py --strategy-id sma_new --allocation 0.2
  
  # Undeploy a strategy
  stratequeue hotswap undeploy --strategy-id momentum_old
  
  # Pause a strategy (keeps positions)
  stratequeue hotswap pause --strategy-id sma_cross
  
  # Resume a paused strategy
  stratequeue hotswap resume --strategy-id sma_cross
  
  # Rebalance portfolio allocations
  stratequeue hotswap rebalance --allocations "sma:0.5,momentum:0.3,random:0.2"
  
  # List currently deployed strategies
  stratequeue hotswap list
  
  # Dry run to see what would happen
  stratequeue hotswap deploy --strategy sma.py --strategy-id test --allocation 0.1 --dry-run
        """ 