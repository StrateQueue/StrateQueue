"""
Base Formatter Class

Provides consistent output formatting and display utilities
used across different CLI commands.
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class BaseFormatter:
    """
    Base class for output formatting

    Provides consistent formatting patterns used across different CLI commands.
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @staticmethod
    def format_header(title: str, width: int = 50) -> str:
        """
        Format a header with title and separator

        Args:
            title: Header title
            width: Total width of header

        Returns:
            Formatted header string
        """
        return f"\n{title}\n{'=' * width}\n"

    @staticmethod
    def format_section(title: str, width: int = 30) -> str:
        """
        Format a section header

        Args:
            title: Section title
            width: Width of separator

        Returns:
            Formatted section string
        """
        return f"\n{title}:\n{'-' * width}\n"

    @staticmethod
    def format_success(message: str) -> str:
        """
        Format success message

        Args:
            message: Success message

        Returns:
            Formatted success message
        """
        return f"✅ {message}"

    @staticmethod
    def format_error(message: str) -> str:
        """
        Format error message

        Args:
            message: Error message

        Returns:
            Formatted error message
        """
        return f"❌ {message}"

    @staticmethod
    def format_warning(message: str) -> str:
        """
        Format warning message

        Args:
            message: Warning message

        Returns:
            Formatted warning message
        """
        return f"⚠️ {message}"

    @staticmethod
    def format_info(message: str) -> str:
        """
        Format info message

        Args:
            message: Info message

        Returns:
            Formatted info message
        """
        return f"ℹ️ {message}"

    @staticmethod
    def format_status_icon(status: str) -> str:
        """
        Get status icon for common statuses

        Args:
            status: Status string

        Returns:
            Appropriate emoji icon
        """
        status_icons = {
            "active": "🟢",
            "running": "🟢",
            "paused": "⏸️",
            "stopped": "⏹️",
            "error": "🔴",
            "failed": "🔴",
            "warning": "🟡",
            "pending": "🟡",
            "unknown": "⚪",
            "success": "✅",
            "info": "ℹ️",
        }

        return status_icons.get(status.lower(), "⚪")

    @staticmethod
    def format_key_value_list(items: dict[str, Any], indent: str = "  ") -> str:
        """
        Format dictionary as key-value list

        Args:
            items: Dictionary to format
            indent: Indentation string

        Returns:
            Formatted key-value list
        """
        lines = []
        for key, value in items.items():
            lines.append(f"{indent}{key}: {value}")

        return "\n".join(lines)

    @staticmethod
    def format_table(headers: list[str], rows: list[list[str]], min_width: int = 10) -> str:
        """
        Format data as simple table

        Args:
            headers: Table headers
            rows: Table rows
            min_width: Minimum column width

        Returns:
            Formatted table string
        """
        if not headers or not rows:
            return ""

        # Calculate column widths
        widths = [max(len(str(header)), min_width) for header in headers]

        for row in rows:
            for i, cell in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(str(cell)))

        # Format header
        header_line = " | ".join(
            header.ljust(width) for header, width in zip(headers, widths, strict=False)
        )
        separator = "-+-".join("-" * width for width in widths)

        # Format rows
        row_lines = []
        for row in rows:
            row_line = " | ".join(
                str(cell).ljust(width) for cell, width in zip(row, widths, strict=False)
            )
            row_lines.append(row_line)

        return f"{header_line}\n{separator}\n" + "\n".join(row_lines)

    @staticmethod
    def format_percentage(value: float, decimals: int = 1) -> str:
        """
        Format percentage value

        Args:
            value: Percentage value (0.0 to 1.0)
            decimals: Number of decimal places

        Returns:
            Formatted percentage string
        """
        return f"{value:.{decimals}%}"

    @staticmethod
    def format_timestamp(timestamp: datetime = None) -> str:
        """
        Format timestamp for display

        Args:
            timestamp: Timestamp to format (default: now)

        Returns:
            Formatted timestamp string
        """
        if timestamp is None:
            timestamp = datetime.now()

        return timestamp.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def format_list_items(items: list[str], bullet: str = "•", indent: str = "  ") -> str:
        """
        Format list with bullets

        Args:
            items: List items
            bullet: Bullet character
            indent: Indentation

        Returns:
            Formatted list string
        """
        return "\n".join(f"{indent}{bullet} {item}" for item in items)

    @staticmethod
    def format_command_example(description: str, command: str, indent: str = "  ") -> str:
        """
        Format command example

        Args:
            description: Command description
            command: Command text
            indent: Indentation

        Returns:
            Formatted command example
        """
        return f"{indent}{description}:\n{indent}  {command}"
