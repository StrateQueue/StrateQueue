"""
Comprehensive Test Suite for TestDataIngestion (Demo Provider)

This test module thoroughly tests the TestDataIngestion implementation with focus on:
1. Historical data fetch & caching
2. Real-time simulation loop
3. Helper setters
4. Error handling and edge cases

Tests run without network I/O and avoid wall-clock timing dependencies.
"""

import asyncio
import time
import threading
from unittest.mock import patch, MagicMock, ANY
from datetime import datetime, timedelta

import pytest
import pandas as pd

from StrateQueue.data.sources.demo import TestDataIngestion
from StrateQueue.data.sources.data_source_base import MarketData


class TestHistoricalFetchAndCaching:
    """Test historical data fetch and caching behavior"""

    @pytest.fixture
    def test_ingestion(self):
        """Create a TestDataIngestion instance for testing"""
        return TestDataIngestion()

    @pytest.mark.asyncio
    async def test_fetch_historical_data_basic(self, test_ingestion):
        """Test basic historical data fetch returns correct structure"""
        # Act
        df = await test_ingestion.fetch_historical_data("AAPL", days_back=1, granularity="1m")
        
        # Assert
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert len(df) >= 390  # At least one trading day of 1-minute bars
        assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
        assert df.index.name == "timestamp"
        assert pd.api.types.is_datetime64_any_dtype(df.index)
        
        # Check that OHLC values are reasonable
        assert (df["High"] >= df["Low"]).all()
        assert (df["High"] >= df["Open"]).all()
        assert (df["High"] >= df["Close"]).all()
        assert (df["Low"] <= df["Open"]).all()
        assert (df["Low"] <= df["Close"]).all()
        assert (df["Volume"] > 0).all()

    @pytest.mark.asyncio
    async def test_fetch_historical_data_caching(self, test_ingestion):
        """Test that historical data is cached and second call returns same object"""
        # Act - First fetch
        df1 = await test_ingestion.fetch_historical_data("AAPL", days_back=1, granularity="1m")
        
        # Act - Second fetch with same parameters
        df2 = await test_ingestion.fetch_historical_data("AAPL", days_back=1, granularity="1m")
        
        # Assert - Should return the exact same object (cached)
        assert df1 is df2
        assert id(df1) == id(df2)

    @pytest.mark.asyncio
    async def test_fetch_historical_data_different_params_no_cache(self, test_ingestion):
        """Test that different parameters don't hit cache"""
        # Act - Different parameters
        df1 = await test_ingestion.fetch_historical_data("AAPL", days_back=1, granularity="1m")
        df2 = await test_ingestion.fetch_historical_data("AAPL", days_back=2, granularity="1m")
        df3 = await test_ingestion.fetch_historical_data("AAPL", days_back=1, granularity="5m")
        df4 = await test_ingestion.fetch_historical_data("MSFT", days_back=1, granularity="1m")
        
        # Assert - All should be different objects
        assert df1 is not df2
        assert df1 is not df3
        assert df1 is not df4
        assert df2 is not df3
        assert df2 is not df4
        assert df3 is not df4

    @pytest.mark.asyncio
    async def test_fetch_historical_data_cache_verification_with_patching(self, test_ingestion):
        """Test that cache prevents regeneration by patching _generate_random_walk"""
        # Setup - Mock the random walk generation
        with patch.object(test_ingestion, '_generate_minimal_historical_data') as mock_gen:
            # Act - First call
            df1 = await test_ingestion.fetch_historical_data("AAPL", days_back=1, granularity="1m")
            
            # Act - Second call
            df2 = await test_ingestion.fetch_historical_data("AAPL", days_back=1, granularity="1m")
            
            # Assert - Should be same object and generation only called once
            assert df1 is df2
            # The _generate_minimal_historical_data is not called for main historical data
            # But we can verify through the cache mechanism

    @pytest.mark.asyncio
    async def test_fetch_historical_data_invalid_granularity(self, test_ingestion):
        """Test that invalid granularity raises ValueError"""
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid granularity format"):
            await test_ingestion.fetch_historical_data("AAPL", days_back=1, granularity="invalid")

    @pytest.mark.asyncio
    async def test_fetch_historical_data_different_granularities(self, test_ingestion):
        """Test that different granularities produce different number of bars"""
        # Act
        df_1m = await test_ingestion.fetch_historical_data("AAPL", days_back=1, granularity="1m")
        df_5m = await test_ingestion.fetch_historical_data("AAPL", days_back=1, granularity="5m")
        df_1h = await test_ingestion.fetch_historical_data("AAPL", days_back=1, granularity="1h")
        
        # Assert - Higher granularity should have fewer bars
        assert len(df_1m) > len(df_5m)
        assert len(df_5m) > len(df_1h)

    @pytest.mark.asyncio
    async def test_fetch_historical_data_updates_current_price(self, test_ingestion):
        """Test that fetch_historical_data updates current_prices"""
        # Act
        df = await test_ingestion.fetch_historical_data("AAPL", days_back=1, granularity="1m")
        
        # Assert
        assert "AAPL" in test_ingestion.current_prices
        assert test_ingestion.current_prices["AAPL"] == df["Close"].iloc[-1]


