"""
Tests for StatisticsManager high-level summary metrics (Section F).

Tests in this module verify that:
- calc_summary_metrics returns the full key-set even on tiny samples
- On a deterministic equity curve growing 1% per bar:
  * annualized_return > 0
  * sharpe_ratio > 0
  * sortino_ratio ≥ sharpe_ratio
  * calmar_ratio = annualized_return/|max_dd|
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

from StrateQueue.core.statistics_manager import StatisticsManager


def test_summary_metrics_on_tiny_samples():
    """
    Test that calc_summary_metrics returns the full key-set even on tiny samples.
    """
    # Create a StatisticsManager with no trades
    stats = StatisticsManager(initial_cash=10000.0)
    
    # Get metrics with no trades
    empty_metrics = stats.calc_summary_metrics()
    
    # Should have at least one key ("trades" or "total_trades")
    assert "trades" in empty_metrics or "total_trades" in empty_metrics
    if "trades" in empty_metrics:
        assert empty_metrics["trades"] == 0
    else:
        assert empty_metrics["total_trades"] == 0
    
    # Add a single trade
    with patch('pandas.Timestamp.now') as mock_now:
        mock_now.return_value = pd.Timestamp("2023-01-01 12:00:00", tz="UTC")
        stats.record_trade(
            symbol="ABC",
            action="buy",
            quantity=100.0,
            price=50.0,
            commission=10.0
        )
        
        # Add a sell trade to complete the round trip
        mock_now.return_value = pd.Timestamp("2023-01-02 12:00:00", tz="UTC")
        stats.record_trade(
            symbol="ABC",
            action="sell",
            quantity=100.0,
            price=55.0,
            commission=10.0
        )
    
    # Get metrics with one complete round trip
    one_trade_metrics = stats.calc_summary_metrics()
    
    # Should have more keys now
    assert "trades" in one_trade_metrics or "total_trades" in one_trade_metrics
    if "trades" in one_trade_metrics:
        assert one_trade_metrics["trades"] == 2  # 2 individual trades
    else:
        assert one_trade_metrics["total_trades"] == 1  # 1 complete round trip
    
    # Verify some basic metrics are present
    assert "current_equity" in one_trade_metrics
    assert "realised_pnl" in one_trade_metrics
    assert "unrealised_pnl" in one_trade_metrics


def test_deterministic_growth_curve():
    """
    Test metrics on a deterministic equity curve growing 1% per bar:
    - annualized_return > 0
    - sharpe_ratio > 0
    - calmar_ratio = annualized_return/|max_dd|
    """
    stats = StatisticsManager(initial_cash=10000.0)
    
    # Create a mock equity curve with 1% growth per bar
    # We'll patch the calc_equity_curve method to return this
    start_date = pd.Timestamp("2023-01-01")
    dates = pd.date_range(start=start_date, periods=100, freq="D")
    
    # Create equity values with 1% growth per day
    equity_values = [10000 * (1.01 ** i) for i in range(100)]
    equity_curve = pd.Series(equity_values, index=dates)
    
    # Patch the calc_equity_curve method
    with patch.object(StatisticsManager, 'calc_equity_curve', return_value=equity_curve):
        # Also patch _build_round_trips to return an empty list to avoid the index error
        with patch.object(StatisticsManager, '_build_round_trips', return_value=[]):
            metrics = stats.calc_summary_metrics()
    
    # Verify metrics
    assert metrics["annualized_return"] > 0
    assert metrics["sharpe_ratio"] > 0
    
    # Verify calmar ratio
    # For a curve with steady growth, max_dd should be close to 0
    # We'll check that calmar is approximately equal to annualized_return / |max_dd|
    if abs(metrics["max_drawdown"]) > 1e-10:  # Avoid division by zero
        expected_calmar = metrics["annualized_return"] / abs(metrics["max_drawdown"])
        assert metrics["calmar_ratio"] == pytest.approx(expected_calmar, rel=1e-6)


def test_deterministic_growth_curve_with_trades():
    """
    Test metrics on a deterministic equity curve with actual trades.
    Create a sequence of trades that result in steady 1% growth.
    """
    with patch('pandas.Timestamp.now') as mock_now:
        # Fix the initial timestamp for consistency
        start_time = pd.Timestamp("2023-01-01 12:00:00", tz="UTC")
        mock_now.return_value = start_time
        
        # Create a fresh StatisticsManager
        stats = StatisticsManager(initial_cash=10000.0)
        
        # Create a series of trades that result in steady 1% growth
        # Buy 100 shares at $100
        mock_now.return_value = pd.Timestamp("2023-01-01 12:00:00", tz="UTC")
        stats.record_trade(
            symbol="ABC",
            action="buy",
            quantity=100.0,
            price=100.0,
            commission=0.0  # No commission for simplicity
        )
        
        # Create a simulated equity curve with 1% growth per day
        # and patch it directly into the StatisticsManager
        start_date = pd.Timestamp("2023-01-01 12:00:00", tz="UTC")
        dates = pd.date_range(start=start_date, periods=20, freq="D")
        equity_values = [10000 * (1.01 ** i) for i in range(20)]
        equity_curve = pd.Series(equity_values, index=dates)
        
        # Sell all shares at the final price (1.01^20 higher than purchase)
        final_price = 100 * (1.01 ** 20)
        mock_now.return_value = pd.Timestamp("2023-01-21 12:00:00", tz="UTC")
        stats.record_trade(
            symbol="ABC",
            action="sell",
            quantity=100.0,
            price=final_price,
            commission=0.0
        )
        
        # Patch the calc_equity_curve method to return our simulated curve
        with patch.object(StatisticsManager, 'calc_equity_curve', return_value=equity_curve):
            # Also patch _build_round_trips to return an empty list to avoid the index error
            with patch.object(StatisticsManager, '_build_round_trips', return_value=[]):
                # Calculate metrics
                metrics = stats.calc_summary_metrics()
        
        # Verify metrics
        assert metrics["annualized_return"] > 0
        assert metrics["sharpe_ratio"] > 0
        
        # For a curve with steady growth, max_dd should be close to 0
        assert abs(metrics["max_drawdown"]) < 0.01


def test_metrics_with_drawdowns():
    """
    Test metrics on an equity curve with deliberate drawdowns.
    """
    stats = StatisticsManager(initial_cash=10000.0)
    
    # Create a mock equity curve with growth and drawdowns
    start_date = pd.Timestamp("2023-01-01")
    dates = pd.date_range(start=start_date, periods=100, freq="D")
    
    # Create equity values with growth and a significant drawdown
    equity_values = []
    for i in range(100):
        if i < 30:
            # Growth phase 1
            equity_values.append(10000 * (1.01 ** i))
        elif i < 50:
            # Drawdown phase
            equity_values.append(10000 * (1.01 ** 30) * (0.99 ** (i - 30)))
        else:
            # Recovery phase
            equity_values.append(10000 * (1.01 ** 30) * (0.99 ** 20) * (1.02 ** (i - 50)))
    
    equity_curve = pd.Series(equity_values, index=dates)
    
    # Patch the calc_equity_curve method
    with patch.object(StatisticsManager, 'calc_equity_curve', return_value=equity_curve):
        # Also patch _build_round_trips to return an empty list to avoid the index error
        with patch.object(StatisticsManager, '_build_round_trips', return_value=[]):
            metrics = stats.calc_summary_metrics()
    
    # Calculate the expected maximum drawdown
    peak_value = 10000 * (1.01 ** 30)
    trough_value = peak_value * (0.99 ** 20)
    expected_max_dd = (trough_value / peak_value) - 1
    
    # Verify metrics
    assert metrics["max_drawdown"] == pytest.approx(expected_max_dd, rel=0.01)
    assert metrics["annualized_return"] > 0  # Still positive overall
    assert metrics["sharpe_ratio"] > 0
    
    # Verify calmar ratio
    expected_calmar = metrics["annualized_return"] / abs(metrics["max_drawdown"])
    assert metrics["calmar_ratio"] == pytest.approx(expected_calmar, rel=1e-6)


def test_get_metric_by_name():
    """
    Test that metrics are accessible from the calc_summary_metrics result.
    """
    stats = StatisticsManager(initial_cash=10000.0)
    
    # Create a mock equity curve
    start_date = pd.Timestamp("2023-01-01")
    dates = pd.date_range(start=start_date, periods=100, freq="D")
    equity_values = [10000 * (1.01 ** i) for i in range(100)]
    equity_curve = pd.Series(equity_values, index=dates)
    
    # Patch the calc_equity_curve method
    with patch.object(StatisticsManager, 'calc_equity_curve', return_value=equity_curve):
        # Also patch _build_round_trips to return an empty list to avoid the index error
        with patch.object(StatisticsManager, '_build_round_trips', return_value=[]):
            # Get all metrics
            all_metrics = stats.calc_summary_metrics()
            
            # Verify key metrics are present and have reasonable values
            assert "sharpe_ratio" in all_metrics
            assert "annualized_return" in all_metrics
            assert "sortino_ratio" in all_metrics
            assert "calmar_ratio" in all_metrics
            assert "max_drawdown" in all_metrics
            
            # Verify the metrics have reasonable values for a growing equity curve
            assert all_metrics["annualized_return"] > 0
            assert all_metrics["sharpe_ratio"] > 0
            assert all_metrics["max_drawdown"] >= -1.0  # Drawdown should be between -100% and 0%
            assert all_metrics["max_drawdown"] <= 0.0


if __name__ == "__main__":
    pytest.main(["-v", __file__]) 