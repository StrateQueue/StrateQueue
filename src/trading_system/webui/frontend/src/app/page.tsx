"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import TradingDashboard from "./components/TradingDashboard";

export default function Home() {
  const [showDashboard, setShowDashboard] = useState(false);

  if (showDashboard) {
    return <TradingDashboard />;
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background p-8">
      <div className="text-center space-y-6">
        <h1 className="text-4xl font-bold tracking-tight">
          Welcome to Stratequeue
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl">
          Transform your backtesting.py strategies into live trading systems
        </p>
        <div className="flex gap-4 justify-center">
          <Button 
            size="lg"
            onClick={() => setShowDashboard(true)}
          >
            Deploy Strategy
          </Button>
          <Button variant="outline" size="lg">
            View Documentation
          </Button>
        </div>
        <div className="mt-8 p-4 bg-muted rounded-lg">
          <p className="text-sm text-muted-foreground">
            🚀 Web UI is running! Ready to deploy your trading strategies.
          </p>
        </div>
      </div>
    </div>
  );
}
