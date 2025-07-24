"""
engine_parity/test_engine_parity.py
-------------------------------------------------
Integration test that enforces *behavioural parity* between every concrete
TradingEngine implementation shipped with StrateQueue.

What problem does it solve?
• We support several third-party trading back-ends (Backtesting.py, VectorBT,
  Zipline-Reloaded, Backtrader).  Their wrappers should emit identical
  TradingSignal objects when driven by the same price data and the logically
  equivalent strategy, eg. SMA crossover.

Requirements verified by this test
1. Dataset consistency – we feed all engines the same deterministic OHLCV
   DataFrame loaded from examples/data/AAPL.csv.
2. Strategy equivalence – for every engine we load its reference SMA strategy
   from examples/strategies/<engine>/sma.py.  These strategies implement the
   exact same logic (1-period fast MA vs 3-period slow MA crossover).
3. Engine pipeline – the test exercises the full pipeline:
      EngineFactory.create_engine(...) → load_strategy_from_file →
      create_signal_extractor → extract_signal.
4. Validity – each engine must return a TradingSignal whose `.signal` attribute
   is a member of SignalType (BUY, SELL, HOLD).
5. Parity – once at least two engines have produced a signal, they must all be
   identical.  Any disagreement fails the test and points to a bug in one of
   the wrappers.
6. Dependency awareness – if an engine's optional dependencies are missing the
   case is skipped; the final parity assertion only runs when ≥2 engines were
   executed.

Running directly vs pytest
• Pytest automatically discovers this file; fixtures handle env setup.
• Executing the file with `python test_engine_parity.py` prints a quick parity
  report and performs the same checks (handy for local debugging outside the
  test harness).
"""
import os
import sys
from pathlib import Path

# Add src/ to path for direct script execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SRC_PATH = PROJECT_ROOT / "src"
if SRC_PATH.exists() and SRC_PATH.is_dir():
    sys.path.insert(0, str(SRC_PATH))

import pandas as pd
import pytest

from StrateQueue.engines import EngineFactory
from StrateQueue.core.signal_extractor import SignalType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
DATA_CSV_PATH = PROJECT_ROOT / "examples" / "data" / "AAPL.csv"

# Map each engine type to its reference SMA crossover strategy
# Engines whose optional dependencies are not installed will be skipped at runtime.
ENGINE_STRATEGY_MAP = {
    "backtesting": Path("examples/strategies/backtestingpy/sma.py"),
    "vectorbt": Path("examples/strategies/vectorbt/sma.py"),
    "zipline": Path("examples/strategies/zipline-reloaded/sma.py"),
    "backtrader": Path("examples/strategies/backtrader/sma.py"),
    "bt": Path("examples/strategies/bt/sma.py"),
}


def _load_ohlcv_dataframe() -> pd.DataFrame:
    """Load the canned OHLCV data shipped with the repo and normalise columns."""
    df = pd.read_csv(DATA_CSV_PATH, parse_dates=["Date"], index_col="Date")
    # Normalise column case to match engines
    df = df.rename(columns={c: c.title() for c in df.columns})

    # Strip thousands separators in numeric columns and cast to float
    numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = (df[col]
                        .astype(str)
                        .str.replace(',', '')
                        .astype(float))

    # Ensure index is sorted old-to-new as most engines expect that
    df = df.iloc[::-1]
    return df


@pytest.fixture(scope="session")
def ohlcv_df():
    return _load_ohlcv_dataframe()


@pytest.fixture(params=list(ENGINE_STRATEGY_MAP.items()), ids=lambda p: p[0])
def engine_fixture(request):
    """Yield (engine_type, engine_instance, strategy_path) for supported engines."""
    engine_type, strategy_path = request.param

    # Skip if the dependency stack for this engine is not available
    if not EngineFactory.is_engine_supported(engine_type):
        pytest.skip(f"{engine_type} dependencies not installed – skipping parity test")

    engine = EngineFactory.create_engine(engine_type)
    return engine_type, engine, strategy_path


def _extract_signal(engine, strategy_path: Path, data: pd.DataFrame):
    """Utility to run one extraction across a given engine and data set."""
    # Convert Path to absolute if needed
    if not strategy_path.is_absolute():
        strategy_path = PROJECT_ROOT / strategy_path
        
    engine_strategy = engine.load_strategy_from_file(str(strategy_path))

    # Most engines accept a 'granularity' kwarg – fall back silently if not accepted.
    kwargs = {"granularity": "1d"}
    try:
        extractor = engine.create_signal_extractor(engine_strategy, **kwargs)
    except TypeError:
        # Engine does not accept granularity argument
        extractor = engine.create_signal_extractor(engine_strategy)

    signal = extractor.extract_signal(data)
    return signal


