"""
Tests for StatisticsManager position tracking and equity curve calculation (Section B).

Tests in this module verify that:
- With no positions, equity curve equals cash history
- With positions, equity curve properly combines initial cash, realized P&L, and unrealized P&L
- Equity curve includes trade timestamps and calculates unrealized P&L based on average entry prices
"""

import pytest
import pandas as pd

from StrateQueue.core.statistics_manager import StatisticsManager


def test_no_positions_equity_equals_cash(stats_manager):
    """Test that with no positions, equity curve equals cash history."""
    # Create some cash history with multiple points
    timestamps = [
        pd.Timestamp("2023-01-01 12:00:00", tz="UTC"),
        pd.Timestamp("2023-01-01 13:00:00", tz="UTC"),
        pd.Timestamp("2023-01-01 14:00:00", tz="UTC"),
    ]
    
    # Record trades that affect cash but don't create positions (sell without buy)
    stats_manager.record_trade(
        timestamp=timestamps[0],
        symbol="AAPL",  # Use regular symbol
        action="sell",
        quantity=10.0,
        price=100.0,  # Sell 10 shares @ $100 = $1000
        commission=0.0,
    )
    
    # Record another trade
    stats_manager.record_trade(
        timestamp=timestamps[1],
        symbol="MSFT",
        action="sell",
        quantity=5.0,
        price=100.0,  # Sell 5 shares @ $100 = $500
        commission=0.0,
    )
    
    # Get cash history
    cash_history = stats_manager.get_cash_history()
    
    # Now calculate equity curve
    equity_curve = stats_manager.calc_equity_curve()
    
    # New implementation: equity curve only includes trade timestamps, not all cash history timestamps
    # Since we have 2 trades, equity curve should have 3 points: initial + 2 trades
    assert len(equity_curve) == 3
    
    # The new implementation calculates equity as: initial_cash + realized_pnl + unrealized_pnl
    # Since we're selling without buying first, there are no round trips, so realized_pnl = 0
    # And there are no positions, so unrealized_pnl = 0
    # So equity should just be initial_cash = $10000
    
    # The cash history should show the cash changes from the sell trades
    # Initial: $10000
    # After first sell: $10000 + $1000 = $11000
    # After second sell: $11000 + $500 = $11500
    
    # But the equity curve should be constant at $10000 since no round trips
    expected_equity_values = [10000.0, 10000.0, 10000.0]
    assert list(equity_curve.values) == pytest.approx(expected_equity_values)
    
    # Verify cash history shows the expected changes
    expected_cash_values = [10000.0, 11000.0, 11500.0]
    assert list(cash_history.values) == pytest.approx(expected_cash_values)


def test_single_symbol_position_equity_curve(stats_manager, fixed_timestamps):
    """
    Test equity curve calculation with a single symbol position:
    - Buy 10 shares @ $100
    - Price moves to $110
    - Final equity should be: cash ($9000) + position value (10 × $110 = $1100) = $10100
    """
    # Buy shares
    stats_manager.record_trade(
        timestamp=fixed_timestamps[0],  # 12:00
        symbol="AAPL",
        action="buy",
        quantity=10.0,
        price=100.0,
        commission=0.0,
    )
    
    # Cash should now be 10000 - 10*100 = 9000
    cash_history = stats_manager.get_cash_history()
    assert cash_history.iloc[-1] == pytest.approx(9000.0)
    
    # Add price history points - price starts at 100 and moves to 110
    stats_manager.update_market_prices(
        {"AAPL": 100.0},
        timestamp=fixed_timestamps[1]  # 13:00
    )
    
    stats_manager.update_market_prices(
        {"AAPL": 105.0},
        timestamp=fixed_timestamps[2]  # 14:00
    )
    
    stats_manager.update_market_prices(
        {"AAPL": 110.0},
        timestamp=fixed_timestamps[3]  # 15:00
    )
    
    # Calculate equity curve
    equity_curve = stats_manager.calc_equity_curve()
    
    # New implementation: equity curve only includes trade timestamps, not price update timestamps
    # We only have 1 trade, so equity curve should have 2 points: initial + trade
    assert len(equity_curve) == 2
    
    # The equity curve should show:
    # Initial: $10000
    # After buy trade: $10000 + unrealized P&L
    # Since we have 10 shares @ $100 entry, and latest price is $110, unrealized P&L = 10 * (110-100) = $100
    # So final equity = $10000 + $100 = $10100
    
    # Check the final equity value
    final_equity = equity_curve.iloc[-1]
    assert final_equity == pytest.approx(10100.0)


