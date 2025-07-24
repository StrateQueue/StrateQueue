#!/usr/bin/env python3.10
"""
BT Signal Extraction Guide
==========================

This script demonstrates how to extract signals from bt (backtest library) results,
specifically focusing on getting the signals from the last day in the backtest.

Key Methods:
1. backtest.security_weights - Get portfolio weights for each security
2. backtest.positions - Get actual share positions
3. Compare with original signals to verify strategy execution
"""

import pandas as pd
import numpy as np
import bt

def create_sample_data():
    """Create sample price data for demonstration"""
    dates = pd.date_range(start='2020-01-01', end='2023-12-31', freq='B')
    n = len(dates)
    
    np.random.seed(42)
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
    
    # Generate random returns and convert to prices
    returns = pd.DataFrame(
        np.random.normal(0.0005, 0.02, (n, len(tickers))),
        index=dates,
        columns=tickers
    )
    
    return (1 + returns).cumprod() * 100

def create_sma_strategy(data, sma_period=20):
    """Create a Simple Moving Average strategy"""
    # Calculate SMA
    sma = data.rolling(sma_period).mean()
    
    # Create signal: 1 when price > SMA, 0 otherwise
    signal = (data > sma).astype(int)
    
    # Create bt strategy
    strategy = bt.Strategy(
        'SMA_Strategy',
        [
            bt.algos.SelectWhere(signal),
            bt.algos.WeighEqually(),
            bt.algos.Rebalance()
        ]
    )
    
    return strategy, signal

def extract_last_day_signals(backtest_obj, original_signals, data):
    """
    KEY FUNCTION: Extract signals from the last day of a bt backtest
    
    Args:
        backtest_obj: The bt.Backtest object after running
        original_signals: DataFrame of original signals used in strategy
        data: Price data DataFrame
    
    Returns:
        dict: Contains last day's weights, positions, signals, and prices
    """
    
    # Get the last trading date
    last_date = data.index[-1]
    
    print(f"Extracting signals for: {last_date.strftime('%Y-%m-%d')}")
    print("-" * 50)
    
    # METHOD 1: Get security weights (portfolio allocation percentages)
    weights = backtest_obj.security_weights
    last_weights = weights.loc[last_date]
    
    print("1. PORTFOLIO WEIGHTS:")
    for security, weight in last_weights.items():
        if abs(weight) > 1e-6:
            print(f"   {security}: {weight:.1%}")
    
    # METHOD 2: Get actual positions (number of shares)
    positions = backtest_obj.positions
    last_positions = positions.loc[last_date]
    
    print("\n2. SHARE POSITIONS:")
    for security, position in last_positions.items():
        if abs(position) > 1e-6:
            print(f"   {security}: {position:.0f} shares")
    
    # METHOD 3: Get original signals for comparison
    last_signals = original_signals.loc[last_date]
    
    print("\n3. SIGNAL VERIFICATION:")
    for security in data.columns:
        signal = last_signals[security]
        weight = last_weights[security]
        has_position = abs(weight) > 1e-6
        
        status = "✓" if (signal == 1 and has_position) or (signal == 0 and not has_position) else "✗"
        print(f"   {security}: Signal={signal}, Has Position={has_position} {status}")
    
    return {
        'date': last_date,
        'weights': last_weights,
        'positions': last_positions,
        'signals': last_signals
    }