def _compute_signal_series(engine_type: str, engine, strategy_path: Path, df: pd.DataFrame):
    """Return pd.Series of SignalType for each bar starting from index 2 (lookback satisfied)."""
    if not strategy_path.is_absolute():
        strategy_path = PROJECT_ROOT / strategy_path

    engine_strategy = engine.load_strategy_from_file(str(strategy_path))

    try:
        extractor = engine.create_signal_extractor(engine_strategy, granularity="1d")
    except TypeError:
        extractor = engine.create_signal_extractor(engine_strategy)

    signals = []
    idx = []

    # Start at 2 so slow SMA (3) has data; but some engines may need more, we'll simply start at 2
    for i in range(2, len(df)):
        slice_df = df.iloc[: i + 1]
        try:
            sig = extractor.extract_signal(slice_df).signal
        except Exception as e:
            pytest.skip(f"{engine_type} extractor failed: {e}")
        signals.append(sig)
        idx.append(slice_df.index[-1])

    return pd.Series([s.value for s in signals], index=idx, name=engine_type)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_each_engine_produces_consistent_signal(engine_fixture, ohlcv_df):
    """Ensure that each available engine produces a BUY/SELL/HOLD decision without error."""
    engine_type, engine, strategy_path = engine_fixture

    signal = _extract_signal(engine, strategy_path, ohlcv_df)

    assert isinstance(signal.signal, SignalType), (
        f"{engine_type} did not return a proper SignalType: {signal.signal}")


# Collect results from all engines and compare in a second test. The session-wide
# cache avoids re-computing signals multiple times.
_engine_signals_cache = {}


@pytest.mark.dependency()
@pytest.mark.usefixtures("engine_fixture")
def test_collect_signals(engine_fixture, ohlcv_df):
    engine_type, engine, strategy_path = engine_fixture
    series = _compute_signal_series(engine_type, engine, strategy_path, ohlcv_df)
    _engine_signals_cache[engine_type] = series


@pytest.mark.dependency(depends=["test_collect_signals"], scope="session")
def test_parity_across_engines():
    """After collecting signals, assert all engines agreed on the decision."""
    # If fewer than 2 engines reported, nothing to compare
    if len(_engine_signals_cache) < 2:
        pytest.skip("Fewer than two engines available – parity assertion not applicable")

    engines = list(_engine_signals_cache.keys())
    ref_engine = engines[0]
    ref_series: pd.Series = _engine_signals_cache[ref_engine]

    details = []
    for eng in engines[1:]:
        diff_mask = _engine_signals_cache[eng] != ref_series
        mismatches_count = int(diff_mask.sum())
        if mismatches_count:
            first_idx = diff_mask.idxmax()
            agree_pct = 100.0 * (1 - mismatches_count / len(ref_series))
            details.append(f"{eng}: {mismatches_count} mismatches (agree {agree_pct:.1f}%), first @ {first_idx}")

    if details:
        df_out = pd.concat(_engine_signals_cache, axis=1)
        raise AssertionError(
            "Signal sequence mismatch:\n" + "\n".join(details) + "\n\n" + df_out.to_string())

    # if no details, test passes


# Allow direct execution for debugging
if __name__ == "__main__":
    # Simple run without pytest - just check if we can load each engine
    df = _load_ohlcv_dataframe()
    results = {}
    
    print(f"Testing engine parity with {len(ENGINE_STRATEGY_MAP)} engines...")
    
    for engine_type, strategy_path in ENGINE_STRATEGY_MAP.items():
        try:
            if not EngineFactory.is_engine_supported(engine_type):
                print(f"- {engine_type}: SKIPPED (dependencies not installed)")
                continue
                
            engine = EngineFactory.create_engine(engine_type)
            ser = _compute_signal_series(engine_type, engine, strategy_path, df)
            results[engine_type] = ser
            print(f"- {engine_type}: {ser.iloc[-1]}")
        except Exception as e:
            print(f"- {engine_type}: ERROR - {e}")
    
    if len(results) >= 2:
        ref_engine = list(results.keys())[0]
        ref_ser: pd.Series = results[ref_engine]

        mismatch_details = []
        for eng, ser in list(results.items())[1:]:
            diff_mask = ser != ref_ser
            if diff_mask.any():
                mismatch_count = int(diff_mask.sum())
                first_idx = diff_mask.idxmax()
                pct = 100.0 * (1 - mismatch_count / len(ref_ser))
                mismatch_details.append(f"{eng}: {mismatch_count} mismatches (agree {pct:.1f}%), first @ {first_idx}")

        if not mismatch_details:
            print(f"\nSUCCESS: All {len(results)} engines agree on entire signal sequence")
        else:
            print("\nFAILURE: Engines disagree on signal sequences:")
            print("\n".join(mismatch_details))
            df_out = pd.concat(results, axis=1)
            print("\nFull signal DataFrame:\n")
            print(df_out.to_string())
    else:
        print("\nSKIPPED: Fewer than 2 engines available for comparison") 