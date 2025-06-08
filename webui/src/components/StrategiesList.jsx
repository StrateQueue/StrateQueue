import React, { useState, useEffect } from 'react';
import { 
  Play, 
  Square, 
  TrendingUp, 
  TrendingDown, 
  Clock,
  Activity,
  DollarSign,
  BarChart3,
  Settings,
  Eye,
  Plus
} from 'lucide-react';
import { Button } from './ui/button';
import {
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
} from './ui/alert-dialog';
import DeployForm from './DeployForm';
import StrategyStatsPanel from './StrategyStatsPanel';

export default function StrategiesList() {
  const [strategies, setStrategies] = useState([]);
  const [liveStats, setLiveStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openStatsId, setOpenStatsId] = useState(null);
  const [stopConfirmId, setStopConfirmId] = useState(null);
  const [liquidatePositions, setLiquidatePositions] = useState(false);

  useEffect(() => {
    fetchStrategies();
    // Poll for updates every 1 second for real-time updates
    const interval = setInterval(() => {
      fetchStrategies();
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // Separate effect to fetch live stats when strategies change
  useEffect(() => {
    if (strategies.length > 0) {
      fetchAllLiveStats();
      const statsInterval = setInterval(fetchAllLiveStats, 1000);
      return () => clearInterval(statsInterval);
    }
  }, [strategies]);

  const fetchStrategies = async () => {
    try {
      const response = await fetch('http://localhost:8400/strategies');
      if (!response.ok) {
        throw new Error('Failed to fetch strategies');
      }
      const data = await response.json();
      setStrategies(data.strategies || []);
      setError(null);
    } catch (err) {
      setError(err.message);
      setStrategies([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchAllLiveStats = async () => {
    if (strategies.length === 0) return;
    
    // Fetch live stats for all strategies in parallel
    const statsPromises = strategies.map(async (strategy) => {
      try {
        const response = await fetch(`http://localhost:8400/strategies/${strategy.id}/statistics`);
        if (response.ok) {
          const data = await response.json();
          return { id: strategy.id, stats: data.metrics };
        }
      } catch (err) {
        console.error(`Error fetching stats for ${strategy.id}:`, err);
      }
      return { id: strategy.id, stats: null };
    });

    try {
      const results = await Promise.all(statsPromises);
      const newLiveStats = {};
      results.forEach(({ id, stats }) => {
        if (stats) {
          newLiveStats[id] = stats;
        }
      });
      setLiveStats(newLiveStats);
    } catch (err) {
      console.error('Error fetching live stats:', err);
    }
  };

  const handleStrategyAction = async (strategyId, action) => {
    try {
      const response = await fetch(`http://localhost:8400/strategies/${strategyId}/${action}`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error(`Failed to ${action} strategy`);
      }
      // Refresh strategies list
      fetchStrategies();
    } catch (err) {
      console.error(`Error ${action}ing strategy:`, err);
      // You might want to show a toast notification here
    }
  };

  const handleStopStrategy = async (strategyId) => {
    try {
      const response = await fetch(`http://localhost:8400/strategies/${strategyId}/stop`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          liquidate: liquidatePositions,
          force: false
        }),
      });
      if (!response.ok) {
        throw new Error('Failed to stop strategy');
      }
      // Reset modal state
      setStopConfirmId(null);
      setLiquidatePositions(false);
      // Refresh strategies list
      fetchStrategies();
    } catch (err) {
      console.error('Error stopping strategy:', err);
      // You might want to show a toast notification here
    }
  };

  const formatPnL = (strategy) => {
    // Use live stats if available, otherwise fall back to strategy metadata
    const liveData = liveStats[strategy.id];
    let pnl, pnlPercent;
    
    if (liveData) {
      pnl = liveData.net_pnl || 0;
      pnlPercent = (liveData.total_return || 0) * 100;
    } else {
      // Fallback to static data
      pnl = strategy.pnl || 0;
      pnlPercent = strategy.pnl_percent || 0;
    }
    
    const safePnl = Number(pnl);
    const safePnlPercent = Number(pnlPercent);
    
    const isPositive = safePnl >= 0;
    const sign = isPositive ? '+' : '';
    return {
      amount: `${sign}$${safePnl.toFixed(2)}`,
      percent: `${sign}${safePnlPercent.toFixed(2)}%`,
      isPositive
    };
  };

  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'running': return 'text-green-600 bg-green-50';
      case 'paused': return 'text-yellow-600 bg-yellow-50';
      case 'stopping': return 'text-orange-600 bg-orange-50';
      case 'stopped': return 'text-red-600 bg-red-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const getModeColor = (mode) => {
    switch (mode) {
      case 'live': return 'text-red-600 bg-red-50 border-red-200';
      case 'paper': return 'text-blue-600 bg-blue-50 border-blue-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center mx-auto max-w-md">
        <Activity size={48} className="text-red-400" />
        <h3 className="mt-6 text-lg font-medium text-gray-900">Error loading strategies</h3>
        <p className="mt-2 text-sm text-gray-500">{error}</p>
        <Button onClick={fetchStrategies} className="mt-4">
          Try Again
        </Button>
      </div>
    );
  }

  if (strategies.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center mx-auto max-w-md">
        <Activity size={48} className="text-gray-400" />
        <h3 className="mt-6 text-lg font-medium text-gray-900">No strategies running</h3>
        <p className="mt-2 text-sm text-gray-500">
          Deploy your first strategy to get started
        </p>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button className="mt-6 flex items-center space-x-2">
              <Plus size={16} className="mr-2" />
              <span>Deploy Strategy</span>
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Deploy Strategy</AlertDialogTitle>
              <AlertDialogDescription>
                Fill in the fields below to deploy a live or paper trading strategy.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="py-4 max-h-[70vh] overflow-y-auto">
              <DeployForm />
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel>Close</AlertDialogCancel>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="grid gap-4">
        {strategies.map((strategy) => {
          const pnl = formatPnL(strategy);
          const liveData = liveStats[strategy.id];
          
          return (
            <div
              key={strategy.id}
              className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-3">
                    <h3 className="text-lg font-medium text-gray-900">
                      {strategy.name}
                    </h3>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(strategy.status)}`}>
                      {strategy.status}
                    </span>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium border ${getModeColor(strategy.mode)}`}>
                      {strategy.mode}
                    </span>
                    {liveData && (
                      <span className="px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 border border-green-200">
                        LIVE
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    <div className="flex items-center gap-2">
                      <BarChart3 size={16} className="text-gray-400" />
                      <div>
                        <p className="text-xs text-gray-500">Symbol</p>
                        <p className="text-sm font-medium">{strategy.symbol}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <DollarSign size={16} className="text-gray-400" />
                      <div>
                        <p className="text-xs text-gray-500">P&L {liveData ? '(Live)' : ''}</p>
                        <p className={`text-sm font-medium ${pnl.isPositive ? 'text-green-600' : 'text-red-600'}`}>
                          {pnl.amount} ({pnl.percent})
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Activity size={16} className="text-gray-400" />
                      <div>
                        <p className="text-xs text-gray-500">
                          {liveData ? 'Trades' : 'Allocation'}
                        </p>
                        <p className="text-sm font-medium">
                          {liveData 
                            ? (liveData.trades || 0)
                            : `${((strategy.allocation ?? 0) * 100).toFixed(1)}%`
                          }
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Clock size={16} className="text-gray-400" />
                      <div>
                        <p className="text-xs text-gray-500">Last Signal</p>
                        <p className="text-sm font-medium">
                          {strategy.last_signal ? formatTime(strategy.last_signal) : 'None'}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span>Started: {formatTime(strategy.started_at)}</span>
                    <span>•</span>
                    <span>Data: {strategy.data_source}</span>
                    <span>•</span>
                    <span>Timeframe: {strategy.granularity}</span>
                    {liveData && (
                      <>
                        <span>•</span>
                        <span className={`flex items-center gap-1 ${
                          liveData.net_pnl >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                          Equity: ${(liveData.current_equity || 0).toFixed(2)}
                        </span>
                      </>
                    )}
                    {strategy.last_signal_type && (
                      <>
                        <span>•</span>
                        <span className="flex items-center gap-1">
                          Last: 
                          {strategy.last_signal_type === 'BUY' ? (
                            <TrendingUp size={12} className="text-green-500" />
                          ) : strategy.last_signal_type === 'SELL' ? (
                            <TrendingDown size={12} className="text-red-500" />
                          ) : (
                            <Activity size={12} className="text-gray-500" />
                          )}
                          {strategy.last_signal_type}
                        </span>
                      </>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 ml-4">
                  {strategy.status === 'paused' && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleStrategyAction(strategy.id, 'resume')}
                      className="flex items-center gap-1"
                    >
                      <Play size={14} />
                      Resume
                    </Button>
                  )}

                  <AlertDialog open={stopConfirmId === strategy.id} onOpenChange={(open) => {
                    if (!open) {
                      setStopConfirmId(null);
                      setLiquidatePositions(false);
                    }
                  }}>
                    <AlertDialogTrigger asChild>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setStopConfirmId(strategy.id)}
                        disabled={strategy.status === 'stopping' || strategy.status === 'stopped'}
                        className="flex items-center gap-1 text-red-600 hover:text-red-700 hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <Square size={14} />
                        {strategy.status === 'stopping' ? 'Stopping...' : 'Stop'}
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Stop "{strategy.name}"?</AlertDialogTitle>
                        <AlertDialogDescription>
                          This will stop the strategy and terminate the trading process.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <div className="py-4">
                        <div className="flex items-center space-x-2">
                          <input
                            type="checkbox"
                            id="liquidate"
                            checked={liquidatePositions}
                            disabled
                            className="rounded border-gray-300 text-gray-400 cursor-not-allowed"
                          />
                          <label htmlFor="liquidate" className="text-sm italic text-gray-400 cursor-not-allowed">
                            Also liquidate all open positions (Coming Soon)
                          </label>
                        </div>
                      </div>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <Button
                          onClick={() => handleStopStrategy(strategy.id)}
                          className="bg-red-600 hover:bg-red-700 text-white"
                        >
                          Stop
                        </Button>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>

                  <Button
                    size="sm"
                    variant="outline"
                    className="flex items-center gap-1"
                    onClick={() => setOpenStatsId(openStatsId === strategy.id ? null : strategy.id)}
                  >
                    <Eye size={14} />
                    {openStatsId === strategy.id ? 'Hide Stats' : 'Show Stats'}
                  </Button>
                </div>
              </div>

              {/* Statistics Panel */}
              {openStatsId === strategy.id && (
                <div className="mt-4">
                  <StrategyStatsPanel 
                    id={strategy.id} 
                    onClose={() => setOpenStatsId(null)} 
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
} 