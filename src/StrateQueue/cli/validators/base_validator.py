"""
Base Validator Class

Provides common validation patterns and utilities used across
different CLI commands for argument validation.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class BaseValidator:
    """
    Base class for argument validation

    Provides common validation patterns used across different CLI commands.
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @staticmethod
    def validate_file_exists(file_path: str, description: str = "file") -> str | None:
        """
        Validate that a file exists

        Args:
            file_path: Path to file
            description: Description for error messages

        Returns:
            Error message if invalid, None if valid
        """
        if not file_path:
            return f"{description} path cannot be empty"

        path = Path(file_path)
        if not path.exists():
            return f"{description} not found: {file_path}"

        if not path.is_file():
            return f"{description} is not a file: {file_path}"

        return None

    @staticmethod
    def validate_directory_exists(dir_path: str, description: str = "directory") -> str | None:
        """
        Validate that a directory exists

        Args:
            dir_path: Path to directory
            description: Description for error messages

        Returns:
            Error message if invalid, None if valid
        """
        if not dir_path:
            return f"{description} path cannot be empty"

        path = Path(dir_path)
        if not path.exists():
            return f"{description} not found: {dir_path}"

        if not path.is_dir():
            return f"{description} is not a directory: {dir_path}"

        return None

    @staticmethod
    def validate_symbols(symbols: list[str]) -> str | None:
        """
        Validate trading symbols format

        Args:
            symbols: List of symbols to validate

        Returns:
            Error message if invalid, None if valid
        """
        if not symbols:
            return "At least one symbol must be provided"

        for symbol in symbols:
            if not symbol or not symbol.strip():
                return "Symbol cannot be empty"

            # Basic symbol format validation
            clean_symbol = symbol.strip().upper()
            if not clean_symbol.replace("-", "").replace("/", "").isalnum():
                return f"Invalid symbol format: {symbol}"

        return None

    @staticmethod
    def validate_allocations(allocations: list[float], count: int) -> str | None:
        """
        Validate allocation values

        Args:
            allocations: List of allocation values
            count: Expected number of allocations

        Returns:
            Error message if invalid, None if valid
        """
        if len(allocations) != count:
            return f"Expected {count} allocations, got {len(allocations)}"

        for i, allocation in enumerate(allocations):
            if allocation < 0:
                return f"Allocation {i+1} cannot be negative: {allocation}"

            if allocation > 1:
                return f"Allocation {i+1} cannot exceed 100%: {allocation}"

        total = sum(allocations)
        if abs(total - 1.0) > 0.001:  # Allow small floating point errors
            return f"Total allocation must equal 100%, got {total:.1%}"

        return None

    @staticmethod
    def validate_data_source(data_source: str) -> str | None:
        """
        Validate data source

        Args:
            data_source: Data source name

        Returns:
            Error message if invalid, None if valid
        """
        valid_sources = ["polygon", "coinmarketcap", "demo"]

        if data_source not in valid_sources:
            return f"Invalid data source: {data_source}. Must be one of: {valid_sources}"

        return None

    @staticmethod
    def validate_broker_choice(broker: str, paper: bool, live: bool) -> str | None:
        """
        Validate broker configuration

        Args:
            broker: Broker name
            paper: Paper trading flag
            live: Live trading flag

        Returns:
            Error message if invalid, None if valid
        """
        if paper and live:
            return "Cannot specify both --paper and --live modes"

        if broker:
            # Try to validate broker exists
            try:
                from ...brokers import get_supported_brokers

                supported = get_supported_brokers()
                if broker not in supported:
                    return f"Unsupported broker: {broker}. Supported: {list(supported.keys())}"
            except ImportError:
                # Basic validation if broker module not available
                known_brokers = ["alpaca", "ibkr", "IBKR", "interactive-brokers", "interactive_brokers", "td_ameritrade"]
                if broker not in known_brokers:
                    return f"Unknown broker: {broker}. Known brokers: {known_brokers}"

        return None

    @staticmethod
    def validate_positive_integer(value: int, name: str) -> str | None:
        """
        Validate positive integer

        Args:
            value: Integer value to validate
            name: Parameter name for error messages

        Returns:
            Error message if invalid, None if valid
        """
        if value is None:
            return None  # Optional parameter

        if value <= 0:
            return f"{name} must be a positive integer, got: {value}"

        return None
