"""
Alpaca Configuration Classes

Contains configuration dataclasses and enums for Alpaca trading setup.
"""

from dataclasses import dataclass
from enum import Enum

@dataclass
class AlpacaConfig:
    """Alpaca API configuration"""
    api_key: str
    secret_key: str
    base_url: str
    paper: bool = True

class PositionSizeMode(Enum):
    """Position sizing modes"""
    FIXED_AMOUNT = "fixed_amount"  # Fixed dollar amount per trade
    FIXED_SHARES = "fixed_shares"  # Fixed number of shares
    PERCENTAGE = "percentage"      # Percentage of portfolio
    SIGNAL_BASED = "signal_based"  # Use signal's suggested position size
    ALL_IN = "all_in"             # Use all available buying power

@dataclass
class PositionSizeConfig:
    """Position sizing configuration"""
    mode: PositionSizeMode = PositionSizeMode.ALL_IN
    value: float = 1.0  # Default 100% of buying power for ALL_IN mode 