#!/usr/bin/env python3.10
"""
Factory Migration Example

This example shows how to migrate from the old data creation patterns
to the new standardized factory patterns while maintaining compatibility.
"""

import asyncio
import os
import sys

# Add the src directory to Python path for examples
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def old_way_example():
    """Example using the old API (still works)"""
    print("📜 Old Way (still supported):")
    print("-" * 30)

    # Old data source creation
    from StrateQueue.data.provider_factory import create_data_source

    provider = create_data_source("demo", granularity="1m")
    print(f"✅ Created provider: {type(provider).__name__}")
    print()


def new_factory_way_example():
    """Example using the new factory pattern"""
    print("🏭 New Factory Way (recommended):")
    print("-" * 35)

    # New factory approach
    from StrateQueue.data import (
        DataProviderConfig,
        DataProviderFactory,
        auto_create_provider,
        get_supported_providers,
    )

    # Method 1: Direct factory usage with configuration
    print("Method 1: Direct factory with config")
    config = DataProviderConfig(provider_type="demo", granularity="1m")
    provider1 = DataProviderFactory.create_provider("demo", config)
    print(f"  ✅ Created: {type(provider1).__name__}")

    # Method 2: Auto-detection based on environment
    print("Method 2: Auto-detection")
    provider2 = auto_create_provider(granularity="5m")
    print(f"  ✅ Auto-created: {type(provider2).__name__}")

    # Method 3: List available providers and choose
    print("Method 3: Provider selection")
    available = get_supported_providers()
    print(f"  Available providers: {available}")

    # Get provider information
    info = DataProviderFactory.get_provider_info("demo")
    print("  Demo provider info:")
    print(f"    Name: {info.name}")
    print(f"    Description: {info.description}")
    print(f"    Markets: {info.supported_markets}")
    print()


def comprehensive_factory_example():
    """Example showing all three factory systems working together"""
    print("🔧 Comprehensive Factory Usage:")
    print("-" * 35)

    # Data Provider Factory
    from StrateQueue.data import DataProviderConfig, DataProviderFactory

    data_config = DataProviderConfig(provider_type="demo", granularity="1m")
    data_provider = DataProviderFactory.create_provider("demo", data_config)
    print(f"📊 Data Provider: {type(data_provider).__name__}")

    # Broker Factory
    try:
        from StrateQueue.brokers import BrokerConfig, BrokerFactory

        BrokerConfig(broker_type="alpaca", paper_trading=True)
        # Note: This would fail without actual Alpaca credentials, but shows the pattern
        print(f"💰 Broker Factory available: {BrokerFactory.get_supported_brokers()}")
    except Exception as e:
        print(f"💰 Broker: {e}")

    # Engine Factory
    try:
        from StrateQueue.engines import EngineFactory

        engine = EngineFactory.create_engine("backtesting")
        print(f"⚙️  Engine: {type(engine).__name__}")
    except Exception as e:
        print(f"⚙️  Engine: {e}")

    print()


async def advanced_data_usage_example():
    """Example showing advanced data provider usage"""
    print("📈 Advanced Data Provider Usage:")
    print("-" * 35)

    # Create provider using factory
    from StrateQueue.data import DataProviderConfig, DataProviderFactory

    config = DataProviderConfig(provider_type="demo", granularity="1m")
    provider = DataProviderFactory.create_provider("demo", config)

    # Subscribe to symbols
    symbols = ["AAPL", "MSFT", "GOOGL"]
    for symbol in symbols:
        provider.subscribe_to_symbol(symbol)
        print(f"  📡 Subscribed to {symbol}")

    # Fetch some historical data
    print("  📊 Fetching historical data...")
    historical_data = await provider.fetch_historical_data("AAPL", days_back=1, granularity="1m")
    print(f"  ✅ Fetched {len(historical_data)} bars for AAPL")

    if len(historical_data) > 0:
        latest_price = historical_data["Close"].iloc[-1]
        print(f"  💰 Latest AAPL price: ${latest_price:.2f}")

    print()


def error_handling_example():
    """Example showing proper error handling with factories"""
    print("🚨 Error Handling Examples:")
    print("-" * 28)

    from StrateQueue.data import DataProviderFactory

    # Test invalid provider
    try:
        DataProviderFactory.create_provider("invalid_provider")
    except ValueError as e:
        print(f"  ❌ Expected error for invalid provider: {e}")

    # Test missing API key for providers that require it
    try:
        # This would fail if we tried to create a real API-based provider without credentials
        supported_providers = DataProviderFactory.get_supported_providers()
        print(f"  ✅ Supported providers: {supported_providers}")

        # Check if provider requires API key
        for provider_type in supported_providers:
            info = DataProviderFactory.get_provider_info(provider_type)
            if info and info.requires_api_key:
                print(f"  🔑 {provider_type} requires API key")
            else:
                print(f"  🆓 {provider_type} does not require API key")

    except Exception as e:
        print(f"  ❌ Error checking providers: {e}")

    print()


def migration_checklist():
    """Checklist for migrating to the new factory pattern"""
    print("📋 Migration Checklist:")
    print("-" * 23)
    print("  1. ✅ Existing code continues to work (backward compatibility)")
    print("  2. ✅ New factory classes available for new code")
    print("  3. ✅ Consistent API across brokers, engines, and data providers")
    print("  4. ✅ Environment-based auto-detection")
    print("  5. ✅ Standardized configuration objects")
    print("  6. ✅ Comprehensive error handling")
    print("  7. ✅ Provider/broker/engine information retrieval")
    print("  8. ✅ Easy extensibility for new providers")
    print()

    print("🔄 Migration Steps:")
    print("  1. Update imports to use factory classes")
    print("  2. Replace direct instantiation with factory methods")
    print("  3. Use configuration objects instead of direct parameters")
    print("  4. Take advantage of auto-detection features")
    print("  5. Add proper error handling")
    print()


async def main():
    """Main example function"""
    print("🏭 Data Provider Factory Migration Example")
    print("=" * 50)
    print()

    # Show both old and new ways
    old_way_example()
    new_factory_way_example()

    # Show comprehensive usage
    comprehensive_factory_example()

    # Show advanced features
    await advanced_data_usage_example()

    # Show error handling
    error_handling_example()

    # Show migration checklist
    migration_checklist()

    print("🎉 Migration example completed!")
    print()
    print("Key Benefits of Factory Pattern:")
    print("  🔄 Consistent API across all modules")
    print("  🔍 Auto-detection capabilities")
    print("  ⚙️  Standardized configuration")
    print("  🔌 Easy extensibility")
    print("  🔒 Backward compatibility")
    print("  🧪 Better testability")


if __name__ == "__main__":
    asyncio.run(main())
