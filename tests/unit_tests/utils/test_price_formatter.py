"""
Unit tests for PriceFormatter utility class

Tests all formatting scenarios to ensure no artificial rounding occurs
and full precision is maintained throughout the system.
"""

import pytest
import math
from src.StrateQueue.utils.price_formatter import PriceFormatter, PrecisionPreservingDataHandler


class TestPriceFormatter:
    """Test cases for PriceFormatter class"""
    
    def test_format_price_basic(self):
        """Test basic price formatting without rounding"""
        # Test whole numbers
        assert PriceFormatter.format_price(100.0) == "100.0"
        assert PriceFormatter.format_price(1.0) == "1.0"
        
        # Test decimal numbers - should preserve all significant digits
        # Note: Due to floating-point precision, we test that the formatted value
        # is very close to the expected value when parsed back
        formatted_9_304567 = PriceFormatter.format_price(9.304567)
        assert abs(float(formatted_9_304567) - 9.304567) < 1e-10
        
        formatted_123_456789 = PriceFormatter.format_price(123.456789)
        assert abs(float(formatted_123_456789) - 123.456789) < 1e-10
        
        formatted_small = PriceFormatter.format_price(0.000123456)
        assert abs(float(formatted_small) - 0.000123456) < 1e-12
        
        # Test very small numbers
        assert PriceFormatter.format_price(0.00000001) == "0.00000001"
        assert PriceFormatter.format_price(1e-8) == "0.00000001"
        
        # Test very large numbers - check precision preservation
        formatted_large = PriceFormatter.format_price(1234567.89)
        assert abs(float(formatted_large) - 1234567.89) < 1e-8
    
    def test_format_price_trailing_zeros(self):
        """Test that trailing zeros are properly removed"""
        # Due to floating-point precision, we test that trailing zeros are removed
        # and the result is close to expected when parsed back
        formatted_9_3 = PriceFormatter.format_price(9.30000)
        assert abs(float(formatted_9_3) - 9.3) < 1e-10
        
        assert PriceFormatter.format_price(100.00000) == "100.0"
        assert PriceFormatter.format_price(0.10000) == "0.1"
        
        formatted_1_23 = PriceFormatter.format_price(1.23000)
        assert abs(float(formatted_1_23) - 1.23) < 1e-10
    
    def test_format_price_force_precision(self):
        """Test forced precision formatting"""
        # Force 2 decimal places
        assert PriceFormatter.format_price(9.304567, force_precision=2) == "9.3"
        assert PriceFormatter.format_price(9.306567, force_precision=2) == "9.31"
        
        # Force 6 decimal places
        assert PriceFormatter.format_price(9.3, force_precision=6) == "9.3"
        assert PriceFormatter.format_price(9.304567, force_precision=6) == "9.304567"
    
    def test_format_price_edge_cases(self):
        """Test edge cases for price formatting"""
        # Test zero
        assert PriceFormatter.format_price(0.0) == "0.0"
        
        # Test None
        assert PriceFormatter.format_price(None) == "0.0"
        
        # Test NaN
        assert PriceFormatter.format_price(float('nan')) == "0.0"
        
        # Test negative numbers
        formatted_neg = PriceFormatter.format_price(-9.304567)
        assert abs(float(formatted_neg) - (-9.304567)) < 1e-10
        assert PriceFormatter.format_price(-100.0) == "-100.0"
    
    def test_format_price_for_display(self):
        """Test display formatting with dollar sign"""
        formatted_display = PriceFormatter.format_price_for_display(9.304567)
        assert formatted_display.startswith("$")
        assert abs(float(formatted_display[1:]) - 9.304567) < 1e-10
        
        assert PriceFormatter.format_price_for_display(100.0) == "$100.0"
        
        formatted_small = PriceFormatter.format_price_for_display(0.000123)
        assert abs(float(formatted_small[1:]) - 0.000123) < 1e-12
        
        # Test edge cases
        assert PriceFormatter.format_price_for_display(None) == "$0.0"
        assert PriceFormatter.format_price_for_display(float('nan')) == "$0.0"
    
    def test_format_price_for_logging(self):
        """Test logging formatting with dollar sign"""
        formatted_log = PriceFormatter.format_price_for_logging(9.304567)
        assert formatted_log.startswith("$")
        assert abs(float(formatted_log[1:]) - 9.304567) < 1e-10
        
        assert PriceFormatter.format_price_for_logging(100.0) == "$100.0"
        
        formatted_small = PriceFormatter.format_price_for_logging(0.000123)
        assert abs(float(formatted_small[1:]) - 0.000123) < 1e-12
        
        # Test edge cases
        assert PriceFormatter.format_price_for_logging(None) == "$0.0"
        assert PriceFormatter.format_price_for_logging(float('nan')) == "$0.0"
    
    def test_format_currency(self):
        """Test currency formatting with different currencies"""
        # Test USD (default)
        formatted_usd = PriceFormatter.format_currency(9.304567)
        assert formatted_usd.startswith("$")
        assert abs(float(formatted_usd[1:]) - 9.304567) < 1e-10
        
        # Test other major currencies
        formatted_eur = PriceFormatter.format_currency(9.304567, "EUR")
        assert formatted_eur.startswith("€")
        assert abs(float(formatted_eur[1:]) - 9.304567) < 1e-10
        
        # Test crypto currencies
        formatted_btc = PriceFormatter.format_currency(0.00123456, "BTC")
        assert formatted_btc.startswith("₿")
        
        # Test unknown currency
        formatted_xyz = PriceFormatter.format_currency(9.304567, "XYZ")
        assert "XYZ" in formatted_xyz
        
        # Test edge cases
        assert PriceFormatter.format_currency(None, "USD") == "0.0 USD"
    
    def test_crypto_precision_scenarios(self):
        """Test scenarios specific to cryptocurrency precision"""
        # Bitcoin prices (high value, moderate precision)
        btc_price = 43567.89123456
        formatted_btc = PriceFormatter.format_price(btc_price)
        assert abs(float(formatted_btc) - btc_price) < 1e-8
        
        # Altcoin prices (low value, high precision needed)
        alt_price = 0.00000123456789
        formatted_alt = PriceFormatter.format_price(alt_price)
        assert abs(float(formatted_alt) - alt_price) < 1e-12
        
        # Stablecoin prices (should be close to 1.0 but with precision)
        stable_price = 1.00123456
        formatted_stable = PriceFormatter.format_price(stable_price)
        assert abs(float(formatted_stable) - stable_price) < 1e-10
        
        # Very small fractions
        tiny_price = 1e-12
        formatted = PriceFormatter.format_price(tiny_price)
        assert "e-" not in formatted.lower()  # Should not use scientific notation
        assert abs(float(formatted) - tiny_price) < 1e-15  # Should preserve exact value
    
    def test_stock_precision_scenarios(self):
        """Test scenarios specific to stock price precision"""
        # Typical stock prices
        stock_price = 156.789123
        formatted_stock = PriceFormatter.format_price(stock_price)
        assert abs(float(formatted_stock) - stock_price) < 1e-10
        
        # Penny stocks
        penny_stock = 0.0123456
        formatted_penny = PriceFormatter.format_price(penny_stock)
        assert abs(float(formatted_penny) - penny_stock) < 1e-12
        
        # High-value stocks
        expensive_stock = 3456.789012
        formatted_expensive = PriceFormatter.format_price(expensive_stock)
        assert abs(float(formatted_expensive) - expensive_stock) < 1e-8


