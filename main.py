#!/usr/bin/env python3

"""
Live Trading System Main Entry Point

This script orchestrates the entire live trading infrastructure:
1. Load strategy scripts dynamically
2. Connect to data sources (real or demo)
3. Generate and display live trading signals
4. Execute trades (future feature)

Usage:
    python3.10 main.py deploy --strategy examples/strategies/sma.py --symbol AAPL --granularity 1m --allocation 0.2 --data-source demo --lookback 60
    python3.10 main.py deploy --strategy examples/strategies/sma.py --symbol DOGE --granularity 1s --allocation 0.2 --data-source demo --lookback 60
"""

from src.trading_system import cli_main

if __name__ == "__main__":
    exit(cli_main()) 