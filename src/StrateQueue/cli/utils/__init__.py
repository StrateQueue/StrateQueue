"""
CLI Utils Module

Provides utility functions for the modular CLI system.
"""

from .logging_setup import get_cli_logger, setup_logging

__all__ = [
    "setup_logging",
    "get_cli_logger",
]
