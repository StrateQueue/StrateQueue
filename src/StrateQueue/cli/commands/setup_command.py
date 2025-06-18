"""
Setup Command

Command for configuring broker credentials and system settings.
"""

import argparse
from pathlib import Path

try:
    from questionary import password, select, text

    QUESTIONARY_AVAILABLE = True
except ImportError:
    QUESTIONARY_AVAILABLE = False

from ..formatters import InfoFormatter
from .base_command import BaseCommand


class SetupCommand(BaseCommand):
    """
    Setup command implementation

    Provides interactive setup for brokers and system configuration.
    """

    @property
    def name(self) -> str:
        return "setup"

    @property
    def description(self) -> str:
        return "Configure brokers and system settings interactively"

    @property
    def aliases(self) -> list[str]:
        return ["config", "configure"]

    def setup_parser(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Configure setup command arguments"""

        parser.add_argument(
            "setup_type",
            nargs="?",
            default=None,
            choices=["broker", "data-provider", "data"],
            help="Type of setup to perform (interactive menu if not provided)",
        )

        parser.add_argument(
            "provider_name",
            nargs="?",
            help="Specific broker or data provider to setup (interactive if not provided)",
        )

        parser.add_argument(
            "--docs",
            "-d",
            action="store_true",
            help="Show documentation instead of interactive setup",
        )

        return parser

    def validate_args(self, args: argparse.Namespace) -> list[str] | None:
        """Validate setup command arguments"""
        if not QUESTIONARY_AVAILABLE and not args.docs:
            return [
                "Interactive setup requires 'questionary' package. Install with: pip install questionary"
            ]
        return None

    def execute(self, args: argparse.Namespace) -> int:
        """Execute setup command"""

        setup_type = getattr(args, "setup_type", None)
        provider_name = getattr(args, "provider_name", None)
        show_docs = getattr(args, "docs", False)

        # If no setup type specified, show interactive menu
        if setup_type is None and not show_docs:
            if not QUESTIONARY_AVAILABLE:
                print("❌ Interactive setup requires 'questionary' package.")
                print("💡 Install with: pip install questionary")
                print("💡 Or use: stratequeue setup --docs")
                return 1

            return self._interactive_main_menu()

        # Normalize setup type
        if setup_type in ["data", "data-provider"]:
            setup_type = "data-provider"

        # Handle documentation requests
        if show_docs:
            if setup_type == "broker":
                print(InfoFormatter.format_broker_setup_instructions(provider_name))
            elif setup_type == "data-provider":
                self._show_data_provider_docs(provider_name)
            else:
                self._show_general_docs()
            return 0

        # Handle specific setup types
        if setup_type == "broker":
            if not QUESTIONARY_AVAILABLE:
                print("❌ Interactive setup requires 'questionary' package.")
                print("💡 Install with: pip install questionary")
                print("💡 Or use: stratequeue setup broker --docs")
                return 1

            broker_name = self._interactive_broker_setup()
            if broker_name:
                print(f"✅ {broker_name.capitalize()} credentials saved.")
                print("💡 Test your setup with: stratequeue status")
                return 0
            else:
                print("⚠️  Setup cancelled.")
                return 130

        elif setup_type == "data-provider":
            if not QUESTIONARY_AVAILABLE:
                print("❌ Interactive setup requires 'questionary' package.")
                print("💡 Install with: pip install questionary")
                print("💡 Or use: stratequeue setup data-provider --docs")
                return 1

            provider_name = self._interactive_data_provider_setup()
            if provider_name:
                print(f"✅ {provider_name.capitalize()} credentials saved.")
                print("💡 Test your setup with: stratequeue status")
                return 0
            else:
                print("⚠️  Setup cancelled.")
                return 130

        else:
            print(InfoFormatter.format_error(f"Unknown setup type: {setup_type}"))
            print("💡 Try: stratequeue setup")
            return 1

    def _interactive_broker_setup(self) -> str | None:
        """
        Interactive broker setup flow with questionary

        Returns:
            Broker name if successful, None if cancelled
        """
        try:
            # Get supported brokers dynamically
            from ...brokers import get_supported_brokers

            brokers = get_supported_brokers()

            if not brokers:
                print("❌ No brokers available in this build.")
                return None

            # Create friendly broker choices
            broker_choices = []
            broker_map = {}
            for broker in brokers:
                if broker == "alpaca":
                    display_name = "Alpaca (US stocks, ETFs, crypto)"
                    broker_choices.append(display_name)
                    broker_map[display_name] = broker
                else:
                    # Future brokers
                    display_name = f"{broker.title()} (Coming soon)"
                    broker_choices.append(display_name)
                    broker_map[display_name] = broker

            print("\n🔧 StrateQueue Broker Setup")
            print("=" * 50)

            # Select broker
            broker_choice = select("Select broker to configure:", choices=broker_choices).ask()

            if broker_choice is None:
                return None

            broker = broker_map[broker_choice]

            if broker == "alpaca":
                return self._setup_alpaca()
            else:
                print(f"❌ {broker.title()} setup not yet implemented.")
                return None

        except KeyboardInterrupt:
            return None
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            return None

    def _setup_alpaca(self) -> str | None:
        """Setup Alpaca broker credentials"""
        print("\n📋 Alpaca Setup")
        print("Get your API keys from: https://app.alpaca.markets/")
        print()

        # Trading mode selection
        mode_choice = select(
            "Select trading mode:",
            choices=[
                "Paper Trading (fake money - recommended for testing)",
                "Live Trading (real money - use with caution!)",
            ],
        ).ask()

        if mode_choice is None:
            return None

        is_paper = "Paper Trading" in mode_choice

        # Get credentials
        if is_paper:
            print("\n🔑 Enter your Paper Trading credentials:")
            api_key = text("Paper API Key:").ask()
            secret_key = password("Paper Secret Key:").ask()
        else:
            print("\n🔑 Enter your Live Trading credentials:")
            print("⚠️  WARNING: This will enable REAL MONEY trading!")
            confirm = select(
                "Are you sure you want to configure live trading?",
                choices=["No, use paper trading instead", "Yes, I understand the risks"],
            ).ask()

            if confirm != "Yes, I understand the risks":
                print("🔄 Switching to paper trading...")
                is_paper = True
                api_key = text("Paper API Key:").ask()
                secret_key = password("Paper Secret Key:").ask()
            else:
                api_key = text("Live API Key:").ask()
                secret_key = password("Live Secret Key:").ask()

        if not api_key or not secret_key:
            print("❌ API key and secret key are required.")
            return None

        # Prepare environment variables
        if is_paper:
            env_vars = {
                "PAPER_KEY": api_key,
                "PAPER_SECRET": secret_key,
                "PAPER_ENDPOINT": "https://paper-api.alpaca.markets",
            }
        else:
            env_vars = {
                "ALPACA_API_KEY": api_key,
                "ALPACA_SECRET_KEY": secret_key,
                "ALPACA_BASE_URL": "https://api.alpaca.markets",
            }

        # Save credentials
        self._write_env_file(env_vars)

        return "alpaca"

    def _write_env_file(self, new_vars: dict) -> None:
        """
        Save key/value pairs to ~/.stratequeue/credentials.env
        Preserves existing variables that aren't being updated.

        Args:
            new_vars: Dictionary of environment variables to save
        """
        cfg_dir = Path.home() / ".stratequeue"
        cfg_dir.mkdir(exist_ok=True)
        env_file = cfg_dir / "credentials.env"

        # Read existing variables
        existing_vars = {}
        if env_file.exists():
            try:
                for line in env_file.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        existing_vars[key.strip()] = value.strip()
            except Exception as e:
                print(f"⚠️  Warning: Could not read existing credentials: {e}")

        # Update with new variables
        existing_vars.update(new_vars)

        # Write back to file
        try:
            lines = []
            lines.append("# StrateQueue Credentials")
            lines.append("# Generated by: stratequeue setup")
            lines.append("")

            for key, value in existing_vars.items():
                lines.append(f"{key}={value}")

            env_file.write_text("\n".join(lines) + "\n")
            print(f"🔒 Credentials saved to {env_file}")

        except Exception as e:
            print(f"❌ Failed to save credentials: {e}")
            # Fallback: show environment variables to set manually
            print("\n💡 Please set these environment variables manually:")
            for key, value in new_vars.items():
                print(f"export {key}={value}")

    def _interactive_main_menu(self) -> int:
        """
        Interactive main menu for setup selection

        Returns:
            Exit code
        """
        try:
            print("\n🔧 StrateQueue Setup")
            print("=" * 50)

            setup_choice = select(
                "What would you like to configure?",
                choices=[
                    "Broker (trading platform credentials)",
                    "Data Provider (market data API keys)",
                ],
            ).ask()

            if setup_choice is None:
                return 130

            if "Broker" in setup_choice:
                broker_name = self._interactive_broker_setup()
                if broker_name:
                    print(f"✅ {broker_name.capitalize()} credentials saved.")
                    print("💡 Test your setup with: stratequeue status")
                    return 0
                else:
                    print("⚠️  Setup cancelled.")
                    return 130

            elif "Data Provider" in setup_choice:
                provider_name = self._interactive_data_provider_setup()
                if provider_name:
                    print(f"✅ {provider_name.capitalize()} credentials saved.")
                    print("💡 Test your setup with: stratequeue status")
                    return 0
                else:
                    print("⚠️  Setup cancelled.")
                    return 130

        except KeyboardInterrupt:
            return 130
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            return 1

    def _interactive_data_provider_setup(self) -> str | None:
        """
        Interactive data provider setup flow with questionary

        Returns:
            Provider name if successful, None if cancelled
        """
        try:
            # Get supported data providers dynamically
            from ...data import get_supported_providers

            providers = get_supported_providers()

            if not providers:
                print("❌ No data providers available in this build.")
                return None

            # Create friendly provider choices - skip demo for setup
            provider_choices = []
            provider_map = {}
            for provider in providers:
                if provider == "polygon":
                    display_name = "Polygon (stocks, crypto, forex - premium)"
                    provider_choices.append(display_name)
                    provider_map[display_name] = provider
                elif provider == "coinmarketcap":
                    display_name = "CoinMarketCap (cryptocurrency data)"
                    provider_choices.append(display_name)
                    provider_map[display_name] = provider
                # Skip demo provider in setup - it doesn't need credentials

            if not provider_choices:
                print("❌ No data providers requiring setup found.")
                print("💡 Demo provider is available without credentials.")
                return None

            print("\n📊 StrateQueue Data Provider Setup")
            print("=" * 50)

            # Select provider
            provider_choice = select(
                "Select data provider to configure:", choices=provider_choices
            ).ask()

            if provider_choice is None:
                return None

            provider = provider_map[provider_choice]

            if provider == "polygon":
                return self._setup_polygon()
            elif provider == "coinmarketcap":
                return self._setup_coinmarketcap()
            else:
                print(f"❌ {provider.title()} setup not yet implemented.")
                return None

        except KeyboardInterrupt:
            return None
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            return None

    def _setup_polygon(self) -> str | None:
        """Setup Polygon data provider credentials"""
        print("\n📋 Polygon.io Setup")
        print("Get your API key from: https://polygon.io/")
        print("💡 Free tier available with rate limits")
        print()

        # Get API key
        api_key = text("Polygon API Key:").ask()

        if not api_key:
            print("❌ API key is required.")
            return None

        # Prepare environment variables
        env_vars = {"POLYGON_API_KEY": api_key, "DATA_PROVIDER": "polygon"}

        # Save credentials
        self._write_env_file(env_vars)

        return "polygon"

    def _setup_coinmarketcap(self) -> str | None:
        """Setup CoinMarketCap data provider credentials"""
        print("\n📋 CoinMarketCap Setup")
        print("Get your API key from: https://pro.coinmarketcap.com/")
        print("💡 Free tier: 333 requests/day")
        print()

        # Get API key
        api_key = text("CoinMarketCap API Key:").ask()

        if not api_key:
            print("❌ API key is required.")
            return None

        # Prepare environment variables
        env_vars = {"CMC_API_KEY": api_key, "DATA_PROVIDER": "coinmarketcap"}

        # Save credentials
        self._write_env_file(env_vars)

        return "coinmarketcap"

    def _show_data_provider_docs(self, provider_name: str | None = None) -> None:
        """Show data provider setup documentation"""
        print("\n📊 Data Provider Setup Documentation")
        print("=" * 50)

        if provider_name == "polygon":
            print("\n🔸 Polygon.io Setup:")
            print("1. Visit: https://polygon.io/")
            print("2. Sign up for an account (free tier available)")
            print("3. Navigate to API Keys section")
            print("4. Copy your API key")
            print("5. Set environment variable: export POLYGON_API_KEY=your_key_here")
            print("\nSupported markets: Stocks, Crypto, Forex")
            print("Rate limits: Depends on your plan")

        elif provider_name == "coinmarketcap":
            print("\n🔸 CoinMarketCap Setup:")
            print("1. Visit: https://pro.coinmarketcap.com/")
            print("2. Sign up for an account (free tier: 333 requests/day)")
            print("3. Navigate to API section")
            print("4. Copy your API key")
            print("5. Set environment variable: export CMC_API_KEY=your_key_here")
            print("\nSupported markets: Cryptocurrency")
            print("Rate limits: 333 requests/day (free tier)")

        else:
            print("\n🔸 Available Data Providers:")
            print()
            print("📈 Polygon.io")
            print("   - Stocks, crypto, forex data")
            print("   - Free tier available")
            print("   - Setup: stratequeue setup data-provider --docs polygon")
            print()
            print("🪙 CoinMarketCap")
            print("   - Cryptocurrency market data")
            print("   - Free tier: 333 requests/day")
            print("   - Setup: stratequeue setup data-provider --docs coinmarketcap")
            print()
            print("🧪 Demo Provider")
            print("   - Simulated data for testing")
            print("   - No API key required")
            print("   - Automatically available")

        print("\n💡 Interactive setup: stratequeue setup data-provider")

    def _show_general_docs(self) -> None:
        """Show general setup documentation"""
        print("\n🔧 StrateQueue Setup Documentation")
        print("=" * 50)
        print()
        print("🔸 Available Setup Options:")
        print()
        print("📊 Data Providers:")
        print("   stratequeue setup data-provider")
        print("   Configure market data sources (Polygon, CoinMarketCap)")
        print()
        print("💼 Brokers:")
        print("   stratequeue setup broker")
        print("   Configure trading platforms (Alpaca)")
        print()
        print("🔸 Interactive Setup:")
        print("   stratequeue setup")
        print("   Choose from menu of available options")
        print()
        print("💡 For specific documentation:")
        print("   stratequeue setup broker --docs")
        print("   stratequeue setup data-provider --docs polygon")
