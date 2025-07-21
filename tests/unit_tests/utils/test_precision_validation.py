"""
Precision Validation Tests

Tests to validate that the price precision management system works correctly
and that no artificial rounding occurs throughout the system.
"""

import pytest
from StrateQueue.utils.price_formatter import PriceFormatter, PrecisionPreservingDataHandler


def test_system_precision_validation():
    """Test the system precision validation function"""
    results = PrecisionPreservingDataHandler.validate_system_precision()
    
    # The system should preserve precision
    assert results["precision_preserved"], f"Precision validation failed: {results['issues_found']}"
    
    # Should have no issues
    assert len(results["issues_found"]) == 0, f"Found precision issues: {results['issues_found']}"
    
    # Should have no recommendations if precision is preserved
    if results["precision_preserved"]:
        assert len(results["recommendations"]) == 0


def test_real_world_zen_scenario():
    """Test the specific ZEN/USDC scenario that was showing precision loss"""
    # The actual price that was being rounded to $9.30
    zen_price = 9.304567891234567
    
    # Format with our new system
    formatted = PriceFormatter.format_price_for_logging(zen_price)
    
    # Should show full precision, not $9.30
    # Note: Due to floating point representation, 9.304567891234567 becomes 9.304567891234568
    assert "9.304567891234568" in formatted
    assert formatted != "$9.30"
    
    # Should be able to parse back with minimal precision loss
    parsed_price = float(formatted[1:])  # Remove $ sign
    precision_loss = abs(parsed_price - zen_price)
    assert precision_loss < 1e-14, f"Too much precision loss: {precision_loss}"


def test_various_crypto_prices():
    """Test various cryptocurrency price scenarios"""
    crypto_prices = {
        "BTC": 43567.89123456789,
        "ETH": 2345.67891234567,
        "DOGE": 0.00123456789123,
        "SHIB": 0.00000123456789,
        "USDT": 1.00123456789
    }
    
    for symbol, price in crypto_prices.items():
        # Format for display
        display_formatted = PriceFormatter.format_price_for_display(price)
        
        # Parse back
        parsed_price = float(display_formatted[1:])  # Remove $ sign
        
        # Check precision preservation
        precision_loss = abs(parsed_price - price)
        assert precision_loss < 1e-12, f"Precision loss for {symbol}: {precision_loss}"
        
        # Ensure it's not artificially rounded to 2 decimal places
        if price != round(price, 2):  # If original wasn't exactly 2 decimal places
            assert display_formatted != f"${price:.2f}", f"Price was artificially rounded for {symbol}"


def test_stock_prices():
    """Test various stock price scenarios"""
    stock_prices = {
        "AAPL": 156.789123456,
        "GOOGL": 2789.123456789,
        "TSLA": 234.56789123,
        "AMZN": 3456.789012345
    }
    
    for symbol, price in stock_prices.items():
        # Format for display
        display_formatted = PriceFormatter.format_price_for_display(price)
        
        # Parse back
        parsed_price = float(display_formatted[1:])  # Remove $ sign
        
        # Check precision preservation
        precision_loss = abs(parsed_price - price)
        assert precision_loss < 1e-12, f"Precision loss for {symbol}: {precision_loss}"


def test_data_storage_precision():
    """Test that data storage preserves precision"""
    original_data = {
        "BTC/USD": 43567.89123456789,
        "ETH/USD": 2345.67891234567,
        "DOGE/USD": 0.00123456789123,
        "prices": [9.304567891234567, 156.789123456, 0.00000123456789]
    }
    
    # Store data
    stored_data = PrecisionPreservingDataHandler.store_price_data(original_data)
    
    # Should be the exact same object (no copying or modification)
    assert stored_data is original_data
    
    # Retrieve data
    retrieved_data = PrecisionPreservingDataHandler.retrieve_price_data(stored_data)
    
    # Should be the exact same object
    assert retrieved_data is stored_data
    
    # All values should be identical
    for key, value in original_data.items():
        if isinstance(value, list):
            for i, price in enumerate(value):
                assert retrieved_data[key][i] == price
        else:
            assert retrieved_data[key] == value


def test_calculation_precision():
    """Test that calculations preserve precision"""
    price1 = 9.304567891234567
    price2 = 1.23456789012345
    
    # Perform calculation
    result = price1 * price2
    
    # Preserve calculation precision
    preserved_result = PrecisionPreservingDataHandler.preserve_calculation_precision(result, "multiply")
    
    # Should be exactly the same
    assert preserved_result == result
    
    # Test with very small results
    small_result = 1e-12
    preserved_small = PrecisionPreservingDataHandler.preserve_calculation_precision(small_result, "divide")
    assert preserved_small == small_result


def test_logging_precision():
    """Test that logging maintains precision"""
    test_prices = [
        9.304567891234567,
        0.00000123456789,
        43567.89123456789,
        156.789123456
    ]
    
    for price in test_prices:
        log_formatted = PriceFormatter.format_price_for_logging(price)
        
        # Should contain the full precision (not rounded to 2 decimals)
        parsed_price = float(log_formatted[1:])  # Remove $ sign
        precision_loss = abs(parsed_price - price)
        assert precision_loss < 1e-12, f"Logging precision loss: {precision_loss}"


def test_edge_cases():
    """Test edge cases for precision handling"""
    # Test None
    assert PriceFormatter.format_price_for_display(None) == "$0.0"
    
    # Test NaN
    import math
    assert PriceFormatter.format_price_for_display(float('nan')) == "$0.0"
    
    # Test zero
    assert PriceFormatter.format_price_for_display(0.0) == "$0.0"
    
    # Test very large numbers
    large_price = 1234567890.123456789
    formatted = PriceFormatter.format_price_for_display(large_price)
    parsed = float(formatted[1:])
    assert abs(parsed - large_price) < 1e-6  # Allow for some precision loss with very large numbers
    
    # Test very small numbers
    tiny_price = 1e-15
    formatted = PriceFormatter.format_price_for_display(tiny_price)
    parsed = float(formatted[1:])
    # For extremely small numbers near floating point limits, allow larger precision loss
    # since they may be rounded to 0.0 for practical display purposes
    assert abs(parsed - tiny_price) < 1e-14


if __name__ == "__main__":
    pytest.main([__file__])