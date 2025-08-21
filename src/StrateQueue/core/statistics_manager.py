from __future__ import annotations

"""Centralised statistics tracking for StrateQueue

This module collects *raw* facts about what happened (prices & trades)
and calculates performance metrics using Empyrical.

High-level design
=================
1.  Every executed (or hypothetical) fill becomes a TradeRecord.
2.  `update_market_prices` appends the latest OHLCV data for each symbol
    and is called once per bar.
3.  Performance metrics are calculated using Empyrical for reliability.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging

import pandas as pd
import empyrical as ep
import numpy as np

from rich.panel import Panel
from rich.table import Table
from rich.console import Console
from rich import box
from rich.text import Text

from .signal_extractor import TradingSignal, SignalType

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Canonical representation of a single fill/order execution."""

    timestamp: pd.Timestamp
    symbol: str
    action: str  # "buy" or "sell" (case-insensitive)
    quantity: float
    price: float
    strategy_id: Optional[str] = None
    commission: float = 0.0
    fees: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def value(self) -> float:
        """Absolute dollar value of the fill (signed)."""
        sign = 1 if self.action.lower() == "buy" else -1
        return sign * self.quantity * self.price
    
    @property
    def realized_pnl(self) -> float:
        """Realized P&L for this trade (simplified calculation)."""
        # For now, we'll calculate a simple P&L based on trade value
        # In a more sophisticated system, this would track position entry/exit prices
        if self.action.lower() == "sell":
            # Selling generates positive P&L (simplified)
            return self.quantity * self.price - self.commission - self.fees
        else:
            # Buying doesn't generate realized P&L until sold
            return 0.0


