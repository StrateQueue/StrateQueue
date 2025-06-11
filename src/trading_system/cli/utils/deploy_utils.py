"""Deploy Command Utilities

Utility functions for processing and validating deploy command arguments.
"""

import os
import logging
import tempfile
from typing import List, Optional
from argparse import Namespace

logger = logging.getLogger(__name__)


def parse_comma_separated(value: str) -> List[str]:
    """
    Parse comma-separated string into list of strings
    
    Args:
        value: Comma-separated string
        
    Returns:
        List of strings with whitespace stripped
    """
    if not value:
        return []
    return [s.strip() for s in value.split(',') if s.strip()]


def apply_smart_defaults(values: List[str], target_count: int, arg_name: str) -> List[str]:
    """
    Apply smart defaulting logic: single value applies to all, multiple values must match count
    
    Args:
        values: List of values
        target_count: Target count (usually number of strategies)
        arg_name: Argument name for error messages
        
    Returns:
        List with proper count
        
    Raises:
        ValueError: If count doesn't match and isn't 1
    """
    if not values:
        return []
    
    if len(values) == 1:
        # Single value applies to all
        return values * target_count
    elif len(values) == target_count:
        # Perfect match
        return values
    else:
        # Mismatch
        raise ValueError(f"{arg_name}: expected 1 value (applies to all) or {target_count} values (one per strategy), got {len(values)}")


def parse_symbols(symbols_str: str) -> List[str]:
    """
    Parse symbols string into list
    
    Args:
        symbols_str: Comma-separated symbols string
        
    Returns:
        List of symbol strings
    """
    return [s.strip().upper() for s in symbols_str.split(',') if s.strip()]


def setup_logging(verbose: bool = False):
    """
    Setup logging configuration
    
    Args:
        verbose: Enable verbose (DEBUG) logging
    """
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('trading_system.log')
        ]
    )


def create_inline_strategy_config(args: Namespace) -> Optional[str]:
    """
    Create a temporary multi-strategy configuration from inline arguments
    
    Args:
        args: Parsed arguments with inline strategy configuration
        
    Returns:
        Temporary config content as string, or None if single strategy
    """
    if not hasattr(args, '_strategies') or len(args._strategies) <= 1:
        return None
    
    # Parse symbols for potential 1:1 mapping
    symbols = parse_symbols(args.symbol)
    
    # Check if we have 1:1 strategy-to-symbol mapping
    if len(args._strategies) == len(symbols):
        config_lines = [
            "# Auto-generated multi-strategy configuration from CLI arguments",
            "# Format: filename,strategy_id,allocation_percentage,symbol",
            "# 1:1 Strategy-to-Symbol mapping mode",
            ""
        ]
        
        for i, strategy_path in enumerate(args._strategies):
            strategy_id = args._strategy_ids[i]
            allocation = args._allocations[i]
            symbol = symbols[i]
            
            config_lines.append(f"{strategy_path},{strategy_id},{allocation},{symbol}")
        
    else:
        # Traditional multi-strategy mode (all strategies on all symbols)
        config_lines = [
            "# Auto-generated multi-strategy configuration from CLI arguments",
            "# Format: filename,strategy_id,allocation_percentage",
            ""
        ]
        
        for i, strategy_path in enumerate(args._strategies):
            strategy_id = args._strategy_ids[i]
            allocation = args._allocations[i]
            
            config_lines.append(f"{strategy_path},{strategy_id},{allocation}")
    
    return "\n".join(config_lines)


def generate_strategy_ids(strategies: List[str]) -> List[str]:
    """
    Generate strategy IDs from strategy file paths
    
    Args:
        strategies: List of strategy file paths
        
    Returns:
        List of strategy IDs derived from filenames
    """
    strategy_ids = []
    for strategy_path in strategies:
        # Use filename without extension as default strategy ID
        strategy_filename = os.path.basename(strategy_path)
        strategy_id = os.path.splitext(strategy_filename)[0]
        strategy_ids.append(strategy_id)
    return strategy_ids


def validate_files_exist(file_paths: List[str]) -> List[str]:
    """
    Validate that all files in the list exist
    
    Args:
        file_paths: List of file paths to check
        
    Returns:
        List of error messages for missing files
    """
    errors = []
    for file_path in file_paths:
        if not os.path.exists(file_path):
            errors.append(f"Strategy file not found: {file_path}")
    return errors


def validate_allocation_values(allocations: List[str]) -> List[str]:
    """
    Validate allocation values for consistency and correctness
    
    Args:
        allocations: List of allocation strings
        
    Returns:
        List of error messages
    """
    errors = []
    
    if not allocations:
        return errors
    
    total_percentage_allocation = 0.0
    total_dollar_allocation = 0.0
    has_percentage = False
    has_dollar = False
    
    for i, allocation_str in enumerate(allocations):
        try:
            allocation_value = float(allocation_str)
            
            if allocation_value <= 0:
                errors.append(f"Allocation {i+1} must be positive, got {allocation_value}")
                continue
            
            # Determine if this is percentage (0-1) or dollar amount (>1)
            if allocation_value <= 1:
                # Percentage allocation
                has_percentage = True
                total_percentage_allocation += allocation_value
            else:
                # Dollar allocation
                has_dollar = True
                total_dollar_allocation += allocation_value
                
        except ValueError:
            errors.append(f"Invalid allocation value: {allocation_str}. Must be a number.")
    
    # Check for mixing allocation types
    if has_percentage and has_dollar:
        errors.append("Cannot mix percentage (0-1) and dollar (>1) allocations. Use one type consistently.")
    
    # Validate percentage allocations sum to reasonable amount
    if has_percentage and total_percentage_allocation > 1.01:  # Allow small rounding errors
        errors.append(f"Total percentage allocation is {total_percentage_allocation:.1%}, which exceeds 100%")
    elif has_percentage and total_percentage_allocation < 0.01:
        errors.append(f"Total percentage allocation is {total_percentage_allocation:.1%}, which is too small")
    
    return errors 