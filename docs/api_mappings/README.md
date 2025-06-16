# API Cross-Reference Mappings

This directory contains cross-reference mappings between different broker APIs and backtesting engine APIs. These "Rosetta Stone" documents help developers translate concepts, parameters, and workflows between different platforms.

## Purpose

When working with multiple brokers and backtesting engines, developers often need to:
- Translate order types between platforms
- Map broker-specific parameters to engine-specific equivalents
- Understand how different platforms handle similar concepts
- Port strategies from backtesting to live trading

## Structure

### Broker-to-Engine Mappings
Files that map broker APIs to backtesting engine APIs:
- `alpaca_to_backtesting_py.md` - Alpaca Trading API ↔ backtesting.py
- `interactive_brokers_to_backtrader.md` - Interactive Brokers ↔ backtrader
- `td_ameritrade_to_zipline.md` - TD Ameritrade ↔ Zipline
- etc.

### Engine-to-Engine Mappings
Files that map between different backtesting engines:
- `backtesting_py_to_backtrader.md` - backtesting.py ↔ backtrader
- `zipline_to_backtrader.md` - Zipline ↔ backtrader
- etc.

### Broker-to-Broker Mappings
Files that map between different broker APIs:
- `alpaca_to_interactive_brokers.md` - Alpaca ↔ Interactive Brokers
- `td_ameritrade_to_schwab.md` - TD Ameritrade ↔ Charles Schwab
- etc.

## Usage

Each mapping file contains:
1. **Order Types Cross-Reference** - How to create equivalent orders
2. **Parameter Mappings** - Field-by-field translations
3. **State Management** - How to query/modify orders and positions
4. **Code Examples** - Side-by-side comparisons
5. **Limitations** - Features that don't translate directly

## Contributing

When adding a new broker or engine to StrateQueue:
1. Create the appropriate mapping file(s)
2. Follow the established template format
3. Include practical code examples
4. Document any platform-specific limitations
5. Update this README with the new file(s)

## Template

See `template.md` for the standard format when creating new mapping files. 