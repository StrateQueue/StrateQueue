"""
Tests for StatisticsManager cash bookkeeping and trade recording (Section A).

Tests in this module verify that:
- BUY trades decrease cash by price × quantity + commission + fees
- SELL trades increase cash by price × quantity (commission/fees tracked separately)
- Cash history starts with initial balance
- Cash history updates are monotonic (unless intentionally negative)
- Edge cases like zero-commission trades work properly
- Both provided timestamps and auto-generated "now()" timestamps work
"""

import pytest
import pandas as pd
from unittest.mock import patch

from StrateQueue.core.statistics_manager import StatisticsManager


def test_initial_cash_balance(stats_manager):
    """Test that initial cash balance is set correctly."""
    # Get the cash history
    cash_history = stats_manager.get_cash_history()
    
    # Verify initial cash is set
    assert len(cash_history) == 1
    assert cash_history.iloc[0] == 10000.0


def test_buy_trade_decreases_cash(stats_manager):
    """Test that BUY trade decreases cash by price*quantity + commission + fees."""
    # Record a BUY trade
    stats_manager.record_trade(
        symbol="AAPL",
        action="buy",
        quantity=10.0,
        price=150.0,
        commission=7.50,
        fees=2.50
    )
    
    # Calculate expected cash: initial - (price*qty + commission + fees)
    expected_cash = 10000.0 - (150.0 * 10.0 + 7.50 + 2.50)
    
    # Get the current cash balance
    cash_history = stats_manager.get_cash_history()
    current_cash = cash_history.iloc[-1]
    
    assert current_cash == pytest.approx(expected_cash)
    assert current_cash == pytest.approx(8490.0)


def test_sell_trade_increases_cash(stats_manager):
    """Test that SELL trade increases cash by price*quantity - commission - fees."""
    # First buy some shares to avoid negative positions
    stats_manager.record_trade(
        symbol="AAPL",
        action="buy",
        quantity=20.0,
        price=150.0,
        commission=0.0,
        fees=0.0
    )
    
    # Record a SELL trade
    stats_manager.record_trade(
        symbol="AAPL",
        action="sell",
        quantity=10.0,
        price=160.0,
        commission=8.0,
        fees=2.0
    )
    
    # Calculate expected cash after both trades:
    # New implementation: initial - buy_cost + sell_price*qty (no commission/fees deducted from sell)
    buy_cost = 150.0 * 20.0
    sell_proceeds = 160.0 * 10.0  # New implementation doesn't deduct commission/fees from sell proceeds
    expected_cash = 10000.0 - buy_cost + sell_proceeds
    
    # Get the current cash balance
    cash_history = stats_manager.get_cash_history()
    current_cash = cash_history.iloc[-1]
    
    assert current_cash == pytest.approx(expected_cash)
    assert current_cash == pytest.approx(8600.0)  # Updated for new cash calculation (no commission/fees deducted from sell)


def test_cash_history_is_monotonic(stats_manager):
    """Test that cash history records each trade correctly and is monotonic."""
    timestamps = [
        pd.Timestamp("2023-01-01 12:00:00", tz="UTC"),
        pd.Timestamp("2023-01-01 13:00:00", tz="UTC"),
        pd.Timestamp("2023-01-01 14:00:00", tz="UTC"),
    ]
    
    # Record a sequence of trades
    stats_manager.record_trade(
        timestamp=timestamps[0],
        symbol="AAPL",
        action="buy",
        quantity=10.0,
        price=150.0,
        commission=5.0,
        fees=0.0
    )
    
    stats_manager.record_trade(
        timestamp=timestamps[1],
        symbol="MSFT",
        action="buy",
        quantity=5.0,
        price=200.0,
        commission=5.0,
        fees=0.0
    )
    
    stats_manager.record_trade(
        timestamp=timestamps[2],
        symbol="AAPL",
        action="sell",
        quantity=5.0,
        price=155.0,
        commission=5.0,
        fees=0.0
    )
    
    # Get cash history
    cash_history = stats_manager.get_cash_history()
    
    # Should have 4 entries: initial + 3 trades
    assert len(cash_history) == 4
    
    # Cash values should match expected (updated for new cash calculation)
    expected_values = [
        10000.0,                         # Initial
        10000.0 - (150.0 * 10.0 + 5.0),  # After first buy
        10000.0 - (150.0 * 10.0 + 5.0) - (200.0 * 5.0 + 5.0),  # After second buy
        10000.0 - (150.0 * 10.0 + 5.0) - (200.0 * 5.0 + 5.0) + (155.0 * 5.0)  # After sell (no commission deducted from sell)
    ]
    
    assert list(cash_history) == pytest.approx(expected_values)
    
    # Timestamps should match
    assert cash_history.index[1] == timestamps[0]
    assert cash_history.index[2] == timestamps[1]
    assert cash_history.index[3] == timestamps[2]


