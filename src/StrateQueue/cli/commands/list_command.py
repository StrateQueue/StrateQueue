"""
List Command

Command for listing available options and resources.
This includes brokers, granularities, and strategies.
"""

import argparse

from ..formatters.info_formatter import InfoFormatter
from .base_command import BaseCommand


class ListCommand(BaseCommand):
    """
    List command implementation

    Handles listing of various system resources and options.
    """

    def __init__(self):
        super().__init__()

    @property
    def name(self) -> str:
        return "list"

    @property
    def description(self) -> str:
        return "List available options and resources"

    @property
    def aliases(self) -> list[str]:
        return ["ls"]

    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Configure list command arguments"""

        parser.add_argument(
            "list_type",
            nargs="?",
            choices=["brokers", "providers", "engines"],
            help="Type of resource to list",
        )

        # Retain --all flag for potential future expansion, but hide it from help
        parser.add_argument(
            "--all",
            action="store_true",
            help=argparse.SUPPRESS,
        )

        return parser

    def validate_args(self, args: argparse.Namespace) -> list[str] | None:
        """Validate list command arguments"""
        # No validation needed - all arguments are optional with choices
        return None

    def execute(self, args: argparse.Namespace) -> int:
        """Execute list command"""

        if not hasattr(args, "list_type") or args.list_type is None:
            # No list type provided, show available options
            print(InfoFormatter.format_command_help())
            return 0

        if args.list_type == "brokers":
            print(InfoFormatter.format_broker_info())
            return 0

        elif args.list_type == "providers":
            print(InfoFormatter.format_provider_info())
            return 0

        elif args.list_type == "engines":
            print(InfoFormatter.format_engine_info())
            return 0

        else:
            # This shouldn't happen due to choices constraint, but handle gracefully
            print(InfoFormatter.format_error(f"Unknown list type: {args.list_type}"))
            print("💡 Available options: brokers, providers, engines")
            return 1

    # Deprecated methods retained for backward compatibility but not exposed
    def _list_strategies(self, args: argparse.Namespace) -> int:
        """This method is deprecated and retained for compatibility."""
        print("⚠️  Strategy listing is no longer supported via CLI.")
        return 0

    def _list_engines(self, args: argparse.Namespace) -> int:
        """This method is deprecated and retained for compatibility."""
        print("⚠️  Engine listing is no longer supported via CLI.")
        return 0