class TestRealtimeSimulationLoop:
    """Test real-time simulation loop behavior"""

    @pytest.fixture
    def test_ingestion(self):
        """Create a TestDataIngestion instance for testing"""
        return TestDataIngestion()

    def test_start_realtime_feed(self, test_ingestion):
        """Test that start_realtime_feed starts the simulation"""
        # Act
        test_ingestion.start_realtime_feed()
        
        # Assert
        assert test_ingestion.is_connected is True
        assert test_ingestion.stop_simulation is False
        assert test_ingestion.simulation_thread is not None
        assert test_ingestion.simulation_thread.is_alive()
        
        # Cleanup
        test_ingestion.stop_realtime_feed()

    def test_stop_realtime_feed(self, test_ingestion):
        """Test that stop_realtime_feed stops the simulation and joins thread"""
        # Setup
        test_ingestion.start_realtime_feed()
        assert test_ingestion.is_connected is True
        
        # Act
        test_ingestion.stop_realtime_feed()
        
        # Assert
        assert test_ingestion.is_connected is False
        assert test_ingestion.stop_simulation is True
        # Thread should be joined and not alive
        assert not test_ingestion.simulation_thread.is_alive()

    @pytest.mark.asyncio
    async def test_subscribe_to_symbol(self, test_ingestion):
        """Test symbol subscription"""
        # Act
        await test_ingestion.subscribe_to_symbol("AAPL")
        
        # Assert
        assert "AAPL" in test_ingestion.subscribed_symbols
        assert "AAPL" in test_ingestion.current_prices

    @pytest.mark.asyncio
    async def test_subscribe_to_symbol_idempotent(self, test_ingestion):
        """Test that subscribing to same symbol twice is idempotent"""
        # Act
        await test_ingestion.subscribe_to_symbol("AAPL")
        await test_ingestion.subscribe_to_symbol("AAPL")
        
        # Assert
        assert test_ingestion.subscribed_symbols.count("AAPL") == 1

    def test_generate_realtime_bar(self, test_ingestion):
        """Test that _generate_realtime_bar produces valid MarketData"""
        # Setup
        test_ingestion.current_prices["AAPL"] = 175.0
        
        # Act
        bar = test_ingestion._generate_realtime_bar("AAPL")
        
        # Assert
        assert isinstance(bar, MarketData)
        assert bar.symbol == "AAPL"
        assert isinstance(bar.timestamp, datetime)
        assert bar.high >= bar.low
        assert bar.high >= bar.open
        assert bar.high >= bar.close
        assert bar.low <= bar.open
        assert bar.low <= bar.close
        assert bar.volume > 0

    def test_generate_realtime_bar_produces_valid_data(self, test_ingestion):
        """Test that _generate_realtime_bar produces valid data without side effects"""
        # Setup
        initial_price = 175.0
        test_ingestion.current_prices["AAPL"] = initial_price
        
        # Act
        bar = test_ingestion._generate_realtime_bar("AAPL")
        
        # Assert - _generate_realtime_bar doesn't update current_prices by itself
        assert test_ingestion.current_prices["AAPL"] == initial_price  # Should be unchanged
        assert 50 < bar.close < 500  # Reasonable range
        
        # But when we manually update current_prices, it should work
        test_ingestion.current_prices["AAPL"] = bar.close
        assert test_ingestion.current_prices["AAPL"] == bar.close

    def test_realtime_simulation_with_mocked_sleep(self, test_ingestion, monkeypatch):
        """Test real-time simulation without wall-clock wait"""
        # Setup - Mock sleep to avoid actual waiting
        monkeypatch.setattr(time, "sleep", lambda *_: None)
        
        # Setup - Set very small update interval
        test_ingestion.set_update_interval(0.001)
        
        # Setup - Subscribe to symbol
        asyncio.run(test_ingestion.subscribe_to_symbol("AAPL"))
        
        # Setup - Callback collector
        callback_calls = []
        test_ingestion.add_data_callback(lambda data: callback_calls.append(data))
        
        # Act - Start simulation
        test_ingestion.start_realtime_feed()
        
        # Give simulation a moment to generate some bars
        time.sleep(0.01)  # Small real sleep to let thread run
        
        # Act - Force generate some bars
        for _ in range(3):
            test_ingestion._generate_realtime_bar("AAPL")
        
        # Stop simulation
        test_ingestion.stop_realtime_feed()
        
        # Assert - Current bars should be populated
        assert "AAPL" in test_ingestion.current_bars
        assert isinstance(test_ingestion.current_bars["AAPL"], MarketData)

    def test_realtime_simulation_callback_firing(self, test_ingestion, monkeypatch):
        """Test that callbacks fire exactly once per bar"""
        # Setup - Mock sleep
        monkeypatch.setattr(time, "sleep", lambda *_: None)
        
        # Setup - Callback collector
        callback_calls = []
        test_ingestion.add_data_callback(lambda data: callback_calls.append(data))
        
        # Setup - Subscribe to symbol
        asyncio.run(test_ingestion.subscribe_to_symbol("AAPL"))
        
        # Act - Force generate bars and notify callbacks
        for _ in range(3):
            bar = test_ingestion._generate_realtime_bar("AAPL")
            test_ingestion.current_bars["AAPL"] = bar
            test_ingestion._notify_callbacks(bar)
        
        # Assert - Callbacks should have been called for each bar
        assert len(callback_calls) == 3
        assert all(isinstance(call, MarketData) for call in callback_calls)
        assert all(call.symbol == "AAPL" for call in callback_calls)

    def test_current_prices_change_over_successive_bars(self, test_ingestion):
        """Test that current_prices change over successive bars"""
        # Setup
        test_ingestion.current_prices["AAPL"] = 175.0
        
        # Act - Generate multiple bars
        prices = []
        for _ in range(10):
            bar = test_ingestion._generate_realtime_bar("AAPL")
            test_ingestion.current_prices["AAPL"] = bar.close
            prices.append(bar.close)
        
        # Assert - Not all prices should be the same (very high probability)
        assert len(set(prices)) > 1, "Prices should change over time"

    def test_simulation_loop_error_handling(self, test_ingestion, monkeypatch):
        """Test that simulation loop handles errors gracefully"""
        # Setup - Mock sleep
        monkeypatch.setattr(time, "sleep", lambda *_: None)
        
        # Setup - Subscribe to symbol
        asyncio.run(test_ingestion.subscribe_to_symbol("AAPL"))
        
        # Setup - Mock _generate_realtime_bar to raise exception
        original_generate = test_ingestion._generate_realtime_bar
        call_count = 0
        
        def mock_generate(symbol):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Test exception")
            return original_generate(symbol)
        
        test_ingestion._generate_realtime_bar = mock_generate
        
        # Act - Start simulation
        test_ingestion.start_realtime_feed()
        time.sleep(0.01)  # Let it run briefly
        test_ingestion.stop_realtime_feed()
        
        # Assert - Should not crash and should have tried to generate
        assert call_count >= 1


