"""Color Formatter Utility

Provides utilities for colorful, attractive CLI output with support for:
- ANSI color codes
- Bold/italic text formatting
- Emoji integration
- Consistent styling across the CLI
"""

import os
import sys


# ANSI color codes
class Colors:
    """ANSI color code constants"""

    # Reset
    RESET = "\033[0m"

    # Regular colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    # Text formatting
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    REVERSE = "\033[7m"
    STRIKETHROUGH = "\033[9m"


class ColorFormatter:
    """Formatter for creating colorful CLI output"""

    def __init__(self, use_colors: bool | None = None):
        """
        Initialize color formatter

        Args:
            use_colors: Whether to use colors (auto-detect if None)
        """
        if use_colors is None:
            # Auto-detect color support
            self.use_colors = self._supports_color()
        else:
            self.use_colors = use_colors

    def _supports_color(self) -> bool:
        """Check if terminal supports colors"""
        # Check if running in a terminal
        if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
            return False

        # Check environment variables
        term = os.environ.get("TERM", "")
        if term == "dumb":
            return False

        # Check for color support indicators
        colorterm = os.environ.get("COLORTERM", "")
        if colorterm in ("truecolor", "24bit"):
            return True

        # Common color-supporting terminals
        if any(term.startswith(t) for t in ["xterm", "screen", "tmux", "rxvt"]):
            return True

        return True  # Default to supporting colors

    def colorize(
        self,
        text: str,
        color: str = "",
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
    ) -> str:
        """
        Apply color and formatting to text

        Args:
            text: Text to format
            color: Color code (from Colors class)
            bold: Apply bold formatting
            italic: Apply italic formatting
            underline: Apply underline formatting

        Returns:
            Formatted text
        """
        if not self.use_colors:
            return text

        formatting = []

        if bold:
            formatting.append(Colors.BOLD)
        if italic:
            formatting.append(Colors.ITALIC)
        if underline:
            formatting.append(Colors.UNDERLINE)
        if color:
            formatting.append(color)

        if formatting:
            return "".join(formatting) + text + Colors.RESET

        return text

    def title(self, text: str) -> str:
        """Format text as a title (bold, bright blue)"""
        return self.colorize(text, Colors.BRIGHT_BLUE, bold=True)

    def subtitle(self, text: str) -> str:
        """Format text as a subtitle (cyan)"""
        return self.colorize(text, Colors.CYAN, bold=True)

    def success(self, text: str) -> str:
        """Format text as success message (green)"""
        return self.colorize(text, Colors.BRIGHT_GREEN, bold=True)

    def warning(self, text: str) -> str:
        """Format text as warning (yellow)"""
        return self.colorize(text, Colors.BRIGHT_YELLOW, bold=True)

    def error(self, text: str) -> str:
        """Format text as error (red)"""
        return self.colorize(text, Colors.BRIGHT_RED, bold=True)

    def command(self, text: str) -> str:
        """Format text as command (bright white, bold)"""
        return self.colorize(text, Colors.BRIGHT_WHITE, bold=True)

    def description(self, text: str) -> str:
        """Format text as description (normal white)"""
        return self.colorize(text, Colors.WHITE)

    def highlight(self, text: str) -> str:
        """Format text as highlighted (bright magenta)"""
        return self.colorize(text, Colors.BRIGHT_MAGENTA, bold=True)

    def muted(self, text: str) -> str:
        """Format text as muted (dim)"""
        return self.colorize(text, Colors.BRIGHT_BLACK)


# Global formatter instance
_formatter = ColorFormatter()


def format_help_header() -> str:
    """Create a colorful help header"""
    header = []

    # Title with emoji and colors
    header.append(
        _formatter.title("🚀 StrateQueue")
        + " - "
        + _formatter.description("Transform your backtesting strategies into live trading")
    )

    # Decorative line
    header.append(_formatter.muted("=" * 80))

    return "\n".join(header)


def format_command_list(commands: dict[str, str]) -> str:
    """
    Format the command list with colors and emojis

    Args:
        commands: Dictionary of command_name -> description

    Returns:
        Formatted command list
    """
    lines = []

    # Command emojis mapping
    command_emojis = {
        "list": "📋",
        "status": "🔍",
        "setup": "⚙️",
        "deploy": "🚀",
        "webui": "🌐",
        "pause": "⏸️",
        "resume": "▶️",
        "stop": "🛑",
        "remove": "🗑️",
        "rebalance": "⚖️",
    }

    lines.append(_formatter.subtitle("📚 Available Commands:"))
    lines.append("")

    for command_name, description in commands.items():
        emoji = command_emojis.get(command_name, "📝")
        command_text = _formatter.command(f"{command_name}")
        desc_text = _formatter.description(description)

        # Add aliases if available
        from ..command_factory import create_command

        command_obj = create_command(command_name)
        aliases = ""
        if command_obj and hasattr(command_obj, "aliases") and command_obj.aliases:
            alias_list = ", ".join(command_obj.aliases)
            aliases = _formatter.muted(f" ({alias_list})")

        lines.append(f"  {emoji} {command_text}{aliases}")
        lines.append(f"      {desc_text}")
        lines.append("")

    return "\n".join(lines)