def extract_signals_for_date(backtest_obj, target_date, original_signals=None):
    """
    Extract signals for any specific date from a bt backtest
    
    Args:
        backtest_obj: The bt.Backtest object after running
        target_date: The date to extract signals for (string or datetime)
        original_signals: Optional DataFrame of original signals
    
    Returns:
        dict: Contains the date's weights, positions, and signals
    """
    
    # Convert string date to datetime if needed
    if isinstance(target_date, str):
        target_date = pd.to_datetime(target_date)
    
    # Get weights and positions for the target date
    weights = backtest_obj.security_weights
    positions = backtest_obj.positions
    
    # Check if date exists in the data
    if target_date not in weights.index:
        available_dates = weights.index
        closest_date = available_dates[available_dates <= target_date][-1] if any(available_dates <= target_date) else available_dates[0]
        print(f"Date {target_date.strftime('%Y-%m-%d')} not found. Using closest date: {closest_date.strftime('%Y-%m-%d')}")
        target_date = closest_date
    
    date_weights = weights.loc[target_date]
    date_positions = positions.loc[target_date]
    
    print(f"Signals for {target_date.strftime('%Y-%m-%d')}:")
    print("-" * 40)
    
    # Show active positions
    active_positions = [(sec, weight) for sec, weight in date_weights.items() if abs(weight) > 1e-6]
    
    if active_positions:
        print("Active positions:")
        for security, weight in active_positions:
            shares = date_positions[security]
            print(f"  {security}: {weight:.1%} ({shares:.0f} shares)")
    else:
        print("No active positions")
    
    # Compare with original signals if provided
    if original_signals is not None and target_date in original_signals.index:
        date_signals = original_signals.loc[target_date]
        print("\nSignal comparison:")
        for security in original_signals.columns:
            signal = date_signals[security]
            weight = date_weights[security] if security in date_weights.index else 0
            has_position = abs(weight) > 1e-6
            status = "✓" if (signal == 1 and has_position) or (signal == 0 and not has_position) else "✗"
            print(f"  {security}: Signal={signal}, Position={has_position} {status}")
    
    return {
        'date': target_date,
        'weights': date_weights,
        'positions': date_positions,
        'active_positions': active_positions
    }

def main():
    """Main demonstration"""
    print("BT SIGNAL EXTRACTION DEMONSTRATION")
    print("=" * 50)
    
    # 1. Create data and strategy
    print("1. Creating sample data and SMA strategy...")
    data = create_sample_data()
    strategy, signals = create_sma_strategy(data, sma_period=20)
    
    # 2. Run backtest
    print("2. Running backtest...")
    backtest = bt.Backtest(strategy, data)
    result = bt.run(backtest)
    
    # 3. Extract last day signals - THIS IS THE KEY PART
    print("3. Extracting last day signals...")
    last_day_info = extract_last_day_signals(backtest, signals, data)
    
    # 4. Show summary
    print(f"\n4. SUMMARY:")
    print(f"   Date: {last_day_info['date'].strftime('%Y-%m-%d')}")
    print(f"   Active positions: {sum(abs(w) > 1e-6 for w in last_day_info['weights'])}")
    print(f"   Total portfolio weight: {last_day_info['weights'].sum():.1%}")
    
    # 5. Show how to use this for live trading
    print(f"\n5. FOR LIVE TRADING:")
    print("   Use these weights to determine your position sizes:")
    
    portfolio_value = 100000  # Example $100k portfolio
    for security, weight in last_day_info['weights'].items():
        if abs(weight) > 1e-6:
            dollar_amount = portfolio_value * weight
            print(f"   {security}: ${dollar_amount:,.0f} ({weight:.1%})")
    
    return last_day_info

def demonstrate_date_specific_extraction():
    """Demonstrate extracting signals for specific dates"""
    
    print("\n" + "=" * 60)
    print("EXTRACTING SIGNALS FOR SPECIFIC DATES")
    print("=" * 60)
    
    # Create data and run backtest
    data = create_sample_data()
    strategy, signals = create_sma_strategy(data, sma_period=20)
    backtest = bt.Backtest(strategy, data)
    result = bt.run(backtest)
    
    # Extract signals for different dates
    test_dates = [
        '2023-01-03',  # Beginning of 2023
        '2023-06-15',  # Mid-year
        '2023-12-29'   # End of year (last trading day)
    ]
    
    for date_str in test_dates:
        print(f"\n{date_str}:")
        extract_signals_for_date(backtest, date_str, signals)

if __name__ == "__main__":
    # Run the main demonstration
    main()
    
    # Run the date-specific demonstration
    demonstrate_date_specific_extraction()