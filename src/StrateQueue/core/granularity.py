"""
Data Granularity Utilities

Handles parsing and validation of data granularity specifications like '1m', '5m', '1h', '1d', etc.
"""

import re
from dataclasses import dataclass
from enum import Enum


class TimeUnit(Enum):
    """Supported time units"""
    SECOND = "s"
    MINUTE = "m"
    HOUR = "h"
    DAY = "d"


@dataclass
class Granularity:
    """Represents a data granularity specification"""
    multiplier: int
    unit: TimeUnit

    def __str__(self) -> str:
        return f"{self.multiplier}{self.unit.value}"

    def to_timespan_params(self) -> tuple[str, int]:
        """Convert to timespan and multiplier parameters for data APIs"""
        if self.unit == TimeUnit.SECOND:
            return "second", self.multiplier
        elif self.unit == TimeUnit.MINUTE:
            return "minute", self.multiplier
        elif self.unit == TimeUnit.HOUR:
            return "hour", self.multiplier
        elif self.unit == TimeUnit.DAY:
            return "day", self.multiplier
        else:
            raise ValueError(f"Unsupported time unit: {self.unit}")

    def to_seconds(self) -> int:
        """Convert granularity to total seconds"""
        if self.unit == TimeUnit.SECOND:
            return self.multiplier
        elif self.unit == TimeUnit.MINUTE:
            return self.multiplier * 60
        elif self.unit == TimeUnit.HOUR:
            return self.multiplier * 3600
        elif self.unit == TimeUnit.DAY:
            return self.multiplier * 86400
        else:
            raise ValueError(f"Unsupported time unit: {self.unit}")


class GranularityParser:
    """Parser for granularity strings like '1m', '5m', '1h', '1d'"""

    # Pattern to match granularity strings: number followed by unit
    PATTERN = re.compile(r'^(\d+)([smhd])$')

    @classmethod
    def parse(cls, granularity_str: str) -> Granularity:
        """
        Parse a granularity string into a Granularity object

        Args:
            granularity_str: String like '1m', '5m', '1h', '1d'

        Returns:
            Granularity object

        Raises:
            ValueError: If the string format is invalid
        """
        if not granularity_str:
            raise ValueError("Granularity string cannot be empty")

        match = cls.PATTERN.match(granularity_str.lower().strip())
        if not match:
            raise ValueError(f"Invalid granularity format: '{granularity_str}'. Expected format like '1m', '5m', '1h', '1d'")

        multiplier_str, unit_str = match.groups()
        multiplier = int(multiplier_str)

        if multiplier <= 0:
            raise ValueError(f"Multiplier must be positive, got: {multiplier}")

        # Map unit string to TimeUnit enum
        unit_map = {
            's': TimeUnit.SECOND,
            'm': TimeUnit.MINUTE,
            'h': TimeUnit.HOUR,
            'd': TimeUnit.DAY
        }

        unit = unit_map[unit_str]
        return Granularity(multiplier, unit)

    @classmethod
    def validate_for_data_source(cls, granularity: Granularity, data_source: str) -> bool:
        """
        Validate if a granularity is supported by a specific data source

        Args:
            granularity: Granularity to validate
            data_source: Data source name ('polygon', 'coinmarketcap', 'demo')

        Returns:
            True if supported, False otherwise
        """
        if data_source == "polygon":
            # Polygon supports seconds, minutes, hours, days
            return True  # Pretty flexible

        elif data_source == "coinmarketcap":
            # CoinMarketCap historical data is typically daily
            # Real-time quotes can be fetched at custom intervals
            if granularity.unit == TimeUnit.DAY:
                return True
            # For real-time simulation, allow any granularity >= 30s due to rate limits
            return granularity.to_seconds() >= 30

        elif data_source == "demo":
            # Demo data can generate any granularity
            return True

        elif data_source == "yfinance":
            # Yahoo Finance supports various granularities but with limitations
            supported_granularities = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"]
            granularity_str = f"{granularity.multiplier}{granularity.unit.value}"
            return granularity_str in supported_granularities

        else:
            return False

    @classmethod
    def get_supported_granularities(cls, data_source: str) -> list[str]:
        """Get list of commonly supported granularities for a data source"""
        if data_source == "polygon":
            return ["1s", "5s", "10s", "30s", "1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]
        elif data_source == "coinmarketcap":
            return ["1d", "1m", "5m", "15m", "30m", "1h"]  # 1d for historical, others for real-time
        elif data_source == "demo":
            return ["1s", "5s", "10s", "30s", "1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1w"]
        elif data_source == "yfinance":
            return ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"]
        else:
            return []


# Predefined common granularities for convenience
class CommonGranularities:
    """Common granularity presets"""
    SECOND_1 = Granularity(1, TimeUnit.SECOND)
    SECOND_5 = Granularity(5, TimeUnit.SECOND)
    SECOND_10 = Granularity(10, TimeUnit.SECOND)
    SECOND_30 = Granularity(30, TimeUnit.SECOND)

    MINUTE_1 = Granularity(1, TimeUnit.MINUTE)
    MINUTE_5 = Granularity(5, TimeUnit.MINUTE)
    MINUTE_15 = Granularity(15, TimeUnit.MINUTE)
    MINUTE_30 = Granularity(30, TimeUnit.MINUTE)

    HOUR_1 = Granularity(1, TimeUnit.HOUR)
    HOUR_2 = Granularity(2, TimeUnit.HOUR)
    HOUR_4 = Granularity(4, TimeUnit.HOUR)
    HOUR_12 = Granularity(12, TimeUnit.HOUR)

    DAY_1 = Granularity(1, TimeUnit.DAY)


def parse_granularity(granularity_str: str) -> Granularity:
    """Convenience function to parse granularity string"""
    return GranularityParser.parse(granularity_str)


def validate_granularity(granularity_str: str, data_source: str) -> tuple[bool, str | None]:
    """
    Validate a granularity string for a specific data source

    Returns:
        (is_valid, error_message)
    """
    try:
        granularity = parse_granularity(granularity_str)
        is_valid = GranularityParser.validate_for_data_source(granularity, data_source)

        if not is_valid:
            supported = GranularityParser.get_supported_granularities(data_source)
            error_msg = f"Granularity '{granularity_str}' not supported by {data_source}. Supported: {', '.join(supported)}"
            return False, error_msg

        return True, None

    except ValueError as e:
        return False, str(e)