def format_examples_section() -> str:
    """Create a colorful examples section"""
    lines = []

    lines.append(_formatter.subtitle("💡 Quick Start Examples:"))
    lines.append("")

    examples = [
        ("Deploy a strategy for testing", "stratequeue deploy --strategy sma.py --symbol AAPL"),
        (
            "Paper trading with fake money",
            "stratequeue deploy --strategy sma.py --symbol AAPL --paper",
        ),
        ("Check system and broker status", "stratequeue status"),
        ("List all supported brokers", "stratequeue list brokers"),
        ("Setup broker credentials", "stratequeue setup broker alpaca"),
        ("Live trading (be careful!)", "stratequeue deploy --strategy sma.py --symbol AAPL --live"),
        (
            "Multi-strategy deployment",
            "stratequeue deploy --strategy sma.py,momentum.py --allocation 0.6,0.4",
        ),
    ]

    for description, command in examples:
        lines.append(f"  {_formatter.muted('# ' + description)}")
        lines.append(f"  {_formatter.command(command)}")
        lines.append("")

    return "\n".join(lines)


def format_help_footer() -> str:
    """Create a colorful help footer"""
    lines = []

    lines.append(_formatter.subtitle("🆘 Getting Help:"))
    lines.append("")
    lines.append(
        f"  {_formatter.command('stratequeue --help')}           {_formatter.muted('# Show this help message')}"
    )
    lines.append(
        f"  {_formatter.command('stratequeue COMMAND --help')}   {_formatter.muted('# Show help for specific command')}"
    )
    lines.append("")

    lines.append(_formatter.subtitle("🔗 Additional Resources:"))
    lines.append("")
    lines.append(
        f"  {_formatter.highlight('Documentation:')} {_formatter.muted('https://stratequeue.com/docs')}"
    )
    lines.append(
        f"  {_formatter.highlight('GitHub:')}        {_formatter.muted('https://github.com/stratequeue/stratequeue')}"
    )
    lines.append(
        f"  {_formatter.highlight('Discord:')}       {_formatter.muted('https://discord.gg/stratequeue')}"
    )
    lines.append("")

    # Decorative footer
    lines.append(_formatter.muted("=" * 80))
    lines.append(
        _formatter.muted("Happy trading! 📈")
        + " "
        + _formatter.description("May your strategies be profitable and your risks be managed! 🎯")
    )

    return "\n".join(lines)


def create_enhanced_help_epilog(commands: dict[str, str]) -> str:
    """
    Create an enhanced, colorful help epilog

    Args:
        commands: Dictionary of command_name -> description

    Returns:
        Enhanced help epilog string
    """
    sections = [format_command_list(commands), format_examples_section(), format_help_footer()]

    return "\n".join(sections)


def format_welcome_message(commands: dict[str, str]) -> str:
    """
    Create a colorful welcome message for when no command is provided

    Args:
        commands: Dictionary of command_name -> description

    Returns:
        Formatted welcome message
    """
    lines = []

    # Header
    lines.append(format_help_header())
    lines.append("")

    # Quick intro
    lines.append(_formatter.description("Welcome to the future of algorithmic trading! 🤖"))
    lines.append("")

    # Quick start
    lines.append(_formatter.subtitle("⚡ Quick Start:"))
    lines.append("")
    lines.append(
        f"  {_formatter.command('stratequeue deploy --strategy sma.py --symbol AAPL --paper')}"
    )
    lines.append(f"  {_formatter.muted('# Test your strategy with fake money')}")
    lines.append("")

    # Available commands (compact version)
    lines.append(_formatter.subtitle("📋 Available Commands:"))
    lines.append("")

    command_emojis = {
        "list": "📋",
        "status": "🔍",
        "setup": "⚙️",
        "deploy": "🚀",
        "webui": "🌐",
        "pause": "⏸️",
        "resume": "▶️",
        "stop": "🛑",
        "remove": "🗑️",
        "rebalance": "⚖️",
    }

    for command_name, description in commands.items():
        emoji = command_emojis.get(command_name, "📝")
        lines.append(
            f"  {emoji} {_formatter.command(command_name):<12} {_formatter.description(description)}"
        )

    lines.append("")

    # Help guidance
    lines.append(_formatter.subtitle("🆘 Get Help:"))
    lines.append("")
    lines.append(
        f"  {_formatter.command('stratequeue --help')}           {_formatter.muted('# Detailed help')}"
    )
    lines.append(
        f"  {_formatter.command('stratequeue COMMAND --help')}   {_formatter.muted('# Command-specific help')}"
    )
    lines.append("")

    # Footer
    lines.append(_formatter.muted("─" * 60))
    lines.append(
        _formatter.success("Ready to transform your backtests into live profits? Let's go! 🎯")
    )

    return "\n".join(lines)
