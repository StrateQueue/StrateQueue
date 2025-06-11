"""
CLI Commands Module

Provides the base command class and command registry for the modular CLI system.
"""

from .base_command import BaseCommand
from .list import ListCommand
from .status import StatusCommand
from .setup import SetupCommand
from .deploy_command import DeployCommand
from .hotswap_command import HotswapCommand
from .webui_command import WebuiCommand

__all__ = [
    'BaseCommand',
    'ListCommand',
    'StatusCommand',
    'SetupCommand',
    'DeployCommand',
    'HotswapCommand',
    'WebuiCommand',
] 