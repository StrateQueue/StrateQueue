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
        Deprecated: provider-specific validation now lives in each provider.

        This method remains as a compatibility shim for code that still calls
        into core-level validation. It attempts a best-effort delegation by
        importing the provider factory and asking the provider class instance
        whether the granularity is accepted. If delegation fails, returns False.
        """
        try:
            # Late import to avoid circulars on module import
            from ..data.provider_factory import DataProviderFactory
            DataProviderFactory._initialize_providers()  # ensure registry
            provider_class = DataProviderFactory._providers.get(data_source)
            if provider_class is None:
                return False
            token = f"{granularity.multiplier}{granularity.unit.value}"
            # Prefer classmethod if present
            if hasattr(provider_class, "accepts_granularity"):
                return bool(provider_class.accepts_granularity(token))  # type: ignore[attr-defined]
            return False
        except Exception:
            return False

    @classmethod
    def get_supported_granularities(cls, data_source: str) -> list[str]:
        """Deprecated: use provider.get_supported_granularities().

        Kept for compatibility. Best-effort delegation to provider class.
        """
        try:
            from ..data.provider_factory import DataProviderFactory
            DataProviderFactory._initialize_providers()
            provider_class = DataProviderFactory._providers.get(data_source)
            if provider_class is None:
                return []
            if hasattr(provider_class, "get_supported_granularities"):
                return sorted(list(provider_class.get_supported_granularities()))  # type: ignore[attr-defined]
            return []
        except Exception:
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
    """Compatibility wrapper: prefer provider-level validation.

    Returns (is_valid, error_message).
    """
    try:
        # Parse to ensure format is valid
        _ = parse_granularity(granularity_str)
    except ValueError as e:
        return False, str(e)

    # Delegate to provider capability when available
    try:
        from ..data.provider_factory import DataProviderFactory
        DataProviderFactory._initialize_providers()
        provider_class = DataProviderFactory._providers.get(data_source)
        if provider_class and hasattr(provider_class, "accepts_granularity"):
            # Direct native support
            if provider_class.accepts_granularity(granularity_str):  # type: ignore[attr-defined]
                return True, None

            # Try resampling plan: if requested is a clean multiple of a supported base, accept
            supported: list[str] = []
            if hasattr(provider_class, "get_supported_granularities"):
                try:
                    supported = sorted(list(provider_class.get_supported_granularities()))  # type: ignore[attr-defined]
                except Exception:
                    supported = []

            if supported:
                try:
                    from .resample import plan_base_granularity
                    _ = plan_base_granularity(supported, granularity_str)
                    # A valid plan exists: allow and provider will fetch base+resample
                    return True, None
                except Exception:
                    pass

            error_msg = (
                f"Granularity '{granularity_str}' not supported by {data_source}. "
                + (f"Supported: {', '.join(supported)}" if supported else "")
            )
            return False, error_msg
    except Exception:
        pass

    # If delegation failed, be conservative
    return False, f"Unable to validate granularity '{granularity_str}' for data source '{data_source}'"
