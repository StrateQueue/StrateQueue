# Trading Engine Abstraction Layer

This directory contains the engine abstraction layer that allows the trading system to support multiple trading frameworks (backtesting.py, Zipline, backtrader, bt, etc.) through a unified interface.

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Strategy      │    │   Engine         │    │   Signal        │
│   Files         │───▶│   Detection      │───▶│   Extraction    │
│                 │    │                  │    │                 │
│ • sma.py        │    │ • Pattern Match  │    │ • TradingSignal │
│ • zipline.py    │    │ • Auto Creation  │    │ • Universal     │
│ • custom.py     │    │ • Validation     │    │ • Format        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                       │
         ▼                        ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Engine-Specific │    │ Abstract Base    │    │ Trading         │
│ Implementation  │    │ Classes          │    │ Execution       │
│                 │    │                  │    │                 │
│ • Load Strategy │    │ • TradingEngine  │    │ • Alpaca        │
│ • Extract Sigs  │    │ • EngineStrategy │    │ • Future Brokers│
│ • Convert Logic │    │ • SignalExtract  │    │ • Paper Trading │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 📁 File Structure

```
engines/
├── README.md                     # This documentation
├── __init__.py                   # Package exports
├── base.py                       # Abstract base classes
├── engine_factory.py             # Detection & factory logic
├── utils.py                      # Engine detection utilities
├── backtesting_engine.py         # Backtesting.py implementation
└── [future_engine].py            # Future engine implementations
```

## 🚀 Adding a New Trading Engine

Follow these steps to add support for a new trading framework:

### Step 1: Create Engine Implementation File

Create a new file `[engine_name]_engine.py` (e.g., `zipline_engine.py`) with the following structure:

```python
"""
[Engine Name] Engine Implementation

Implements the trading engine interface for [Engine Name] strategies.
"""

import pandas as pd
import logging
from typing import Type, Optional, Dict, Any

from .base import TradingEngine, EngineStrategy, EngineSignalExtractor, EngineInfo
from ..signal_extractor import TradingSignal, SignalType

logger = logging.getLogger(__name__)


class [EngineName]EngineStrategy(EngineStrategy):
    """Wrapper for [Engine Name] strategies"""
    
    def get_lookback_period(self) -> int:
        """Get the minimum number of bars required by this strategy"""
        # Implement engine-specific lookback calculation
        pass
    
    def get_strategy_name(self) -> str:
        """Get a human-readable name for this strategy"""
        pass
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get strategy parameters"""
        pass


class [EngineName]SignalExtractor(EngineSignalExtractor):
    """Signal extractor for [Engine Name] strategies"""
    
    def extract_signal(self, historical_data: pd.DataFrame) -> TradingSignal:
        """Extract trading signal from historical data"""
        # Implement engine-specific signal extraction
        pass
    
    def get_minimum_bars_required(self) -> int:
        """Get minimum number of bars needed for signal extraction"""
        pass


class [EngineName]Engine(TradingEngine):
    """Trading engine implementation for [Engine Name]"""
    
    def get_engine_info(self) -> EngineInfo:
        """Get information about this engine"""
        return EngineInfo(
            name="[Engine Display Name]",
            version="x.x.x",
            supported_features={
                "signal_extraction": True,
                "live_trading": True,
                "multi_strategy": True,
                "limit_orders": True,
                "stop_orders": False  # Example
            },
            description="Description of the trading engine"
        )
    
    def load_strategy_from_file(self, strategy_path: str) -> [EngineName]EngineStrategy:
        """Load a [Engine Name] strategy from file"""
        # Implement engine-specific strategy loading
        pass
    
    def create_signal_extractor(self, engine_strategy: [EngineName]EngineStrategy, 
                              **kwargs) -> [EngineName]SignalExtractor:
        """Create a signal extractor for [Engine Name] strategy"""
        pass
    
    def validate_strategy_file(self, strategy_path: str) -> bool:
        """Check if strategy file is compatible with [Engine Name]"""
        # Implement validation logic
        pass
    
    def calculate_lookback_period(self, strategy_path: str, 
                                default_lookback: int = 50) -> int:
        """Calculate required lookback period for strategy"""
        # Implement lookback calculation
        pass
```

### Step 2: Add Detection Patterns

Update `utils.py` to add detection patterns for your engine:

```python
def _detect_engine_indicators(content: str) -> Dict[str, List[str]]:
    # Add your engine patterns
    indicators = {
        'backtesting': [...],
        'zipline': [...],
        '[your_engine]': [],  # Add this
        'unknown': []
    }
    
    # [Your Engine] indicators
    your_engine_patterns = [
        (r'import\s+your_engine', 'imports your_engine'),
        (r'def\s+your_function\(', 'has your_function'),
        # Add more patterns...
    ]
    
    # Check your engine patterns
    for pattern, description in your_engine_patterns:
        if re.search(pattern, content, re.MULTILINE):
            indicators['[your_engine]'].append(description)
```

### Step 3: Register Engine in Factory

Update `engine_factory.py` to register your new engine:

```python
@classmethod
def _initialize_engines(cls):
    """Initialize available engines (lazy loading)"""
    if cls._initialized:
        return
        
    # Existing engines...
    
    # Your new engine
    try:
        from .[your_engine]_engine import [YourEngine]Engine
        cls._engines['[your_engine]'] = [YourEngine]Engine
        logger.debug("Registered [your_engine] engine")
    except ImportError as e:
        logger.warning(f"Could not load [your_engine] engine: {e}")
```

### Step 4: Update Package Exports

Add your engine to `__init__.py`:

