"""
Command Registry

Centralized registration of all CLI commands.
Import this module to ensure all commands are registered.
"""

from .command_factory import CommandFactory
from .commands import ListCommand, StatusCommand, SetupCommand, DeployCommand, WebuiCommand, DaemonCommand

# Register all commands
CommandFactory.register_command(ListCommand)
CommandFactory.register_command(StatusCommand)
CommandFactory.register_command(SetupCommand)
CommandFactory.register_command(DeployCommand)
CommandFactory.register_command(WebuiCommand) 
CommandFactory.register_command(DaemonCommand) 