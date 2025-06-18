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
            choices=["brokers", "granularities", "strategies", "strategy", "engines"],
            help="Type of resource to list",
        )

        parser.add_argument(
            "--all",
            action="store_true",
            help="Show all known engines including those with missing dependencies (engines only)",
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

        elif args.list_type == "granularities":
            print(InfoFormatter.format_granularity_info())
            return 0

        elif args.list_type in ["strategies", "strategy"]:
            return self._list_strategies(args)

        elif args.list_type == "engines":
            return self._list_engines(args)

        else:
            # This shouldn't happen due to choices constraint, but handle gracefully
            print(InfoFormatter.format_error(f"Unknown list type: {args.list_type}"))
            print("💡 Available options: brokers, granularities, strategies, engines")
            return 1

    def _list_strategies(self, args: argparse.Namespace) -> int:
        """List strategies (simplified version)"""
        print("📊 Strategy Listing")
        print("")
        print("Strategy listing is not available in this simplified version.")
        print("Previously this required daemon mode, which has been removed.")
        print("")
        print("💡 To see your strategies:")
        print("  • Check your strategy files directory")
        print("  • Use 'stratequeue deploy --strategy <file>' to run strategies")
        print("")
        return 0

    def _list_engines(self, args: argparse.Namespace) -> int:
        """List trading engines with availability information"""
        try:
            from ...engines import (
                get_supported_engines,
                get_all_known_engines,
                get_unavailable_engines,
            )

            supported = get_supported_engines()
            unavailable = get_unavailable_engines()

            if args.all:
                # Show comprehensive table with all engines
                print("🔧 Trading Engines (All)")
                print("")
                
                if not supported and not unavailable:
                    print("No engines found.")
                    return 0

                # Header
                print(f"{'Engine':<12} {'Status':<12} {'How to enable'}")
                print(f"{'-' * 12} {'-' * 12} {'-' * 50}")

                # Show supported engines
                for engine in supported:
                    print(f"{engine:<12} {'available':<12} (already installed)")

                # Show unavailable engines
                for engine, reason in unavailable.items():
                    print(f"{engine:<12} {'missing':<12} {reason}")

            else:
                # Show only supported engines (default)
                print("🔧 Trading Engines (Available)")
                print("")
                
                if not supported:
                    print("No engines are currently available.")
                    print("")
                    if unavailable:
                        print("💡 Engines that need installation:")
                        for engine, reason in unavailable.items():
                            print(f"  • {engine}: {reason}")
                        print("")
                        print("Run 'stratequeue list engines --all' to see details.")
                    return 0

                for engine in supported:
                    print(f"  • {engine}")

                if unavailable:
                    print("")
                    print(f"💡 {len(unavailable)} additional engine(s) available with installation.")
                    print("Run 'stratequeue list engines --all' to see details.")

            print("")
            return 0

        except Exception as e:
            print(f"❌ Error listing engines: {e}")
            return 1
