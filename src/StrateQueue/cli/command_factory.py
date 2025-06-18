"""
Command Factory

Factory class for creating and managing CLI commands.
Follows the same pattern as BrokerFactory and EngineFactory.
"""

import logging

from .commands.base_command import BaseCommand

logger = logging.getLogger(__name__)


class CommandFactory:
    """
    Factory for creating and managing CLI commands

    Provides command registration, discovery, and creation functionality
    similar to BrokerFactory and EngineFactory.
    """

    _registered_commands: dict[str, type[BaseCommand]] = {}

    @classmethod
    def register_command(cls, command_class: type[BaseCommand]) -> None:
        """
        Register a command class

        Args:
            command_class: Command class to register
        """
        command_instance = command_class()
        command_name = command_instance.name

        if command_name in cls._registered_commands:
            logger.warning(f"Command '{command_name}' already registered, overwriting")

        cls._registered_commands[command_name] = command_class

        # Also register aliases
        for alias in command_instance.aliases:
            if alias in cls._registered_commands:
                logger.warning(f"Command alias '{alias}' already registered, overwriting")
            cls._registered_commands[alias] = command_class

        logger.debug(f"Registered command: {command_name}")

    @classmethod
    def get_command(cls, command_name: str) -> BaseCommand | None:
        """
        Create a command instance by name

        Args:
            command_name: Name of command to create

        Returns:
            Command instance or None if not found
        """
        command_class = cls._registered_commands.get(command_name)
        if command_class:
            return command_class()
        return None

    @classmethod
    def get_supported_commands(cls) -> dict[str, str]:
        """
        Get all supported commands with their descriptions

        Returns:
            Dictionary mapping command names to descriptions
        """
        commands = {}
        seen_classes = set()

        for _command_name, command_class in cls._registered_commands.items():
            # Avoid duplicates for commands with aliases
            if command_class in seen_classes:
                continue

            seen_classes.add(command_class)
            command_instance = command_class()

            # Use the primary name, not alias
            primary_name = command_instance.name
            commands[primary_name] = command_instance.description

        return commands

    @classmethod
    def list_commands(cls) -> list[str]:
        """
        List all available command names (including aliases)

        Returns:
            List of command names
        """
        return list(cls._registered_commands.keys())

    @classmethod
    def command_exists(cls, command_name: str) -> bool:
        """
        Check if a command exists

        Args:
            command_name: Command name to check

        Returns:
            True if command exists
        """
        return command_name in cls._registered_commands

    @classmethod
    def auto_discover_commands(cls) -> None:
        """
        Auto-discover and register commands from the commands module

        This method would scan for command classes and register them automatically.
        For now, commands need to be manually registered.
        """
        logger.debug("Auto-discovery not yet implemented")

    @classmethod
    def clear_registry(cls) -> None:
        """
        Clear the command registry (useful for testing)
        """
        cls._registered_commands.clear()
        logger.debug("Command registry cleared")


def register_command(command_class: type[BaseCommand]) -> type[BaseCommand]:
    """
    Decorator for registering commands

    Args:
        command_class: Command class to register

    Returns:
        The same command class (for decorator pattern)
    """
    CommandFactory.register_command(command_class)
    return command_class


def get_supported_commands() -> dict[str, str]:
    """
    Convenience function to get supported commands

    Returns:
        Dictionary mapping command names to descriptions
    """
    return CommandFactory.get_supported_commands()


def create_command(command_name: str) -> BaseCommand | None:
    """
    Convenience function to create a command

    Args:
        command_name: Name of command to create

    Returns:
        Command instance or None if not found
    """
    return CommandFactory.get_command(command_name)
