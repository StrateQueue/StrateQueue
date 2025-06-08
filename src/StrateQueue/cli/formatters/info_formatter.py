"""
Information Formatter

Specialized formatter for displaying system information like brokers,
granularities, and other informational content.
"""

from .base_formatter import BaseFormatter


class InfoFormatter(BaseFormatter):
    """
    Formatter for information display commands (list, status, etc.)
    """

    @staticmethod
    def format_granularity_info() -> str:
        """
        Format granularity information for display

        Returns:
            Formatted granularity information
        """
        try:
            from ...core.granularity import GranularityParser
        except ImportError:
            return InfoFormatter.format_error(
                "Granularity information not available (missing dependencies)"
            )

        output = []
        output.append(InfoFormatter.format_header("Supported granularities by data source"))

        for source in ["polygon", "coinmarketcap", "demo"]:
            granularities = GranularityParser.get_supported_granularities(source)
            output.append(f"\n{source.upper()}:")
            output.append(f"  Supported: {', '.join(granularities)}")

            if source == "polygon":
                output.append("  Default: 1m (very flexible with most timeframes)")
            elif source == "coinmarketcap":
                output.append("  Default: 1d (historical), supports intraday real-time simulation")
            elif source == "demo":
                output.append("  Default: 1m (can generate any granularity)")

        output.append("\nExample granularity formats:")
        examples = [
            "  1s   = 1 second",
            "  30s  = 30 seconds",
            "  1m   = 1 minute",
            "  5m   = 5 minutes",
            "  1h   = 1 hour",
            "  1d   = 1 day"
        ]
        output.extend(examples)
        output.append("")

        return "\n".join(output)

    @staticmethod
    def format_broker_info() -> str:
        """
        Format broker information for display

        Returns:
            Formatted broker information
        """
        output = []
        output.append("📊 Supported Brokers:")
        output.append("=" * 50)

        try:
            from ...brokers import list_broker_features
            broker_info = list_broker_features()

            for broker_name, info in broker_info.items():
                output.append(f"\n{broker_name.upper()}:")
                output.append(f"  Name: {info.name}")
                output.append(f"  Description: {info.description}")
                output.append(f"  Paper Trading: {'✅' if info.paper_trading else '❌'}")
                output.append(f"  Markets: {', '.join(info.supported_markets)}")

                # Show key features
                features = info.supported_features
                if features:
                    key_features = []
                    if features.get('market_orders'): key_features.append('Market Orders')
                    if features.get('limit_orders'): key_features.append('Limit Orders')
                    if features.get('crypto_trading'): key_features.append('Crypto')
                    if features.get('options_trading'): key_features.append('Options')
                    if features.get('futures_trading'): key_features.append('Futures')

                    if key_features:
                        output.append(f"  Features: {', '.join(key_features)}")

        except ImportError:
            output.extend([
                "",
                InfoFormatter.format_error("Broker information not available (missing dependencies)"),
                "",
                "🔧 To enable broker support:",
                "  pip install stratequeue",
                "",
                "📊 Available Brokers (when installed):",
                "  • Alpaca - US stocks, ETFs, and crypto",
                "  • Interactive Brokers (ibkr, IBKR, interactive-brokers)",
                "  • Kraken - Coming soon",
                "",
                "💡 Quick Start:",
                "  1. Install dependencies: pip install stratequeue",
                "  2. Setup broker: stratequeue setup broker alpaca",
                "  3. Check status: stratequeue status"
            ])

        output.append("")
        return "\n".join(output)

    @staticmethod
    def format_broker_status() -> str:
        """
        Format broker status information for display

        Returns:
            Formatted broker status
        """
        output = []
        output.append("🔍 Broker Environment Status:")
        output.append("=" * 50)

        try:
            from ...brokers import get_supported_brokers

            # Try to get actual broker status
            try:
                from ...brokers.broker_helpers import get_broker_environment_status, get_alpaca_config_from_env

                # Retrieve full status information
                full_status = get_broker_environment_status()

                # Only display brokers that are actually implemented/supported
                supported = set(get_supported_brokers())

                for broker in supported:
                    broker_info = full_status.get(
                        broker,
                        {
                            'detected': False,
                            'valid': False,
                            'error_message': 'Status not available',
                        },
                    )

                    output.append(f"\n{broker.upper()}:")

                    # Basic detection/validation summary
                    if broker_info.get('detected') and broker_info.get('valid'):
                        output.append("  ✅ Detected and configured")
                    elif broker_info.get('detected') and not broker_info.get('valid'):
                        output.append(
                            f"  ⚠️  Detected but invalid: {broker_info.get('error_message', 'Unknown error')}"
                        )
                    else:
                        output.append(
                            f"  ❌ Not detected: {broker_info.get('error_message', 'Credentials not found')}"
                        )

                    # Extra details for specific brokers
                    if broker == 'alpaca' and broker_info.get('detected'):
                        try:
                            alpaca_cfg = get_alpaca_config_from_env()
                            trading_mode = 'Paper' if alpaca_cfg.get('paper_trading', True) else 'Live'
                            output.append(f"  Trading Mode: {trading_mode}")
                        except Exception:  # pragma: no cover
                            pass

                    # Provide setup help for brokers that aren't valid/configured yet
                    if not broker_info.get('valid'):
                        output.append(f"  💡 Setup help: stratequeue setup broker {broker}")

            except (ImportError, AttributeError):
                # Fallback: show supported brokers without status
                supported = get_supported_brokers()
                for broker_name in supported:
                    output.append(f"\n{broker_name.upper()}:")
                    output.append("  ❓ Status check not available")
                    output.append(f"  💡 Setup help: stratequeue setup broker {broker_name}")

        except ImportError:
            output.extend([
                "",
                InfoFormatter.format_error("Broker status check not available (missing dependencies)"),
                "",
                "🔧 To check broker status:",
                "  pip install stratequeue",
                "",
                "💡 After installation:",
                "  stratequeue status      # Check your broker setup",
                "  stratequeue setup broker alpaca  # Get setup instructions"
            ])

        output.append("")
        return "\n".join(output)

    @staticmethod
    def format_engine_info() -> str:
        """
        Format trading engine information for display

        Returns:
            Formatted engine information
        """
        output = []
        output.append("🔧 Available Trading Engines:")
        output.append("=" * 50)

        try:
            from ...engines import get_supported_engines, get_unavailable_engines, get_all_known_engines

            # Get engine information
            supported = get_supported_engines()
            unavailable = get_unavailable_engines()
            all_known = get_all_known_engines()

            # Show supported engines first
            if supported:
                output.append("\n✅ AVAILABLE ENGINES:")
                for engine in supported:
                    output.append(f"  • {engine.capitalize()}")
                    
                    # Add engine-specific descriptions
                    if engine == "backtesting":
                        output.append("    - Fast vectorized backtesting with Pandas")
                        output.append("    - Best for: Simple strategies, quick prototyping")
                    elif engine == "vectorbt":
                        output.append("    - High-performance vectorized backtesting")
                        output.append("    - Best for: Complex strategies, large datasets")
                    elif engine == "zipline":
                        output.append("    - Algorithmic trading library by Quantopian")
                        output.append("    - Best for: Professional strategies, research")
                    elif engine == "backtrader":
                        output.append("    - Feature-rich backtesting platform")
                        output.append("    - Best for: Advanced analysis, multiple assets")

            # Show unavailable engines with installation hints
            if unavailable:
                output.append("\n❌ UNAVAILABLE ENGINES:")
                for engine, reason in unavailable.items():
                    output.append(f"  • {engine.capitalize()}")
                    output.append(f"    - Status: {reason}")

            # Show usage examples
            output.append("\n💡 USAGE EXAMPLES:")
            output.append("  # Auto-detect engine from strategy file")
            output.append("  stratequeue deploy --strategy my_strategy.py --symbol AAPL")
            output.append("")
            output.append("  # Force specific engine")
            output.append("  stratequeue deploy --engine vectorbt --strategy my_vbt_strategy.py --symbol BTC-USD")
            output.append("")
            output.append("  # List supported engines")
            output.append("  stratequeue list engines")

        except ImportError:
            output.extend([
                "",
                InfoFormatter.format_error("Engine information not available (missing dependencies)"),
                "",
                "🔧 To enable engine support:",
                "  pip install stratequeue[vectorbt]    # For VectorBT",
                "  pip install stratequeue[zipline]     # For Zipline-Reloaded", 
                "  pip install stratequeue[backtrader]  # For Backtrader",
                "",
                "📊 Engine Features (when installed):",
                "  • backtesting.py - Fast, simple backtesting",
                "  • VectorBT - High-performance vectorized analysis",
                "  • Zipline - Professional algorithmic trading",
                "  • Backtrader - Advanced strategy development"
            ])

        output.append("")
        return "\n".join(output)

    @staticmethod
    def format_broker_setup_instructions(broker_type: str | None = None) -> str:
        """
        Format broker setup instructions

        Args:
            broker_type: Specific broker type or None for all

        Returns:
            Formatted setup instructions
        """
        output = []
        output.append("🔧 Broker Setup Instructions:")
        output.append("=" * 50)

        try:
            from ...brokers.broker_helpers import get_setup_instructions

            if broker_type and broker_type != 'all':
                instructions = get_setup_instructions(broker_type)
                if instructions:
                    output.append(f"\n{broker_type.upper()} Setup:")
                    output.append(instructions)
                else:
                    output.extend([
                        "",
                        InfoFormatter.format_error(f"No setup instructions available for {broker_type}"),
                        "💡 Available brokers: alpaca, ibkr, IBKR, interactive-brokers"
                    ])
            else:
                # Show all broker setup instructions
                all_instructions = get_setup_instructions()
                for broker, instructions in all_instructions.items():
                    output.append(f"\n{broker.upper()} Setup:")
                    output.append(instructions)
                    output.append("-" * 30)

        except ImportError:
            output.extend([
                "",
                InfoFormatter.format_error("Broker setup instructions not available (missing dependencies)"),
                "",
                "🔧 To get setup instructions:",
                "  pip install stratequeue",
                "",
                "📋 Manual Setup (Alpaca Paper Trading):",
                "  1. Create account at alpaca.markets",
                "  2. Get API keys from dashboard",
                "  3. Set environment variables for paper trading:",
                "     export PAPER_KEY='your_paper_key_here'",
                "     export PAPER_SECRET='your_paper_secret_here'",
                "     export PAPER_ENDPOINT='https://paper-api.alpaca.markets/v2'",
                "",
                "📋 Alternative Setup (Live Trading - Use with caution):",
                "  3. Set environment variables for live trading:",
                "     export ALPACA_API_KEY='your_live_key_here'",
                "     export ALPACA_SECRET_KEY='your_live_secret_here'",
                "     export ALPACA_BASE_URL='https://api.alpaca.markets'",
                "",
                "💡 After setup:",
                "  source .env  # or export $(cat .env | xargs)",
                "  stratequeue status                    # Verify setup",
                "  stratequeue deploy --strategy sma.py --symbol AAPL --paper"
            ])

        output.append("")
        return "\n".join(output)

    @staticmethod
    def format_provider_info() -> str:
        """
        Format data provider information for display

        Returns:
            Formatted provider information
        """
        output: list[str] = []
        output.append("📊 Supported Data Providers:")
        output.append("=" * 50)

        try:
            from ...data.provider_factory import list_provider_features

            provider_info = list_provider_features()

            if not provider_info:
                output.append("No data providers found.")
            else:
                for provider_name, info in provider_info.items():
                    output.append(f"\n{provider_name.upper()}:")
                    output.append(f"  Name: {info.name}")
                    output.append(f"  Description: {info.description}")
                    output.append(f"  Markets: {', '.join(info.supported_markets)}")

                    # Key features summary
                    if info.supported_features:
                        enabled_features = [k.replace('_', ' ').title() for k, v in info.supported_features.items() if v]
                        if enabled_features:
                            output.append(f"  Features: {', '.join(enabled_features)}")

                    output.append(f"  Requires API Key: {'✅' if info.requires_api_key else '❌'}")

        except ImportError:
            output.extend([
                "",
                InfoFormatter.format_error("Data provider information not available (missing dependencies)"),
                "",
                "🔧 To enable data provider support:",
                "  pip install stratequeue[providers]",
                "",
            ])

        output.append("")
        return "\n".join(output)

    @staticmethod
    def format_provider_status() -> str:
        """
        Format data provider environment status for display.

        This checks whether each implemented data provider is supported by the
        codebase and whether the necessary credentials (e.g. API keys) are
        available in the current environment.

        Returns:
            Human-readable provider status string
        """
        import os

        output: list[str] = []
        output.append("🔍 Data Provider Environment Status:")
        output.append("=" * 50)

        try:
            from ...data.provider_factory import get_supported_providers

            supported_providers = get_supported_providers()

            for provider in supported_providers:
                output.append(f"\n{provider.upper()}:")

                configured = False
                error_msg = ""

                # Basic credential detection per provider
                if provider == "polygon":
                    configured = bool(os.getenv("POLYGON_API_KEY"))
                    if not configured:
                        error_msg = "No POLYGON_API_KEY found in environment"

                elif provider == "coinmarketcap":
                    configured = bool(os.getenv("CMC_API_KEY"))
                    if not configured:
                        error_msg = "No CMC_API_KEY found in environment"

                elif provider == "demo":
                    # Demo provider never needs credentials
                    configured = True

                elif provider == "yfinance":
                    # yfinance is public – no credentials necessary
                    configured = True

                else:
                    # Fallback for future providers – assume not configured
                    error_msg = "Credential check not implemented"

                if configured:
                    output.append("  ✅ Detected and configured")
                else:
                    output.append(f"  ❌ Not detected: {error_msg}")
                    output.append(f"  💡 Setup help: export REQUIRED_ENV_VARS_FOR_{provider.upper()}")

        except ImportError:
            output.extend([
                "",
                InfoFormatter.format_error("Data provider status check not available (missing dependencies)"),
                "",
                "🔧 To check provider status:",
                "  pip install stratequeue[providers]",
            ])

        output.append("")
        return "\n".join(output)

    @staticmethod
    def format_command_help() -> str:
        """
        Format available commands help

        Returns:
            Formatted command help
        """
        output = []
        output.append("📋 StrateQueue Available Commands")
        output.append("=" * 50)
        output.append("Available list commands:")
        output.append("  brokers         List supported brokers and their features")
        output.append("  providers       List supported data providers")
        output.append("")
        output.append("Usage:")
        output.append("  stratequeue list brokers         # Show all supported brokers")
        output.append("  stratequeue list providers       # Show available data providers")
        output.append("")
        output.append("Examples:")
        output.append("  stratequeue list brokers")
        output.append("  stratequeue list providers")

        return "\n".join(output)
