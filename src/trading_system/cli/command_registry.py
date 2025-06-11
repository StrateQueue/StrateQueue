"""
Command Registry

Registers all available commands with the CommandFactory.
This module should be imported to ensure all commands are registered.
"""

from .command_factory import CommandFactory
from .commands import ListCommand, StatusCommand, SetupCommand, DeployCommand, WebuiCommand, PauseCommand, ResumeCommand, StopCommand, RemoveCommand, RebalanceCommand


def register_all_commands():
    """Register all available commands with the factory"""
    
    # Register the implemented commands
    CommandFactory.register_command(ListCommand)
    CommandFactory.register_command(StatusCommand)
    CommandFactory.register_command(SetupCommand)
    CommandFactory.register_command(DeployCommand)
    CommandFactory.register_command(WebuiCommand)
    CommandFactory.register_command(PauseCommand)
    CommandFactory.register_command(ResumeCommand)
    CommandFactory.register_command(StopCommand)
    CommandFactory.register_command(RemoveCommand)
    CommandFactory.register_command(RebalanceCommand)


# Auto-register commands when this module is imported
register_all_commands() 