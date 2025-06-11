"""
CLI Commands Module

Provides the base command class and command registry for the modular CLI system.
"""

from .base_command import BaseCommand
from .list import ListCommand
from .status import StatusCommand
from .setup import SetupCommand
from .deploy_command import DeployCommand
from .webui_command import WebuiCommand
from .pause_command import PauseCommand
from .resume_command import ResumeCommand
from .stop_command import StopCommand
from .remove_command import RemoveCommand
from .rebalance_command import RebalanceCommand

__all__ = [
    'BaseCommand',
    'ListCommand',
    'StatusCommand',
    'SetupCommand',
    'DeployCommand',
    'WebuiCommand',
    'PauseCommand',
    'ResumeCommand',
    'StopCommand',
    'RemoveCommand',
    'RebalanceCommand',
] 