class TestRealWorldScenarios:
    """Test real-world scenarios that caused the original precision issues"""
    
    def test_zen_usdc_scenario(self):
        """Test the specific ZEN/USDC scenario that showed $9.30 instead of full precision"""
        # Simulate the actual price that was being rounded
        actual_price = 9.304567891234
        
        # Old way (what was causing the issue)
        old_formatted = f"${actual_price:.2f}"
        assert old_formatted == "$9.30"  # This was the problem
        
        # New way (with PriceFormatter)
        new_formatted = PriceFormatter.format_price_for_logging(actual_price)
        # Due to floating-point precision, check that it's very close
        parsed_price = float(new_formatted[1:])  # Remove $ sign
        assert abs(parsed_price - actual_price) < 1e-12
        
        # Most importantly, it should NOT be rounded to 2 decimal places
        assert new_formatted != "$9.30"
        assert len(new_formatted.split('.')[1]) > 2  # More than 2 decimal places
    
    def test_signal_extraction_logging(self):
        """Test the signal extraction logging scenario"""
        signal_price = 9.304567891234567
        
        # Simulate the old logging format
        old_log_message = f"Extracted signal: HOLD at price: ${signal_price:.2f}"
        assert "9.30" in old_log_message
        
        # New logging format
        new_log_message = f"Extracted signal: HOLD at price: {PriceFormatter.format_price_for_logging(signal_price)}"
        # Due to floating-point precision, check that it preserves more precision than .2f
        formatted_price = PriceFormatter.format_price_for_logging(signal_price)
        parsed_price = float(formatted_price[1:])  # Remove $ sign
        assert abs(parsed_price - signal_price) < 1e-12
        
        # Most importantly, it should NOT be rounded to 2 decimal places
        assert formatted_price != "$9.30"
        assert len(formatted_price.split('.')[1]) > 2  # More than 2 decimal places


if __name__ == "__main__":
    pytest.main([__file__])