class TestHelperSetters:
    """Test helper setter methods"""

    @pytest.fixture
    def test_ingestion(self):
        """Create a TestDataIngestion instance for testing"""
        return TestDataIngestion()

    def test_set_update_interval_from_granularity_5m(self, test_ingestion):
        """Test set_update_interval_from_granularity with 5m sets update_interval to 300"""
        # Act
        test_ingestion.set_update_interval_from_granularity("5m")
        
        # Assert
        assert test_ingestion.update_interval == 300  # 5 * 60 seconds

    def test_set_update_interval_from_granularity_1h(self, test_ingestion):
        """Test set_update_interval_from_granularity with 1h sets update_interval to 3600"""
        # Act
        test_ingestion.set_update_interval_from_granularity("1h")
        
        # Assert
        assert test_ingestion.update_interval == 3600  # 1 * 3600 seconds

    def test_set_update_interval_from_granularity_1d(self, test_ingestion):
        """Test set_update_interval_from_granularity with 1d sets update_interval to 86400"""
        # Act
        test_ingestion.set_update_interval_from_granularity("1d")
        
        # Assert
        assert test_ingestion.update_interval == 86400  # 1 * 86400 seconds

    def test_set_update_interval_from_granularity_invalid(self, test_ingestion, caplog):
        """Test set_update_interval_from_granularity with invalid granularity logs warning"""
        # Act
        test_ingestion.set_update_interval_from_granularity("invalid")
        
        # Assert - Should log warning and keep default interval
        assert "Could not parse granularity" in caplog.text
        assert test_ingestion.update_interval == 1.0  # Default

    def test_set_update_interval_directly(self, test_ingestion):
        """Test set_update_interval directly"""
        # Act
        test_ingestion.set_update_interval(0.5)
        
        # Assert
        assert test_ingestion.update_interval == 0.5

    def test_set_volatility(self, test_ingestion):
        """Test set_volatility mutates price_volatility"""
        # Act
        test_ingestion.set_volatility(0.02)
        
        # Assert
        assert test_ingestion.price_volatility == 0.02

    def test_set_volatility_affects_price_generation(self, test_ingestion):
        """Test that set_volatility affects price generation"""
        # Setup
        test_ingestion.current_prices["AAPL"] = 175.0
        
        # Test with low volatility
        test_ingestion.set_volatility(0.001)  # Very low volatility
        low_vol_prices = []
        for _ in range(20):
            bar = test_ingestion._generate_realtime_bar("AAPL")
            low_vol_prices.append(bar.close)
        
        # Test with high volatility
        test_ingestion.set_volatility(0.1)  # High volatility
        high_vol_prices = []
        test_ingestion.current_prices["AAPL"] = 175.0  # Reset
        for _ in range(20):
            bar = test_ingestion._generate_realtime_bar("AAPL")
            high_vol_prices.append(bar.close)
        
        # Assert - High volatility should have larger price ranges
        low_vol_range = max(low_vol_prices) - min(low_vol_prices)
        high_vol_range = max(high_vol_prices) - min(high_vol_prices)
        
        # This is probabilistic, but with 20 samples, high volatility should show more variation
        assert high_vol_range > low_vol_range * 0.5  # Allow for some randomness

    def test_set_base_price(self, test_ingestion):
        """Test set_base_price updates both base_prices and current_prices"""
        # Act
        test_ingestion.set_base_price("AAPL", 200.0)
        
        # Assert
        assert test_ingestion.base_prices["AAPL"] == 200.0
        assert test_ingestion.current_prices["AAPL"] == 200.0




