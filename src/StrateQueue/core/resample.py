"""
Core resampling utilities for deriving coarser OHLCV bars from finer ones.

Rules (standard):
- open = first
- high = max
- low = min
- close = last
- volume = sum

The planning helper chooses a base fetch interval from a provider's supported
granularities such that the requested target is an exact multiple of the base.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

import pandas as pd

from .granularity import GranularityParser


@dataclass(frozen=True)
class ResamplePlan:
    """Plan describing how to obtain the requested target granularity.

    If ``target_granularity`` is None, the source equals target and no
    resampling is required.
    """

    source_granularity: str
    target_granularity: str | None


def _to_seconds(token: str) -> int:
    """Convert a granularity token like '1s', '5m', '1h', '1d' to seconds.

    Only supports units handled by GranularityParser (s/m/h/d). Tokens that are
    not parseable (e.g. '1wk', '1mo') will raise ValueError.
    """
    return GranularityParser.parse(token).to_seconds()


def to_pandas_rule(token: str) -> str:
    """Translate a granularity token to a pandas offset alias.

    Pandas accepts strings like '1S', '5T', '1H', '1D'. We map:
    - seconds → 'S'
    - minutes → 'T'
    - hours   → 'H'
    - days    → 'D'
    """
    g = GranularityParser.parse(token)
    # Pandas offset aliases: 'min' should be used instead of deprecated 'T'
    unit_map = {
        's': 'S',
        'm': 'min',
        'h': 'H',
        'd': 'D',
    }
    return f"{g.multiplier}{unit_map[g.unit.value]}"


def resample_ohlcv(df: pd.DataFrame, target_token: str,
                   *, label: str = 'right', closed: str = 'right') -> pd.DataFrame:
    """Resample an OHLCV DataFrame to a target granularity.

    Assumes the input DataFrame has columns: Open, High, Low, Close, Volume and
    a DatetimeIndex. Returns a new DataFrame at the requested frequency.
    """
    if df.empty:
        return df

    # Ensure timezone-naive index to avoid surprises across providers
    if getattr(df.index, 'tz', None) is not None:
        df = df.copy()
        df.index = df.index.tz_convert(None)

    rule = to_pandas_rule(target_token)
    agg = {
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum',
    }
    out = (
        df.resample(rule, label=label, closed=closed)
          .agg(agg)
          .dropna(how='any')
    )
    return out


def plan_base_granularity(supported: Iterable[str], requested: str) -> ResamplePlan:
    """Choose a base fetch granularity from ``supported`` for ``requested``.

    Strategy:
    - If ``requested`` is in ``supported``, fetch directly (no resample).
    - Else, among parseable supported tokens with seconds <= requested seconds,
      choose the largest whose seconds divides the requested seconds evenly.
    - If no such divisor exists, raise ValueError with a helpful message.
    """
    sup = set(supported)
    if requested in sup:
        return ResamplePlan(source_granularity=requested, target_granularity=None)

    # Parse requested
    try:
        req_sec = _to_seconds(requested)
    except Exception as e:
        raise ValueError(f"Requested granularity '{requested}' is invalid: {e}")

    # Filter to parseable, not greater than requested
    candidates: list[Tuple[str, int]] = []
    for tok in sup:
        try:
            sec = _to_seconds(tok)
        except Exception:
            continue  # skip tokens we cannot parse (e.g., 1wk, 1mo)
        if sec <= req_sec:
            candidates.append((tok, sec))

    if not candidates:
        raise ValueError(
            f"No suitable base granularity for '{requested}'. Provider supports: {sorted(sup)}"
        )

    # Pick the largest divisor
    candidates.sort(key=lambda kv: kv[1])
    best: str | None = None
    best_sec = -1
    for tok, sec in candidates:
        if req_sec % sec == 0 and sec > best_sec:
            best = tok
            best_sec = sec

    if best is None:
        raise ValueError(
            "Requested granularity '{requested}' is not an integer multiple of any "
            f"supported base from {sorted(sup)}"
        )

    return ResamplePlan(source_granularity=best, target_granularity=requested)

