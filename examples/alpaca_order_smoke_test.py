#!/usr/bin/env python3
"""
Alpaca Order-Type SMOKE TEST  (paper account)

Runs one request for **every** order-type / order-class / TIF / extended-hours
combination documented in `alpaca_to_backtesting_py.md`.

Requirements
------------
export ALPACA_API_KEY="PKxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export ALPACA_SECRET_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
# (OPTIONAL) export ALPACA_BASE_URL="https://paper-api.alpaca.markets"

Simply run:
    python3.10 examples/alpaca_order_smoke_test.py
"""

import pytest
pytest.skip("Example script - skip during automated test suite", allow_module_level=True)

import logging
import sys
import time

import pandas as pd

from StrateQueue.brokers.broker_factory import auto_create_broker
from StrateQueue.core.signal_extractor import SignalType, TradingSignal

# --------------------------------------------------------------------------- #
# Helper – pull a last price so limit/stop prices are "reasonable"            #
# --------------------------------------------------------------------------- #
def last_trade_price(broker, symbol: str, fallback: float = 100.0) -> float:
    """
    Tries a few different Alpaca-py endpoints for the most recent trade price.
    Falls back to `fallback` if market-data permission isn't available.
    """
    try:
        # New alpaca-py (>=2.0) – market-data client lives inside broker
        trade = broker.trading_client.get_latest_trade(symbol)
        return float(trade.price)
    except Exception:
        pass

    try:
        # Older alpaca-py (<=1.x)
        barset = broker.trading_client.get_barset(symbol, "minute", limit=1)
        return float(barset[symbol][0].c)
    except Exception:
        logging.warning("Couldn't fetch live quote – using fallback price.")
    return fallback


