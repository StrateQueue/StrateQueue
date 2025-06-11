"""
Information Formatter

Specialized formatter for displaying system information like brokers,
granularities, and other informational content.
"""

from typing import Dict, Any, List, Optional
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
                "  pip install stratequeue[trading]",
                "",
                "📊 Available Brokers (when installed):",
                "  • Alpaca - US stocks, ETFs, and crypto",
                "  • Interactive Brokers - Coming soon", 
                "  • Kraken - Coming soon",
                "",
                "💡 Quick Start:",
                "  1. Install dependencies: pip install stratequeue[trading]",
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
                from ...brokers.utils import get_broker_status
                status = get_broker_status()
                
                for broker, broker_status in status.items():
                    output.append(f"\n{broker.upper()}:")
                    for env_var, value in broker_status.items():
                        status_icon = "✅" if value else "❌"
                        output.append(f"  {status_icon} {env_var}: {'Set' if value else 'Not set'}")
                    
                    # Provide helpful guidance if not set up
                    if not any(broker_status.values()):
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
                "  pip install stratequeue[trading]",
                "",
                "💡 After installation:",
                "  stratequeue status      # Check your broker setup",
                "  stratequeue setup broker alpaca  # Get setup instructions"
            ])
        
        output.append("")
        return "\n".join(output)
    
    @staticmethod
    def format_broker_setup_instructions(broker_type: Optional[str] = None) -> str:
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
            from ...brokers.utils import get_setup_instructions
            
            if broker_type and broker_type != 'all':
                instructions = get_setup_instructions(broker_type)
                if instructions:
                    output.append(f"\n{broker_type.upper()} Setup:")
                    output.append(instructions)
                else:
                    output.extend([
                        "",
                        InfoFormatter.format_error(f"No setup instructions available for {broker_type}"),
                        "💡 Available brokers: alpaca, interactive_brokers, td_ameritrade"
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
                "  pip install stratequeue[trading]",
                "",
                "📋 Manual Setup (Alpaca Example):",
                "  1. Create account at alpaca.markets",
                "  2. Get API keys from dashboard", 
                "  3. Set environment variables:",
                "     export ALPACA_API_KEY='your_key_here'",
                "     export ALPACA_API_SECRET='your_secret_here'",
                "  4. For paper trading (recommended):",
                "     export ALPACA_BASE_URL='https://paper-api.alpaca.markets'",
                "  5. For live trading:",
                "     export ALPACA_BASE_URL='https://api.alpaca.markets'",
                "",
                "💡 After setup:",
                "  stratequeue status                    # Verify setup",
                "  stratequeue deploy --strategy sma.py --symbol AAPL --paper"
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
        output.append("  granularities   List supported data granularities by source")
        output.append("")
        output.append("Usage:")
        output.append("  stratequeue list brokers         # Show all supported brokers")
        output.append("  stratequeue list granularities  # Show data timeframe options")
        output.append("")
        output.append("Examples:")
        output.append("  stratequeue list brokers")
        output.append("  stratequeue list granularities")
        
        return "\n".join(output) 