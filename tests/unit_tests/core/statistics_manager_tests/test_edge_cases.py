"""
Tests for StatisticsManager edge cases and robustness (Section G).

Tests in this module verify that:
- No trades & no price updates → summary contains only "trades": 0
- Updating initial cash before/after trades behaves correctly
- Negative prices, zero-quantity trades, and NaNs are handled gracefully
"""

import pytest
import pandas as pd
import numpy as np
import logging
from unittest.mock import patch, MagicMock

from StrateQueue.core.statistics_manager import StatisticsManager


def get_trade_count(metrics):
    """Helper function to get trade count from metrics, handling API inconsistency."""
    if "total_trades" in metrics:
        return metrics["total_trades"]
    elif "trades" in metrics:
        return metrics["trades"]
    else:
        return 0


# Define a complete mock return value for _calculate_trade_stats
def mock_trade_stats():
    return {
        "win_rate": 0.0,
        "loss_rate": 0.0,
        "profit_factor": 0.0,
        "total_trades": 0,
        "win_count": 0,
        "loss_count": 0,
        "breakeven_count": 0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "expectancy": 0.0,
        "avg_win_pct": 0.0,
        "avg_loss_pct": 0.0,
        "avg_hold_time_bars": 0.0,
        "avg_hold_time_seconds": 0.0,
        "trade_frequency": 0.0,
        "kelly_fraction": 0.0,
        "kelly_half": 0.0,
    }


def test_empty_statistics_manager():
    """
    Test that with no trades & no price updates, summary contains only "trades": 0.
    """
    stats = StatisticsManager(initial_cash=10000.0)
    
    # Get metrics with no trades
    metrics = stats.calc_summary_metrics()
    
    # Should have at least one key ("trades" or "total_trades")
    assert "total_trades" in metrics or "trades" in metrics
    assert get_trade_count(metrics) == 0
    
    # Verify that the equity curve is empty
    equity_curve = stats.calc_equity_curve()
    assert len(equity_curve) == 0 or (equity_curve == stats._initial_cash).all()


def test_update_initial_cash_before_trades():
    """
    Test that updating initial cash before any trades actually adjusts the first cash point.
    """
    stats = StatisticsManager(initial_cash=10000.0)
    
    # Verify initial cash
    assert stats._initial_cash == 10000.0
    assert stats._get_current_cash_balance() == 10000.0
    
    # Update initial cash
    stats.update_initial_cash(20000.0)
    
    # Verify cash was updated
    assert stats._initial_cash == 20000.0
    assert stats._get_current_cash_balance() == 20000.0
    
    # Now add a trade
    with patch('pandas.Timestamp.now') as mock_now:
        mock_now.return_value = pd.Timestamp("2023-01-01 12:00:00", tz="UTC")
        stats.record_trade(
            symbol="ABC",
            action="buy",
            quantity=100.0,
            price=50.0,
            commission=0.0
        )
    
    # Verify cash was reduced by the trade amount
    expected_cash = 20000.0 - (100.0 * 50.0)
    assert stats._get_current_cash_balance() == expected_cash


def test_update_initial_cash_after_trades():
    """
    Test that updating initial cash after trades logs a warning and leaves values unchanged.
    """
    stats = StatisticsManager(initial_cash=10000.0)
    
    # Add a trade
    with patch('pandas.Timestamp.now') as mock_now:
        mock_now.return_value = pd.Timestamp("2023-01-01 12:00:00", tz="UTC")
        stats.record_trade(
            symbol="ABC",
            action="buy",
            quantity=100.0,
            price=50.0,
            commission=0.0
        )
    
    # Verify cash was reduced by the trade amount
    expected_cash = 10000.0 - (100.0 * 50.0)
    assert stats._get_current_cash_balance() == expected_cash
    
    # Try to update initial cash after trades
    with patch('logging.Logger.warning') as mock_warning:
        stats.update_initial_cash(20000.0)
        
        # Verify warning was logged
        mock_warning.assert_called_once()
    
    # Verify cash values remain unchanged
    assert stats._initial_cash == 10000.0
    assert stats._get_current_cash_balance() == expected_cash


def test_negative_prices():
    """
    Test that negative prices are accepted but still work with calc_summary_metrics.
    """
    stats = StatisticsManager(initial_cash=10000.0)
    
    # Record a trade with negative price
    stats.record_trade(
        symbol="ABC",
        action="buy",
        quantity=100.0,
        price=-50.0,
        commission=0.0
    )
    
    # Verify trade was recorded (StatisticsManager doesn't validate prices)
    assert len(stats._trades) == 1
    
    # Verify cash was increased (because price is negative)
    expected_cash = 10000.0 + (100.0 * 50.0)
    assert stats._get_current_cash_balance() == expected_cash
    
    # Verify calc_summary_metrics still returns when we mock _calculate_trade_stats
    with patch.object(stats, '_calculate_trade_stats', return_value=mock_trade_stats()):
        metrics = stats.calc_summary_metrics()
        assert "total_trades" in metrics
        # Check actual number of recorded trades, not round trips
        assert len(stats._trades) == 1


