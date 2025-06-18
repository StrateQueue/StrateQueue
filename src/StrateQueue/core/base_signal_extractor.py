from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict
import pandas as pd
import logging

log = logging.getLogger(__name__)


class BaseSignalExtractor(ABC):
    """
    Common helpers for every EngineSignalExtractor.
    Concrete extractors inherit *both* this mix-in
    and the engine's own SignalExtractor base class.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def _safe_get_last_value(self, series: pd.Series, default: Any = 0) -> Any:
        """Safely get the last value from a series, with fallback."""
        try:
            if len(series) == 0:
                return default
            return series.iloc[-1]
        except (IndexError, AttributeError):
            return default
    
    def _safe_get_previous_value(self, series: pd.Series, default: Any = 0) -> Any:
        """Safely get the second-to-last value from a series, with fallback."""
        try:
            if len(series) < 2:
                return default
            return series.iloc[-2]
        except (IndexError, AttributeError):
            return default
    
    def _crossover_occurred(self, fast_series: pd.Series, slow_series: pd.Series) -> bool:
        """Check if fast crossed above slow in the most recent bar."""
        if len(fast_series) < 2 or len(slow_series) < 2:
            return False
        
        current_fast = self._safe_get_last_value(fast_series)
        current_slow = self._safe_get_last_value(slow_series)
        prev_fast = self._safe_get_previous_value(fast_series)
        prev_slow = self._safe_get_previous_value(slow_series)
        
        return (current_fast > current_slow) and (prev_fast <= prev_slow)
    
    def _crossunder_occurred(self, fast_series: pd.Series, slow_series: pd.Series) -> bool:
        """Check if fast crossed below slow in the most recent bar."""
        if len(fast_series) < 2 or len(slow_series) < 2:
            return False
        
        current_fast = self._safe_get_last_value(fast_series)
        current_slow = self._safe_get_last_value(slow_series)
        prev_fast = self._safe_get_previous_value(fast_series)
        prev_slow = self._safe_get_previous_value(slow_series)
        
        return (current_fast < current_slow) and (prev_fast >= prev_slow)
    
    def _clean_indicators(self, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Clean indicators dict, converting numpy types to native Python types."""
        cleaned = {}
        for key, value in indicators.items():
            try:
                # Convert numpy types to native Python types
                if hasattr(value, 'item'):
                    cleaned[key] = value.item()
                elif hasattr(value, 'dtype'):
                    cleaned[key] = float(value) if 'float' in str(value.dtype) else int(value)
                else:
                    cleaned[key] = value
            except (ValueError, TypeError):
                # Fallback to original value if conversion fails
                cleaned[key] = value
        return cleaned
    
    @abstractmethod
    def extract_signal(self, data: pd.DataFrame) -> tuple:
        """Extract trading signal from data. Must be implemented by concrete classes."""
        pass 