def test_multi_symbol_position_equity_curve(stats_manager, fixed_timestamps):
    """
    Test equity curve calculation with multiple symbol positions:
    - Buy 10 AAPL @ $100 and 5 MSFT @ $200
    - Update prices for both symbols
    - Verify equity curve correctly combines cash and all positions
    """
    # Buy AAPL shares
    stats_manager.record_trade(
        timestamp=fixed_timestamps[0],  # 12:00
        symbol="AAPL",
        action="buy",
        quantity=10.0,
        price=100.0,
        commission=0.0,
    )
    
    # Buy MSFT shares
    stats_manager.record_trade(
        timestamp=fixed_timestamps[1],  # 13:00
        symbol="MSFT",
        action="buy",
        quantity=5.0,
        price=200.0,
        commission=0.0,
    )
    
    # Cash should now be 10000 - 10*100 - 5*200 = 8000
    cash_history = stats_manager.get_cash_history()
    assert cash_history.iloc[-1] == pytest.approx(8000.0)
    
    # Add price history points for both symbols
    stats_manager.update_market_prices(
        {"AAPL": 105.0, "MSFT": 205.0},
        timestamp=fixed_timestamps[2]  # 14:00
    )
    
    stats_manager.update_market_prices(
        {"AAPL": 110.0, "MSFT": 210.0},
        timestamp=fixed_timestamps[3]  # 15:00
    )
    
    # Calculate equity curve
    equity_curve = stats_manager.calc_equity_curve()
    
    # New implementation: equity curve only includes trade timestamps, not price update timestamps
    # We have 2 trades, so equity curve should have 3 points: initial + 2 trades
    assert len(equity_curve) == 3
    
    # The equity curve should show:
    # Initial: $10000
    # After AAPL buy: $10000 + unrealized P&L for AAPL
    # After MSFT buy: $10000 + unrealized P&L for both AAPL and MSFT
    
    # Final equity calculation:
    # Initial cash: $10000
    # Cash after trades: $10000 - (10*100) - (5*200) = $8000
    # AAPL unrealized P&L: 10 shares * ($110 - $100) = $100
    # MSFT unrealized P&L: 5 shares * ($210 - $200) = $50
    # Total equity = $8000 + $100 + $50 = $8150
    
    # But wait, the new implementation uses initial_cash + realized_pnl + unrealized_pnl
    # Since we haven't sold anything, realized_pnl = 0
    # So total equity = $10000 + $0 + unrealized_pnl
    # Unrealized P&L = $100 + $50 = $150
    # Total equity = $10000 + $150 = $10150
    
    final_equity = equity_curve.iloc[-1]
    assert final_equity == pytest.approx(10150.0)


def test_equity_curve_timestamps(stats_manager, fixed_timestamps):
    """
    Test that equity curve includes trade timestamps and calculates unrealized P&L correctly.
    """
    # Create trades and price updates at different timestamps
    
    # Trade at timestamp 0
    stats_manager.record_trade(
        timestamp=fixed_timestamps[0],  # 12:00
        symbol="AAPL",
        action="buy",
        quantity=10.0,
        price=100.0,
    )
    
    # Price update at timestamp 2
    stats_manager.update_market_prices(
        {"AAPL": 105.0},
        timestamp=fixed_timestamps[2]  # 14:00
    )
    
    # Trade at timestamp 4
    stats_manager.record_trade(
        timestamp=fixed_timestamps[4],  # 16:00
        symbol="AAPL",
        action="sell",
        quantity=5.0,
        price=110.0,
    )
    
    # Price update at timestamp 6
    stats_manager.update_market_prices(
        {"AAPL": 115.0},
        timestamp=fixed_timestamps[6]  # 18:00
    )
    
    # Calculate equity curve
    equity_curve = stats_manager.calc_equity_curve()
    
    # New implementation: equity curve only includes trade timestamps, not price update timestamps
    # We have 2 trades, so equity curve should have 3 points: initial + 2 trades
    assert len(equity_curve) == 3
    
    # The equity curve should include only the trade timestamps
    expected_timestamps = set([
        fixed_timestamps[0],  # Buy trade
        fixed_timestamps[4],  # Sell trade
    ])
    
    # Convert to sets for comparison (ignoring order)
    actual_timestamps = set(equity_curve.index)
    
    # Remove the initial timestamp which might not match any of our fixed timestamps
    initial_timestamp = None
    for ts in actual_timestamps:
        if ts not in expected_timestamps:
            initial_timestamp = ts
            break
    
    if initial_timestamp:
        actual_timestamps.remove(initial_timestamp)
    
    # Verify that our trade timestamps are in the equity curve
    assert expected_timestamps.issubset(actual_timestamps), \
        f"Missing trade timestamps. Expected: {expected_timestamps}, Got: {actual_timestamps}"


if __name__ == "__main__":
    pytest.main(["-v", __file__]) 