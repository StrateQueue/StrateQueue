"""tests/unit_tests/data_path/test_granularity_utils.py

REQUIREMENTS
------------
1. Parsing valid granularity strings with `parse_granularity` must produce
   objects whose `to_seconds()` conforms to expectations.
2. Invalid strings must raise `ValueError`.
3. Source-specific validation rules via `validate_granularity` must match the
   documented constraints for *CoinMarketCap*.

If all assertions in this file pass the requirements are satisfied.
"""

from __future__ import annotations

import pytest

from StrateQueue.core.granularity import parse_granularity, validate_granularity


# ---------------------------------------------------------------------------
# Valid parse cases
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "txt,seconds",
    [
        ("1s", 1),
        ("30s", 30),
        ("1m", 60),
        ("4h", 4 * 3600),
        ("1d", 86400),
    ],
)
def test_parse_to_seconds(txt: str, seconds: int):
    assert parse_granularity(txt).to_seconds() == seconds


# ---------------------------------------------------------------------------
# Invalid parse cases
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad", ["", "0m", "7x", "23"])
def test_bad_parse_raises(bad: str):
    with pytest.raises(ValueError):
        parse_granularity(bad)


# ---------------------------------------------------------------------------
# Source-specific validation for CoinMarketCap
# ---------------------------------------------------------------------------

def test_cmc_validation_rules():
    ok, _ = validate_granularity("1d", "coinmarketcap")
    assert ok

    # 1m is actually supported by CoinMarketCap according to their provider
    ok, _ = validate_granularity("1m", "coinmarketcap")
    assert ok 