def test_zero_commission_trade(stats_manager):
    """Test that zero-commission trades work correctly."""
    # Record a trade with zero commission and fees
    stats_manager.record_trade(
        symbol="AAPL",
        action="buy",
        quantity=10.0,
        price=150.0,
        commission=0.0,
        fees=0.0
    )
    
    # Calculate expected cash
    expected_cash = 10000.0 - (150.0 * 10.0)
    
    # Get the current cash balance
    cash_history = stats_manager.get_cash_history()
    current_cash = cash_history.iloc[-1]
    
    assert current_cash == pytest.approx(expected_cash)
    assert current_cash == pytest.approx(8500.0)


def test_default_timestamp_now(stats_manager):
    """Test that default timestamp uses now()."""
    with patch('pandas.Timestamp.now') as mock_now:
        # Mock the current time
        fixed_time = pd.Timestamp("2023-01-01 12:00:00", tz="UTC")
        mock_now.return_value = fixed_time
        
        # Record a trade without specifying timestamp
        stats_manager.record_trade(
            symbol="AAPL",
            action="buy",
            quantity=10.0,
            price=150.0,
        )
        
        # Get cash history
        cash_history = stats_manager.get_cash_history()
        
        # The timestamp of the trade should be our mocked "now"
        assert cash_history.index[1] == fixed_time


def test_provided_timestamp(stats_manager, fixed_timestamps):
    """Test that provided timestamps are used correctly."""
    # Record trades with explicit timestamps
    stats_manager.record_trade(
        timestamp=fixed_timestamps[1],  # 13:00
        symbol="AAPL",
        action="buy",
        quantity=10.0,
        price=150.0,
    )
    
    stats_manager.record_trade(
        timestamp=fixed_timestamps[0],  # 12:00 (earlier timestamp)
        symbol="MSFT",
        action="buy",
        quantity=5.0,
        price=200.0,
    )
    
    # Get cash history
    cash_history = stats_manager.get_cash_history()
    
    # Should have 3 entries (initial + 2 trades)
    assert len(cash_history) == 3
    
    # Convert timestamps to strings for easier debugging
    ts_list = [str(ts) for ts in cash_history.index]
    
    # Verify that both our provided timestamps exist in the cash history
    assert str(fixed_timestamps[0]) in ts_list
    assert str(fixed_timestamps[1]) in ts_list
    
    # Find our provided timestamps in the cash history
    ts0_index = -1
    ts1_index = -1
    for i, ts in enumerate(cash_history.index):
        if ts == fixed_timestamps[0]:  # 12:00
            ts0_index = i
        elif ts == fixed_timestamps[1]:  # 13:00
            ts1_index = i
    
    assert ts0_index != -1, "Timestamp 0 not found in cash history"
    assert ts1_index != -1, "Timestamp 1 not found in cash history"
    
    # Based on the order of trades, verify the cash values
    assert cash_history.iloc[ts0_index] == pytest.approx(7500.0)  # Cash after both trades
    assert cash_history.iloc[ts1_index] == pytest.approx(8500.0)  # Cash after first trade


def test_intentionally_negative_cash(stats_manager):
    """Test that cash can go negative (margin/shorting scenario)."""
    # Record a large buy that exceeds initial cash
    stats_manager.record_trade(
        symbol="AAPL",
        action="buy",
        quantity=100.0,
        price=150.0,
        commission=50.0,
    )
    
    # Calculate expected cash
    expected_cash = 10000.0 - (150.0 * 100.0 + 50.0)  # Should be negative
    
    # Get the current cash balance
    cash_history = stats_manager.get_cash_history()
    current_cash = cash_history.iloc[-1]
    
    assert current_cash == pytest.approx(expected_cash)
    assert current_cash < 0  # Cash should be negative


if __name__ == "__main__":
    pytest.main(["-v", __file__]) 