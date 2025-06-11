"use client";

import React, { useState, useEffect } from 'react';
import { 
  Play, 
  Pause, 
  Square, 
  Settings, 
  TrendingUp, 
  TrendingDown, 
  DollarSign, 
  Activity, 
  BarChart3, 
  Plus,
  Search,
  Bell,
  Home,
  Layers,
  Target,
  ArrowUp,
  ArrowDown,
  MoreVertical,
  Edit,
  Trash2,
  Copy
} from 'lucide-react';

const TradingDashboard = () => {
  const [activeView, setActiveView] = useState('overview');
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [animatedValues, setAnimatedValues] = useState({});

  // Mock data for strategies
  const strategies = [
    {
      id: 1,
      name: "SMA Crossover",
      file: "examples/strategies/sma.py",
      symbols: ["AAPL"],
      status: "running",
      pnl: 2420.50,
      pnlPercent: 4.8,
      trades: 27,
      winRate: 68.5,
      lastUpdate: "2 mins ago",
      allocation: 0.4
    },
    {
      id: 2,
      name: "Momentum Strategy",
      file: "examples/strategies/momentum.py", 
      symbols: ["MSFT", "GOOGL"],
      status: "running",
      pnl: -340.75,
      pnlPercent: -1.2,
      trades: 15,
      winRate: 42.2,
      lastUpdate: "5 mins ago",
      allocation: 0.35
    },
    {
      id: 3,
      name: "Random Strategy",
      file: "examples/strategies/random.py",
      symbols: ["BTC"],
      status: "paused", 
      pnl: 750.25,
      pnlPercent: 2.1,
      trades: 34,
      winRate: 55.8,
      lastUpdate: "1 hour ago",
      allocation: 0.25
    }
  ];

  const recentTrades = [
    { id: 1, strategy: 'SMA Crossover', symbol: 'AAPL', type: 'BUY', price: 185.42, pnl: 125, time: '10:30:15' },
    { id: 2, strategy: 'Momentum Strategy', symbol: 'MSFT', type: 'SELL', price: 340.15, pnl: -32, time: '10:15:22' },
    { id: 3, strategy: 'SMA Crossover', symbol: 'AAPL', type: 'SELL', price: 186.20, pnl: 78, time: '09:45:10' },
    { id: 4, strategy: 'Random Strategy', symbol: 'BTC', type: 'BUY', price: 43250, pnl: 425, time: '09:30:05' }
  ];

  useEffect(() => {
    const interval = setInterval(() => {
      setAnimatedValues({
        totalPnl: Math.random() * 200 + 2830,
        activeTrades: Math.floor(Math.random() * 5) + 8
      });
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const StatusBadge = ({ status }: { status: string }) => {
    const colors = {
      running: 'bg-green-500/20 text-green-400 border-green-500/30',
      paused: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
      stopped: 'bg-red-500/20 text-red-400 border-red-500/30'
    };
    
    const icons = {
      running: <Play className="w-3 h-3" />,
      paused: <Pause className="w-3 h-3" />,
      stopped: <Square className="w-3 h-3" />
    };

    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium ${colors[status as keyof typeof colors]}`}>
        {icons[status as keyof typeof icons]}
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  };

  const MetricCard = ({ title, value, change, icon: Icon, trend, subtitle }: any) => (
    <div className="bg-card border rounded-xl p-6 hover:bg-accent/50 transition-all duration-300">
      <div className="flex items-center justify-between mb-4">
        <div className="p-2 bg-primary/10 rounded-lg">
          <Icon className="w-5 h-5 text-primary" />
        </div>
        {change && (
          <span className={`flex items-center gap-1 text-sm font-medium ${trend === 'up' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
            {trend === 'up' ? <ArrowUp className="w-4 h-4" /> : <ArrowDown className="w-4 h-4" />}
            {change}
          </span>
        )}
      </div>
      <div>
        <p className="text-2xl font-bold mb-1">{value}</p>
        <p className="text-muted-foreground text-sm">{title}</p>
        {subtitle && <p className="text-muted-foreground text-xs mt-1">{subtitle}</p>}
      </div>
    </div>
  );

  const OverviewView = () => (
    <div className="space-y-6">
      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Total Portfolio PnL"
          value={`$${(animatedValues.totalPnl || 2830.50).toLocaleString()}`}
          change="+4.2%"
          trend="up"
          icon={DollarSign}
          subtitle="Last 24 hours"
        />
        <MetricCard
          title="Active Strategies"
          value="2"
          change="+1"
          trend="up"
          icon={Activity}
          subtitle="1 paused"
        />
        <MetricCard
          title="Total Trades Today"
          value={animatedValues.activeTrades || 12}
          change="+3"
          trend="up"
          icon={BarChart3}
          subtitle="8 profitable"
        />
        <MetricCard
          title="Success Rate"
          value="65.3%"
          change="+2.1%"
          trend="up"
          icon={Target}
          subtitle="All strategies"
        />
      </div>

      {/* Recent Activity */}
      <div className="bg-card border rounded-xl p-6">
        <h3 className="text-lg font-semibold mb-6">Recent Trading Signals</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left border-b">
                <th className="pb-3 text-sm font-medium text-muted-foreground">Strategy</th>
                <th className="pb-3 text-sm font-medium text-muted-foreground">Symbol</th>
                <th className="pb-3 text-sm font-medium text-muted-foreground">Signal</th>
                <th className="pb-3 text-sm font-medium text-muted-foreground">Price</th>
                <th className="pb-3 text-sm font-medium text-muted-foreground">PnL</th>
                <th className="pb-3 text-sm font-medium text-muted-foreground">Time</th>
              </tr>
            </thead>
            <tbody>
              {recentTrades.map((trade) => (
                <tr key={trade.id} className="border-b hover:bg-accent/50 transition-colors">
                  <td className="py-3 font-medium">{trade.strategy}</td>
                  <td className="py-3 text-muted-foreground">{trade.symbol}</td>
                  <td className="py-3">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      trade.type === 'BUY' ? 'bg-green-500/20 text-green-600 dark:text-green-400' : 'bg-red-500/20 text-red-600 dark:text-red-400'
                    }`}>
                      {trade.type}
                    </span>
                  </td>
                  <td className="py-3 text-muted-foreground">${trade.price.toLocaleString()}</td>
                  <td className={`py-3 font-medium ${trade.pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                    {trade.pnl >= 0 ? '+' : ''}${trade.pnl}
                  </td>
                  <td className="py-3 text-muted-foreground text-sm">{trade.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );

  const StrategiesView = () => (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center">
        <div>
          <h2 className="text-2xl font-bold">Strategy Management</h2>
          <p className="text-muted-foreground mt-1">Monitor and control your deployed trading strategies</p>
        </div>
        <div className="flex gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
            <input 
              type="text" 
              placeholder="Search strategies..."
              className="pl-9 pr-4 py-2 bg-background border rounded-lg placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring transition-colors"
            />
          </div>
          <button className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors">
            <Plus className="w-4 h-4" />
            Deploy Strategy
          </button>
        </div>
      </div>

      {/* Strategy Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {strategies.map((strategy) => (
          <div key={strategy.id} className="bg-card border rounded-xl p-6 hover:bg-accent/50 transition-all duration-300">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold mb-1">{strategy.name}</h3>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span>{strategy.file}</span>
                </div>
                <div className="flex items-center gap-1 mt-1">
                  <span className="text-xs text-muted-foreground">Symbols:</span>
                  {strategy.symbols.map((symbol, idx) => (
                    <span key={symbol} className="text-xs bg-secondary px-1.5 py-0.5 rounded">
                      {symbol}
                    </span>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={strategy.status} />
                <button className="p-1 hover:bg-accent rounded">
                  <MoreVertical className="w-4 h-4 text-muted-foreground" />
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
              <div>
                <p className="text-xs text-muted-foreground mb-1">PnL</p>
                <p className={`font-semibold ${strategy.pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                  {strategy.pnl >= 0 ? '+' : ''}${strategy.pnl.toLocaleString()}
                </p>
                <p className={`text-xs ${strategy.pnlPercent >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                  {strategy.pnlPercent >= 0 ? '+' : ''}{strategy.pnlPercent}%
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Allocation</p>
                <p className="font-semibold">{(strategy.allocation * 100).toFixed(0)}%</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Trades</p>
                <p className="font-semibold">{strategy.trades}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Win Rate</p>
                <p className="font-semibold">{strategy.winRate}%</p>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div className="text-xs text-muted-foreground">
                <span>Updated {strategy.lastUpdate}</span>
              </div>
              <div className="flex gap-2">
                {strategy.status === 'running' ? (
                  <button className="p-2 hover:bg-accent rounded-lg transition-colors">
                    <Pause className="w-4 h-4 text-yellow-600 dark:text-yellow-400" />
                  </button>
                ) : (
                  <button className="p-2 hover:bg-accent rounded-lg transition-colors">
                    <Play className="w-4 h-4 text-green-600 dark:text-green-400" />
                  </button>
                )}
                <button className="p-2 hover:bg-accent rounded-lg transition-colors">
                  <Settings className="w-4 h-4 text-muted-foreground" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const AlertsView = () => (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">System Alerts</h2>
        <p className="text-muted-foreground mt-1">Monitor strategy alerts and system notifications</p>
      </div>
      
      <div className="space-y-4">
        <div className="bg-card border rounded-xl p-4 border-l-4 border-l-yellow-500">
          <div className="flex items-center gap-3">
            <Bell className="w-5 h-5 text-yellow-500" />
            <div>
              <p className="font-medium">Strategy Performance Alert</p>
              <p className="text-sm text-muted-foreground">Momentum Strategy drawdown exceeded 5% threshold</p>
              <p className="text-xs text-muted-foreground mt-1">2 minutes ago</p>
            </div>
          </div>
        </div>
        
        <div className="bg-card border rounded-xl p-4 border-l-4 border-l-green-500">
          <div className="flex items-center gap-3">
            <TrendingUp className="w-5 h-5 text-green-500" />
            <div>
              <p className="font-medium">Successful Trade Execution</p>
              <p className="text-sm text-muted-foreground">SMA Crossover executed BUY signal for AAPL at $185.42</p>
              <p className="text-xs text-muted-foreground mt-1">5 minutes ago</p>
            </div>
          </div>
        </div>
        
        <div className="bg-card border rounded-xl p-4 border-l-4 border-l-blue-500">
          <div className="flex items-center gap-3">
            <Activity className="w-5 h-5 text-blue-500" />
            <div>
              <p className="font-medium">System Status</p>
              <p className="text-sm text-muted-foreground">All strategies running normally, market data connection stable</p>
              <p className="text-xs text-muted-foreground mt-1">10 minutes ago</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const sidebarItems = [
    { id: 'overview', label: 'Overview', icon: Home },
    { id: 'strategies', label: 'Strategies', icon: Layers },
    { id: 'alerts', label: 'Alerts', icon: Bell },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Sidebar */}
      <div className="fixed inset-y-0 left-0 w-64 bg-card border-r">
        <div className="flex items-center gap-3 p-6 border-b">
          <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Stratequeue</h1>
            <p className="text-xs text-muted-foreground">Live Trading</p>
          </div>
        </div>
        
        <nav className="p-4 space-y-2">
          {sidebarItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveView(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                activeView === item.id 
                  ? 'bg-primary text-primary-foreground' 
                  : 'text-muted-foreground hover:text-foreground hover:bg-accent'
              }`}
            >
              <item.icon className="w-5 h-5" />
              {item.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Main Content */}
      <div className="ml-64 p-6">
        {/* Top Bar */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold">
              {activeView === 'overview' && 'Dashboard Overview'}
              {activeView === 'strategies' && 'Strategy Management'}
              {activeView === 'alerts' && 'System Alerts'}
            </h2>
            <p className="text-muted-foreground mt-1">
              {new Date().toLocaleDateString('en-US', { 
                weekday: 'long', 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric' 
              })}
            </p>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-2 bg-green-500/20 text-green-600 dark:text-green-400 rounded-lg border border-green-500/30">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span className="text-sm font-medium">Live Market</span>
            </div>
            <button className="relative p-2 hover:bg-accent rounded-lg transition-colors">
              <Bell className="w-5 h-5 text-muted-foreground" />
              <div className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full"></div>
            </button>
          </div>
        </div>

        {/* Content */}
        {activeView === 'overview' && <OverviewView />}
        {activeView === 'strategies' && <StrategiesView />}
        {activeView === 'alerts' && <AlertsView />}
      </div>
    </div>
  );
};

export default TradingDashboard; 