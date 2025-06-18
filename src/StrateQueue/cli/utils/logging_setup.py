"""
Logging Setup Utilities

Provides standardized logging configuration for CLI commands.
"""

import logging
import sys


def setup_logging(verbose: bool = False, log_file: str | None = None) -> None:
    """
    Setup logging configuration for CLI

    Args:
        verbose: Enable verbose/debug logging
        log_file: Optional log file path
    """
    # Determine log level
    log_level = logging.DEBUG if verbose else logging.INFO

    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Setup console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)

    # Setup file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # Always debug level for file
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Reduce noise from external libraries unless verbose
    if not verbose:
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("websocket").setLevel(logging.WARNING)


def get_cli_logger(name: str) -> logging.Logger:
    """
    Get a properly configured logger for CLI components

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    return logging.getLogger(f"StrateQueue.cli.{name}")