# --------------------------------------------------------------------------- #
# Build the test plan                                                         #
# --------------------------------------------------------------------------- #
def build_test_signals(price: float) -> list[tuple[str, str, TradingSignal]]:
    """
    Returns (description, symbol, signal) tuples for every order permutation
    we claim to support.
    """
    p = price  # shorthand
    stock = "AAPL"
    crypto = "BTC/USD"

    tests: list[tuple[str, str, TradingSignal]] = [
        # Basic single-leg BUY orders only (avoid sell position issues) ---
        (
            "Market BUY (DAY)",
            stock,
            TradingSignal(
                SignalType.BUY, 1, p, pd.Timestamp.now(), {}, time_in_force="day", size=1.0
            ),
        ),
        (
            "Limit BUY (DAY)",
            stock,
            TradingSignal(
                SignalType.LIMIT_BUY,
                1,
                p,
                pd.Timestamp.now(),
                {},
                limit_price=p * 0.995,
                time_in_force="day",
                size=1.0,
            ),
        ),
        (
            "Stop BUY (DAY)",
            stock,
            TradingSignal(
                SignalType.STOP_BUY,
                1,
                p,
                pd.Timestamp.now(),
                {},
                stop_price=p * 1.005,
                time_in_force="day",
                size=1.0,
            ),
        ),
        (
            "Stop-Limit BUY (DAY)",
            stock,
            TradingSignal(
                SignalType.STOP_LIMIT_BUY,
                1,
                p,
                pd.Timestamp.now(),
                {},
                stop_price=p * 1.004,
                limit_price=p * 1.006,
                time_in_force="day",
                size=1.0,
            ),
        ),
        # Advanced order-classes (BUY only) ------------------------------
        (
            "Bracket (entry+SL+TP)",
            stock,
            TradingSignal(
                SignalType.BUY,
                1,
                p,
                pd.Timestamp.now(),
                {"tp": p * 1.03, "sl": p * 0.97},
                time_in_force="day",
                size=1.0,
            ),
        ),
        (
            "OTO (TP only)",
            stock,
            TradingSignal(
                SignalType.LIMIT_BUY,
                1,
                p,
                pd.Timestamp.now(),
                {"tp": p * 1.02},
                limit_price=p * 0.99,
                time_in_force="day",
                size=1.0,
            ),
        ),
        (
            "OTO (SL only)",
            stock,
            TradingSignal(
                SignalType.BUY,
                1,
                p,
                pd.Timestamp.now(),
                {"sl": p * 0.98},
                time_in_force="day",
                size=1.0,
            ),
        ),
        # Time-in-force variations ----------------------------------------
        (
            "Limit BUY (GTC)",
            stock,
            TradingSignal(
                SignalType.LIMIT_BUY,
                1,
                p,
                pd.Timestamp.now(),
                {},
                limit_price=p * 0.995,
                time_in_force="gtc",
                size=1.0,
            ),
        ),
        (
            "Limit BUY (IOC)",
            stock,
            TradingSignal(
                SignalType.LIMIT_BUY,
                1,
                p,
                pd.Timestamp.now(),
                {},
                limit_price=p * 0.995,
                time_in_force="ioc",
                size=1.0,
            ),
        ),
        (
            "Limit BUY (FOK)",
            stock,
            TradingSignal(
                SignalType.LIMIT_BUY,
                1,
                p,
                pd.Timestamp.now(),
                {},
                limit_price=p * 0.995,
                time_in_force="fok",
                size=1.0,
            ),
        ),
        (
            "Limit BUY (OPG)",
            stock,
            TradingSignal(
                SignalType.LIMIT_BUY,
                1,
                p,
                pd.Timestamp.now(),
                {},
                limit_price=p * 0.995,
                time_in_force="opg",
                size=1.0,
            ),
        ),
        # Extended hours --------------------------------------------------
        (
            "Extended-hrs LIMIT_BUY",
            stock,
            TradingSignal(
                SignalType.LIMIT_BUY,
                1,
                p,
                pd.Timestamp.now(),
                {"extended_hours": True},
                limit_price=p * 0.995,
                time_in_force="day",
                size=1.0,
            ),
        ),
        # Crypto (using notional amounts) --------------------------------
        (
            "Crypto Market BUY",
            crypto,
            TradingSignal(SignalType.BUY, 1, p, pd.Timestamp.now(), {}, size=0.1),
        ),  # $100 worth
    ]
    return tests


# --------------------------------------------------------------------------- #
# Main test runner                                                            #
# --------------------------------------------------------------------------- #
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    log = logging.getLogger("smoke")

    broker = auto_create_broker()
    if not broker.connect():
        log.error("Could not connect to Alpaca with given credentials.")
        sys.exit(1)

    price = last_trade_price(broker, "AAPL", fallback=170.0)
    plan = build_test_signals(price)

    passed, failed = 0, 0
    log.info(f"🧪 Running {len(plan)} order-validation tests …\n")

    for desc, symbol, sig in plan:
        # Tag every order so we can identify it in the dashboard
        if not sig.metadata:
            sig.metadata = {}
        sig.metadata["label"] = desc.replace(" ", "_").lower()
        sig.metadata["validate_only"] = True  # <-- important!

        result = broker.execute_signal(symbol, sig)
        if result.success:
            status = "✅"
            passed += 1
            order_id_str = f"order_id={result.order_id}" if result.order_id else ""
        else:
            status = "❌"
            failed += 1
            order_id_str = f"error: {result.message}" if result.message else ""

        log.info(f"{status} {desc:35s}  ➜  symbol={symbol:7s}  {order_id_str}")

        # Respect API rate-limit
        time.sleep(0.2)

    log.info("\n────────── Summary ──────────")
    log.info(f"Passed: {passed}")
    log.info(f"Failed: {failed}")
    log.info(
        "Note: all requests were sent with validate_only=True " "(they never reach the market)."
    )

    # Cleanup: nothing to cancel because nothing was actually submitted
    broker.disconnect()


if __name__ == "__main__":
    main()
