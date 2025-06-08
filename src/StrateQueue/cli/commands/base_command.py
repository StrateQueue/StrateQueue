"""
Base Command Class

Abstract base class that all CLI commands must inherit from.
Provides consistent interface and common functionality.
"""

import abc
import argparse
import logging

logger = logging.getLogger(__name__)


class BaseCommand(abc.ABC):
    """
    Abstract base class for all CLI commands

    Each command should inherit from this class and implement:
    - setup_parser(): Configure command-specific arguments
    - execute(): Run the command logic
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Command name (e.g., 'deploy', 'status')"""
        pass

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Command description for help text"""
        pass

    @property
    def aliases(self) -> list[str]:
        """Command aliases (optional)"""
        return []

    @abc.abstractmethod
    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """
        Configure command-specific arguments

        Args:
            parser: ArgumentParser instance to configure

        Returns:
            Configured parser
        """
        pass

    @abc.abstractmethod
    def execute(self, args: argparse.Namespace) -> int:
        """
        Execute the command

        Args:
            args: Parsed command line arguments

        Returns:
            Exit code (0 for success, non-zero for error)
        """
        pass

    def validate_args(self, args: argparse.Namespace) -> list[str] | None:
        """
        Validate command arguments

        Args:
            args: Parsed command line arguments

        Returns:
            List of validation errors, or None if valid
        """
        return None

    def pre_execute(self, args: argparse.Namespace) -> bool:
        """
        Pre-execution hook (e.g., setup, validation)

        Args:
            args: Parsed command line arguments

        Returns:
            True if execution should continue, False to abort
        """
        # Validate arguments
        errors = self.validate_args(args)
        if errors:
            for error in errors:
                self.logger.error(f"Validation error: {error}")
                print(f"❌ {error}")
            return False

        return True

    def post_execute(self, args: argparse.Namespace, exit_code: int) -> int:
        """
        Post-execution hook (e.g., cleanup, logging)

        Args:
            args: Parsed command line arguments
            exit_code: Exit code from execute()

        Returns:
            Final exit code
        """
        if exit_code == 0:
            self.logger.info(f"Command '{self.name}' completed successfully")
        else:
            self.logger.error(f"Command '{self.name}' failed with exit code {exit_code}")

        return exit_code

    def run(self, args: argparse.Namespace) -> int:
        """
        Full command execution with hooks

        Args:
            args: Parsed command line arguments

        Returns:
            Exit code
        """
        try:
            # Pre-execution
            if not self.pre_execute(args):
                return 1

            # Main execution
            exit_code = self.execute(args)

            # Post-execution
            return self.post_execute(args, exit_code)

        except Exception as e:
            self.logger.exception(f"Unexpected error in command '{self.name}': {e}")
            print(f"❌ Unexpected error: {e}")
            return 1
