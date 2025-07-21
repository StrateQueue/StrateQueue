# CCXT Broker Setup Guide

The CCXT broker provides access to 250+ cryptocurrency exchanges through a unified interface. This guide shows you how to set up and use CCXT with StrateQueue.

## Quick Setup

```bash
# Interactive setup with exchange selection menu
stratequeue setup broker

# Then select "CCXT (250+ cryptocurrency exchanges)"
```

## Exchange Selection Menu

When you select CCXT during setup, you'll see an interactive menu:

```
🏦 CCXT Exchange Selection
============================================================

Select a cryptocurrency exchange:

📈 Popular Exchanges:
   1. Binance          (binance) 🧪 
   2. Coinbase Pro     (coinbase) 🧪 🔑
   3. Kraken           (kraken) 🔴 
   4. Bybit            (bybit) 🧪 
   5. OKX              (okx) 🧪 🔑
   6. KuCoin           (kucoin) 🧪 🔑
   7. Huobi            (huobi) 🔴 
   8. Bitfinex         (bitfinex) 🔴 
   9. Gate.io          (gateio) 🔴 
  10. MEXC             (mexc) 🔴 

  11. 📝 Manual input (other exchange)
  12. ❌ Cancel

🧪 = Testnet/Sandbox available
🔑 = Requires passphrase
🔴 = Live trading only
```

### Top 10 Popular Exchanges

The setup menu shows the 10 most popular exchanges first for easy selection:

1. **Binance** - World's largest crypto exchange
2. **Coinbase Pro** - US-based, requires passphrase
3. **Kraken** - Established US exchange
4. **Bybit** - Popular derivatives exchange
5. **OKX** - Global exchange, requires passphrase
6. **KuCoin** - Global exchange, requires passphrase
7. **Huobi** - Asian exchange
8. **Bitfinex** - Advanced trading features
9. **Gate.io** - Wide selection of altcoins
10. **MEXC** - Emerging exchange

### Manual Input

If your exchange isn't in the top 10, select "Manual input" to enter any of the 240+ supported exchanges:

```
📝 Manual Exchange Input
--------------------------------------------------
Enter the exchange ID (e.g., 'bittrex', 'poloniex', 'gemini')
Type 'list' to see all supported exchanges
Type 'back' to return to the main menu

Exchange ID: gemini
✅ Valid exchange: gemini
```

## Environment Variables

After setup, CCXT uses these environment variables:

```bash
# Required
export CCXT_EXCHANGE=binance
export CCXT_API_KEY=your_api_key_here
export CCXT_SECRET_KEY=your_secret_key_here

# Optional
export CCXT_PASSPHRASE=your_passphrase  # For exchanges that require it
export CCXT_PAPER_TRADING=true          # Enable testnet/sandbox
```

## Exchange-Specific Setup

### Binance
```bash
# Get API keys from: https://www.binance.com/en/my/settings/api-management
export CCXT_EXCHANGE=binance
export CCXT_API_KEY=your_binance_api_key
export CCXT_SECRET_KEY=your_binance_secret_key
export CCXT_PAPER_TRADING=true  # Use testnet
```

### Coinbase Pro
```bash
# Get API keys from: https://pro.coinbase.com/profile/api
export CCXT_EXCHANGE=coinbase
export CCXT_API_KEY=your_coinbase_api_key
export CCXT_SECRET_KEY=your_coinbase_secret_key
export CCXT_PASSPHRASE=your_coinbase_passphrase  # Required!
export CCXT_PAPER_TRADING=true  # Use sandbox
```

### Kraken
```bash
# Get API keys from: https://www.kraken.com/u/security/api
export CCXT_EXCHANGE=kraken
export CCXT_API_KEY=your_kraken_api_key
export CCXT_SECRET_KEY=your_kraken_secret_key
# Note: Kraken doesn't have testnet
```

## Deployment

Once configured, you can deploy strategies using CCXT:

```bash
# Use generic CCXT broker
stratequeue deploy --broker ccxt

# Use exchange-specific syntax
stratequeue deploy --broker ccxt.binance
stratequeue deploy --broker ccxt.coinbase
stratequeue deploy --broker ccxt.kraken
```

## Testing Your Setup

```bash
# Check broker status
stratequeue status

# List available brokers
stratequeue list brokers

# Test with a simple strategy
stratequeue deploy --broker ccxt.binance --paper
```

## Troubleshooting

### Connection Issues
- Verify your API keys are correct
- Check that API keys have trading permissions
- For testnet, ensure sandbox is enabled for your API key
- Some exchanges require IP whitelisting

### Exchange-Specific Issues

**Coinbase Pro:**
- Must include passphrase
- API key needs "trade" permission
- Sandbox available at https://public.sandbox.pro.coinbase.com

**Binance:**
- Enable "Enable Trading" permission
- Testnet available at https://testnet.binance.vision

**Kraken:**
- Requires "Create & modify orders" permission
- No testnet available

### Rate Limits
CCXT automatically handles rate limiting, but you may need to:
- Reduce trading frequency
- Upgrade to higher API tier
- Use multiple API keys (advanced)

## Supported Features

| Feature | Support |
|---------|---------|
| Market Orders | ✅ |
| Limit Orders | ✅ |
| Stop Orders | ⚠️ Exchange dependent |
| Paper Trading | ⚠️ Exchange dependent |
| Multiple Strategies | ✅ |
| Real-time Data | ✅ |
| Order Management | ✅ |

## Next Steps

1. **Set up your exchange**: `stratequeue setup broker`
2. **Test connection**: `stratequeue status`
3. **Deploy a strategy**: `stratequeue deploy --broker ccxt.your_exchange`
4. **Monitor performance**: Use StrateQueue's built-in monitoring

For more advanced configuration and troubleshooting, see the [CCXT Documentation](https://docs.ccxt.com/).