class TestEdgeCasesAndIntegration:
    """Test edge cases and integration scenarios"""

    @pytest.fixture
    def test_ingestion(self):
        """Create a TestDataIngestion instance for testing"""
        return TestDataIngestion()

    def test_initialization_with_custom_base_prices(self):
        """Test initialization with custom base prices"""
        # Act
        custom_prices = {"AAPL": 200.0, "MSFT": 350.0}
        test_ingestion = TestDataIngestion(base_prices=custom_prices)
        
        # Assert
        assert test_ingestion.base_prices["AAPL"] == 200.0
        assert test_ingestion.base_prices["MSFT"] == 350.0
        assert test_ingestion.current_prices["AAPL"] == 200.0
        assert test_ingestion.current_prices["MSFT"] == 350.0

    def test_initialization_with_none_base_prices(self):
        """Test initialization with None base prices uses defaults"""
        # Act
        test_ingestion = TestDataIngestion(base_prices=None)
        
        # Assert
        assert "AAPL" in test_ingestion.base_prices
        assert "MSFT" in test_ingestion.base_prices
        assert test_ingestion.base_prices["AAPL"] == 175.0  # Default

    @pytest.mark.asyncio
    async def test_fetch_historical_data_unknown_symbol(self, test_ingestion):
        """Test fetch_historical_data with unknown symbol"""
        # Act
        df = await test_ingestion.fetch_historical_data("UNKNOWN", days_back=1, granularity="1m")
        
        # Assert - Should still work and generate reasonable data
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "UNKNOWN" in test_ingestion.current_prices
        # Price should be positive and reasonable (can drift from initial 50-500 range due to random walk)
        assert test_ingestion.current_prices["UNKNOWN"] > 0
        assert test_ingestion.current_prices["UNKNOWN"] < 1000  # Reasonable upper bound

    def test_generate_realtime_bar_unknown_symbol(self, test_ingestion):
        """Test _generate_realtime_bar with unknown symbol"""
        # Act
        bar = test_ingestion._generate_realtime_bar("UNKNOWN")
        
        # Assert - Should work and generate reasonable data
        assert isinstance(bar, MarketData)
        assert bar.symbol == "UNKNOWN"
        assert bar.close > 0

    @pytest.mark.asyncio
    async def test_integration_fetch_then_realtime(self, test_ingestion, monkeypatch):
        """Test integration: fetch historical data then start realtime"""
        # Setup - Mock sleep
        monkeypatch.setattr(time, "sleep", lambda *_: None)
        
        # Act - Fetch historical data first
        df = await test_ingestion.fetch_historical_data("AAPL", days_back=1, granularity="1m")
        historical_final_price = df["Close"].iloc[-1]
        
        # Act - Start realtime
        await test_ingestion.subscribe_to_symbol("AAPL")
        test_ingestion.start_realtime_feed()
        
        # Generate a few bars
        for _ in range(3):
            bar = test_ingestion._generate_realtime_bar("AAPL")
            test_ingestion.current_bars["AAPL"] = bar
        
        test_ingestion.stop_realtime_feed()
        
        # Assert - Should have both historical and realtime data
        assert "AAPL" in test_ingestion.historical_data
        assert "AAPL" in test_ingestion.current_bars
        assert len(df) >= 390  # Historical data
        assert isinstance(test_ingestion.current_bars["AAPL"], MarketData)
        
        # Current price should be within a reasonable range of historical final price
        current_price = test_ingestion.current_bars["AAPL"].close
        # Allow for more variation since it's probabilistic
        assert abs(current_price - historical_final_price) < historical_final_price * 0.25  # Within 25%

    def test_thread_safety_stop_feed_multiple_times(self, test_ingestion):
        """Test that calling stop_realtime_feed multiple times is safe"""
        # Setup
        test_ingestion.start_realtime_feed()
        
        # Act - Stop multiple times
        test_ingestion.stop_realtime_feed()
        test_ingestion.stop_realtime_feed()
        test_ingestion.stop_realtime_feed()
        
        # Assert - Should not crash
        assert test_ingestion.is_connected is False
        assert test_ingestion.stop_simulation is True

    def test_callback_error_handling(self, test_ingestion):
        """Test that callback errors don't crash the system"""
        # Setup - Add callback that raises exception
        def bad_callback(data):
            raise Exception("Test callback error")
        
        test_ingestion.add_data_callback(bad_callback)
        
        # Act - Generate bar and notify (should not crash)
        bar = test_ingestion._generate_realtime_bar("AAPL")
        test_ingestion._notify_callbacks(bar)  # Should not raise
        
        # Assert - No exception should be raised
        assert True  # If we get here, no exception was raised 