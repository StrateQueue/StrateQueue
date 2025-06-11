"use client";

import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import TradingDashboard from "./components/TradingDashboard";

// Animated subtitle component
const AnimatedSubtitle = () => {
  const frameworks = [
    'Backtesting.py',
    'VectorBT', 
    'LEAN',
    'Backtrader',
    'Jesse',
    'FastQuant',
    'Nautilus Trader',
    'PyAlgoTrade',
    'Zipline Reloaded'
  ];

  const brokers = [
    'IBKR',
    'Alpaca',
    'Charles Schwab',
    'TD Ameritrade', 
    'Coinbase',
    'E*TRADE',
    'Binance',
    'Fidelity',
    'Kraken'
  ];

  const [currentIndex, setCurrentIndex] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  const frameworkRef = useRef<HTMLSpanElement>(null);
  const brokerRef = useRef<HTMLSpanElement>(null);
  const intervalRef = useRef<NodeJS.Timeout>();

  const animateSlotMachine = (element: HTMLSpanElement | null, fromText: string, toText: string, duration = 800): Promise<void> => {
    return new Promise((resolve) => {
      if (!element) {
        resolve();
        return;
      }

      const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
      const startTime = Date.now();
      
      const animate = () => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        if (progress < 1) {
          // Generate random characters with decreasing frequency
          const randomText = toText.split('').map((char, index) => {
            const charProgress = Math.max(0, (progress * toText.length - index) / 3);
            if (charProgress >= 1) {
              return char;
            } else if (charProgress > 0 && Math.random() < 0.7) {
              return char;
            } else {
              return chars[Math.floor(Math.random() * chars.length)];
            }
          }).join('');
          
          element.textContent = randomText;
          requestAnimationFrame(animate);
        } else {
          element.textContent = toText;
          resolve();
        }
      };
      
      animate();
    });
  };

  const cycleToNext = async () => {
    if (isAnimating) return;
    
    setIsAnimating(true);
    const nextIndex = (currentIndex + 1) % frameworks.length;
    
    const currentFramework = frameworks[currentIndex];
    const newFramework = frameworks[nextIndex];
    const currentBroker = brokers[currentIndex];
    const newBroker = brokers[nextIndex];
    
    // Animate both slot machines with slight offset
    const frameworkAnimation = animateSlotMachine(frameworkRef.current, currentFramework, newFramework, 800);
    
    // Slight delay for natural feel
    setTimeout(() => {
      animateSlotMachine(brokerRef.current, currentBroker, newBroker, 600);
    }, 200);
    
    await frameworkAnimation;
    setCurrentIndex(nextIndex);
    setIsAnimating(false);
  };

  useEffect(() => {
    // Initialize text content
    if (frameworkRef.current) {
      frameworkRef.current.textContent = frameworks[currentIndex];
    }
    if (brokerRef.current) {
      brokerRef.current.textContent = brokers[currentIndex];
    }

    // Start auto-cycling
    intervalRef.current = setInterval(cycleToNext, 4000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [currentIndex]);

  const handleMouseEnter = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
  };

  const handleMouseLeave = () => {
    intervalRef.current = setInterval(cycleToNext, 4000);
  };

  return (
    <p 
      className="text-xl text-muted-foreground max-w-2xl leading-relaxed"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      Test, optimize, and deploy your{' '}
      <span 
        ref={frameworkRef}
        className="text-foreground font-bold"
      >
        Backtesting.py
      </span>{' '}
      strategy instantly to{' '}
      <span 
        ref={brokerRef}
        className="text-foreground font-bold"
      >
        Alpaca
      </span>.{' '}
      No vendor lock-in, maximum flexibility.
    </p>
  );
};

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
        <AnimatedSubtitle />
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
