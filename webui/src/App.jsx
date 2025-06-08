import React from 'react';
import Sidebar from './components/Sidebar';
import MainHeader from './components/MainHeader';
import StrategiesList from './components/StrategiesList';

export default function App() {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex flex-col flex-1 bg-white">
        <MainHeader />
        <main className="flex-1 overflow-y-auto">
          <StrategiesList />
        </main>
      </div>
    </div>
  );
} 