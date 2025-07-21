# New test module for DisplayManager behavioural unit tests

from __future__ import annotations

import re
from types import SimpleNamespace

import pandas as pd
import pytest

from StrateQueue.live_system.display_manager import DisplayManager
from StrateQueue.core.signal_extractor import TradingSignal, SignalType


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def stats_stub(monkeypatch: pytest.MonkeyPatch):
    """Very lightweight StatisticsManager stub capturing calls."""
    stub = SimpleNamespace(records=[], calls=0)

    def _rec_signal(**kwargs):
        stub.records.append(kwargs)
        stub.calls += 1

    monkeypatch.setattr(stub, "record_signal", _rec_signal, raising=False)
    monkeypatch.setattr(stub, "display_enhanced_summary", lambda: None, raising=False)
    return stub


@pytest.fixture()
def disp(stats_stub):
    return DisplayManager(is_multi_strategy=False, statistics_manager=stats_stub)


# ---------------------------------------------------------------------------
# Tests – display_signal & log_trade
# ---------------------------------------------------------------------------

def test_display_signal_emits_emoji(disp: DisplayManager, capsys):
    sig = TradingSignal(SignalType.BUY, 123.456, pd.Timestamp("2024-01-01"), {})
    disp.display_signal("AAPL", sig, 1)

    out = capsys.readouterr().out
    assert "📈" in out  # correct emoji for BUY
    assert "$123.456" in out  # precise price without floating point artifacts


def test_log_trade_side_effects(disp: DisplayManager, stats_stub):
    sig = TradingSignal(SignalType.SELL, 1.0, pd.Timestamp.utcnow(), {})
    disp.log_trade("BTCUSD", sig)

    assert disp.get_trade_count() == 1
    # ensure trade cloned into statistics manager
    assert stats_stub.calls == 1

    # returned trade log must be a *copy*
    log_copy = disp.get_trade_log()
    log_copy.clear()
    assert disp.get_trade_count() == 1


# ---------------------------------------------------------------------------
# Tests – session summary
# ---------------------------------------------------------------------------

def test_display_session_summary_counts(disp: DisplayManager, capsys):
    ts = pd.Timestamp.utcnow()
    for s_type in [SignalType.BUY, SignalType.BUY, SignalType.CLOSE]:
        disp.log_trade("ETHUSD", TradingSignal(s_type, 1.0, ts, {}))

    disp.display_session_summary({"ETHUSD": TradingSignal(SignalType.BUY, 1.0, ts, {})})

    out = capsys.readouterr().out
    assert "Total Signals Generated: 3" in out
    assert re.search(r"BUY:\s+2", out)
    assert re.search(r"CLOSE:\s+1", out)


# ---------------------------------------------------------------------------
# Tests – multi-strategy signal router
# ---------------------------------------------------------------------------

def test_multi_strategy_router_invocation(monkeypatch: pytest.MonkeyPatch, capsys):
    multi = DisplayManager(is_multi_strategy=True)

    # monkeypatch internal helper to count calls
    call_counter = {"multi": 0}

    def _fake(self, *a, **kw):
        call_counter["multi"] += 1

    monkeypatch.setattr(
        DisplayManager, "_display_multi_strategy_signals", _fake, raising=False
    )

    sig = TradingSignal(SignalType.BUY, 1.0, pd.Timestamp.utcnow(), {})
    multi.display_signals_summary({"BTCUSD": {"s1": sig}}, 1)
    assert call_counter["multi"] == 1 