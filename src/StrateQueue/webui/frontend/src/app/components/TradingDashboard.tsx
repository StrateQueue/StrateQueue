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
  Copy,
  Power,
  Info,
  X
} from 'lucide-react';

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Switch } from "@/components/ui/switch";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';

const TradingDashboard = () => {
  const [activeTab, setActiveTab] = useState('overview');
  const [animatedValues, setAnimatedValues] = useState<{
    totalPnl?: number;
    activeTrades?: number;
  }>({});
  const [strategies, setStrategies] = useState<any[]>([]);
  const [strategiesLoading, setStrategiesLoading] = useState(true);
  const [strategiesError, setStrategiesError] = useState<string | null>(null);

  // Fetch strategies from the daemon API
  const fetchStrategies = async () => {
    try {
      setStrategiesLoading(true);
      setStrategiesError(null);
      
      // First check daemon health
      const healthResponse = await fetch('http://localhost:8400/health');
      if (!healthResponse.ok) {
        throw new Error('Daemon not responding');
      }
      
      // Get daemon status which includes strategies
      const statusResponse = await fetch('http://localhost:8400/status');
      const statusData = await statusResponse.json();
      
      if (statusData.daemon_running) {
        if (statusData.trading_system_running && statusData.strategy_details) {
          // Use the new detailed strategy information
          const strategyList = statusData.strategy_details.map((detail: any) => ({
            id: detail.id,
            name: detail.id,
            status: detail.status === 'initialized' ? 'Running' : 
                   detail.status === 'paused' ? 'Paused' : 
                   detail.status.charAt(0).toUpperCase() + detail.status.slice(1),
            symbols: detail.symbols || [],
            allocation: detail.allocation || 0.0,
            file_path: detail.file_path
          }));
          setStrategies(strategyList);
        } else if (statusData.trading_system_running) {
          // Fallback for backward compatibility
          setStrategies([{
            id: 'system',
            name: 'Trading System',
            status: 'Running',
            symbols: statusData.system_status?.symbols || [],
            allocation: 1.0,
            file_path: null
          }]);
        } else {
          setStrategies([]);
        }
      } else {
        setStrategies([]);
        setStrategiesError('Daemon not running');
      }
    } catch (error) {
      console.error('Failed to fetch strategies:', error);
      setStrategiesError('Failed to connect to daemon');
      setStrategies([]);
    } finally {
      setStrategiesLoading(false);
    }
  };

  const recentTrades = [
    { id: 1, strategy: 'SMA Crossover', symbol: 'AAPL', type: 'BUY', price: 185.42, pnl: 125, time: '10:30:15' },
    { id: 2, strategy: 'Momentum Strategy', symbol: 'MSFT', type: 'SELL', price: 340.15, pnl: -32, time: '10:15:22' },
    { id: 3, strategy: 'SMA Crossover', symbol: 'AAPL', type: 'SELL', price: 186.20, pnl: 78, time: '09:45:10' },
    { id: 4, strategy: 'Random Strategy', symbol: 'BTC', type: 'BUY', price: 43250, pnl: 425, time: '09:30:05' }
  ];

  useEffect(() => {
    // Fetch strategies on component mount
    fetchStrategies();
    
    // Set up polling for live updates every 10 seconds
    const strategiesInterval = setInterval(fetchStrategies, 10000);
    
    // Animated values for demo purposes
    const animationInterval = setInterval(() => {
      setAnimatedValues({
        totalPnl: Math.random() * 200 + 2830,
        activeTrades: Math.floor(Math.random() * 5) + 8
      });
    }, 3000);
    
    return () => {
      clearInterval(strategiesInterval);
      clearInterval(animationInterval);
    };
  }, []);

  const StatusBadge = ({ status }: { status: string }) => {
    const variants = {
      running: 'default',
      paused: 'secondary', 
      stopped: 'destructive'
    } as const;
    
    const icons = {
      running: <Play className="w-3 h-3 mr-1" />,
      paused: <Pause className="w-3 h-3 mr-1" />,
      stopped: <Square className="w-3 h-3 mr-1" />
    };

    return (
      <Badge variant={variants[status as keyof typeof variants]} className="inline-flex items-center">
        {icons[status as keyof typeof icons]}
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    );
  };

  const MetricCard = ({ title, value, change, icon: Icon, trend, subtitle }: any) => (
    <Card className="hover:bg-accent/50 transition-all duration-300">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Icon className="h-4 w-4 text-muted-foreground" />
            </TooltipTrigger>
            <TooltipContent>
              <p>{subtitle}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {change && (
          <p className={`text-xs flex items-center ${trend === 'up' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
            {trend === 'up' ? <ArrowUp className="w-3 h-3 mr-1" /> : <ArrowDown className="w-3 h-3 mr-1" />}
            {change}
          </p>
        )}
        {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
      </CardContent>
    </Card>
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
          subtitle="Total profit/loss for all active strategies"
        />
        <MetricCard
          title="Active Strategies"
          value={strategies.filter(s => s.status === 'running').length.toString()}
          change={strategies.length > 0 ? `+${strategies.length}` : "0"}
          trend="up"
          icon={Activity}
          subtitle="Currently running trading strategies"
        />
        <MetricCard
          title="Total Trades Today"
          value={animatedValues.activeTrades || 12}
          change="+3"
          trend="up"
          icon={BarChart3}
          subtitle="Buy and sell signals executed today"
        />
        <MetricCard
          title="Success Rate"
          value="65.3%"
          change="+2.1%"
          trend="up"
          icon={Target}
          subtitle="Percentage of profitable trades"
        />
      </div>

      <Separator />

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Trading Signals</CardTitle>
          <CardDescription>Latest buy and sell signals from your strategies</CardDescription>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[400px]">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Strategy</TableHead>
                  <TableHead>Symbol</TableHead>
                  <TableHead>Signal</TableHead>
                  <TableHead>Price</TableHead>
                  <TableHead>PnL</TableHead>
                  <TableHead>Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentTrades.map((trade) => (
                  <TableRow key={trade.id}>
                    <TableCell className="font-medium">{trade.strategy}</TableCell>
                    <TableCell>{trade.symbol}</TableCell>
                    <TableCell>
                      <Badge variant={trade.type === 'BUY' ? 'default' : 'secondary'}>
                        {trade.type}
                      </Badge>
                    </TableCell>
                    <TableCell>${trade.price.toLocaleString()}</TableCell>
                    <TableCell className={trade.pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                      {trade.pnl >= 0 ? '+' : ''}${trade.pnl}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{trade.time}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );

  const StrategiesView = () => (
    <div className="space-y-6">
      {/* Loading State */}
      {strategiesLoading && (
        <div className="flex items-center justify-center py-12">
          <div className="flex items-center gap-3">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
            <span className="text-sm text-muted-foreground">Loading strategies...</span>
          </div>
        </div>
      )}

      {/* Error State */}
      {strategiesError && !strategiesLoading && (
        <Alert className="border-l-4 border-l-red-500">
          <Info className="h-4 w-4" />
          <AlertDescription>
            <div>
              <p className="font-medium">No strategies available</p>
              <p className="text-sm text-muted-foreground">{strategiesError}</p>
              <p className="text-xs text-muted-foreground mt-2">
                💡 Start a trading system: <code>stratequeue deploy --strategy examples/strategies/sma.py --symbol AAPL --daemon</code>
              </p>
              <Button 
                variant="outline" 
                size="sm" 
                className="mt-3"
                onClick={fetchStrategies}
              >
                Retry
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {/* Strategy Cards */}
      {!strategiesLoading && !strategiesError && strategies.length > 0 && (
        <ScrollArea className="h-[600px]">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pr-4">
            {strategies.map((strategy) => (
              <Card key={strategy.id} className="hover:bg-accent/50 transition-all duration-300">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="space-y-2">
                      <CardTitle className="text-lg">{strategy.name}</CardTitle>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">Symbols:</span>
                        {strategy.symbols.map((symbol: string) => (
                          <Badge key={symbol} variant="outline" className="text-xs">
                            {symbol}
                          </Badge>
                        ))}
                      </div>
                      {strategy.allocation && (
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground">Allocation:</span>
                          <Badge variant="secondary" className="text-xs">
                            {(strategy.allocation * 100).toFixed(1)}%
                          </Badge>
                        </div>
                      )}
                    </div>
                    <Badge 
                      variant={strategy.status === 'Running' ? 'default' : 
                               strategy.status === 'Paused' ? 'secondary' : 'destructive'}
                      className="text-xs"
                    >
                      {strategy.status}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Switch 
                        checked={strategy.status === 'Running'} 
                        onCheckedChange={() => handleStrategyToggle(strategy.id, strategy.status === 'Running')}
                        disabled={strategy.status === 'Stopped'}
                      />
                      <span className="text-sm text-muted-foreground">
                        {strategy.status === 'Running' ? 'Active' : 'Paused'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button 
                            variant="ghost" 
                            size="sm"
                            className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Undeploy Strategy</AlertDialogTitle>
                            <AlertDialogDescription>
                              Are you sure you want to undeploy "{strategy.name}"? 
                              This will stop the strategy and liquidate all open positions.
                              This action cannot be undone.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                              onClick={() => handleStrategyDelete(strategy.id)}
                            >
                              Undeploy Strategy
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </ScrollArea>
      )}

      {/* Empty State when no strategies but no error */}
      {!strategiesLoading && !strategiesError && strategies.length === 0 && (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="text-muted-foreground mb-4">
              <Activity className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium">No strategies running</p>
              <p className="text-sm">Deploy your first strategy to get started</p>
            </div>
            <Button 
              variant="outline" 
              className="mt-4"
              onClick={fetchStrategies}
            >
              <Plus className="w-4 h-4 mr-2" />
              Deploy Strategy
            </Button>
          </div>
        </div>
      )}
    </div>
  );

  const AlertsView = () => (
    <div className="space-y-6">
      <ScrollArea className="h-[600px]">
        <div className="space-y-4 pr-4">
          <Alert className="border-l-4 border-l-yellow-500">
            <Bell className="h-4 w-4" />
            <AlertDescription>
              <div>
                <p className="font-medium">Strategy Performance Alert</p>
                <p className="text-sm text-muted-foreground">Momentum Strategy drawdown exceeded 5% threshold</p>
                <p className="text-xs text-muted-foreground mt-1">2 minutes ago</p>
              </div>
            </AlertDescription>
          </Alert>
          
          <Alert className="border-l-4 border-l-green-500">
            <TrendingUp className="h-4 w-4" />
            <AlertDescription>
              <div>
                <p className="font-medium">Successful Trade Execution</p>
                <p className="text-sm text-muted-foreground">SMA Crossover executed BUY signal for AAPL at $185.42</p>
                <p className="text-xs text-muted-foreground mt-1">5 minutes ago</p>
              </div>
            </AlertDescription>
          </Alert>
          
          <Alert className="border-l-4 border-l-blue-500">
            <Activity className="h-4 w-4" />
            <AlertDescription>
              <div>
                <p className="font-medium">System Status</p>
                <p className="text-sm text-muted-foreground">All strategies running normally, market data connection stable</p>
                <p className="text-xs text-muted-foreground mt-1">10 minutes ago</p>
              </div>
            </AlertDescription>
          </Alert>
          
          <Alert className="border-l-4 border-l-orange-500">
            <Info className="h-4 w-4" />
            <AlertDescription>
              <div>
                <p className="font-medium">Market Hours Notice</p>
                <p className="text-sm text-muted-foreground">Markets will close in 30 minutes. Consider adjusting positions.</p>
                <p className="text-xs text-muted-foreground mt-1">15 minutes ago</p>
              </div>
            </AlertDescription>
          </Alert>
        </div>
      </ScrollArea>
    </div>
  );

  const navItems = [
    { id: 'overview', label: 'Overview', icon: Home },
    { id: 'strategies', label: 'Strategies', icon: Layers },
    { id: 'alerts', label: 'Alerts', icon: Bell },
  ];

  // Handle strategy pause/resume
  const handleStrategyToggle = async (strategyId: string, currentlyActive: boolean) => {
    try {
      const endpoint = currentlyActive ? 'pause' : 'resume';
      const response = await fetch(`http://localhost:8400/strategy/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ strategy_id: strategyId }),
      });

      if (response.ok) {
        // Refresh strategies to get updated status
        await fetchStrategies();
      } else {
        console.error(`Failed to ${endpoint} strategy:`, await response.text());
      }
    } catch (error) {
      console.error(`Error ${currentlyActive ? 'pausing' : 'resuming'} strategy:`, error);
    }
  };

  // Handle strategy deletion
  const handleStrategyDelete = async (strategyId: string) => {
    try {
      const response = await fetch('http://localhost:8400/strategy/undeploy', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          strategy_id: strategyId,
          liquidate_positions: true 
        }),
      });

      if (response.ok) {
        // Refresh strategies to remove deleted strategy
        await fetchStrategies();
      } else {
        console.error('Failed to undeploy strategy:', await response.text());
      }
    } catch (error) {
      console.error('Error undeploying strategy:', error);
    }
  };

  return (
    <div className="min-h-screen flex bg-background">
      {/* Fixed Sidebar */}
      <div className="w-64 bg-card border-r flex flex-col h-screen">
        {/* Sidebar Header */}
        <div className="p-6 border-b flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold">Stratequeue</h1>
              <p className="text-xs text-muted-foreground">Live Trading</p>
            </div>
          </div>
        </div>
        
        {/* Navigation - Scrollable middle section */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-4">
            <nav className="space-y-2">
              {navItems.map((item) => (
                <Button
                  key={item.id}
                  variant={activeTab === item.id ? "default" : "ghost"}
                  className="w-full justify-start"
                  onClick={() => setActiveTab(item.id)}
                >
                  <item.icon className="w-5 h-5 mr-2" />
                  {item.label}
                </Button>
              ))}
            </nav>
          </div>
        </div>
        
        {/* Sidebar Footer - Always visible at bottom */}
        <div className="p-4 border-t flex-shrink-0">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="outline" className="w-full justify-start">
                  <Power className="w-4 h-4 mr-2" />
                  System Status
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>All systems operational</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col">
        {/* Top Bar */}
        <div className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div className="flex h-16 items-center justify-between px-6">
            <div>
              <h2 className="text-2xl font-bold">
                {activeTab === 'overview' && 'Dashboard Overview'}
                {activeTab === 'strategies' && 'Strategy Management'}
                {activeTab === 'alerts' && 'System Alerts'}
              </h2>
              <p className="text-sm text-muted-foreground">
                {activeTab === 'overview' && new Date().toLocaleDateString('en-US', { 
                  weekday: 'long', 
                  year: 'numeric', 
                  month: 'long', 
                  day: 'numeric' 
                })}
                {activeTab === 'strategies' && 'Monitor and control your deployed trading strategies'}
                {activeTab === 'alerts' && 'Monitor strategy alerts and system notifications'}
              </p>
            </div>
            
            <div className="flex items-center gap-4">
              {/* Strategy Management Actions */}
              {activeTab === 'strategies' && (
                <div className="flex gap-3">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
                    <Input 
                      type="text" 
                      placeholder="Search strategies..."
                      className="pl-9 w-64"
                    />
                  </div>
                  <Button>
                    <Plus className="w-4 h-4 mr-2" />
                    Deploy Strategy
                  </Button>
                </div>
              )}
              
              {/* Default Actions */}
              <Badge variant="outline" className="border-green-500/30 text-green-600 dark:text-green-400">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse mr-2"></div>
                Live Market
              </Badge>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="outline" size="icon" className="relative">
                      <Bell className="w-5 h-5" />
                      <div className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full"></div>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>View notifications</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-auto">
          <div className="p-6">
            {activeTab === 'overview' && <OverviewView />}
            {activeTab === 'strategies' && <StrategiesView />}
            {activeTab === 'alerts' && <AlertsView />}
          </div>
        </div>
      </div>
    </div>
  );
};

export default TradingDashboard; 