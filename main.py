#!/usr/bin/env python3

"""
Live Trading System Main Entry Point

This script orchestrates the entire live trading infrastructure:
1. Load strategy scripts dynamically
2. Calculate required lookback periods
3. Connect to data sources (real or demo)
4. Generate and display live trading signals
5. Execute trades (future feature)

Usage:
    python3 main.py --strategy sma.py --symbols AAPL,MSFT --data-source demo
    python3 main.py --strategy sma.py --symbols AAPL --data-source polygon --lookback 50
"""

from src.trading_system import cli_main

if __name__ == "__main__":
    exit(cli_main()) 