"""
Base Parser Class

Provides common parsing functionality and standardized argument patterns
used across different CLI commands.
"""

import argparse
import logging

logger = logging.getLogger(__name__)


class BaseParser:
    """
    Base class for command-specific parsers

    Provides common argument patterns and utilities used across
    different CLI commands.
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @staticmethod
    def add_common_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """
        Add arguments common to most commands

        Args:
            parser: ArgumentParser to configure

        Returns:
            Configured parser
        """
        parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

        parser.add_argument(
            "--dry-run", action="store_true", help="Show what would be done without executing"
        )

        return parser

    @staticmethod
    def add_strategy_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """
        Add strategy-related arguments

        Args:
            parser: ArgumentParser to configure

        Returns:
            Configured parser
        """
        strategy_group = parser.add_argument_group("Strategy Options")

        strategy_group.add_argument(
            "--strategy",
            "--strategies",
            type=str,
            help="Strategy file(s) or strategy configuration",
        )

        strategy_group.add_argument(
            "--allocation",
            "--allocations",
            type=str,
            help="Strategy allocation(s) (comma-separated for multiple strategies)",
        )

        return parser

    @staticmethod
    def add_symbol_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """
        Add symbol/market arguments

        Args:
            parser: ArgumentParser to configure

        Returns:
            Configured parser
        """
        market_group = parser.add_argument_group("Market Options")

        market_group.add_argument("--symbol", type=str, help="Trading symbols (comma-separated)")

        market_group.add_argument(
            "--timeframe",
            dest="granularity",
            type=str,
            help="Timeframe (e.g., 1m, 5m, 1h, 1d)",
        )

        return parser

    @staticmethod
    def add_data_source_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """
        Add data source arguments

        Args:
            parser: ArgumentParser to configure

        Returns:
            Configured parser
        """
        data_group = parser.add_argument_group("Data Source Options")

        data_group.add_argument(
            "--data-source",
            choices=["polygon", "coinmarketcap", "demo", "yfinance"],
            default="yfinance",
            help="Data source for market data",
        )

        from ...multi_strategy.strategy_config import DEFAULT_LOOKBACK_PERIOD

        data_group.add_argument(
            "--lookback",
            type=int,
            default=DEFAULT_LOOKBACK_PERIOD,
            help=f"Lookback period for historical data (default: {DEFAULT_LOOKBACK_PERIOD} bars)",
        )

        return parser

    @staticmethod
    def add_broker_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """
        Add broker-related arguments

        Args:
            parser: ArgumentParser to configure

        Returns:
            Configured parser
        """
        broker_group = parser.add_argument_group("Broker Options")

        broker_group.add_argument("--broker", type=str, help="Broker to use for trading")

        broker_group.add_argument("--paper", action="store_true", help="Use paper trading mode")

        broker_group.add_argument(
            "--live",
            action="store_true",
            help="Use live trading mode (requires proper credentials)",
        )

        return parser

    @staticmethod
    def parse_comma_separated(value: str) -> list[str]:
        """
        Parse comma-separated values

        Args:
            value: Comma-separated string

        Returns:
            List of cleaned values
        """
        if not value:
            return []

        return [item.strip() for item in value.split(",") if item.strip()]

    @staticmethod
    def apply_smart_defaults(values: list[str], target_count: int, arg_name: str) -> list[str]:
        """
        Apply smart defaults when fewer values than expected are provided

        Args:
            values: List of provided values
            target_count: Expected number of values
            arg_name: Argument name for error messages

        Returns:
            List with applied defaults
        """
        if len(values) == 0:
            raise ValueError(f"No {arg_name} provided")

        if len(values) == 1 and target_count > 1:
            # Use the single value for all targets
            return values * target_count

        if len(values) != target_count:
            raise ValueError(
                f"Expected {target_count} {arg_name}, got {len(values)}. "
                f"Provide either 1 (will be applied to all) or {target_count} values."
            )

        return values
