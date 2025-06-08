import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from './ui/button';
import {
  RHFProvider,
  FormField,
  FormItem,
  FormLabel,
  FormControl,
  FormDescription,
  FormMessage,
} from './ui/form';
import { Input } from './ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';

const schema = z.object({
  strategyFile: z.any(),
  strategyId: z.string().optional(),
  allocation: z.string().optional(),
  symbol: z.string().default('AAPL'),
  provider: z.string().default('demo'),
  timeframe: z.string().default('1m'),
  broker: z.string().default('alpaca'),
  engine: z.string().optional(),
  lookback: z.preprocess((v) => {
    const n = typeof v === 'string' ? parseInt(v, 10) : v;
    return Number.isNaN(n) ? undefined : n;
  }, z.number().int().min(1).default(1000)),
  duration: z.preprocess((v) => {
    const n = typeof v === 'string' ? parseInt(v, 10) : v;
    return Number.isNaN(n) ? undefined : n;
  }, z.number().int().min(1).default(60)),
  tradingMode: z.enum(['signals', 'paper', 'live']).default('signals'),
});

const providerOptions = [
  { value: 'polygon', label: 'Polygon' },
  { value: 'coinmarketcap', label: 'CoinMarketCap' },
  { value: 'demo', label: 'Demo' },
  { value: 'yfinance', label: 'Yahoo Finance' },
];

const brokerOptions = [
  { value: 'alpaca', label: 'Alpaca' },
];

const engineOptions = [
  { value: 'auto', label: 'Auto (detect from strategy)' },
  { value: 'backtesting', label: 'Backtesting.py' },
  { value: 'vectorbt', label: 'VectorBT' },
  { value: 'zipline', label: 'Zipline' },
  { value: 'backtrader', label: 'Backtrader' },
];

export default function DeployForm() {
  const methods = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      symbol: 'AAPL',
      provider: 'demo',
      timeframe: '1m',
      broker: 'alpaca',
      engine: 'auto',
      lookback: 1000,
      duration: 60,
      tradingMode: 'signals',
    },
  });

  const [uploading, setUploading] = useState(false);

  const onSubmit = async (values) => {
    try {
      // Upload strategy file first
      if (!values.strategyFile || values.strategyFile.length === 0) {
        alert('Please select a strategy file');
        return;
      }
      setUploading(true);
      const fileData = new FormData();
      fileData.append('file', values.strategyFile[0]);
      const uploadResp = await fetch('http://localhost:8400/upload_strategy', {
        method: 'POST',
        body: fileData,
      });
      if (!uploadResp.ok) throw new Error(await uploadResp.text());
      const { path } = await uploadResp.json();

      // Build deploy payload
      const payload = {
        strategy: path,
        strategy_id: values.strategyId,
        allocation: values.allocation,
        symbol: values.symbol,
        data_source: values.provider,
        granularity: values.timeframe,
        broker: values.broker,
        engine: values.engine === 'auto' ? undefined : values.engine,
        lookback: values.lookback,
        duration: values.duration,
        mode: values.tradingMode, // signals/paper/live
      };

      console.log('Deploy payload', payload);
      
      // First validate the configuration
      const validateResp = await fetch('http://localhost:8400/deploy/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      
      if (!validateResp.ok) throw new Error(await validateResp.text());
      const validation = await validateResp.json();
      
      if (!validation.valid) {
        alert('❌ Validation failed:\n' + validation.errors.join('\n'));
        return;
      }
      
      // If validation passes, start deployment
      const deployResp = await fetch('http://localhost:8400/deploy/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      
      if (!deployResp.ok) throw new Error(await deployResp.text());
      const result = await deployResp.json();
      
      alert(`✅ ${result.message}`);
      
    } catch (err) {
      console.error('Deploy failed', err);
      alert('❌ Deploy failed: ' + err.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <RHFProvider methods={methods} onSubmit={onSubmit} className="space-y-6">
      {/* Strategy file */}
      <FormField
        name="strategyFile"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Strategy File (.py)</FormLabel>
            <FormControl>
              <Input type="file" accept=".py" onChange={(e) => field.onChange(e.target.files)} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      {/* Strategy ID */}
      <FormField
        name="strategyId"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Strategy ID</FormLabel>
            <FormControl>
              <Input placeholder="Optional human-friendly name" {...field} />
            </FormControl>
          </FormItem>
        )}
      />

      {/* Allocation */}
      <FormField
        name="allocation"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Allocation</FormLabel>
            <FormControl>
              <Input placeholder="e.g. 0.5 (50%) or 10000 ($10k)" {...field} />
            </FormControl>
            <FormDescription>
              Portfolio allocation as percentage (0-1) or dollar amount. Required for multi-strategy mode.
            </FormDescription>
          </FormItem>
        )}
      />

      {/* Symbol */}
      <FormField
        name="symbol"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Symbol(s)</FormLabel>
            <FormControl>
              <Input placeholder="e.g. AAPL or BTC,ETH" {...field} />
            </FormControl>
          </FormItem>
        )}
      />

      {/* Provider */}
      <FormField
        name="provider"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Data Provider</FormLabel>
            <FormControl>
              <Select onValueChange={field.onChange} value={field.value}>
                <SelectTrigger>
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  {providerOptions.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormControl>
          </FormItem>
        )}
      />

      {/* Timeframe */}
      <FormField
        name="timeframe"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Timeframe</FormLabel>
            <FormControl>
              <Input placeholder="1m, 5m, 1h, 1d…" {...field} />
            </FormControl>
          </FormItem>
        )}
      />

      {/* Broker */}
      <FormField
        name="broker"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Broker</FormLabel>
            <FormControl>
              <Select onValueChange={field.onChange} value={field.value}>
                <SelectTrigger>
                  <SelectValue placeholder="Select broker" />
                </SelectTrigger>
                <SelectContent>
                  {brokerOptions.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormControl>
          </FormItem>
        )}
      />

      {/* Engine */}
      <FormField
        name="engine"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Engine</FormLabel>
            <FormControl>
              <Select onValueChange={field.onChange} value={field.value || ''}>
                <SelectTrigger>
                  <SelectValue placeholder="Auto-detect" />
                </SelectTrigger>
                <SelectContent>
                  {engineOptions.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormControl>
          </FormItem>
        )}
      />

      {/* Lookback */}
      <FormField
        name="lookback"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Lookback (bars)</FormLabel>
            <FormControl>
              <Input type="number" {...field} />
            </FormControl>
          </FormItem>
        )}
      />

      {/* Duration */}
      <FormField
        name="duration"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Duration (minutes)</FormLabel>
            <FormControl>
              <Input type="number" {...field} />
            </FormControl>
          </FormItem>
        )}
      />

      {/* Trading mode */}
      <FormField
        name="tradingMode"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Trading Mode</FormLabel>
            <FormControl>
              <Select onValueChange={field.onChange} value={field.value}>
                <SelectTrigger>
                  <SelectValue placeholder="Select mode" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="signals">Signals Only</SelectItem>
                  <SelectItem value="paper">Paper Trading</SelectItem>
                  <SelectItem value="live">Live Trading</SelectItem>
                </SelectContent>
              </Select>
            </FormControl>
          </FormItem>
        )}
      />

      <Button type="submit" disabled={uploading}>
        {uploading ? 'Uploading…' : 'Deploy'}
      </Button>
    </RHFProvider>
  );
} 