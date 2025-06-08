"""
Status Command

Command for checking system and broker environment status.
"""

import argparse

from ..formatters import InfoFormatter
from .base_command import BaseCommand


class StatusCommand(BaseCommand):
    """
    Status command implementation

    Checks system and broker environment status, including credential validation.
    """

    @property
    def name(self) -> str:
        return "status"

    @property
    def description(self) -> str:
        return "Check system and broker status"

    @property
    def aliases(self) -> list[str]:
        return ["check", "health"]

    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Configure status command arguments"""

        parser.add_argument(
            "status_type",
            nargs="?",
            default="system",
            choices=["broker", "provider", "system"],
            help="Type of status to check (default: system = brokers + providers)",
        )

        parser.add_argument(
            "--detailed", "-d", action="store_true", help="Show detailed status information"
        )

        return parser

    def validate_args(self, args: argparse.Namespace) -> list[str] | None:
        """Validate status command arguments"""
        # No validation needed - all arguments are optional with choices
        return None

    def execute(self, args: argparse.Namespace) -> int:
        """Execute status command"""

        if args.status_type == "broker":
            print(InfoFormatter.format_broker_status())
            return 0

        elif args.status_type == "provider":
            print(InfoFormatter.format_provider_status())
            return 0

        elif args.status_type == "system":
            # Show both broker and provider status for a holistic view
            print(InfoFormatter.format_broker_status())
            print(InfoFormatter.format_provider_status())

            # Placeholder for future system health checks (daemon, database, etc.)
            return 0

        else:
            # This shouldn't happen due to choices constraint, but handle gracefully
            print(InfoFormatter.format_error(f"Unknown status type: {args.status_type}"))
            print("💡 Available options: broker, provider, system")
            print("💡 Try: stratequeue status broker")
            return 1
