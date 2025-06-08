from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict
import pandas as pd
import logging

from .signal_extractor import TradingSignal, SignalType

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
    
    def _abort_insufficient_bars(self, data: pd.DataFrame) -> TradingSignal | None:
        """
        Check if there's insufficient data and return a HOLD signal if so.
        
        Args:
            data: Historical data DataFrame
            
        Returns:
            TradingSignal with HOLD if insufficient data, None if data is sufficient
        """
        min_bars = getattr(self, 'min_bars_required', 2)
        if len(data) < min_bars:
            log.warning(f"Insufficient historical data ({len(data)} < {min_bars}) - emitting HOLD")
            price = 0.0
            if len(data) > 0 and 'Close' in data.columns:
                price = self._safe_get_last_value(data['Close'])
            signal = self._safe_hold(price=price)
            # Flag insufficient data for downstream tests/analytics
            signal.indicators['insufficient_data'] = True
            return signal
        return None
    
    def _safe_hold(self, price: float = 0.0, error: Exception | str | None = None) -> TradingSignal:
        """
        Create a safe HOLD signal as a fallback.
        
        Args:
            price: Current price for the signal
            error: Optional error that caused the fallback
            
        Returns:
            TradingSignal with HOLD signal type
        """
        metadata = {"error": str(error)} if error else {}
        return TradingSignal(
            signal=SignalType.HOLD,
            price=price,
            timestamp=pd.Timestamp.now(),
            indicators={},
            metadata=metadata
        )
    
    def get_minimum_bars_required(self) -> int:
        """
        Get minimum number of bars needed for signal extraction.
        
        Default implementation combines min_bars_required and engine strategy lookback.
        Concrete extractors can override this if they need different logic.
        """
        min_bars = getattr(self, 'min_bars_required', 2)
        engine_strategy = getattr(self, 'engine_strategy', None)
        if engine_strategy:
            return max(min_bars, engine_strategy.get_lookback_period())
        return min_bars
    
    def _apply_memory_limit(self, data: pd.DataFrame, history_multiplier: int = 3) -> pd.DataFrame:
        """
        Apply memory limit to historical data to prevent unbounded growth.
        
        Keeps a maximum of lookback_period * history_multiplier bars.
        
        Args:
            data: Historical data DataFrame
            history_multiplier: Multiplier for lookback period to determine max bars
            
        Returns:
            Trimmed DataFrame if needed, original DataFrame otherwise
        """
        lookback = self.get_minimum_bars_required()
        max_bars = lookback * history_multiplier
        
        if len(data) > max_bars:
            log.debug(f"Trimming history from {len(data)} to {max_bars} bars (lookback={lookback}, multiplier={history_multiplier})")
            return data.tail(max_bars)
        
        return data
    
    def _trim_open_candle(self, data: pd.DataFrame, granularity_seconds: int | None = None) -> pd.DataFrame:
        """Remove the still-forming candle at the end of *data*.

        If *granularity_seconds* is provided and the timestamp of the last row is
        less than that many seconds behind *now*, the final row is considered an
        open candle and is dropped.  A copied DataFrame is returned to avoid
        mutating the caller's object.
        """
        if granularity_seconds is None or len(data) == 0:
            # Nothing to do: either no granularity hint or data empty.
            return data

        try:
            last_ts = data.index[-1]
        except Exception:
            # If index is not datetime-like, bail out.
            return data

        # Use UTC 'now' to avoid timezone headaches; convert *last_ts* if naive.
        now = pd.Timestamp.utcnow()
        if last_ts.tzinfo is None:
            # Make *now* naive as well for a fair comparison.
            now = now.tz_localize(None)

        elapsed = (now - last_ts).total_seconds()
        if elapsed < granularity_seconds:
            # Last bar is still open ⇒ drop it.
            return data.iloc[:-1].copy() if len(data) > 1 else data.iloc[:0].copy()
        return data
    
    @abstractmethod
    def extract_signal(self, data: pd.DataFrame) -> TradingSignal:
        """Extract trading signal from data. Must be implemented by concrete classes."""
        pass 