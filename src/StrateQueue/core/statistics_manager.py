from __future__ import annotations

"""Centralised statistics tracking for StrateQueue

This module collects *raw* facts about what happened (prices & trades)
and offers on-demand portfolio analytics (PnL, Sharpe, etc.).  Nothing
is calculated at ingestion time – we always recompute from the raw data
so that metrics stay consistent whenever new observations arrive.

High-level design
=================
1.  Every executed (or hypothetical) fill becomes a TradeRecord.
2.  `update_market_prices` appends the latest close/mark for each symbol
    and is called once per bar.
3.  Analytics functions (`calc_equity_curve`, `calc_summary_metrics`, …)
    build metrics on the fly from the current raw series.

The class is *engine- & broker-agnostic*: keep the interface minimal so
all callers (Zipline extractor, Alpaca broker, multi-strategy runner …)
can use the **same** object.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging

import pandas as pd
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


@dataclass
class RoundTrip:
    """Represents a complete round-trip trade (entry and exit)."""
    
    symbol: str
    entry_timestamp: pd.Timestamp
    exit_timestamp: pd.Timestamp
    entry_price: float
    exit_price: float
    quantity: float
    entry_commission: float
    exit_commission: float
    gross_pnl: float  # P&L before commissions
    net_pnl: float    # P&L after commissions
    
    @property
    def is_winner(self) -> bool:
        """True if this round-trip was profitable (net P&L > 0)."""
        return self.net_pnl > 0
    
    @property
    def hold_duration(self) -> pd.Timedelta:
        """Duration this position was held."""
        return self.exit_timestamp - self.entry_timestamp


class StatisticsManager:
    """Collects price marks & trades and produces portfolio statistics."""

    def __init__(self, initial_cash: float = 100000.0):
        # Raw storage ----------------------------------------------------
        self._trades: List[TradeRecord] = []
        self._price_history: Dict[str, pd.Series] = {}
        
        # Cash tracking --------------------------------------------------
        self._initial_cash = float(initial_cash)
        self._cash_history: pd.Series = pd.Series(dtype=float)  # timestamp -> cash_balance
        
        # Signal tracking ------------------------------------------------
        self._signal_history: List[Dict[str, Any]] = []
        self._latest_signals: Dict[str, Dict[str, Any]] = {}  # symbol -> {signal, price, timestamp}
        
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
            cash_change = trade_value - trade.commission - trade.fees  # Cash increases (net of costs)
        
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
        
        if signal.signal in {SignalType.HOLD, SignalType.CLOSE}:
            return  # nothing to do for trade recording

        qty = signal.quantity or 0.0
        if qty == 0.0:
            # If the strategy did not specify a quantity we assume *notional*
            # trade of size 1 so that directionality is still recorded.
            qty = 1.0

        self.record_trade(
            timestamp=signal.timestamp,
            strategy_id=getattr(signal, "strategy_id", None),
            symbol=symbol,
            action="buy" if signal.signal == SignalType.BUY else "sell",
            quantity=qty,
            price=signal.price,
            commission=0.0,
        )

    # ------------------------------------------------------------------
    def update_market_prices(
        self, latest_prices: Dict[str, float], timestamp: "pd.Timestamp | None" = None
    ) -> None:
        """Append the latest *close* (or mark price) for each symbol."""
        ts_raw = pd.Timestamp.now(tz="UTC") if timestamp is None else pd.Timestamp(timestamp)
        ts = ts_raw if ts_raw.tzinfo is not None else ts_raw.tz_localize("UTC")
        for symbol, price in latest_prices.items():
            series = self._price_history.get(symbol)
            if series is None:
                series = pd.Series(dtype=float)
            series.loc[ts] = float(price)
            self._price_history[symbol] = series

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
    # ANALYTICS
    # ------------------------------------------------------------------
    def _build_position_timeseries(self) -> pd.DataFrame:
        """Return a DataFrame of cumulative position per symbol over time."""
        if not self._trades:
            return pd.DataFrame()

        # Build a DataFrame of signed quantities per trade
        rows = []
        for tr in self._trades:
            sign = 1 if tr.action == "buy" else -1
            rows.append({
                "timestamp": tr.timestamp,
                "symbol": tr.symbol,
                "delta_qty": sign * tr.quantity,
            })
        df = pd.DataFrame(rows).set_index("timestamp")
        # Pivot into symbol columns & cumulative sum
        pos = (
            df.pivot_table(values="delta_qty", index=df.index, columns="symbol", aggfunc="sum")
            .sort_index()
            .cumsum()
        )
        return pos

    # ------------------------------------------------------------------
    def calc_equity_curve(self) -> pd.Series:
        """Compute portfolio equity over time (cash + position values)."""
        # Always start with cash, even if no positions yet
        cash_series = self._cash_history.copy()
        
        # If no price history, equity is just cash
        if not self._price_history:
            return cash_series

        # Combine price series into DataFrame with forward-fill
        price_df = (
            pd.concat(self._price_history, axis=1)
            .sort_index()
            .ffill()
        )

        positions = self._build_position_timeseries()
        
        # Create a comprehensive time index from all sources
        all_indices = [cash_series.index]
        if not positions.empty:
            all_indices.append(positions.index)
        if not price_df.empty:
            all_indices.append(price_df.index)
        
        common_index = pd.Index([])
        for idx in all_indices:
            common_index = common_index.union(idx)
        common_index = common_index.sort_values()
        
        # Align all series on the same index
        cash_series = cash_series.reindex(common_index).ffill()
        
        if positions.empty:
            # No positions, equity = cash only
            return cash_series
        
        # Align price and position data
        price_df = price_df.reindex(common_index).ffill()
        positions = positions.reindex(common_index).ffill().fillna(0.0)
        
        # Calculate position values
        position_values = (positions * price_df).sum(axis=1)
        
        # Total equity = cash + position values
        equity_curve = cash_series + position_values.fillna(0.0)
        
        return equity_curve

    # ------------------------------------------------------------------
    def _calculate_realised_pnl(self) -> float:
        """Calculate realized P&L using FIFO cost basis accounting."""
        realised = 0.0
        inventory: Dict[str, List[tuple[float, float, float]]] = {}  # (cost_price, quantity, commission_per_share) tuples

        for tr in self._trades:
            inv = inventory.setdefault(tr.symbol, [])
            
            if tr.action == "buy":
                # Include commission in cost basis (industry standard)
                commission_per_share = (tr.commission + tr.fees) / tr.quantity if tr.quantity > 0 else 0
                effective_cost_per_share = tr.price + commission_per_share
                inv.append((effective_cost_per_share, tr.quantity, commission_per_share))
            else:  # sell
                qty_to_sell = tr.quantity
                sell_commission = tr.commission + tr.fees
                gross_proceeds = tr.price * tr.quantity
                net_proceeds = gross_proceeds - sell_commission
                
                # FIFO: match against oldest lots first
                total_cost_basis = 0.0
                while qty_to_sell > 0 and inv:
                    cost_per_share, available_qty, _ = inv[0]
                    
                    if available_qty <= qty_to_sell:
                        # Use entire lot
                        qty_used = available_qty
                        inv.pop(0)  # Remove this lot entirely
                    else:
                        # Partial lot usage
                        qty_used = qty_to_sell
                        inv[0] = (cost_per_share, available_qty - qty_used, inv[0][2])  # Update remaining quantity
                    
                    # Add to total cost basis for this sale
                    total_cost_basis += cost_per_share * qty_used
                    qty_to_sell -= qty_used
                
                # Calculate P&L: net proceeds - total cost basis
                trade_pnl = net_proceeds - total_cost_basis
                realised += trade_pnl
                
        return realised

    # ------------------------------------------------------------------
    def _calculate_unrealised_pnl(self) -> float:
        """Calculate unrealized P&L from current positions."""
        if not self._price_history:
            return 0.0
            
        # Get current positions
        positions = self._build_position_timeseries()
        if positions.empty:
            return 0.0
            
        # Get latest prices
        latest_prices = {}
        for symbol, price_series in self._price_history.items():
            if not price_series.empty:
                latest_prices[symbol] = price_series.iloc[-1]
        
        if not latest_prices:
            return 0.0
            
        # Calculate cost basis for current positions using FIFO (same logic as realized P&L)
        inventory: Dict[str, List[tuple[float, float, float]]] = {}  # (cost_price, quantity, commission_per_share) tuples
        
        # Replay trades to build current cost basis
        for tr in self._trades:
            inv = inventory.setdefault(tr.symbol, [])
            
            if tr.action == "buy":
                # Include commission in cost basis (same as realized P&L)
                commission_per_share = (tr.commission + tr.fees) / tr.quantity if tr.quantity > 0 else 0
                effective_cost_per_share = tr.price + commission_per_share
                inv.append((effective_cost_per_share, tr.quantity, commission_per_share))
            else:  # sell
                qty_to_sell = tr.quantity
                while qty_to_sell > 0 and inv:
                    cost_per_share, available_qty, commission_per_share = inv[0]
                    if available_qty <= qty_to_sell:
                        qty_used = available_qty
                        inv.pop(0)
                    else:
                        qty_used = qty_to_sell
                        inv[0] = (cost_per_share, available_qty - qty_used, commission_per_share)
                    qty_to_sell -= qty_used
        
        # Calculate unrealized P&L for remaining positions
        unrealised = 0.0
        for symbol, inv in inventory.items():
            if symbol in latest_prices:
                current_price = latest_prices[symbol]
                for cost_per_share, quantity, _ in inv:
                    # Unrealized P&L = (current_price - commission_inclusive_cost) * quantity
                    unrealised += (current_price - cost_per_share) * quantity
        
        return unrealised

    # ------------------------------------------------------------------
    def _calculate_total_fees(self) -> float:
        """Calculate total fees and commissions paid across all trades."""
        total_fees = 0.0
        for trade in self._trades:
            total_fees += trade.commission + trade.fees
        return total_fees

    # ------------------------------------------------------------------
    def _calculate_annualization_factor(self, returns_series: pd.Series) -> float:
        """Calculate annualization factor based on the frequency of returns."""
        if len(returns_series) < 2:
            return 252  # Default to daily
            
        # Calculate median time difference between observations
        time_diffs = returns_series.index.to_series().diff().dropna()
        if time_diffs.empty:
            return 252
            
        median_diff = time_diffs.median()
        
        # Convert to seconds
        if hasattr(median_diff, 'total_seconds'):
            seconds = median_diff.total_seconds()
        else:
            seconds = median_diff / pd.Timedelta(seconds=1)
        
        # Calculate periods per year
        if seconds <= 0:
            return 252
            
        periods_per_day = 86400 / seconds  # seconds in a day
        periods_per_year = periods_per_day * 365
        
        # Cap at reasonable bounds
        return min(max(periods_per_year, 1), 365 * 24 * 60)  # Between yearly and per-minute

    # ------------------------------------------------------------------
    def _calculate_exposure_time(self) -> float:
        """Calculate exposure time as percentage of bars with open positions."""
        positions = self._build_position_timeseries()
        if positions.empty:
            return 0.0
        
        # Check which bars have any open positions
        position_totals = positions.abs().sum(axis=1)
        bars_with_positions = (position_totals > 0).sum()
        total_bars = len(position_totals)
        
        return bars_with_positions / total_bars if total_bars > 0 else 0.0

    # ------------------------------------------------------------------
    def _calculate_equity_peak(self, curve: pd.Series) -> float:
        """Calculate peak equity value."""
        if curve.empty:
            return self._initial_cash
        return curve.cummax().iloc[-1]

    # ------------------------------------------------------------------
    def _calculate_annualized_return(self, curve: pd.Series, annualization_factor: float) -> float:
        """Calculate annualized return (CAGR)."""
        if curve.empty or len(curve) < 2:
            return 0.0
        
        total_return = curve.iloc[-1] / curve.iloc[0] - 1
        periods = len(curve)
        
        if periods == 0 or annualization_factor == 0:
            return total_return
            
        # Convert to annualized: (1 + total_return)^(periods_per_year / periods) - 1
        years = periods / annualization_factor
        if years > 0:
            return (1 + total_return) ** (1 / years) - 1
        return total_return

    # ------------------------------------------------------------------
    def _calculate_annualized_volatility(self, rets: pd.Series, annualization_factor: float) -> float:
        """Calculate annualized volatility."""
        if rets.empty or rets.std() == 0:
            return 0.0
        return rets.std() * np.sqrt(annualization_factor)

    # ------------------------------------------------------------------
    def _calculate_sortino_ratio(self, rets: pd.Series, annualization_factor: float, risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio (like Sharpe but using downside deviation)."""
        if rets.empty or len(rets) < 2:
            return 0.0
            
        # Convert annual risk-free rate to per-period rate
        rf_per_period = risk_free_rate / annualization_factor
        excess_returns = rets - rf_per_period
        
        # Only consider negative returns for denominator
        downside_returns = excess_returns[excess_returns < 0]
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0
            
        return (excess_returns.mean() / downside_returns.std()) * np.sqrt(annualization_factor)

    # ------------------------------------------------------------------
    def _calculate_calmar_ratio(self, annualized_return: float, max_drawdown: float) -> float:
        """Calculate Calmar ratio (CAGR / abs(max drawdown))."""
        if abs(max_drawdown) == 0:
            return 0.0
        return annualized_return / abs(max_drawdown)

    # ------------------------------------------------------------------
    def _calculate_drawdown_stats(self, curve: pd.Series) -> Dict[str, float]:
        """Calculate detailed drawdown statistics."""
        if curve.empty or len(curve) < 2:
            return {
                "avg_drawdown": 0.0,
                "max_drawdown_duration": 0,
                "avg_drawdown_duration": 0.0
            }
        
        # Calculate drawdown series
        running_max = curve.cummax()
        drawdowns = curve / running_max - 1
        
        # Find drawdown periods (consecutive negative values)
        in_drawdown = drawdowns < 0
        
        # Find start and end of each drawdown period
        drawdown_periods = []
        start_idx = None
        
        for i, is_dd in enumerate(in_drawdown):
            if is_dd and start_idx is None:
                # Start of drawdown
                start_idx = i
            elif not is_dd and start_idx is not None:
                # End of drawdown
                dd_values = drawdowns.iloc[start_idx:i]
                duration = i - start_idx
                min_dd = dd_values.min()
                drawdown_periods.append({
                    'duration': duration,
                    'min_drawdown': min_dd
                })
                start_idx = None
        
        # Handle case where we end in a drawdown
        if start_idx is not None:
            dd_values = drawdowns.iloc[start_idx:]
            duration = len(dd_values)
            min_dd = dd_values.min()
            drawdown_periods.append({
                'duration': duration,
                'min_drawdown': min_dd
            })
        
        if not drawdown_periods:
            return {
                "avg_drawdown": 0.0,
                "max_drawdown_duration": 0,
                "avg_drawdown_duration": 0.0
            }
        
        # Calculate statistics
        durations = [dd['duration'] for dd in drawdown_periods]
        drawdown_magnitudes = [dd['min_drawdown'] for dd in drawdown_periods]
        
        return {
            "avg_drawdown": np.mean(drawdown_magnitudes),
            "max_drawdown_duration": max(durations),
            "avg_drawdown_duration": np.mean(durations)
        }

    # ------------------------------------------------------------------
    def _build_round_trips(self) -> List[RoundTrip]:
        """Build round-trip trades from the trade blotter using FIFO inventory accounting."""
        round_trips = []
        
        # Track inventory per symbol: list of (entry_price, quantity, entry_timestamp, entry_commission) tuples
        inventory: Dict[str, List[tuple[float, float, pd.Timestamp, float]]] = {}
        
        for trade in self._trades:
            symbol = trade.symbol
            inv = inventory.setdefault(symbol, [])
            
            if trade.action == "buy":
                # Add to inventory
                inv.append((trade.price, trade.quantity, trade.timestamp, trade.commission + trade.fees))
            else:  # sell
                qty_to_sell = trade.quantity
                total_exit_commission = trade.commission + trade.fees
                
                while qty_to_sell > 0 and inv:
                    entry_price, available_qty, entry_timestamp, entry_commission = inv[0]
                    
                    if available_qty <= qty_to_sell:
                        # Use entire lot
                        qty_used = available_qty
                        inv.pop(0)  # Remove this lot entirely
                    else:
                        # Partial lot usage
                        qty_used = qty_to_sell
                        inv[0] = (entry_price, available_qty - qty_used, entry_timestamp, entry_commission)
                    
                    # Calculate P&L for this round-trip
                    gross_pnl = (trade.price - entry_price) * qty_used
                    # Allocate commissions proportionally
                    entry_comm_allocated = entry_commission * (qty_used / (available_qty if available_qty > 0 else qty_used))
                    exit_comm_allocated = total_exit_commission * (qty_used / trade.quantity)
                    net_pnl = gross_pnl - entry_comm_allocated - exit_comm_allocated
                    
                    # Create round-trip record
                    round_trip = RoundTrip(
                        symbol=symbol,
                        entry_timestamp=entry_timestamp,
                        exit_timestamp=trade.timestamp,
                        entry_price=entry_price,
                        exit_price=trade.price,
                        quantity=qty_used,
                        entry_commission=entry_comm_allocated,
                        exit_commission=exit_comm_allocated,
                        gross_pnl=gross_pnl,
                        net_pnl=net_pnl
                    )
                    round_trips.append(round_trip)
                    
                    qty_to_sell -= qty_used
        
        return round_trips

    # ------------------------------------------------------------------
    def _calculate_trade_stats(self) -> Dict[str, float]:
        """Calculate trade-level statistics from round-trip trades."""
        round_trips = self._build_round_trips()
        
        if not round_trips:
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
        
        total_trades = len(round_trips)
        winners = [rt for rt in round_trips if rt.is_winner]
        losers = [rt for rt in round_trips if not rt.is_winner and rt.net_pnl < 0]
        breakevens = [rt for rt in round_trips if rt.net_pnl == 0]
        
        win_count = len(winners)
        loss_count = len(losers)
        
        # Calculate rates
        win_rate = win_count / total_trades if total_trades > 0 else 0.0
        loss_rate = loss_count / total_trades if total_trades > 0 else 0.0
        
        # Calculate profit factor: sum of wins / abs(sum of losses)
        total_wins = sum(rt.net_pnl for rt in winners)
        total_losses = sum(rt.net_pnl for rt in losers)  # This will be negative
        
        if total_losses == 0:
            profit_factor = float('inf') if total_wins > 0 else 0.0
        else:
            profit_factor = total_wins / abs(total_losses)
        
        # Calculate average dollar amounts
        avg_win = total_wins / win_count if win_count > 0 else 0.0
        avg_loss = total_losses / loss_count if loss_count > 0 else 0.0  # This will be negative
        
        # Calculate expectancy (average $ per trade)
        total_pnl = sum(rt.net_pnl for rt in round_trips)
        expectancy = total_pnl / total_trades if total_trades > 0 else 0.0
        
        # Calculate average percentage returns
        # For percentage calculations, we need the entry value (price * quantity)
        avg_win_pct = 0.0
        avg_loss_pct = 0.0
        
        if win_count > 0:
            win_pct_returns = []
            for rt in winners:
                entry_value = rt.entry_price * rt.quantity
                if entry_value > 0:
                    pct_return = rt.net_pnl / entry_value
                    win_pct_returns.append(pct_return)
            avg_win_pct = sum(win_pct_returns) / len(win_pct_returns) if win_pct_returns else 0.0
        
        if loss_count > 0:
            loss_pct_returns = []
            for rt in losers:
                entry_value = rt.entry_price * rt.quantity
                if entry_value > 0:
                    pct_return = rt.net_pnl / entry_value
                    loss_pct_returns.append(pct_return)
            avg_loss_pct = sum(loss_pct_returns) / len(loss_pct_returns) if loss_pct_returns else 0.0
        
        # Calculate hold time metrics
        total_hold_seconds = 0.0
        total_hold_bars = 0.0
        
        # Get equity curve to use its time index for bar counting
        equity_curve = self.calc_equity_curve()
        
        for rt in round_trips:
            # Wall-clock hold time (easy)
            total_hold_seconds += rt.hold_duration.total_seconds()
            
            # Bar count hold time (count index positions between entry and exit)
            if not equity_curve.empty:
                try:
                    # Find the index positions for entry and exit timestamps
                    entry_loc = equity_curve.index.get_indexer([rt.entry_timestamp], method='ffill')[0]
                    exit_loc = equity_curve.index.get_indexer([rt.exit_timestamp], method='ffill')[0]
                    
                    # Count bars between entry (inclusive) and exit (exclusive)
                    if entry_loc >= 0 and exit_loc >= 0:
                        bars_held = max(0, exit_loc - entry_loc)
                        total_hold_bars += bars_held
                except (IndexError, KeyError):
                    # If timestamps not found in index, skip this round trip for bar counting
                    pass
        
        avg_hold_time_seconds = total_hold_seconds / total_trades if total_trades > 0 else 0.0
        avg_hold_time_bars = total_hold_bars / total_trades if total_trades > 0 else 0.0
        
        # Calculate trade frequency (round-trips per year)
        trade_frequency = 0.0
        if not equity_curve.empty and total_trades > 0:
            # Calculate years traded from equity curve time span
            time_span = equity_curve.index[-1] - equity_curve.index[0]
            years_traded = time_span.total_seconds() / (365.25 * 24 * 3600)  # Account for leap years
            if years_traded > 0:
                trade_frequency = total_trades / years_traded
        
        # Calculate Kelly criterion (optimal fraction)
        kelly_fraction = 0.0
        kelly_half = 0.0
        if avg_loss != 0 and total_trades > 0:
            # Use discrete payoff formula: f* = (b*p - q) / b
            # where b = avg_win / |avg_loss|, p = win_rate, q = loss_rate
            b = avg_win / abs(avg_loss)  # payoff ratio
            p = win_rate  # already calculated above
            q = loss_rate  # already calculated above
            kelly_fraction = (b * p - q) / b if b > 0 else 0.0
            # Clamp between 0 and 1 (no leverage above full equity)
            kelly_fraction = min(max(kelly_fraction, 0.0), 1.0)
            kelly_half = 0.5 * kelly_fraction  # Conservative half-Kelly
        
        return {
            "win_rate": win_rate,
            "loss_rate": loss_rate,
            "profit_factor": profit_factor,
            "total_trades": total_trades,
            "win_count": win_count,
            "loss_count": loss_count,
            "breakeven_count": len(breakevens),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "expectancy": expectancy,
            "avg_win_pct": avg_win_pct,
            "avg_loss_pct": avg_loss_pct,
            "avg_hold_time_bars": avg_hold_time_bars,
            "avg_hold_time_seconds": avg_hold_time_seconds,
            "trade_frequency": trade_frequency,
            "kelly_fraction": kelly_fraction,
            "kelly_half": kelly_half,
        }

    # ------------------------------------------------------------------
    def calc_summary_metrics(self, risk_free_rate: float = 0.02) -> Dict[str, Any]:
        curve = self.calc_equity_curve()

        # Nothing useful yet
        if curve.empty or (curve != 0).sum() < 2:
            return {"trades": len(self._trades)}

        # Start measuring from the first non-zero equity
        curve = curve.loc[curve.ne(0).idxmax():]

        # Safety – avoid /0 and nan in small samples
        if len(curve) < 2:
            return {"trades": len(self._trades)}

        rets = curve.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
        total_ret = curve.iloc[-1] / curve.iloc[0] - 1
        max_dd = (curve / curve.cummax() - 1).min()
        
        # Calculate annualized Sharpe ratio (industry standard)
        sharpe = 0.0
        annualization_factor = 252  # Default
        if len(rets) > 1 and rets.std() > 0:
            annualization_factor = self._calculate_annualization_factor(rets)
            # Convert annual risk-free rate to per-period rate
            rf_per_period = risk_free_rate / annualization_factor
            # Calculate excess returns
            excess_returns = rets - rf_per_period
            # Annualized Sharpe ratio
            sharpe = (excess_returns.mean() / rets.std()) * np.sqrt(annualization_factor)

        realised_pnl = self._calculate_realised_pnl()
        unrealised_pnl = self._calculate_unrealised_pnl()
        total_fees = self._calculate_total_fees()
        
        # Calculate all the new easy metrics (equity-curve based)
        exposure_time = self._calculate_exposure_time()
        equity_peak = self._calculate_equity_peak(curve)
        annualized_return = self._calculate_annualized_return(curve, annualization_factor)
        annualized_volatility = self._calculate_annualized_volatility(rets, annualization_factor)
        sortino = self._calculate_sortino_ratio(rets, annualization_factor, risk_free_rate)
        calmar = self._calculate_calmar_ratio(annualized_return, max_dd)
        dd_stats = self._calculate_drawdown_stats(curve)
        
        # Calculate expected daily return
        expected_daily_return = rets.mean() if not rets.empty else 0.0
        
        # Calculate best/worst day
        best_day = rets.max() if not rets.empty else 0.0
        worst_day = rets.min() if not rets.empty else 0.0
        
        # Calculate trade-level statistics (round-trip based)
        trade_stats = self._calculate_trade_stats()
        
        return {
            "trades": len(self._trades),
            "total_return": total_ret,
            "max_drawdown": max_dd,
            "sharpe": sharpe,
            "realised_pnl": realised_pnl,
            "unrealised_pnl": unrealised_pnl,
            "net_pnl": realised_pnl + unrealised_pnl,
            "total_fees": total_fees,
            "gross_pnl": realised_pnl + unrealised_pnl + total_fees,  # P&L before fees
            "current_cash": self._get_current_cash_balance(),
            "initial_cash": self._initial_cash,
            "current_equity": curve.iloc[-1] if not curve.empty else self._initial_cash,
            "annualization_factor": annualization_factor,
            # New easy metrics (🟢 from the categorization)
            "exposure_time": exposure_time,
            "equity_peak": equity_peak,
            "annualized_return": annualized_return,
            "annualized_volatility": annualized_volatility,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "avg_drawdown": dd_stats["avg_drawdown"],
            "max_drawdown_duration": dd_stats["max_drawdown_duration"],
            "avg_drawdown_duration": dd_stats["avg_drawdown_duration"],
            "expected_daily_return": expected_daily_return,
            "best_day": best_day,
            "worst_day": worst_day,
            # New medium metrics (🟡 trade-level based)
            "win_rate": trade_stats["win_rate"],
            "loss_rate": trade_stats["loss_rate"],
            "profit_factor": trade_stats["profit_factor"],
            "round_trips": trade_stats["total_trades"],
            "win_count": trade_stats["win_count"],
            "loss_count": trade_stats["loss_count"],
            "breakeven_count": trade_stats["breakeven_count"],
            "avg_win": trade_stats["avg_win"],
            "avg_loss": trade_stats["avg_loss"],
            "expectancy": trade_stats["expectancy"],
            "avg_win_pct": trade_stats["avg_win_pct"],
            "avg_loss_pct": trade_stats["avg_loss_pct"],
            "avg_hold_time_bars": trade_stats["avg_hold_time_bars"],
            "avg_hold_time_seconds": trade_stats["avg_hold_time_seconds"],
            "trade_frequency": trade_stats["trade_frequency"],
            "kelly_fraction": trade_stats["kelly_fraction"],
            "kelly_half": trade_stats["kelly_half"],
        }

    # ------------------------------------------------------------------
    def get_metric(self, metric_name: str, risk_free_rate: float = 0.02) -> float:
        """Get a specific metric by name.
        
        Args:
            metric_name: Name of the metric to retrieve
            risk_free_rate: Risk-free rate for Sharpe/Sortino calculations
            
        Returns:
            The metric value, or 0.0 if not available
            
        Available metrics:
            - trades, total_return, max_drawdown, sharpe, realised_pnl, unrealised_pnl,
              net_pnl, total_fees, gross_pnl, current_cash, initial_cash, current_equity,
              annualization_factor
            - Easy metrics: exposure_time, equity_peak, annualized_return, 
              annualized_volatility, sortino_ratio, calmar_ratio, avg_drawdown,
              max_drawdown_duration, avg_drawdown_duration, expected_daily_return,
              best_day, worst_day
            - Trade-level metrics: win_rate, loss_rate, profit_factor, round_trips,
              win_count, loss_count, breakeven_count, avg_win, avg_loss, expectancy,
              avg_win_pct, avg_loss_pct, avg_hold_time_bars, avg_hold_time_seconds,
              trade_frequency, kelly_fraction, kelly_half
        """
        metrics = self.calc_summary_metrics(risk_free_rate)
        return metrics.get(metric_name, 0.0)

    # ------------------------------------------------------------------
    def get_all_metric_names(self) -> list[str]:
        """Get a list of all available metric names."""
        metrics = self.calc_summary_metrics()
        return list(metrics.keys())

    # ------------------------------------------------------------------
    def display_summary(self) -> str:
        m = self.calc_summary_metrics()
        lines = ["📊 STATISTICS SUMMARY"]
        if not m or len(m) == 1:
            lines.append("No data collected yet.")
        else:
            lines.append(f"Trades            : {m['trades']}")
            lines.append(f"Current Equity    : ${m.get('current_equity', 0):,.2f}")
            lines.append(f"Current Cash      : ${m.get('current_cash', 0):,.2f}")
            lines.append(f"Initial Cash      : ${m.get('initial_cash', 0):,.2f}")
            lines.append(f"Equity Peak       : ${m.get('equity_peak', 0):,.2f}")
            
            if "total_return" in m:
                lines.append(f"Total Return      : {m['total_return']*100:6.2f}%")
                lines.append(f"Annualized Return : {m.get('annualized_return',0)*100:6.2f}%")
                lines.append(f"Annualized Vol    : {m.get('annualized_volatility',0)*100:6.2f}%")
                lines.append(f"Max Draw-down     : {m['max_drawdown']*100:6.2f}%")
                lines.append(f"Avg Draw-down     : {m.get('avg_drawdown',0)*100:6.2f}%")
                lines.append(f"Max DD Duration   : {m.get('max_drawdown_duration',0)} periods")
                lines.append(f"Exposure Time     : {m.get('exposure_time',0)*100:6.2f}%")
                lines.append(f"Sharpe Ratio      : {m['sharpe']:.3f}")
                lines.append(f"Sortino Ratio     : {m.get('sortino_ratio',0):.3f}")
                lines.append(f"Calmar Ratio      : {m.get('calmar_ratio',0):.3f}")
                lines.append(f"Best Day          : {m.get('best_day',0)*100:6.2f}%")
                lines.append(f"Worst Day         : {m.get('worst_day',0)*100:6.2f}%")
                
            # Trade-level statistics
            if m.get('round_trips', 0) > 0:
                lines.append(f"Round Trips       : {m.get('round_trips', 0)}")
                lines.append(f"Win Rate          : {m.get('win_rate',0)*100:6.2f}%")
                lines.append(f"Loss Rate         : {m.get('loss_rate',0)*100:6.2f}%")
                lines.append(f"Profit Factor     : {m.get('profit_factor',0):.3f}")
                lines.append(f"Winners/Losers    : {m.get('win_count',0)}/{m.get('loss_count',0)}")
                lines.append(f"Average $ Win     : ${m.get('avg_win',0):,.2f}")
                lines.append(f"Average $ Loss    : ${m.get('avg_loss',0):,.2f}")
                lines.append(f"Expectancy        : ${m.get('expectancy',0):,.2f}")
                lines.append(f"Average % Win     : {m.get('avg_win_pct',0)*100:6.2f}%")
                lines.append(f"Average % Loss    : {m.get('avg_loss_pct',0)*100:6.2f}%")
                lines.append(f"Avg Hold (bars)   : {m.get('avg_hold_time_bars',0):,.1f}")
                lines.append(f"Avg Hold (days)   : {m.get('avg_hold_time_seconds',0)/86400:,.1f}")
                lines.append(f"Trade Frequency   : {m.get('trade_frequency',0):,.1f} per year")
                lines.append(f"Kelly Fraction    : {m.get('kelly_fraction',0):6.2%}")
                lines.append(f"½-Kelly (safe)    : {m.get('kelly_half',0):6.2%}")
                
            lines.append(f"Realised P&L      : ${m.get('realised_pnl',0):,.2f}")
            lines.append(f"Unrealised P&L    : ${m.get('unrealised_pnl',0):,.2f}")
            lines.append(f"Net P&L           : ${m.get('net_pnl',0):,.2f}")
            lines.append(f"Total Fees        : ${m.get('total_fees',0):,.2f}")
            lines.append(f"Gross P&L         : ${m.get('gross_pnl',0):,.2f}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # PERSISTENCE HELPERS
    # ------------------------------------------------------------------
    def save_trades(self, path: str) -> None:
        df = pd.DataFrame([t.__dict__ for t in self._trades])
        df.to_csv(path, index=False)

    def save_equity_curve(self, path: str) -> None:
        curve = self.calc_equity_curve()
        if curve.empty:
            return
        curve.to_csv(path, header=["equity"])
    
    def save_cash_history(self, path: str) -> None:
        """Save cash balance history to CSV."""
        if self._cash_history.empty:
            return
        self._cash_history.to_csv(path, header=["cash_balance"])

    def display_enhanced_summary(self) -> None:
        """Display enhanced statistics summary using Rich formatting."""
        console = Console()
        
        # Get metrics
        m = self.calc_summary_metrics()
        
        if not m or len(m) == 1:
            console.print(Panel("No data collected yet.", title="📊 Statistics Summary"))
            return
        
        # Session Overview Panel
        session_panel = self._create_session_panel()
        
        # Portfolio Statistics Panel  
        portfolio_panel = self._create_portfolio_panel(m)
        
        # Trade Analytics Panel
        trade_panel = self._create_trade_panel(m)
        
        # Print all panels
        console.print(session_panel)
        console.print(portfolio_panel)
        console.print(trade_panel)
    
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
                    table.add_row(f"  • {symbol}: [{color}]{signal_type}[/{color}] @ ${price:,.2f}")
        
        return Panel(table, title="📊 Session Overview", box=box.ROUNDED)
    
    def _create_portfolio_panel(self, metrics: Dict[str, Any]) -> Panel:
        """Create the portfolio statistics panel."""
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold white", justify="left")
        table.add_column(justify="right")
        
        # Equity and cash info
        current_equity = metrics.get('current_equity', 0)
        current_cash = metrics.get('current_cash', 0)
        initial_cash = metrics.get('initial_cash', 0)
        equity_peak = metrics.get('equity_peak', 0)
        
        table.add_row("Current Equity", f"${current_equity:,.2f}")
        table.add_row("Current Cash", f"${current_cash:,.2f}")
        table.add_row("Initial Cash", f"${initial_cash:,.2f}")
        table.add_row("Equity Peak", f"${equity_peak:,.2f}")
        
        # Returns and risk metrics
        if "total_return" in metrics:
            total_return = metrics['total_return']
            annualized_return = metrics.get('annualized_return', 0)
            annualized_vol = metrics.get('annualized_volatility', 0)
            max_dd = metrics['max_drawdown']
            avg_dd = metrics.get('avg_drawdown', 0)
            exposure_time = metrics.get('exposure_time', 0)
            
            # Color coding for returns
            total_return_color = "green" if total_return >= 0 else "red"
            ann_return_color = "green" if annualized_return >= 0 else "red"
            
            table.add_row("", "")  # Spacing
            table.add_row("Total Return", f"[{total_return_color}]{total_return*100:6.2f}%[/{total_return_color}]")
            table.add_row("Annualized Return", f"[{ann_return_color}]{annualized_return*100:6.2f}%[/{ann_return_color}]")
            table.add_row("Annualized Vol", f"{annualized_vol*100:6.2f}%")
            table.add_row("Max Drawdown", f"[red]{max_dd*100:6.2f}%[/red]")
            table.add_row("Avg Drawdown", f"[red]{avg_dd*100:6.2f}%[/red]")
            table.add_row("Max DD Duration", f"{metrics.get('max_drawdown_duration', 0)} periods")
            table.add_row("Exposure Time", f"{exposure_time*100:6.2f}%")
            
            # Ratios
            sharpe = metrics['sharpe']
            sortino = metrics.get('sortino_ratio', 0)
            calmar = metrics.get('calmar_ratio', 0)
            
            table.add_row("", "")  # Spacing
            table.add_row("Sharpe Ratio", f"{sharpe:.3f}")
            table.add_row("Sortino Ratio", f"{sortino:.3f}")
            table.add_row("Calmar Ratio", f"{calmar:.3f}")
            
            # Best/worst day
            best_day = metrics.get('best_day', 0)
            worst_day = metrics.get('worst_day', 0)
            
            table.add_row("", "")  # Spacing
            table.add_row("Best Day", f"[green]{best_day*100:6.2f}%[/green]")
            table.add_row("Worst Day", f"[red]{worst_day*100:6.2f}%[/red]")
        
        return Panel(table, title="📈 Portfolio Statistics", box=box.ROUNDED)
    
    def _create_trade_panel(self, metrics: Dict[str, Any]) -> Panel:
        """Create the trade analytics panel."""
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold white", justify="left") 
        table.add_column(justify="right")
        
        # Basic trade info
        trades = metrics.get('trades', 0)
        table.add_row("Total Trades", f"{trades}")
        
        # Round trip analysis
        if metrics.get('round_trips', 0) > 0:
            round_trips = metrics.get('round_trips', 0)
            win_rate = metrics.get('win_rate', 0)
            loss_rate = metrics.get('loss_rate', 0)
            profit_factor = metrics.get('profit_factor', 0)
            win_count = metrics.get('win_count', 0)
            loss_count = metrics.get('loss_count', 0)
            
            table.add_row("Round Trips", f"{round_trips}")
            table.add_row("Win Rate", f"[green]{win_rate*100:6.2f}%[/green]")
            table.add_row("Loss Rate", f"[red]{loss_rate*100:6.2f}%[/red]")
            table.add_row("Profit Factor", f"{profit_factor:.3f}")
            table.add_row("Winners/Losers", f"[green]{win_count}[/green]/[red]{loss_count}[/red]")
            
            # Average trade metrics
            avg_win = metrics.get('avg_win', 0)
            avg_loss = metrics.get('avg_loss', 0)
            expectancy = metrics.get('expectancy', 0)
            avg_win_pct = metrics.get('avg_win_pct', 0)
            avg_loss_pct = metrics.get('avg_loss_pct', 0)
            
            table.add_row("", "")  # Spacing
            table.add_row("Average $ Win", f"[green]${avg_win:,.2f}[/green]")
            table.add_row("Average $ Loss", f"[red]${avg_loss:,.2f}[/red]")
            table.add_row("Expectancy", f"${expectancy:,.2f}")
            table.add_row("Average % Win", f"[green]{avg_win_pct*100:6.2f}%[/green]")
            table.add_row("Average % Loss", f"[red]{avg_loss_pct*100:6.2f}%[/red]")
            
            # Hold time and frequency
            avg_hold_bars = metrics.get('avg_hold_time_bars', 0)
            avg_hold_days = metrics.get('avg_hold_time_seconds', 0) / 86400
            trade_frequency = metrics.get('trade_frequency', 0)
            kelly_fraction = metrics.get('kelly_fraction', 0)
            kelly_half = metrics.get('kelly_half', 0)
            
            table.add_row("", "")  # Spacing
            table.add_row("Avg Hold (bars)", f"{avg_hold_bars:,.1f}")
            table.add_row("Avg Hold (days)", f"{avg_hold_days:,.1f}")
            table.add_row("Trade Frequency", f"{trade_frequency:,.1f} per year")
            table.add_row("Kelly Fraction", f"{kelly_fraction:6.2%}")
            table.add_row("½-Kelly (safe)", f"{kelly_half:6.2%}")
        
        # P&L breakdown
        realised_pnl = metrics.get('realised_pnl', 0)
        unrealised_pnl = metrics.get('unrealised_pnl', 0) 
        net_pnl = metrics.get('net_pnl', 0)
        total_fees = metrics.get('total_fees', 0)
        gross_pnl = metrics.get('gross_pnl', 0)
        
        table.add_row("", "")  # Spacing
        
        # Color code P&L
        realised_color = "green" if realised_pnl >= 0 else "red"
        unrealised_color = "green" if unrealised_pnl >= 0 else "red"
        net_color = "green" if net_pnl >= 0 else "red"
        gross_color = "green" if gross_pnl >= 0 else "red"
        
        table.add_row("Realised P&L", f"[{realised_color}]${realised_pnl:,.2f}[/{realised_color}]")
        table.add_row("Unrealised P&L", f"[{unrealised_color}]${unrealised_pnl:,.2f}[/{unrealised_color}]")
        table.add_row("Net P&L", f"[{net_color}]${net_pnl:,.2f}[/{net_color}]")
        table.add_row("Total Fees", f"${total_fees:,.2f}")
        table.add_row("Gross P&L", f"[{gross_color}]${gross_pnl:,.2f}[/{gross_color}]")
        
        return Panel(table, title="📊 Trade Analytics", box=box.ROUNDED) 