"""Hotswap Command Validator

Handles complex validation logic for hotswap command operations including
strategy deployment, management, and portfolio rebalancing.
"""

import os
from typing import List, Tuple, Dict, Any
from argparse import Namespace

from .base_validator import BaseValidator


class HotswapValidator(BaseValidator):
    """Validator for hotswap command arguments"""
    
    def validate(self, args: Namespace) -> Tuple[bool, List[str]]:
        """
        Validate hotswap operation arguments
        
        Args:
            args: Parsed command arguments
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Validate based on operation type
        if args.operation == 'deploy':
            deploy_errors = self._validate_deploy_operation(args)
            errors.extend(deploy_errors)
            
        elif args.operation == 'undeploy':
            undeploy_errors = self._validate_undeploy_operation(args)
            errors.extend(undeploy_errors)
            
        elif args.operation in ['pause', 'resume']:
            pause_resume_errors = self._validate_pause_resume_operation(args)
            errors.extend(pause_resume_errors)
            
        elif args.operation == 'rebalance':
            rebalance_errors = self._validate_rebalance_operation(args)
            errors.extend(rebalance_errors)
            
        elif args.operation == 'list':
            # List operation needs no specific validation
            pass
        
        return len(errors) == 0, errors
    
    def _validate_deploy_operation(self, args: Namespace) -> List[str]:
        """Validate deploy operation arguments"""
        errors = []
        
        # Strategy file is required
        if not args.strategy:
            errors.append("--strategy is required for deploy operation")
        else:
            # Validate strategy file exists
            if not os.path.exists(args.strategy):
                errors.append(f"Strategy file not found: {args.strategy}")
        
        # Strategy ID is required
        if not args.strategy_id:
            errors.append("--strategy-id is required for deploy operation")
        
        # Allocation is required
        if args.allocation is None:
            errors.append("--allocation is required for deploy operation")
        else:
            # Validate allocation value
            if args.allocation <= 0:
                errors.append("Allocation must be positive")
            elif args.allocation > 1:
                errors.append("Allocation must be <= 1.0 (100%)")
        
        return errors
    
    def _validate_undeploy_operation(self, args: Namespace) -> List[str]:
        """Validate undeploy operation arguments"""
        errors = []
        
        # Strategy ID is required
        if not args.strategy_id:
            errors.append("--strategy-id is required for undeploy operation")
        
        return errors
    
    def _validate_pause_resume_operation(self, args: Namespace) -> List[str]:
        """Validate pause/resume operation arguments"""
        errors = []
        
        # Strategy ID is required
        if not args.strategy_id:
            errors.append(f"--strategy-id is required for {args.operation} operation")
        
        return errors
    
    def _validate_rebalance_operation(self, args: Namespace) -> List[str]:
        """Validate rebalance operation arguments"""
        errors = []
        
        # Allocations are required
        if not args.allocations:
            errors.append("--allocations is required for rebalance operation")
        else:
            # Parse and validate allocations format
            allocation_errors = self._validate_allocations_format(args.allocations)
            errors.extend(allocation_errors)
        
        return errors
    
    def _validate_allocations_format(self, allocations_str: str) -> List[str]:
        """Validate allocations string format"""
        errors = []
        
        try:
            # Parse "strategy1:0.4,strategy2:0.6" format
            allocations = {}
            total_allocation = 0.0
            
            for alloc_pair in allocations_str.split(','):
                if ':' not in alloc_pair:
                    errors.append(f"Invalid allocation format: '{alloc_pair}'. Expected 'strategy:allocation'")
                    continue
                
                parts = alloc_pair.split(':')
                if len(parts) != 2:
                    errors.append(f"Invalid allocation format: '{alloc_pair}'. Expected 'strategy:allocation'")
                    continue
                
                strategy_id = parts[0].strip()
                allocation_str = parts[1].strip()
                
                if not strategy_id:
                    errors.append("Strategy ID cannot be empty in allocation")
                    continue
                
                try:
                    allocation_value = float(allocation_str)
                    if allocation_value <= 0:
                        errors.append(f"Allocation for '{strategy_id}' must be positive, got {allocation_value}")
                    elif allocation_value > 1:
                        errors.append(f"Allocation for '{strategy_id}' must be <= 1.0, got {allocation_value}")
                    else:
                        allocations[strategy_id] = allocation_value
                        total_allocation += allocation_value
                        
                except ValueError:
                    errors.append(f"Invalid allocation value for '{strategy_id}': '{allocation_str}'. Must be a number.")
            
            # Check total allocation
            if allocations and total_allocation > 1.01:  # Allow small rounding errors
                errors.append(f"Total allocation is {total_allocation:.1%}, which exceeds 100%")
            elif allocations and total_allocation < 0.01:
                errors.append(f"Total allocation is {total_allocation:.1%}, which is too small")
                
        except Exception as e:
            errors.append(f"Error parsing allocations: {e}")
        
        return errors
    
    def validate_strategy_exists_in_system(self, strategy_id: str, system: Dict[str, Any]) -> bool:
        """
        Validate that a strategy exists in the running system
        
        Args:
            strategy_id: Strategy identifier to check
            system: Running system info
            
        Returns:
            True if strategy exists
        """
        strategies = system.get('strategies', {})
        return strategy_id in strategies
    
    def validate_strategy_not_exists_in_system(self, strategy_id: str, system: Dict[str, Any]) -> bool:
        """
        Validate that a strategy does NOT exist in the running system
        
        Args:
            strategy_id: Strategy identifier to check
            system: Running system info
            
        Returns:
            True if strategy does not exist
        """
        return not self.validate_strategy_exists_in_system(strategy_id, system) 