```python
from .[your_engine]_engine import [YourEngine]Engine

__all__ = [
    # ... existing exports ...
    '[YourEngine]Engine'
]
```

### Step 5: Update Detection Logic

Update `utils.py` detection scoring in `detect_engine_from_analysis()`:

```python
def detect_engine_from_analysis(analysis: Dict[str, any]) -> str:
    indicators = analysis['engine_indicators']
    
    backtesting_score = len(indicators['backtesting'])
    zipline_score = len(indicators['zipline'])
    your_engine_score = len(indicators['[your_engine]'])  # Add this
    
    # Update scoring logic
    scores = {
        'backtesting': backtesting_score,
        'zipline': zipline_score,
        '[your_engine]': your_engine_score  # Add this
    }
    
    # Return highest scoring engine
    if max(scores.values()) > 0:
        return max(scores, key=scores.get)
    else:
        return 'unknown'
```

## 🧪 Testing Your New Engine

Create a test script to verify your engine works:

```python
#!/usr/bin/env python3

from StrateQueue.engines import (
    detect_engine_type, 
    EngineFactory,
    auto_create_engine
)

def test_your_engine():
    # Test detection
    strategy_file = "path/to/your/strategy.py"
    engine_type = detect_engine_type(strategy_file)
    print(f"Detected: {engine_type}")
    
    # Test creation
    engine = EngineFactory.create_engine('[your_engine]')
    info = engine.get_engine_info()
    print(f"Created: {info.name} v{info.version}")
    
    # Test strategy loading
    strategy = engine.load_strategy_from_file(strategy_file)
    print(f"Loaded: {strategy.get_strategy_name()}")
    
    # Test signal extraction
    extractor = engine.create_signal_extractor(strategy)
    # ... test with sample data

if __name__ == "__main__":
    test_your_engine()
```

## 🔍 Engine Implementation Examples

### Zipline Engine (Future Implementation)

```python
# Key Zipline patterns to detect:
zipline_patterns = [
    (r'def\s+initialize\s*\(\s*context\s*\)', 'has initialize(context)'),
    (r'def\s+handle_data\s*\(\s*context\s*,\s*data\s*\)', 'has handle_data'),
    (r'order_target_percent\(', 'uses order_target_percent'),
    (r'context\.\w+', 'uses context object'),
]

# Signal extraction approach:
# 1. Mock Zipline's order functions
# 2. Run initialize() and handle_data() 
# 3. Capture order calls and convert to TradingSignal
```

### Backtrader Engine (Future Implementation)

```python
# Key Backtrader patterns:
backtrader_patterns = [
    (r'import\s+backtrader', 'imports backtrader'),
    (r'class\s+\w+\(bt\.Strategy\)', 'inherits from bt.Strategy'),
    (r'def\s+next\(self\)', 'has next method'),
    (r'self\.buy\(\)', 'uses self.buy()'),
]

# Signal extraction approach:
# 1. Mock Cerebro and data feeds
# 2. Run strategy in test mode
# 3. Capture trade decisions
```

## 📋 Required Interface Implementation

Every new engine **must** implement these abstract methods:

### TradingEngine Interface
- `get_engine_info()` - Return engine metadata
- `load_strategy_from_file()` - Load strategy file into engine-specific wrapper
- `create_signal_extractor()` - Create signal extractor for strategies
- `validate_strategy_file()` - Check if file is compatible
- `calculate_lookback_period()` - Calculate required historical data

### EngineStrategy Interface  
- `get_lookback_period()` - Return minimum bars needed
- `get_strategy_name()` - Return human-readable name
- `get_parameters()` - Return strategy parameters

### EngineSignalExtractor Interface
- `extract_signal()` - Convert strategy logic to TradingSignal
- `get_minimum_bars_required()` - Return minimum data requirement

## 🎯 Key Design Principles

1. **Engine Independence** - Each engine is completely isolated
2. **Universal Signal Format** - All engines produce `TradingSignal` objects
3. **Automatic Detection** - Users don't need to specify engine types
4. **Backward Compatibility** - Existing workflows continue to work
5. **Lazy Loading** - Engines are only loaded when needed
6. **Error Graceful** - Missing engines don't break the system

## 🔧 Advanced Features



### Engine-Specific Configuration
```python
class YourEngineConfig:
    """Configuration specific to your engine"""
    def __init__(self):
        self.custom_setting = True
        self.optimization_level = "high"
```

### Multi-Strategy Support
```python
def supports_multi_strategy(self) -> bool:
    """Check if engine supports running multiple strategies"""
    return True  # or False based on engine capabilities
```

## 🚨 Common Pitfalls

1. **Don't modify** existing `TradingSignal` format - it's universal
2. **Don't break** backward compatibility with existing strategies
3. **Do handle** missing dependencies gracefully (use try/except in factory)
4. **Do add** comprehensive detection patterns
5. **Do test** with various strategy file formats
6. **Don't assume** specific data formats - be flexible

## 📚 Resources

- [Backtesting.py Documentation](https://kernc.github.io/backtesting.py/)
- [Zipline Documentation](https://zipline.ml4trading.io/)
- [Backtrader Documentation](https://www.backtrader.com/)
- [Trading Signal Format](../signal_extractor.py) - See `TradingSignal` class

## 🤝 Contributing

When adding a new engine:

1. Follow the step-by-step guide above
2. Add comprehensive tests
3. Update this documentation
4. Add example strategies for your engine
5. Submit a pull request with clear description

The engine abstraction layer is designed to be extensible and maintainable. Happy coding! 🚀 