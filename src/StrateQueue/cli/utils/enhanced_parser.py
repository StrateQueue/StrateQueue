"""Enhanced Argument Parser

Custom ArgumentParser subclass that provides enhanced help formatting
with colors, emojis, and better organization.
"""

import argparse
import sys

from .color_formatter import ColorFormatter


class EnhancedHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Enhanced help formatter with color support and better layout"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.formatter = ColorFormatter()

    def _format_usage(self, usage, actions, groups, prefix):
        """Format the usage line with colors"""
        if prefix is None:
            prefix = self.formatter.subtitle("Usage: ")
        else:
            prefix = self.formatter.subtitle(prefix)

        # Get the standard usage formatting
        usage_text = super()._format_usage(usage, actions, groups, None)

        # Apply formatting to the usage text
        if usage_text:
            # Highlight the program name
            parts = usage_text.split(" ", 1)
            if len(parts) > 1:
                prog_name = self.formatter.command(parts[0])
                rest = self.formatter.description(parts[1])
                usage_text = f"{prog_name} {rest}"
            else:
                usage_text = self.formatter.command(usage_text)

        return f"{prefix}{usage_text}\n\n"

    def _format_action_invocation(self, action):
        """Format action invocation with colors"""
        if not action.option_strings:
            # Positional argument
            default = self._get_default_metavar_for_positional(action)
            (metavar,) = self._metavar_formatter(action, default)(1)
            return self.formatter.highlight(metavar)
        else:
            # Optional argument
            parts = []

            # if the Optional doesn't take a value, format is:
            #    -s, --long
            if action.nargs == 0:
                parts.extend([self.formatter.command(opt) for opt in action.option_strings])

            # if the Optional takes a value, format is:
            #    -s ARGS, --long ARGS
            else:
                default = self._get_default_metavar_for_optional(action)
                args_string = self._format_args(action, default)
                for option_string in action.option_strings:
                    parts.append(
                        f"{self.formatter.command(option_string)} {self.formatter.highlight(args_string)}"
                    )

            return ", ".join(parts)

    def _split_lines(self, text, width):
        """Split lines while preserving ANSI color codes"""
        # Don't split lines that contain ANSI codes to avoid breaking formatting
        if "\033[" in text:
            return [text]
        return super()._split_lines(text, width)

    def start_section(self, heading):
        """Start a section with enhanced formatting"""
        if heading:
            # Apply different formatting based on heading type
            if heading.lower() in ["positional arguments", "arguments"]:
                heading = self.formatter.subtitle(f"📝 {heading}:")
            elif heading.lower() in ["optional arguments", "options"]:
                heading = self.formatter.subtitle(f"⚙️  {heading}:")
            elif heading.lower() in ["commands", "subcommands"]:
                heading = self.formatter.subtitle(f"🚀 {heading}:")
            else:
                heading = self.formatter.subtitle(f"📋 {heading}:")

        super().start_section(heading)


class EnhancedArgumentParser(argparse.ArgumentParser):
    """Enhanced ArgumentParser with better help formatting"""

    def __init__(self, *args, **kwargs):
        # Set our custom formatter as default
        if "formatter_class" not in kwargs:
            kwargs["formatter_class"] = EnhancedHelpFormatter

        super().__init__(*args, **kwargs)
        self.color_formatter = ColorFormatter()

    def format_help(self):
        """Format help with enhanced styling"""
        help_text = super().format_help()

        # If colors are disabled, return plain text
        if not self.color_formatter.use_colors:
            return help_text

        return help_text

    def error(self, message):
        """Enhanced error formatting"""
        # Format error message with colors
        error_msg = self.color_formatter.error(f"❌ Error: {message}")

        # Add suggestion
        suggestion = self.color_formatter.muted("💡 Try: --help for more information")

        # Print to stderr with formatting
        sys.stderr.write(f"{error_msg}\n{suggestion}\n")
        sys.exit(2)

    def print_help(self, file=None):
        """Print help with enhanced formatting"""
        if file is None:
            file = sys.stdout

        self._print_message(self.format_help(), file)


def create_enhanced_parser(*args, **kwargs) -> EnhancedArgumentParser:
    """
    Create an enhanced argument parser with color support

    Args:
        *args: Arguments to pass to ArgumentParser
        **kwargs: Keyword arguments to pass to ArgumentParser

    Returns:
        Enhanced ArgumentParser instance
    """
    return EnhancedArgumentParser(*args, **kwargs)
