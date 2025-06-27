"""Deploy Command Utilities

Utility functions for processing and validating deploy command arguments.
"""

import logging
import os
from argparse import Namespace
from pathlib import Path
import StrateQueue

logger = logging.getLogger(__name__)


def parse_comma_separated(value: str) -> list[str]:
    """
    Parse comma-separated string into list of strings

    Args:
        value: Comma-separated string

    Returns:
        List of strings with whitespace stripped
    """
    if not value:
        return []
    return [s.strip() for s in value.split(",") if s.strip()]


def apply_smart_defaults(values: list[str], target_count: int, arg_name: str) -> list[str]:
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
        raise ValueError(
            f"{arg_name}: expected 1 value (applies to all) or {target_count} values (one per strategy), got {len(values)}"
        )


def parse_symbols(symbols_str: str) -> list[str]:
    """
    Parse symbols string into list

    Args:
        symbols_str: Comma-separated symbols string

    Returns:
        List of symbol strings
    """
    return [s.strip().upper() for s in symbols_str.split(",") if s.strip()]


# Re-export the canonical setup_logging function


def create_inline_strategy_config(args: Namespace) -> str | None:
    """
    Create a temporary multi-strategy configuration from inline arguments

    Args:
        args: Parsed arguments with inline strategy configuration

    Returns:
        Temporary config content as string, or None if single strategy
    """
    if not hasattr(args, "_strategies") or len(args._strategies) <= 1:
        return None

    # Parse symbols for potential 1:1 mapping
    symbols = parse_symbols(args.symbol)

    # Check if we have 1:1 strategy-to-symbol mapping
    if len(args._strategies) == len(symbols):
        config_lines = [
            "# Auto-generated multi-strategy configuration from CLI arguments",
            "# Format: filename,strategy_id,allocation_percentage,symbol",
            "# 1:1 Strategy-to-Symbol mapping mode",
            "",
        ]

        # Use symbol-aware strategy ID generation for better uniqueness
        if not hasattr(args, "_strategy_ids") or not args._strategy_ids:
            unique_strategy_ids = generate_strategy_ids_with_symbols(args._strategies, symbols)
        else:
            unique_strategy_ids = args._strategy_ids

        for i, strategy_path in enumerate(args._strategies):
            strategy_id = unique_strategy_ids[i]
            allocation = args._allocations[i]
            symbol = symbols[i]

            config_lines.append(f"{strategy_path},{strategy_id},{allocation},{symbol}")

    else:
        # Traditional multi-strategy mode (all strategies on all symbols)
        config_lines = [
            "# Auto-generated multi-strategy configuration from CLI arguments",
            "# Format: filename,strategy_id,allocation_percentage",
            "",
        ]

        # Use regular unique strategy ID generation
        if not hasattr(args, "_strategy_ids") or not args._strategy_ids:
            unique_strategy_ids = generate_strategy_ids(args._strategies)
        else:
            unique_strategy_ids = args._strategy_ids

        for i, strategy_path in enumerate(args._strategies):
            strategy_id = unique_strategy_ids[i]
            allocation = args._allocations[i]

            config_lines.append(f"{strategy_path},{strategy_id},{allocation}")

    return "\n".join(config_lines)


def generate_strategy_ids(strategies: list[str]) -> list[str]:
    """
    Generate strategy IDs from strategy file paths with automatic uniqueness

    Args:
        strategies: List of strategy file paths

    Returns:
        List of unique strategy IDs derived from filenames
    """
    strategy_ids = []
    seen_ids = set()

    for strategy_path in strategies:
        # Use filename without extension as base strategy ID
        strategy_filename = os.path.basename(strategy_path)
        base_strategy_id = os.path.splitext(strategy_filename)[0]

        # Check for duplicates and generate unique ID if needed
        strategy_id = base_strategy_id
        if strategy_id in seen_ids:
            # Generate unique ID with timestamp
            from datetime import datetime

            timestamp = datetime.now().strftime("%y%m%d_%H%M")
            strategy_id = f"{base_strategy_id}_{timestamp}"

            # Final safety check for extreme edge cases
            counter = 1
            original_unique_id = strategy_id
            while strategy_id in seen_ids:
                strategy_id = f"{original_unique_id}_{counter}"
                counter += 1

        strategy_ids.append(strategy_id)
        seen_ids.add(strategy_id)

    return strategy_ids


def generate_strategy_ids_with_symbols(strategies: list[str], symbols: list[str]) -> list[str]:
    """
    Generate strategy IDs with symbol-based uniqueness for 1:1 mapping

    Args:
        strategies: List of strategy file paths
        symbols: List of symbols for 1:1 mapping

    Returns:
        List of unique strategy IDs with symbol integration
    """
    if len(strategies) != len(symbols):
        # Fallback to regular generation if not 1:1 mapping
        return generate_strategy_ids(strategies)

    strategy_ids = []
    seen_ids = set()

    for i, strategy_path in enumerate(strategies):
        # Use filename without extension as base strategy ID
        strategy_filename = os.path.basename(strategy_path)
        base_strategy_id = os.path.splitext(strategy_filename)[0]
        symbol = symbols[i]

        # Check for duplicates and generate unique ID if needed
        strategy_id = base_strategy_id
        if strategy_id in seen_ids:
            # For 1:1 mapping, append symbol first
            strategy_id = f"{base_strategy_id}_{symbol}"

            # If still conflicts, add timestamp
            if strategy_id in seen_ids:
                from datetime import datetime

                timestamp = datetime.now().strftime("%y%m%d_%H%M")
                strategy_id = f"{base_strategy_id}_{symbol}_{timestamp}"

                # Final safety check
                counter = 1
                original_unique_id = strategy_id
                while strategy_id in seen_ids:
                    strategy_id = f"{original_unique_id}_{counter}"
                    counter += 1

        strategy_ids.append(strategy_id)
        seen_ids.add(strategy_id)

    return strategy_ids


def validate_files_exist(file_paths: list[str]) -> list[str]:
    """
    Validate that all files in the list exist - if they aren't in the CWD,
    fall back to the examples bundled in the installed package.

    Args:
        file_paths: List of file paths to check

    Returns:
        List of error messages for missing files
    """
    errors = []
    
    # Helper to resolve bundled demo paths
    pkg_root = Path(StrateQueue.__file__).resolve().parent.parent  # <site-packages>
    
    def _resolve_demo(rel_path: str) -> str | None:
        candidate = (pkg_root / rel_path).resolve()
        return str(candidate) if candidate.exists() else None
    
    for i, original in enumerate(file_paths):
        if os.path.exists(original):
            continue
        resolved = _resolve_demo(original)
        if resolved:
            file_paths[i] = resolved  # mutate in-place so downstream code works
        else:
            errors.append(f"Strategy file not found: {original}")
    return errors


def validate_allocation_values(allocations: list[str]) -> list[str]:
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
        errors.append(
            "Cannot mix percentage (0-1) and dollar (>1) allocations. Use one type consistently."
        )

    # Validate percentage allocations sum to reasonable amount
    if has_percentage and total_percentage_allocation > 1.01:  # Allow small rounding errors
        errors.append(
            f"Total percentage allocation is {total_percentage_allocation:.1%}, which exceeds 100%"
        )
    elif has_percentage and total_percentage_allocation < 0.01:
        errors.append(
            f"Total percentage allocation is {total_percentage_allocation:.1%}, which is too small"
        )

    return errors