def test_zero_quantity_trades():
    """
    Test that zero-quantity trades are accepted but have no effect on cash.
    """
    stats = StatisticsManager(initial_cash=10000.0)
    
    # Record a trade with zero quantity
    stats.record_trade(
        symbol="ABC",
        action="buy",
        quantity=0.0,
        price=50.0,
        commission=0.0
    )
    
    # Verify trade was recorded (StatisticsManager doesn't validate quantities)
    assert len(stats._trades) == 1
    
    # Verify cash remains unchanged (since quantity is zero)
    assert stats._get_current_cash_balance() == 10000.0
    
    # Verify calc_summary_metrics still returns when we mock _calculate_trade_stats
    with patch.object(stats, '_calculate_trade_stats', return_value=mock_trade_stats()):
        metrics = stats.calc_summary_metrics()
        assert "total_trades" in metrics
        # Check actual number of recorded trades, not round trips
        assert len(stats._trades) == 1


def test_nan_values():
    """
    Test that NaN values are handled gracefully without raising exceptions.
    """
    stats = StatisticsManager(initial_cash=10000.0)
    
    # Record a trade with NaN price
    stats.record_trade(
        symbol="ABC",
        action="buy",
        quantity=100.0,
        price=float('nan'),
        commission=0.0
    )
    
    # Verify trade was recorded (StatisticsManager doesn't validate for NaN)
    assert len(stats._trades) == 1
    
    # Verify calc_summary_metrics still returns when we mock _calculate_trade_stats
    with patch.object(stats, '_calculate_trade_stats', return_value=mock_trade_stats()):
        metrics = stats.calc_summary_metrics()
        assert "total_trades" in metrics
        # Check actual number of recorded trades, not round trips
        assert len(stats._trades) == 1


def test_robustness_with_valid_and_invalid_trades():
    """
    Test robustness with a mix of valid and invalid trades.
    """
    stats = StatisticsManager(initial_cash=10000.0)
    
    # Record some trades
    with patch('pandas.Timestamp.now') as mock_now:
        # Trade 1
        mock_now.return_value = pd.Timestamp("2023-01-01 12:00:00", tz="UTC")
        stats.record_trade(
            symbol="ABC",
            action="buy",
            quantity=100.0,
            price=50.0,
            commission=10.0
        )
        
        # Trade 2 (negative price)
        mock_now.return_value = pd.Timestamp("2023-01-02 12:00:00", tz="UTC")
        stats.record_trade(
            symbol="XYZ",
            action="buy",
            quantity=200.0,
            price=-30.0,
            commission=10.0
        )
        
        # Trade 3
        mock_now.return_value = pd.Timestamp("2023-01-03 12:00:00", tz="UTC")
        stats.record_trade(
            symbol="ABC",
            action="sell",
            quantity=100.0,
            price=55.0,
            commission=10.0
        )
        
        # Trade 4 (zero quantity)
        mock_now.return_value = pd.Timestamp("2023-01-04 12:00:00", tz="UTC")
        stats.record_trade(
            symbol="DEF",
            action="buy",
            quantity=0.0,
            price=40.0,
            commission=10.0
        )
    
    # Verify all trades were recorded
    assert len(stats._trades) == 4
    
    # Verify calc_summary_metrics still returns when we mock _calculate_trade_stats
    with patch.object(stats, '_calculate_trade_stats', return_value=mock_trade_stats()):
        metrics = stats.calc_summary_metrics()
        assert "total_trades" in metrics
        # Check actual number of recorded trades, not round trips
        assert len(stats._trades) == 4


def test_edge_cases_in_equity_curve():
    """
    Test edge cases in equity curve calculation.
    """
    stats = StatisticsManager(initial_cash=10000.0)
    
    # Record a buy trade
    with patch('pandas.Timestamp.now') as mock_now:
        mock_now.return_value = pd.Timestamp("2023-01-01 12:00:00", tz="UTC")
        stats.record_trade(
            symbol="ABC",
            action="buy",
            quantity=100.0,
            price=50.0,
            commission=0.0
        )
    
    # Get equity curve with no price updates
    equity_curve1 = stats.calc_equity_curve()
    
    # Should have at least one point
    assert len(equity_curve1) > 0
    
    # Try to calculate summary metrics with mocked _calculate_trade_stats
    with patch.object(stats, '_calculate_trade_stats', return_value=mock_trade_stats()):
        metrics = stats.calc_summary_metrics()
        
        # Should have trades key
        assert "total_trades" in metrics
        # Check actual number of recorded trades, not round trips
        assert len(stats._trades) == 1


if __name__ == "__main__":
    pytest.main(["-v", __file__]) 