class StatisticsManager:
    """Collects price marks & trades and logs them for analysis."""

    def __init__(self, initial_cash: float = 100000.0, allocation: float = 0.0):
        # Raw storage ----------------------------------------------------
        self._trades: List[TradeRecord] = []
        self._ohlcv_history: Dict[str, pd.DataFrame] = {}  # symbol -> DataFrame with OHLCV columns
        
        # Cash tracking --------------------------------------------------
        self._initial_cash = float(initial_cash)
        self._cash_history: pd.Series = pd.Series(dtype=float)  # timestamp -> cash_balance
        
        # Signal tracking ------------------------------------------------
        self._signal_history: List[Dict[str, Any]] = []
        self._latest_signals: Dict[str, Dict[str, Any]] = {}  # symbol -> {signal, price, timestamp}
        
        # Allocation tracking ---------------------------------------------
        self._allocation = float(allocation) if allocation > 0 else self._initial_cash
        
        # Initialize with starting cash balance
        initial_time = pd.Timestamp.now(tz="UTC")
        self._cash_history.loc[initial_time] = self._initial_cash

    # ------------------------------------------------------------------
    # DATA INGESTION
    # ------------------------------------------------------------------
    def record_trade(
        self,
        *,
        timestamp: "pd.Timestamp | None" = None,
        strategy_id: str | None = None,
        symbol: str,
        action: str,
        quantity: float,
        price: float,
        commission: float = 0.0,
        fees: float = 0.0,
        metadata: Dict[str, Any] | None = None,
        **extra: Any,
    ) -> None:
        """Store a *real* fill coming from a broker.

        Keyword-only arguments to keep the call sites self-documenting.
        Extra kwargs are merged into metadata for forward compatibility.
        """
        ts_raw = pd.Timestamp.now(tz="UTC") if timestamp is None else pd.Timestamp(timestamp)
        # Normalise timezone: ensure *all* timestamps are UTC-aware
        ts = ts_raw if ts_raw.tzinfo is not None else ts_raw.tz_localize("UTC")
        md = metadata.copy() if metadata else {}
        md.update(extra)

        trade = TradeRecord(
            timestamp=ts,
            symbol=symbol,
            action=action.lower(),
            quantity=float(quantity),
            price=float(price),
            strategy_id=strategy_id,
            commission=float(commission),
            fees=float(fees),
            metadata=md,
        )
        self._trades.append(trade)
        
        # Update cash balance: buy = cash out, sell = cash in
        trade_value = trade.quantity * trade.price
        total_cost = trade_value + trade.commission + trade.fees
        
        if trade.action == "buy":
            cash_change = -total_cost  # Cash decreases
        else:  # sell
            cash_change = trade_value  # Cash increases (we get back the full sale value)
        
        # Update cash history
        current_cash = self._get_current_cash_balance()
        new_cash_balance = current_cash + cash_change
        self._cash_history.loc[ts] = new_cash_balance

    # ------------------------------------------------------------------
    def record_signal(
        self,
        *,
        timestamp: "pd.Timestamp | None" = None,
        symbol: str,
        signal_type: str,
        price: float,
        strategy_id: str | None = None,
        **metadata: Any,
    ) -> None:
        """Record a trading signal for session tracking."""
        ts_raw = pd.Timestamp.now(tz="UTC") if timestamp is None else pd.Timestamp(timestamp)
        ts = ts_raw if ts_raw.tzinfo is not None else ts_raw.tz_localize("UTC")
        
        signal_record = {
            "timestamp": ts,
            "symbol": symbol,
            "signal": signal_type.upper(),
            "price": float(price),
            "strategy_id": strategy_id,
            **metadata
        }
        
        self._signal_history.append(signal_record)
        self._latest_signals[symbol] = signal_record

    # ------------------------------------------------------------------
    def record_hypothetical_trade(self, signal: TradingSignal, symbol: str) -> None:
        """Capture a trade that *would* occur if the signal were executed.

        This is used in **signals-only** mode so the analytics are still
        meaningful even when no broker is connected.
        """
        # Record the signal for session tracking
        self.record_signal(
            timestamp=signal.timestamp,
            symbol=symbol,
            signal_type=signal.signal.value,
            price=signal.price,
            strategy_id=getattr(signal, "strategy_id", None),
        )
        
        if signal.signal == SignalType.HOLD:
            return  # nothing to do for trade recording

        qty = signal.quantity or 0.0
        if qty == 0.0:
            if signal.signal == SignalType.BUY:
                # For BUY signals, use the allocation to calculate quantity
                if self._allocation > 0:
                    qty = self._allocation / signal.price
                else:
                    qty = 1.0
            elif signal.signal == SignalType.CLOSE:
                # For CLOSE signals, find the current position and use that quantity
                current_positions = self._build_position_timeseries()
                qty = current_positions.get(symbol, 0.0)
                if qty == 0.0:
                    # Fallback to allocation-based quantity
                    if self._allocation > 0:
                        qty = self._allocation / signal.price
                    else:
                        qty = 1.0
            else:
                # For other signals, use allocation
                if self._allocation > 0:
                    qty = self._allocation / signal.price
                else:
                    qty = 1.0

        # Determine action: BUY for BUY signals, SELL for SELL/CLOSE signals
        action = "buy" if signal.signal == SignalType.BUY else "sell"

        self.record_trade(
            timestamp=signal.timestamp,
            strategy_id=getattr(signal, "strategy_id", None),
            symbol=symbol,
            action=action,
            quantity=qty,
            price=signal.price,
            commission=0.0,
        )

    # ------------------------------------------------------------------
    def update_market_prices(
        self, 
        latest_data: Dict[str, "float | Dict[str, float]"], 
        timestamp: "pd.Timestamp | None" = None
    ) -> None:
        """Append the latest OHLCV data for each symbol.
        
        Args:
            latest_data: Dict mapping symbol to either:
                - float: Just the close price (backward compatibility)
                - Dict: Full OHLCV data
                    Format: {
                        "AAPL": {
                            "open": 150.0,
                            "high": 152.0, 
                            "low": 149.0,
                            "close": 151.0,
                            "volume": 1000000
                        }
                    }
            timestamp: Optional timestamp for the data
        """
        ts_raw = pd.Timestamp.now(tz="UTC") if timestamp is None else pd.Timestamp(timestamp)
        ts = ts_raw if ts_raw.tzinfo is not None else ts_raw.tz_localize("UTC")
        
        for symbol, data in latest_data.items():
            # Handle both formats: float (close price only) or dict (full OHLCV)
            if isinstance(data, (int, float)):
                # Backward compatibility: just close price
                close_price = float(data)
                new_row = pd.DataFrame([{
                    'open': close_price,
                    'high': close_price,
                    'low': close_price,
                    'close': close_price,
                    'volume': 0.0
                }], index=[ts])
            else:
                # Full OHLCV data
                ohlcv = data
                new_row = pd.DataFrame([{
                    'open': float(ohlcv.get('open', ohlcv.get('close', 0.0))),
                    'high': float(ohlcv.get('high', ohlcv.get('close', 0.0))),
                    'low': float(ohlcv.get('low', ohlcv.get('close', 0.0))),
                    'close': float(ohlcv.get('close', 0.0)),
                    'volume': float(ohlcv.get('volume', 0.0))
                }], index=[ts])
            
            # Append to existing data - avoid concatenation warnings
            if symbol not in self._ohlcv_history or self._ohlcv_history[symbol].empty:
                # First data point for this symbol
                self._ohlcv_history[symbol] = new_row
            else:
                # Append to existing data
                self._ohlcv_history[symbol] = pd.concat([
                    self._ohlcv_history[symbol], 
                    new_row
                ], ignore_index=False).sort_index()

    # ------------------------------------------------------------------
    # CASH TRACKING HELPERS
    # ------------------------------------------------------------------
    def _get_current_cash_balance(self) -> float:
        """Get the most recent cash balance."""
        if self._cash_history.empty:
            return self._initial_cash
        return self._cash_history.iloc[-1]
    
    def get_cash_history(self) -> pd.Series:
        """Return the full cash balance history."""
        return self._cash_history.copy()
    
    def update_initial_cash(self, new_initial_cash: float) -> None:
        """Update the initial cash balance (useful when broker account info becomes available)."""
        if len(self._trades) > 0:
            logger.warning("Cannot update initial cash after trades have been recorded")
            return
            
        old_cash = self._initial_cash
        self._initial_cash = float(new_initial_cash)
        
        # Update the cash history
        if not self._cash_history.empty:
            # Replace the initial entry
            first_timestamp = self._cash_history.index[0]
            self._cash_history.loc[first_timestamp] = self._initial_cash
        else:
            # Create initial entry
            initial_time = pd.Timestamp.now(tz="UTC")
            self._cash_history.loc[initial_time] = self._initial_cash
            
        logger.info(f"Updated initial cash from ${old_cash:,.2f} to ${self._initial_cash:,.2f}")

    # ------------------------------------------------------------------
    # HELPER METHODS FOR OHLCV DATA
    # ------------------------------------------------------------------
    def get_close_prices(self, symbol: str) -> pd.Series:
        """Get close price series for a symbol."""
        if symbol in self._ohlcv_history and not self._ohlcv_history[symbol].empty:
            return self._ohlcv_history[symbol]['close']
        return pd.Series(dtype=float)
    
    def get_ohlcv_data(self, symbol: str) -> pd.DataFrame:
        """Get full OHLCV DataFrame for a symbol."""
        return self._ohlcv_history.get(symbol, pd.DataFrame())
    
    def get_all_symbols(self) -> List[str]:
        """Get list of all symbols with OHLCV data."""
        return list(self._ohlcv_history.keys())
    
    def get_latest_price(self, symbol: str) -> float:
        """Get the latest close price for a symbol."""
        close_prices = self.get_close_prices(symbol)
        if not close_prices.empty:
            return close_prices.iloc[-1]
        return 0.0

    # ------------------------------------------------------------------
    # CORE CALCULATION METHODS (using Empyrical)
    # ------------------------------------------------------------------
    def calc_equity_curve(self) -> pd.Series:
        """Calculate the equity curve representing total portfolio value over time."""
        if not self._trades:
            # No trades yet, just return initial cash
            if not self._cash_history.empty:
                return self._cash_history.copy()
            else:
                return pd.Series([self._initial_cash], index=[pd.Timestamp.now(tz="UTC")])
        
        # Build equity curve by calculating total portfolio value at each trade timestamp
        equity_points = []
        
        # Start with initial cash
        initial_time = self._cash_history.index[0] if not self._cash_history.empty else pd.Timestamp.now(tz="UTC")
        equity_points.append((initial_time, self._initial_cash))
        
        # Calculate realized P&L at each trade completion
        running_realized_pnl = 0.0
        round_trips = self._build_round_trips()
        
        # Create a mapping of exit times to realized P&L
        exit_pnl_map = {}
        for trip in round_trips:
            exit_time = trip['exit_time']
            if exit_time not in exit_pnl_map:
                exit_pnl_map[exit_time] = 0.0
            exit_pnl_map[exit_time] += trip['pnl']
        
        # Sort trades by timestamp to build equity curve chronologically
        sorted_trades = sorted(self._trades, key=lambda t: t.timestamp)
        
        for trade in sorted_trades:
            # Add realized P&L from completed round trips up to this point
            if trade.timestamp in exit_pnl_map:
                running_realized_pnl += exit_pnl_map[trade.timestamp]
            
            # Calculate total equity at this point: initial cash + realized P&L + unrealized P&L
            unrealized_pnl = self._calculate_unrealized_pnl_at_time(trade.timestamp)
            total_equity = self._initial_cash + running_realized_pnl + unrealized_pnl
            
            equity_points.append((trade.timestamp, total_equity))
        
        # Create equity curve series
        equity_curve = pd.Series([point[1] for point in equity_points], 
                                index=[point[0] for point in equity_points])
        
        return equity_curve

    def _calculate_realised_pnl(self) -> float:
        """Calculate total realized P&L from all completed trades."""
        # Build round trips to calculate proper P&L
        round_trips = self._build_round_trips()
        return sum(trip['pnl'] for trip in round_trips)

    def _calculate_unrealised_pnl(self) -> float:
        """Calculate unrealized P&L from current positions."""
        if not self._trades:
            return 0.0
            
        # Get current positions
        positions = self._build_position_timeseries()
        if not positions:
            return 0.0
            
        unrealized_pnl = 0.0
        
        # Calculate unrealized P&L for each position
        for symbol, position in positions.items():
            if position != 0:  # Has position
                current_price = self.get_latest_price(symbol)
                if current_price > 0:
                    # Calculate average entry price from trades
                    symbol_trades = [t for t in self._trades if t.symbol == symbol]
                    if symbol_trades:
                        # Simple average entry price (could be improved with VWAP)
                        entry_prices = [t.price for t in symbol_trades if t.action == "buy"]
                        if entry_prices:
                            avg_entry = sum(entry_prices) / len(entry_prices)
                            unrealized_pnl += position * (current_price - avg_entry)
        
        return unrealized_pnl
    
    def _calculate_unrealized_pnl_at_time(self, timestamp: pd.Timestamp) -> float:
        """Calculate unrealized P&L for open positions as of a specific timestamp."""
        # Get all trades up to this timestamp
        trades_up_to_time = [t for t in self._trades if t.timestamp <= timestamp]
        
        if not trades_up_to_time:
            return 0.0
        
        # Calculate positions as of this timestamp
        positions = {}
        for trade in trades_up_to_time:
            symbol = trade.symbol
            if symbol not in positions:
                positions[symbol] = 0
            
            if trade.action == "buy":
                positions[symbol] += trade.quantity
            elif trade.action == "sell":
                positions[symbol] -= trade.quantity
        
        # Calculate unrealized P&L using the latest available price
        unrealized_pnl = 0.0
        for symbol, position in positions.items():
            if position != 0:  # Has open position
                current_price = self.get_latest_price(symbol)
                if current_price > 0:
                    # Calculate average entry price from buy trades up to this time
                    symbol_trades = [t for t in trades_up_to_time if t.symbol == symbol]
                    entry_prices = [t.price for t in symbol_trades if t.action == "buy"]
                    if entry_prices:
                        avg_entry = sum(entry_prices) / len(entry_prices)
                        unrealized_pnl += position * (current_price - avg_entry)
        
        return unrealized_pnl

    def _calculate_total_fees(self) -> float:
        """Calculate total fees from all trades."""
        return sum(trade.commission + trade.fees for trade in self._trades)

    def _calculate_annualization_factor(self, returns_series: pd.Series) -> float:
        """Stub: Returns 252."""
        return 252.0

    def _calculate_exposure_time(self) -> float:
        """Calculate total exposure time in days."""
        if not self._trades:
            return 0.0
        
        if len(self._trades) < 2:
            return 0.0
        
        total_time = (self._trades[-1].timestamp - self._trades[0].timestamp).total_seconds()
        return total_time / 86400.0  # Convert to days
    
    def _calculate_exposure_percentage(self) -> float:
        """Calculate percentage of time with positions."""
        if not self._trades:
            return 0.0
        
        if len(self._trades) < 2:
            return 0.0
        
        # Calculate total time period
        total_time = (self._trades[-1].timestamp - self._trades[0].timestamp).total_seconds()
        if total_time == 0:
            return 0.0
        
        # Calculate time with positions by analyzing round trips
        round_trips = self._build_round_trips()
        exposure_time = 0.0
        
        for trip in round_trips:
            duration = trip['duration']  # Already in seconds
            exposure_time += duration
        
        # Cap at 100% (can't have more than 100% exposure)
        percentage = (exposure_time / total_time) * 100.0
        return min(percentage, 100.0)  # Return as percentage, capped at 100%

    def _calculate_equity_peak(self, curve: pd.Series) -> float:
        """Calculate the peak equity value."""
        if curve.empty:
            return self._initial_cash
        return float(curve.max())

    def _calculate_annualized_return(self, curve: pd.Series, annualization_factor: float) -> float:
        """Calculate annualized return using Empyrical."""
        if curve.empty or len(curve) < 2:
            return 0.0
        
        returns = curve.pct_change().dropna()
        try:
            return ep.annual_return(returns)
        except Exception:
            return 0.0

    def _calculate_annualized_volatility(self, rets: pd.Series, annualization_factor: float) -> float:
        """Calculate annualized volatility using Empyrical."""
        if rets.empty:
            return 0.0
        try:
            return ep.annual_volatility(rets)
        except Exception:
            return 0.0

    def _calculate_sortino_ratio(self, rets: pd.Series, annualization_factor: float, risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio using Empyrical."""
        if rets.empty:
            return 0.0
        try:
            return ep.sortino_ratio(rets, required_return=risk_free_rate)
        except Exception:
            return 0.0

    def _calculate_calmar_ratio(self, annualized_return: float, max_drawdown: float) -> float:
        """Calculate Calmar ratio using custom calculation."""
        if max_drawdown == 0:
            return 0.0
        return annualized_return / abs(max_drawdown)
    
    # Custom return calculation methods (NumPy 2.0 compatible)
    def _custom_cum_returns_final(self, returns: pd.Series) -> float:
        """Custom implementation of cum_returns_final that works with NumPy 2.0."""
        if returns.empty:
            return 0.0
        return (1 + returns).prod() - 1

    def _custom_annual_return(self, returns: pd.Series, periods_per_year: int = 252) -> float:
        """Custom implementation of annual_return that works with NumPy 2.0."""
        if returns.empty:
            return 0.0
        total_return = self._custom_cum_returns_final(returns)
        num_periods = len(returns)
        if num_periods == 0:
            return 0.0
        return (1 + total_return) ** (periods_per_year / num_periods) - 1

    def _custom_annual_volatility(self, returns: pd.Series, periods_per_year: int = 252) -> float:
        """Custom implementation of annual_volatility that works with NumPy 2.0."""
        if returns.empty:
            return 0.0
        return returns.std() * np.sqrt(periods_per_year)

    def _custom_sharpe_ratio(self, returns: pd.Series, risk_free: float = 0.02, periods_per_year: int = 252) -> float:
        """Custom implementation of sharpe_ratio that works with NumPy 2.0."""
        if returns.empty:
            return 0.0
        excess_returns = returns - risk_free / periods_per_year
        if excess_returns.std() == 0:
            return 0.0
        return excess_returns.mean() / excess_returns.std() * np.sqrt(periods_per_year)

    def _custom_sortino_ratio(self, returns: pd.Series, required_return: float = 0.02, periods_per_year: int = 252) -> float:
        """Custom implementation of sortino_ratio that works with NumPy 2.0."""
        if returns.empty:
            return 0.0
        excess_returns = returns - required_return / periods_per_year
        downside_returns = excess_returns[excess_returns < 0]
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            # If no downside returns, return a high positive value (perfect downside protection)
            return 999.0 if excess_returns.mean() > 0 else 0.0
        return excess_returns.mean() / downside_returns.std() * np.sqrt(periods_per_year)

    def _custom_max_drawdown(self, returns: pd.Series) -> float:
        """Custom implementation of max_drawdown that works with NumPy 2.0."""
        if returns.empty:
            return 0.0
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        return drawdown.min()

    def _custom_expected_return(self, returns: pd.Series) -> float:
        """Custom implementation of expected_return that works with NumPy 2.0."""
        if returns.empty:
            return 0.0
        # For daily returns, we should return the mean daily return
        # But since we're dealing with cash flows, this might not be meaningful
        # Let's return the mean return but with a more descriptive name
        return returns.mean()

    def _custom_best(self, returns: pd.Series) -> float:
        """Custom implementation of best that works with NumPy 2.0."""
        if returns.empty:
            return 0.0
        return returns.max()

    def _custom_worst(self, returns: pd.Series) -> float:
        """Custom implementation of worst that works with NumPy 2.0."""
        if returns.empty:
            return 0.0
        return returns.min()
    
    def _custom_best_period(self, returns: pd.Series) -> float:
        """Calculate best period return (not necessarily a day)."""
        if returns.empty:
            return 0.0
        return returns.max()
    
    def _custom_worst_period(self, returns: pd.Series) -> float:
        """Calculate worst period return (not necessarily a day)."""
        if returns.empty:
            return 0.0
        return returns.min()
    
    def _custom_calmar_ratio(self, returns: pd.Series) -> float:
        """Custom implementation of calmar_ratio that works with NumPy 2.0."""
        if returns.empty:
            return 0.0
        annual_return = self._custom_annual_return(returns)
        max_dd = self._custom_max_drawdown(returns)
        if max_dd == 0:
            return 0.0
        return annual_return / abs(max_dd)
    
    def _custom_drawdown_series(self, returns: pd.Series) -> pd.Series:
        """Custom implementation of drawdown series that works with NumPy 2.0."""
        if returns.empty:
            return pd.Series(dtype=float)
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        return drawdown

    def _calculate_drawdown_stats(self, curve: pd.Series) -> Dict[str, float]:
        """Calculate drawdown statistics using Empyrical."""
        if curve.empty or len(curve) < 2:
            return {
                "avg_drawdown": 0.0,
                "max_drawdown_duration": 0,
                "avg_drawdown_duration": 0.0
            }
        
        returns = curve.pct_change().dropna()
        
        # Calculate drawdowns using custom implementation (NumPy 2.0 compatible)
        try:
            drawdowns = self._custom_drawdown_series(returns)
            max_drawdown = self._custom_max_drawdown(returns)
        except Exception:
            return {
                "avg_drawdown": 0.0,
                "max_drawdown_duration": 0,
                "avg_drawdown_duration": 0.0
            }
        
        if drawdowns.empty:
            return {
                "avg_drawdown": 0.0,
                "max_drawdown_duration": 0,
                "avg_drawdown_duration": 0.0
            }
        
        # Calculate drawdown statistics
        avg_drawdown = drawdowns.mean()
        
        # Calculate drawdown durations
        drawdown_periods = []
        in_drawdown = False
        start_idx = None
        
        for i, dd in enumerate(drawdowns):
            if dd < 0 and not in_drawdown:
                in_drawdown = True
                start_idx = i
            elif dd >= 0 and in_drawdown:
                in_drawdown = False
                if start_idx is not None:
                    drawdown_periods.append(i - start_idx)
        
        # Handle case where still in drawdown at end
        if in_drawdown and start_idx is not None:
            drawdown_periods.append(len(drawdowns) - start_idx)
        
        max_dd_duration = max(drawdown_periods) if drawdown_periods else 0
        avg_dd_duration = sum(drawdown_periods) / len(drawdown_periods) if drawdown_periods else 0.0
        
        return {
            "avg_drawdown": float(avg_drawdown),
            "max_drawdown_duration": int(max_dd_duration),
            "avg_drawdown_duration": float(avg_dd_duration)
        }

    def _build_round_trips(self) -> List:
        """Build round trip trades from individual trades."""
        if not self._trades:
            return []
        
        # Group trades by symbol
        symbol_trades = {}
        for trade in self._trades:
            if trade.symbol not in symbol_trades:
                symbol_trades[trade.symbol] = []
            symbol_trades[trade.symbol].append(trade)
        
        round_trips = []
        
        # Build round trips for each symbol
        for symbol, trades in symbol_trades.items():
            position = 0
            entry_price = 0
            entry_time = None
            
            for trade in trades:
                if trade.action == "buy":
                    if position == 0:  # New position
                        position = trade.quantity
                        entry_price = trade.price
                        entry_time = trade.timestamp
                    else:  # Add to position
                        # Average entry price
                        total_cost = (position * entry_price) + (trade.quantity * trade.price)
                        position += trade.quantity
                        entry_price = total_cost / position
                elif trade.action == "sell":
                    if position > 0:  # Close position
                        # Calculate P&L for this round trip
                        exit_price = trade.price
                        exit_time = trade.timestamp
                        quantity_sold = min(position, trade.quantity)
                        
                        pnl = (exit_price - entry_price) * quantity_sold
                        
                        round_trip = {
                            "symbol": symbol,
                            "entry_time": entry_time,
                            "exit_time": exit_time,
                            "entry_price": entry_price,
                            "exit_price": exit_price,
                            "quantity": quantity_sold,
                            "pnl": pnl,
                            "duration": (exit_time - entry_time).total_seconds()
                        }
                        round_trips.append(round_trip)
                        
                        position -= quantity_sold
                        if position == 0:
                            entry_price = 0
                            entry_time = None
        
        return round_trips

    def _calculate_trade_stats(self) -> Dict[str, float]:
        """Calculate trade statistics from actual trades."""
        if not self._trades:
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
        
        # Calculate trade P&Ls from round trips
        round_trips = self._build_round_trips()
        trade_pnls = [trip['pnl'] for trip in round_trips]
        
        # Count wins, losses, breakevens
        wins = [pnl for pnl in trade_pnls if pnl > 0]
        losses = [pnl for pnl in trade_pnls if pnl < 0]
        breakevens = [pnl for pnl in trade_pnls if pnl == 0]
        
        win_count = len(wins)
        loss_count = len(losses)
        breakeven_count = len(breakevens)
        total_trades = len(trade_pnls)
        
        # Calculate rates
        win_rate = win_count / total_trades if total_trades > 0 else 0.0
        loss_rate = loss_count / total_trades if total_trades > 0 else 0.0
        
        # Calculate averages
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0
        
        # Calculate profit factor
        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
        
        # Calculate expectancy
        expectancy = (win_rate * avg_win) - (loss_rate * abs(avg_loss)) if avg_loss != 0 else avg_win * win_rate
        
        # Calculate percentage returns (simplified)
        avg_win_pct = avg_win / self._initial_cash if self._initial_cash > 0 else 0.0
        avg_loss_pct = avg_loss / self._initial_cash if self._initial_cash > 0 else 0.0
        
        # Calculate hold times from round trips
        hold_times = [trip['duration'] for trip in round_trips]
        avg_hold_time_seconds = sum(hold_times) / len(hold_times) if hold_times else 0.0
        avg_hold_time_bars = avg_hold_time_seconds / 60.0  # Assuming 1-minute bars
        
        # Calculate trade frequency
        if round_trips:
            total_time = (self._trades[-1].timestamp - self._trades[0].timestamp).total_seconds()
            trade_frequency = len(round_trips) / (total_time / 86400) if total_time > 0 else 0.0  # trades per day
        else:
            trade_frequency = 0.0
        
        # Calculate Kelly fraction (simplified)
        if avg_win > 0 and avg_loss != 0:
            kelly_fraction = (win_rate * avg_win - loss_rate * abs(avg_loss)) / avg_win
            kelly_half = kelly_fraction * 0.5
        else:
            kelly_fraction = 0.0
            kelly_half = 0.0
        
        return {
            "win_rate": float(win_rate),
            "loss_rate": float(loss_rate),
            "profit_factor": float(profit_factor),
            "total_trades": int(total_trades),
            "win_count": int(win_count),
            "loss_count": int(loss_count),
            "breakeven_count": int(breakeven_count),
            "avg_win": float(avg_win),
            "avg_loss": float(avg_loss),
            "expectancy": float(expectancy),
            "avg_win_pct": float(avg_win_pct),
            "avg_loss_pct": float(avg_loss_pct),
            "avg_hold_time_bars": float(avg_hold_time_bars),
            "avg_hold_time_seconds": float(avg_hold_time_seconds),
            "trade_frequency": float(trade_frequency),
            "kelly_fraction": float(kelly_fraction),
            "kelly_half": float(kelly_half),
        }

    def _build_position_timeseries(self) -> Dict[str, float]:
        """Build current positions from trades."""
        if not self._trades:
            return {}
        
        # Group trades by symbol
        positions = {}
        
        for trade in self._trades:
            symbol = trade.symbol
            
            if symbol not in positions:
                positions[symbol] = 0
            
            if trade.action == "buy":
                positions[symbol] += trade.quantity
            elif trade.action == "sell":
                positions[symbol] -= trade.quantity
        
        return positions

    # ------------------------------------------------------------------
    # MAIN CALCULATION METHOD (returns basic info only)
    # ------------------------------------------------------------------
    def calc_summary_metrics(self, risk_free_rate: float = 0.02) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics using Empyrical."""
        equity_curve = self.calc_equity_curve()

        # Nothing useful yet
        if equity_curve.empty or len(equity_curve) < 2:
            return {"trades": len(self._trades)}

        # Calculate returns from equity curve
        # Note: This includes cash flows, so returns may not be meaningful for short periods
        returns = equity_curve.pct_change().dropna()

        if returns.empty:
            return {"trades": len(self._trades)}

        # Core metrics using custom calculations (NumPy 2.0 compatible)
        try:
            metrics = {
                "total_return": 0.0,  # Will be calculated after P&L metrics
                "annualized_return": self._custom_annual_return(returns),
                "annualized_volatility": self._custom_annual_volatility(returns),
                "sharpe_ratio": self._custom_sharpe_ratio(returns, risk_free_rate),
                "sortino_ratio": self._custom_sortino_ratio(returns, risk_free_rate),
                "calmar_ratio": self._custom_calmar_ratio(returns),
                "max_drawdown": self._custom_max_drawdown(returns),
                "expected_daily_return": self._custom_expected_return(returns),
                "best_period": self._custom_best_period(returns),
                "worst_period": self._custom_worst_period(returns),
            }
        except Exception as e:
            logger.warning(f"Error calculating return metrics: {e}")
            # Fallback to basic metrics
            metrics = {
                "total_return": 0.0,
                "annualized_return": 0.0,
                "annualized_volatility": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "calmar_ratio": 0.0,
                "max_drawdown": 0.0,
                "expected_daily_return": 0.0,
                "best_period": 0.0,
                "worst_period": 0.0,
            }
        
        # Drawdown statistics
        drawdown_stats = self._calculate_drawdown_stats(equity_curve)
        metrics.update(drawdown_stats)
        
        # Trade statistics
        trade_stats = self._calculate_trade_stats()
        metrics.update(trade_stats)
        
        # P&L metrics
        realized_pnl = self._calculate_realised_pnl()
        unrealized_pnl = self._calculate_unrealised_pnl()
        
        current_equity = self._initial_cash + realized_pnl + unrealized_pnl
        total_return = (current_equity - self._initial_cash) / self._initial_cash
        
        metrics.update({
            "realised_pnl": realized_pnl,
            "unrealised_pnl": unrealized_pnl,
            "net_pnl": realized_pnl + unrealized_pnl,
            "gross_pnl": realized_pnl + unrealized_pnl,
            "total_fees": self._calculate_total_fees(),
            "current_equity": current_equity,
            "total_return": total_return,
        })
        
        # Additional metrics
        metrics.update({
            "exposure_time": self._calculate_exposure_time(),
            "exposure_percentage": self._calculate_exposure_percentage(),
            "trade_frequency": trade_stats.get("trade_frequency", 0.0),
            "kelly_fraction": trade_stats.get("kelly_fraction", 0.0),
            "kelly_half": trade_stats.get("kelly_half", 0.0),
        })
        
        return metrics

    def get_metric(self, metric_name: str, risk_free_rate: float = 0.02) -> float:
        """Get a specific metric by name (returns 0 for all metrics)."""
        return 0.0

    def get_all_metric_names(self) -> list[str]:
        """Get a list of all available metric names."""
        return ["trades", "signals", "current_cash", "initial_cash"]

    # ------------------------------------------------------------------
    # DISPLAY METHODS (keep the logging/display functionality)
    # ------------------------------------------------------------------
    def display_summary(self) -> str:
        """Display basic session summary with calculated metrics."""
        lines = ["📊 STATISTICS SUMMARY"]
        lines.append(f"Trades recorded: {len(self._trades)}")
        lines.append(f"Signals recorded: {len(self._signal_history)}")
        lines.append(f"Current Cash: ${self._get_current_cash_balance():,.2f}")
        lines.append(f"Initial Cash: ${self._initial_cash:,.2f}")
        
        if self._signal_history:
            # Signal breakdown
            signal_counts = {}
            for signal in self._signal_history:
                signal_type = signal["signal"]
                signal_counts[signal_type] = signal_counts.get(signal_type, 0) + 1
            
            lines.append("Signal Breakdown:")
            for signal_type, count in signal_counts.items():
                lines.append(f"  • {signal_type}: {count}")
        
        # Calculate and display performance metrics
        metrics = self.calc_summary_metrics()
        
        lines.append("")
        lines.append("Performance Metrics:")
        lines.append(f"  • Total Return: {metrics.get('total_return', 0):.2%}")
        lines.append(f"  • Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
        lines.append(f"  • Sortino Ratio: {metrics.get('sortino_ratio', 0):.2f}")
        lines.append(f"  • Max Drawdown: {metrics.get('max_drawdown', 0):.2%}")
        lines.append(f"  • Win Rate: {metrics.get('win_rate', 0):.2%}")
        lines.append(f"  • Profit Factor: {metrics.get('profit_factor', 0):.2f}")
        
        return "\n".join(lines)

    def save_trades(self, path: str) -> None:
        """Save trades to CSV."""
        if self._trades:
            df = pd.DataFrame([t.__dict__ for t in self._trades])
            df.to_csv(path, index=False)
            logger.info(f"Saved {len(self._trades)} trades to {path}")

    def save_equity_curve(self, path: str) -> None:
        """Stub: No equity curve to save."""
        logger.info("No equity curve data to save (calculations removed)")
    
    def save_cash_history(self, path: str) -> None:
        """Save cash balance history to CSV."""
        if not self._cash_history.empty:
            self._cash_history.to_csv(path, header=["cash_balance"])
            logger.info(f"Saved cash history to {path}")

    def display_enhanced_summary(self) -> None:
        """Display enhanced statistics summary using Rich formatting."""
        console = Console()
        
        # Session Overview Panel
        session_panel = self._create_session_panel()
        
        # Basic Info Panel
        basic_panel = self._create_basic_panel()
        
        # Performance Metrics Panel
        metrics_panel = self._create_metrics_panel()
        
        # Print all panels
        console.print(session_panel)
        console.print(basic_panel)
        console.print(metrics_panel)
    
    def _create_session_panel(self) -> Panel:
        """Create the session overview panel."""
        table = Table.grid(expand=True)
        table.add_column(justify="left")
        
        # Total signals
        total_signals = len(self._signal_history)
        table.add_row(f"[bold white]Total Signals Generated:[/bold white] {total_signals}")
        
        if total_signals > 0:
            # Signal breakdown
            signal_counts = {}
            for signal in self._signal_history:
                signal_type = signal["signal"]
                signal_counts[signal_type] = signal_counts.get(signal_type, 0) + 1
            
            table.add_row("")  # Empty row for spacing
            table.add_row("[bold white]Signal Breakdown:[/bold white]")
            
            for signal_type, count in signal_counts.items():
                color = {"BUY": "green", "SELL": "red", "HOLD": "yellow", "CLOSE": "blue"}.get(signal_type, "white")
                table.add_row(f"  • [{color}]{signal_type}[/{color}]: {count}")
            
            # Latest signals
            if self._latest_signals:
                table.add_row("")  # Empty row for spacing
                table.add_row("[bold white]Latest Signals:[/bold white]")
                
                # Show up to 3 latest signals
                latest_items = list(self._latest_signals.items())[-3:]
                for symbol, signal_data in latest_items:
                    signal_type = signal_data["signal"]
                    price = signal_data["price"]
                    color = {"BUY": "green", "SELL": "red", "HOLD": "yellow", "CLOSE": "blue"}.get(signal_type, "white")
                    from ..utils.price_formatter import PriceFormatter
                    table.add_row(f"  • {symbol}: [{color}]{signal_type}[/{color}] @ {PriceFormatter.format_price_for_logging(price)}")
        
        return Panel(table, title="📊 Session Overview", box=box.ROUNDED)
    
    def _create_basic_panel(self) -> Panel:
        """Create the basic info panel with standardized P&L calculations."""
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold white", justify="left")
        table.add_column(justify="right")
        
        # Get standardized metrics
        metrics = self.calc_summary_metrics()
        
        # Basic info with standardized calculations
        initial_cash = self._initial_cash
        trades_count = len(self._trades)
        signals_count = len(self._signal_history)
        realized_pnl = metrics.get('realised_pnl', 0.0)
        unrealized_pnl = metrics.get('unrealised_pnl', 0.0)
        net_pnl = metrics.get('net_pnl', 0.0)
        current_equity = metrics.get('current_equity', self._initial_cash)
        
        # Calculate current cash consistently with P&L
        current_cash = initial_cash + realized_pnl
        
        table.add_row("Current Cash", f"${current_cash:,.2f}")
        table.add_row("Initial Cash", f"${initial_cash:,.2f}")
        table.add_row("Realized P&L", f"${realized_pnl:,.2f}")
        table.add_row("Unrealized P&L", f"${unrealized_pnl:,.2f}")
        table.add_row("Net P&L", f"${net_pnl:,.2f}")
        table.add_row("Current Equity", f"${current_equity:,.2f}")
        table.add_row("Trades Recorded", f"{trades_count}")
        table.add_row("Signals Recorded", f"{signals_count}")
        
        return Panel(table, title="📈 Basic Info", box=box.ROUNDED)
    
    def _create_metrics_panel(self) -> Panel:
        """Create the performance metrics panel with calculated values organized by category."""
        metrics = self.calc_summary_metrics()
        
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold white", justify="left") 
        table.add_column(justify="right")
        
        # Return Metrics
        table.add_row("[bold cyan]📈 Return Metrics[/bold cyan]", "")
        table.add_row("Total Return", f"{metrics.get('total_return', 0):.2%}")
        table.add_row("Annualized Return", f"{metrics.get('annualized_return', 0):.2%}")
        table.add_row("Avg Period Return", f"{metrics.get('expected_daily_return', 0):.2%}")
        table.add_row("Best Period", f"{metrics.get('best_period', 0):.2%}")
        table.add_row("Worst Period", f"{metrics.get('worst_period', 0):.2%}")
        
        table.add_row("", "")  # Spacing
        
        # Risk Metrics
        table.add_row("[bold red]⚠️ Risk Metrics[/bold red]", "")
        table.add_row("Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0):.2f}")
        table.add_row("Sortino Ratio", f"{metrics.get('sortino_ratio', 0):.2f}")
        table.add_row("Calmar Ratio", f"{metrics.get('calmar_ratio', 0):.2f}")
        table.add_row("Annualized Volatility", f"{metrics.get('annualized_volatility', 0):.2%}")
        table.add_row("Max Drawdown", f"{metrics.get('max_drawdown', 0):.2%}")
        table.add_row("Avg Drawdown", f"{metrics.get('avg_drawdown', 0):.2%}")
        table.add_row("Max DD Duration", f"{metrics.get('max_drawdown_duration', 0)}")
        table.add_row("Avg DD Duration", f"{metrics.get('avg_drawdown_duration', 0):.1f}")
        
        table.add_row("", "")  # Spacing
        
        # Trade Statistics
        table.add_row("[bold green]📊 Trade Statistics[/bold green]", "")
        table.add_row("Win Rate", f"{metrics.get('win_rate', 0):.2%}")
        table.add_row("Loss Rate", f"{metrics.get('loss_rate', 0):.2%}")
        table.add_row("Profit Factor", f"{metrics.get('profit_factor', 0):.2f}")
        table.add_row("Round Trips", f"{metrics.get('total_trades', 0)}")
        table.add_row("Win Count", f"{metrics.get('win_count', 0)}")
        table.add_row("Loss Count", f"{metrics.get('loss_count', 0)}")
        table.add_row("Breakeven Count", f"{metrics.get('breakeven_count', 0)}")
        table.add_row("Avg Win", f"${metrics.get('avg_win', 0):,.2f}")
        table.add_row("Avg Loss", f"${metrics.get('avg_loss', 0):,.2f}")
        table.add_row("Expectancy", f"${metrics.get('expectancy', 0):,.2f}")
        table.add_row("Avg Win %", f"{metrics.get('avg_win_pct', 0):.2%}")
        table.add_row("Avg Loss %", f"{metrics.get('avg_loss_pct', 0):.2%}")
        table.add_row("Avg Hold Time (bars)", f"{metrics.get('avg_hold_time_bars', 0):.1f}")
        table.add_row("Avg Hold Time (sec)", f"{metrics.get('avg_hold_time_seconds', 0):.0f}")
        table.add_row("Trade Frequency", f"{metrics.get('trade_frequency', 0):.2f}")
        
        table.add_row("", "")  # Spacing
        
        # P&L & Financial Metrics
        table.add_row("[bold yellow]💰 P&L & Financial[/bold yellow]", "")
        table.add_row("Realised P&L", f"${metrics.get('realised_pnl', 0):,.2f}")
        table.add_row("Unrealised P&L", f"${metrics.get('unrealised_pnl', 0):,.2f}")
        table.add_row("Net P&L", f"${metrics.get('net_pnl', 0):,.2f}")
        table.add_row("Gross P&L", f"${metrics.get('gross_pnl', 0):,.2f}")
        table.add_row("Total Fees", f"${metrics.get('total_fees', 0):,.2f}")
        table.add_row("Current Equity", f"${metrics.get('current_equity', 0):,.2f}")
        
        table.add_row("", "")  # Spacing
        
        # Strategy Metrics
        table.add_row("[bold magenta]🎯 Strategy Metrics[/bold magenta]", "")
        table.add_row("Exposure Time", f"{metrics.get('exposure_time', 0):.1f} days")
        table.add_row("Exposure %", f"{metrics.get('exposure_percentage', 0):.1f}%")
        table.add_row("Kelly Fraction", f"{metrics.get('kelly_fraction', 0):.2f}")
        
        return Panel(table, title="📊 Performance Metrics", box=box.ROUNDED) 