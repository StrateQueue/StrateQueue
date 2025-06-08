import React from 'react';
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
  setupType: z.enum(['broker', 'data-provider']),
  broker: z.string().optional(),
  provider: z.string().optional(),
  apiKey: z.string().optional(),
  secretKey: z.string().optional(),
  paper: z.boolean().optional(),
  alpacaTradingMode: z.enum(['paper', 'live']).optional(),
  polygonApiKey: z.string().optional(),
  cmcApiKey: z.string().optional(),
});

const brokerOptions = [
  { value: 'alpaca', label: 'Alpaca (US stocks, ETFs, crypto)' },
  // Future brokers could be added here
];

const providerOptions = [
  { value: 'polygon', label: 'Polygon (stocks, crypto, forex - premium)' },
  { value: 'coinmarketcap', label: 'CoinMarketCap (cryptocurrency data)' },
  { value: 'demo', label: 'Demo (No credentials)' },
  { value: 'yfinance', label: 'Yahoo Finance (Free stock data)' },
];

export default function SettingsForm() {
  const methods = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      setupType: 'broker',
      broker: 'alpaca',
      provider: 'polygon',
      apiKey: '',
      secretKey: '',
      paper: true,
      alpacaTradingMode: 'paper',
      polygonApiKey: '',
      cmcApiKey: '',
    },
  });

  const watchType = methods.watch('setupType');
  const watchBroker = methods.watch('broker');
  const watchProvider = methods.watch('provider');

  const onSubmit = async (values) => {
    console.log('Settings saved', values);
    console.log('Current watchType:', watchType); // Debug log
    
    try {
      // Transform form values into environment variables
      const env = {};
      
      if (values.setupType === 'broker' && values.broker === 'alpaca') {
        if (values.alpacaTradingMode === 'paper') {
          env.PAPER_KEY = values.apiKey;
          env.PAPER_SECRET = values.secretKey;
          env.PAPER_ENDPOINT = 'https://paper-api.alpaca.markets';
        } else {
          env.ALPACA_API_KEY = values.apiKey;
          env.ALPACA_SECRET_KEY = values.secretKey;
          env.ALPACA_BASE_URL = 'https://api.alpaca.markets';
        }
      }
      
      if (values.setupType === 'data-provider') {
        if (values.provider === 'polygon' && values.polygonApiKey) {
          env.POLYGON_API_KEY = values.polygonApiKey;
        }
        if (values.provider === 'coinmarketcap' && values.cmcApiKey) {
          env.CMC_API_KEY = values.cmcApiKey;
        }
        // Always set the provider type
        env.DATA_PROVIDER = values.provider;
      }
      
      // Make API call to save configuration
      const response = await fetch('http://localhost:8400/config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(env),
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText);
      }
      
      const result = await response.json();
      console.log('Configuration saved successfully:', result);
      alert(`✅ Configuration saved successfully!\n\n${result.message}\n\nRun "stratequeue status" to verify your setup.`);
      
    } catch (error) {
      console.error('Failed to save configuration:', error);
      alert(`❌ Failed to save configuration:\n\n${error.message}\n\nMake sure the StrateQueue daemon is running.`);
    }
  };

  console.log('Current form state:', { watchType, watchBroker, watchProvider });

  return (
    <RHFProvider methods={methods} onSubmit={onSubmit} className="space-y-6">
      {/* Setup type selector */}
      <FormField
        name="setupType"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Configuration Type</FormLabel>
            <FormControl>
              <Select onValueChange={field.onChange} value={field.value}>
                <SelectTrigger>
                  <SelectValue placeholder="Select configuration type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="broker">Broker Credentials</SelectItem>
                  <SelectItem value="data-provider">Data Provider Credentials</SelectItem>
                </SelectContent>
              </Select>
            </FormControl>
            <FormDescription>
              Choose whether to configure broker or data provider settings.
            </FormDescription>
          </FormItem>
        )}
      />

      {watchType === 'broker' && (
        <>
          {/* Broker select */}
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
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormControl>
              </FormItem>
            )}
          />

          {watchBroker === 'alpaca' && (
            <>
              {/* Trading mode */}
              <FormField
                name="alpacaTradingMode"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Trading Mode</FormLabel>
                    <FormControl>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select trading mode" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="paper">Paper Trading (fake money - recommended)</SelectItem>
                          <SelectItem value="live">Live Trading (real money - use with caution!)</SelectItem>
                        </SelectContent>
                      </Select>
                    </FormControl>
                    <FormDescription>
                      Paper trading uses simulated money for testing strategies safely.
                    </FormDescription>
                  </FormItem>
                )}
              />

              <FormField
                name="apiKey"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Alpaca API Key</FormLabel>
                    <FormControl>
                      <Input placeholder="PK..." {...field} />
                    </FormControl>
                    <FormDescription>
                      Get your API keys from: https://app.alpaca.markets/
                    </FormDescription>
                    <FormMessage>
                      {methods.formState.errors.apiKey?.message}
                    </FormMessage>
                  </FormItem>
                )}
              />

              <FormField
                name="secretKey"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Alpaca Secret Key</FormLabel>
                    <FormControl>
                      <Input type="password" placeholder="SK..." {...field} />
                    </FormControl>
                    <FormMessage>
                      {methods.formState.errors.secretKey?.message}
                    </FormMessage>
                  </FormItem>
                )}
              />
            </>
          )}
        </>
      )}

      {watchType === 'data-provider' && (
        <>
          {/* Provider select */}
          <FormField
            name="provider"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Data Provider</FormLabel>
                <FormControl>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select data provider" />
                    </SelectTrigger>
                    <SelectContent>
                      {providerOptions.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormControl>
              </FormItem>
            )}
          />

          {watchProvider === 'polygon' && (
            <FormField
              name="polygonApiKey"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Polygon API Key</FormLabel>
                  <FormControl>
                    <Input placeholder="API Key..." {...field} />
                  </FormControl>
                  <FormDescription>
                    Get your API key from: https://polygon.io/ (Free tier available)
                  </FormDescription>
                  <FormMessage>
                    {methods.formState.errors.polygonApiKey?.message}
                  </FormMessage>
                </FormItem>
              )}
            />
          )}

          {watchProvider === 'coinmarketcap' && (
            <FormField
              name="cmcApiKey"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>CoinMarketCap API Key</FormLabel>
                  <FormControl>
                    <Input placeholder="API Key..." {...field} />
                  </FormControl>
                  <FormDescription>
                    Get your API key from: https://pro.coinmarketcap.com/ (Free tier: 333 requests/day)
                  </FormDescription>
                  <FormMessage>
                    {methods.formState.errors.cmcApiKey?.message}
                  </FormMessage>
                </FormItem>
              )}
            />
          )}

          {watchProvider === 'demo' && (
            <div className="p-4 bg-gray-50 rounded-md">
              <p className="text-sm text-gray-600">
                📊 Demo provider uses simulated market data for testing and development.
                No API key required.
              </p>
            </div>
          )}

          {watchProvider === 'yfinance' && (
            <div className="p-4 bg-gray-50 rounded-md">
              <p className="text-sm text-gray-600">
                📈 Yahoo Finance provides free stock market data.
                No API key required.
              </p>
            </div>
          )}
        </>
      )}

      <Button type="submit">Save Configuration</Button>
    </RHFProvider>
  );
} 