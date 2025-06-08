import React from 'react';
import { Activity, Plus } from 'lucide-react';
import { Button } from './ui/button';

export default function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center mx-auto max-w-md">
      <Activity size={48} className="text-gray-400" />
      <h3 className="mt-6 text-lg font-medium text-gray-900">No strategies running</h3>
      <p className="mt-2 text-sm text-gray-500">
        Deploy your first strategy to get started
      </p>
      <Button className="mt-6 flex items-center space-x-2">
        <Plus size={16} className="mr-2" />
        <span>Deploy Strategy</span>
      </Button>
    </div>
  );
} 