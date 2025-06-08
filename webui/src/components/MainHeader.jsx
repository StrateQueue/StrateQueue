import React, { useState, useEffect } from 'react';
import { Plus, Settings } from 'lucide-react';
import { Button } from './ui/button';
import {
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogAction,
  AlertDialogCancel,
} from './ui/alert-dialog';
import SettingsForm from './SettingsForm';
import DeployForm from './DeployForm';

export default function MainHeader() {
  const [strategyCount, setStrategyCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStrategyCount();
    // Poll for updates every 30 seconds
    const interval = setInterval(fetchStrategyCount, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchStrategyCount = async () => {
    try {
      const response = await fetch('http://localhost:8400/strategies');
      if (response.ok) {
        const data = await response.json();
        setStrategyCount(data.strategies?.length || 0);
      }
    } catch (err) {
      // Silently handle errors - count will remain 0
    } finally {
      setLoading(false);
    }
  };

  return (
    <header className="flex items-center justify-between border-b px-6 py-4">
      <div>
        <h2 className="text-xl font-semibold">Strategy Management</h2>
        <p className="text-sm text-gray-500">
          Monitor and control your deployed trading strategies
          {!loading && (
            <span className="ml-2 px-2 py-1 bg-blue-50 text-blue-700 rounded-full text-xs font-medium">
              {strategyCount} active
            </span>
          )}
        </p>
      </div>
      <div className="flex items-center">
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button className="flex items-center space-x-2">
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

        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="outline" className="ml-3">
              <Settings size={16} className="mr-2" />
              <span>Settings</span>
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Settings</AlertDialogTitle>
              <AlertDialogDescription>
                Configure your broker credentials and data provider settings.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="py-4 max-h-[70vh] overflow-y-auto">
              <SettingsForm />
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel>Close</AlertDialogCancel>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </header>
  );
} 