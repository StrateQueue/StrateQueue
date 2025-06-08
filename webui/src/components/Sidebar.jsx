import React from 'react';
import { Layers } from 'lucide-react';
import { Button } from './ui/button';

export default function Sidebar() {
  return (
    <aside className="w-60 border-r h-full flex flex-col py-4 px-3">
      <a href="/" className="flex items-center space-x-2 px-2">
        <img src="/zoom.png" alt="StrateQueue logo" className="h-8 w-8 object-contain" />
        <div className="leading-tight">
          <h1 className="text-lg font-semibold">
            <span>Strate</span>
            <span className="text-red-600">Queue</span>
          </h1>
          <p className="text-xs text-gray-500 -mt-1">Live Trading</p>
        </div>
      </a>

      <nav className="mt-10 space-y-1">
        <Button
          variant="outline"
          className="w-full justify-start space-x-2 bg-gray-100 text-gray-900 hover:bg-gray-200"
        >
          <Layers size={18} />
          <span>Strategies</span>
        </Button>
      </nav>

      {/* Bottom-left notification indicator */}
      <div className="mt-auto pl-1 pb-2">
        <div className="relative">
          <div className="h-8 w-8 rounded-full bg-red-600 flex items-center justify-center text-white text-sm font-semibold">
            N
          </div>
        </div>
      </div>
    </aside>
  );
} 