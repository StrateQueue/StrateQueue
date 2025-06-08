import React, { useEffect, useState } from 'react';
import { X, RefreshCw, TrendingUp, TrendingDown, DollarSign, Activity, BarChart3, Clock, Target, Zap } from 'lucide-react';

export default function StrategyStatsPanel({ id, onClose }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    let timer;
    const fetchStats = async () => {
      try {
        setLoading(true);
        const res = await fetch(`http://localhost:8400/strategies/${id}/statistics`);
        if (!res.ok) throw new Error('Failed to fetch statistics');
        
        const data = await res.json();
        setStats(data);
        setLastUpdated(new Date());
        setError(null);
      } catch (err) {
        console.error('Error fetching statistics:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    fetchStats(); // Initial fetch
    timer = setInterval(fetchStats, 1000); // Update every second
    
    return () => clearInterval(timer); // Cleanup on unmount
  }, [id]);

  if (loading && !stats) {
    return (
      <div className="p-4 border rounded-md bg-white shadow-md animate-pulse">
        <div className="flex justify-between items-center mb-4">
          <h2 className="font-semibold text-lg">Loading Statistics...</h2>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-gray-100">
            <X size={18} />
          </button>
        </div>
        <div className="h-40 flex items-center justify-center">
          <RefreshCw size={24} className="animate-spin text-blue-500" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 border rounded-md bg-white shadow-md">
        <div className="flex justify-between items-center mb-4">
          <h2 className="font-semibold text-lg text-red-600">Error</h2>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-gray-100">
            <X size={18} />
          </button>
        </div>
        <p className="text-red-500">{error}</p>
        <button 
          onClick={() => setLoading(true)} 
          className="mt-4 px-3 py-1 border rounded-md hover:bg-gray-50"
        >
          Retry
        </button>
      </div>
    );
  }

  const m = stats?.metrics || {};

  const formatPercent = (value) => `${(value * 100).toFixed(2)}%`;
  const formatCurrency = (value) => `$${value.toFixed(2)}`;
  const formatNumber = (value, decimals = 2) => value.toFixed(decimals);
  const formatDays = (seconds) => (seconds / 86400).toFixed(1);

  return (
    <div className="p-6 border rounded-lg bg-white shadow-lg max-w-7xl">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-3">
          <BarChart3 className="text-blue-600" size={24} />
          <h2 className="font-bold text-xl text-gray-900">Live Statistics Dashboard</h2>
          <span className="px-2 py-1 bg-green-100 text-green-800 text-xs font-medium rounded-full">
            LIVE
          </span>
        </div>
        <button onClick={onClose} className="p-2 rounded-full hover:bg-gray-100 transition-colors">
          <X size={20} />
        </button>
      </div>

      {lastUpdated && (
        <p className="text-xs text-gray-500 mb-4 flex items-center gap-1">
          <Clock size={12} />
          Last updated: {lastUpdated.toLocaleTimeString()}
        </p>
      )}

      {/* Key Performance Indicators */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-gradient-to-br from-green-50 to-green-100 border border-green-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <DollarSign className="text-green-600" size={20} />
            <span className="text-xs font-medium text-green-600">NET P&L</span>
          </div>
          <p className={`text-2xl font-bold ${m.net_pnl >= 0 ? 'text-green-700' : 'text-red-700'}`}>
            {formatCurrency(m.net_pnl || 0)}
          </p>
        </div>

        <div className="bg-gradient-to-br from-blue-50 to-blue-100 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <TrendingUp className="text-blue-600" size={20} />
            <span className="text-xs font-medium text-blue-600">TOTAL RETURN</span>
          </div>
          <p className={`text-2xl font-bold ${(m.total_return || 0) >= 0 ? 'text-green-700' : 'text-red-700'}`}>
            {formatPercent(m.total_return || 0)}
          </p>
        </div>

        <div className="bg-gradient-to-br from-purple-50 to-purple-100 border border-purple-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <Activity className="text-purple-600" size={20} />
            <span className="text-xs font-medium text-purple-600">SHARPE RATIO</span>
          </div>
          <p className="text-2xl font-bold text-purple-700">
            {formatNumber(m.sharpe || 0, 3)}
          </p>
        </div>

        <div className="bg-gradient-to-br from-orange-50 to-orange-100 border border-orange-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <Target className="text-orange-600" size={20} />
            <span className="text-xs font-medium text-orange-600">WIN RATE</span>
          </div>
          <p className="text-2xl font-bold text-orange-700">
            {formatPercent(m.win_rate || 0)}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Portfolio Overview */}
        <div className="bg-gray-50 rounded-lg p-4">
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <DollarSign size={16} className="text-gray-600" />
            Portfolio Overview
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Current Equity:</span>
              <span className="font-medium">{formatCurrency(m.current_equity || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Current Cash:</span>
              <span className="font-medium">{formatCurrency(m.current_cash || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Initial Cash:</span>
              <span className="font-medium">{formatCurrency(m.initial_cash || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Equity Peak:</span>
              <span className="font-medium">{formatCurrency(m.equity_peak || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Exposure Time:</span>
              <span className="font-medium">{formatPercent(m.exposure_time || 0)}</span>
            </div>
          </div>
        </div>

        {/* Performance Metrics */}
        <div className="bg-gray-50 rounded-lg p-4">
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <TrendingUp size={16} className="text-gray-600" />
            Returns & Risk
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Annualized Return:</span>
              <span className={`font-medium ${(m.annualized_return || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatPercent(m.annualized_return || 0)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Annualized Volatility:</span>
              <span className="font-medium">{formatPercent(m.annualized_volatility || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Max Drawdown:</span>
              <span className="font-medium text-red-600">{formatPercent(m.max_drawdown || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Avg Drawdown:</span>
              <span className="font-medium text-red-600">{formatPercent(m.avg_drawdown || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Max DD Duration:</span>
              <span className="font-medium">{m.max_drawdown_duration || 0} periods</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Sortino Ratio:</span>
              <span className="font-medium">{formatNumber(m.sortino_ratio || 0, 3)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Calmar Ratio:</span>
              <span className="font-medium">{formatNumber(m.calmar_ratio || 0, 3)}</span>
            </div>
          </div>
        </div>

        {/* Trade Analytics */}
        <div className="bg-gray-50 rounded-lg p-4">
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Activity size={16} className="text-gray-600" />
            Trade Analytics
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Total Trades:</span>
              <span className="font-medium">{m.trades || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Round Trips:</span>
              <span className="font-medium">{m.round_trips || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Win/Loss Count:</span>
              <span className="font-medium">
                <span className="text-green-600">{m.win_count || 0}</span>
                /
                <span className="text-red-600">{m.loss_count || 0}</span>
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Loss Rate:</span>
              <span className="font-medium text-red-600">{formatPercent(m.loss_rate || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Profit Factor:</span>
              <span className="font-medium">{formatNumber(m.profit_factor || 0, 2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Expectancy:</span>
              <span className={`font-medium ${(m.expectancy || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatCurrency(m.expectancy || 0)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Trade Frequency:</span>
              <span className="font-medium">{formatNumber(m.trade_frequency || 0, 1)}/year</span>
            </div>
          </div>
        </div>
      </div>

      {/* Detailed Metrics Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        {/* P&L Breakdown */}
        <div className="bg-gray-50 rounded-lg p-4">
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <DollarSign size={16} className="text-gray-600" />
            P&L Breakdown
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Realised P&L:</span>
              <span className={`font-medium ${(m.realised_pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatCurrency(m.realised_pnl || 0)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Unrealised P&L:</span>
              <span className={`font-medium ${(m.unrealised_pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatCurrency(m.unrealised_pnl || 0)}
              </span>
            </div>
            <div className="flex justify-between border-t pt-2">
              <span className="text-gray-900 font-medium">Net P&L:</span>
              <span className={`font-bold ${(m.net_pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatCurrency(m.net_pnl || 0)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Total Fees:</span>
              <span className="font-medium">{formatCurrency(m.total_fees || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Gross P&L:</span>
              <span className={`font-medium ${(m.gross_pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatCurrency(m.gross_pnl || 0)}
              </span>
            </div>
          </div>
        </div>

        {/* Trade Performance */}
        <div className="bg-gray-50 rounded-lg p-4">
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Target size={16} className="text-gray-600" />
            Trade Performance
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Average Win:</span>
              <span className="font-medium text-green-600">{formatCurrency(m.avg_win || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Average Loss:</span>
              <span className="font-medium text-red-600">{formatCurrency(m.avg_loss || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Average Win %:</span>
              <span className="font-medium text-green-600">{formatPercent(m.avg_win_pct || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Average Loss %:</span>
              <span className="font-medium text-red-600">{formatPercent(m.avg_loss_pct || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Avg Hold (bars):</span>
              <span className="font-medium">{formatNumber(m.avg_hold_time_bars || 0, 1)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Avg Hold (days):</span>
              <span className="font-medium">{formatDays(m.avg_hold_time_seconds || 0)}</span>
            </div>
          </div>
        </div>

        {/* Daily Performance */}
        <div className="bg-gray-50 rounded-lg p-4">
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Zap size={16} className="text-gray-600" />
            Daily Performance
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Expected Daily Return:</span>
              <span className={`font-medium ${(m.expected_daily_return || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatPercent(m.expected_daily_return || 0)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Best Day:</span>
              <span className="font-medium text-green-600">{formatPercent(m.best_day || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Worst Day:</span>
              <span className="font-medium text-red-600">{formatPercent(m.worst_day || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Avg DD Duration:</span>
              <span className="font-medium">{formatNumber(m.avg_drawdown_duration || 0, 1)} periods</span>
            </div>
          </div>
        </div>

        {/* Risk Management */}
        <div className="bg-gray-50 rounded-lg p-4">
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <BarChart3 size={16} className="text-gray-600" />
            Risk Management
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Kelly Fraction:</span>
              <span className="font-medium">{formatPercent(m.kelly_fraction || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">½-Kelly (Safe):</span>
              <span className="font-medium text-blue-600">{formatPercent(m.kelly_half || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Breakeven Trades:</span>
              <span className="font-medium">{m.breakeven_count || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Annualization Factor:</span>
              <span className="font-medium">{formatNumber(m.annualization_factor || 252, 0)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="mt-6 pt-4 border-t text-xs text-gray-500 flex justify-between items-center">
        <p>Stats URL: {stats?.stats_url || 'N/A'}</p>
        <p>Updates every second • Strategy ID: {id}</p>
      </div>
    </div>
  );
} 