"""
Strategy Configuration Management

Handles loading, parsing, and validation of multi-strategy configurations:
- Strategy config file parsing
- Path resolution and validation
- Allocation validation and normalization
"""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Default lookback period for strategies (in bars)
DEFAULT_LOOKBACK_PERIOD = 60

@dataclass
class StrategyConfig:
    """Configuration for a single strategy"""
    strategy_id: str
    file_path: str
    allocation: float
    lookback_period: int = DEFAULT_LOOKBACK_PERIOD
    strategy_class: type | None = None
    signal_extractor: object | None = None  # Will be LiveSignalExtractor
    symbol: str | None = None  # Optional symbol for 1:1 strategy-symbol mapping

class ConfigManager:
    """Manages loading and validation of strategy configurations"""

    def __init__(self, config_file_path: str, lookback_override: int | None = None):
        """
        Initialize ConfigManager

        Args:
            config_file_path: Path to strategy configuration file
            lookback_override: Override default lookback period with this value
        """
        self.config_file_path = config_file_path
        self.lookback_override = lookback_override
        self.strategy_configs: dict[str, StrategyConfig] = {}
        self.max_lookback_period = DEFAULT_LOOKBACK_PERIOD  # Default fallback

    def load_configurations(self) -> dict[str, StrategyConfig]:
        """
        Load strategy configurations from file

        Returns:
            Dictionary of strategy_id -> StrategyConfig

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config format is invalid
        """
        if not os.path.exists(self.config_file_path):
            raise FileNotFoundError(f"Strategy config file not found: {self.config_file_path}")

        logger.info(f"Loading strategy configurations from {self.config_file_path}")

        self.strategy_configs = {}

        with open(self.config_file_path) as f:
            lines = f.readlines()

        total_allocation = 0.0
        for line_num, line in enumerate(lines, 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            config = self._parse_config_line(line, line_num)

            # Check for duplicate strategy IDs
            if config.strategy_id in self.strategy_configs:
                raise ValueError(f"Duplicate strategy ID: {config.strategy_id}")

            self.strategy_configs[config.strategy_id] = config
            total_allocation += config.allocation

            logger.info(f"Loaded strategy config: {config.strategy_id} "
                       f"({config.file_path}, {config.allocation:.1%})")

        if not self.strategy_configs:
            raise ValueError("No strategies found in configuration file")

        # Validate total allocation
        if abs(total_allocation - 1.0) > 0.01:  # Allow small rounding errors
            logger.warning(f"Total allocation is {total_allocation:.1%}, not 100%")

        return self.strategy_configs

    def _parse_config_line(self, line: str, line_num: int) -> StrategyConfig:
        """
        Parse a single configuration line

        Args:
            line: Configuration line to parse
            line_num: Line number for error reporting

        Returns:
            StrategyConfig object

        Raises:
            ValueError: If line format is invalid
        """
        # Parse line: filename,strategy_id,allocation[,symbol]
        parts = [part.strip() for part in line.split(',')]
        if len(parts) not in [3, 4]:
            raise ValueError(f"Invalid format in line {line_num}: {line}. "
                           f"Expected: filename,strategy_id,allocation[,symbol]")

        file_path, strategy_id, allocation_str = parts[:3]
        symbol = parts[3] if len(parts) == 4 else None

        # Validate allocation
        try:
            allocation = float(allocation_str)
            if allocation <= 0 or allocation > 1:
                raise ValueError(f"Allocation must be between 0 and 1, got {allocation}")
        except ValueError as e:
            raise ValueError(f"Invalid allocation in line {line_num}: {allocation_str}. {e}")

        # Resolve file path
        resolved_path = self._resolve_file_path(file_path)
        if not os.path.exists(resolved_path):
            raise FileNotFoundError(f"Strategy file not found: {resolved_path}")

        return StrategyConfig(
            strategy_id=strategy_id,
            file_path=resolved_path,
            allocation=allocation,
            symbol=symbol
        )

    def _resolve_file_path(self, file_path: str) -> str:
        """
        Resolve strategy file path (support relative and absolute paths)

        Args:
            file_path: File path from config

        Returns:
            Resolved absolute path
        """
        if os.path.isabs(file_path):
            return file_path

        # Try relative to config file directory first
        config_dir = os.path.dirname(self.config_file_path)
        resolved_path = os.path.join(config_dir, file_path)
        if os.path.exists(resolved_path):
            return resolved_path

        # Try relative to current working directory
        return file_path

    def set_lookback_periods(self, lookback_period: int) -> int:
        """
        Set lookback period for all strategies

        Args:
            lookback_period: Lookback period to use for all strategies

        Returns:
            The lookback period that was set
        """
        for strategy_id, config in self.strategy_configs.items():
            config.lookback_period = lookback_period
            logger.info(f"Strategy {strategy_id}: Set lookback = {lookback_period}")

        self.max_lookback_period = lookback_period
        logger.info(f"Lookback period set to {lookback_period} bars for all strategies")

        return lookback_period

    def get_strategy_configs(self) -> dict[str, StrategyConfig]:
        """Get all loaded strategy configurations"""
        return self.strategy_configs.copy()

    def get_strategy_ids(self) -> list[str]:
        """Get list of all strategy IDs"""
        return list(self.strategy_configs.keys())

    def get_max_lookback_period(self) -> int:
        """Get the maximum lookback period required across all strategies"""
        return self.max_lookback_period

    def get_allocations(self) -> dict[str, float]:
        """Get allocation mapping for portfolio manager"""
        return {config.strategy_id: config.allocation
                for config in self.strategy_configs.values()}
