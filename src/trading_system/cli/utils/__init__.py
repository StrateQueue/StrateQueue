"""
CLI Utils Module

Provides utility functions for the modular CLI system.
"""

from .logging_setup import setup_logging, get_cli_logger

__all__ = [
    'setup_logging',
    'get_cli_logger',
] 