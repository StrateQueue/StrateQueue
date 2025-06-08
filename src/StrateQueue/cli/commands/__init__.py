"""
CLI Commands Module

Provides the base command class and command registry for the modular CLI system.
"""

from .base_command import BaseCommand
from .daemon_command import DaemonCommand
from .deploy_command import DeployCommand
from .list_command import ListCommand
from .setup_command import SetupCommand
from .status_command import StatusCommand
from .webui_command import WebUICommand

__all__ = [
    "BaseCommand",
    "DaemonCommand",
    "ListCommand",
    "StatusCommand",
    "SetupCommand",
    "DeployCommand",
    "WebUICommand",
]
