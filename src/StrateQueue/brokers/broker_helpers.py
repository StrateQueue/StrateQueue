"""
Broker Utility Functions

Utilities for broker detection, credential validation, and environment setup.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def detect_broker_from_environment() -> str | None:
    """
    Detect which broker to use based on environment variables

    Returns:
        Broker type name ('alpaca', 'interactive_brokers', etc.) or None if no broker detected
    """

    # Check for Alpaca credentials (support multiple environment variable names)
    paper_key = (
        os.getenv('PAPER_KEY') or
        os.getenv('PAPER_API_KEY') or
        os.getenv('ALPACA_API_KEY')
    )
    paper_secret = (
        os.getenv('PAPER_SECRET') or
        os.getenv('PAPER_SECRET_KEY') or
        os.getenv('ALPACA_SECRET_KEY')
    )
    live_key = os.getenv('ALPACA_API_KEY')
    live_secret = os.getenv('ALPACA_SECRET_KEY')

    if (paper_key and paper_secret) or (live_key and live_secret):
        return 'alpaca'

    # Check for Interactive Brokers credentials
    if os.getenv('IB_TWS_PORT') or os.getenv('IB_CLIENT_ID') or os.getenv('IB_TWS_HOST'):
        return 'ibkr'

    # Check for TD Ameritrade credentials
    if os.getenv('TD_CLIENT_ID') or os.getenv('TD_REFRESH_TOKEN'):
        return 'td_ameritrade'

    return None


def detect_all_brokers_from_environment() -> list[str]:
    """
    Detect all available brokers from environment variables

    Returns:
        List of broker types detected from environment
    """
    detected_brokers = []

    # Check for Alpaca credentials (support multiple environment variable names)
    paper_key = (
        os.getenv('PAPER_KEY') or
        os.getenv('PAPER_API_KEY') or
        os.getenv('ALPACA_API_KEY')
    )
    paper_secret = (
        os.getenv('PAPER_SECRET') or
        os.getenv('PAPER_SECRET_KEY') or
        os.getenv('ALPACA_SECRET_KEY')
    )
    live_key = os.getenv('ALPACA_API_KEY')
    live_secret = os.getenv('ALPACA_SECRET_KEY')

    if (paper_key and paper_secret) or (live_key and live_secret):
        detected_brokers.append('alpaca')

    # Check for Interactive Brokers
    if os.getenv('IB_TWS_PORT') or os.getenv('IB_CLIENT_ID') or os.getenv('IB_TWS_HOST'):
        detected_brokers.append('ibkr')

    # Check for TD Ameritrade
    if os.getenv('TD_CLIENT_ID') or os.getenv('TD_REFRESH_TOKEN'):
        detected_brokers.append('td_ameritrade')

    return detected_brokers


def get_alpaca_config_from_env(paper_trading: bool = None) -> dict[str, Any]:
    """
    Extract Alpaca configuration from environment variables

    Args:
        paper_trading: Force paper (True) or live (False) trading. If None, auto-detect.

    Returns:
        Configuration dictionary for Alpaca broker
    """
    config = {}

    # Normalize environment variable spelling (support common variations)
    paper_key = (
        os.getenv("PAPER_KEY") or
        os.getenv("PAPER_API_KEY") or           # common variation
        os.getenv("ALPACA_API_KEY")             # fallback
    )
    paper_secret = (
        os.getenv("PAPER_SECRET") or
        os.getenv("PAPER_SECRET_KEY") or        # user typo we saw in issue
        os.getenv("ALPACA_SECRET_KEY")          # fallback
    )

    live_key = os.getenv("ALPACA_API_KEY")
    live_secret = os.getenv("ALPACA_SECRET_KEY")

    # Check what credentials are available
    has_paper_creds = bool(paper_key and paper_secret)
    has_live_creds = bool(live_key and live_secret)

    # Determine trading mode
    if paper_trading is None:
        # Auto-detect: prefer paper if available, otherwise live
        if has_paper_creds:
            paper_trading = True
        elif has_live_creds:
            paper_trading = False
        else:
            # Default to paper if no credentials found
            paper_trading = True

    # Select appropriate credentials
    if paper_trading:
        if has_paper_creds:
            config['api_key'] = paper_key
            config['secret_key'] = paper_secret
            config['base_url'] = os.getenv('PAPER_ENDPOINT', 'https://paper-api.alpaca.markets')
        else:
            # Fall back to live credentials for paper trading if no paper creds
            config['api_key'] = os.getenv('ALPACA_API_KEY')
            config['secret_key'] = os.getenv('ALPACA_SECRET_KEY')
            config['base_url'] = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
    else:
        # Live trading
        if has_live_creds:
            config['api_key'] = os.getenv('ALPACA_API_KEY')
            config['secret_key'] = os.getenv('ALPACA_SECRET_KEY')
            config['base_url'] = os.getenv('ALPACA_BASE_URL', 'https://api.alpaca.markets')
        else:
            # This should cause an error - no live credentials for live trading
            config['api_key'] = None
            config['secret_key'] = None
            config['base_url'] = 'https://api.alpaca.markets'

    config['paper_trading'] = paper_trading

    # Remove /v2 suffix if present since TradingClient adds it automatically
    if config.get('base_url') and config['base_url'].endswith('/v2'):
        config['base_url'] = config['base_url'][:-3]
        logger.info(f"Removed /v2 suffix from base_url: {config['base_url']}")

    return config


def get_interactive_brokers_config_from_env() -> dict[str, Any]:
    """
    Extract Interactive Brokers configuration from environment variables

    Returns:
        Configuration dictionary for Interactive Brokers
    """
    return {
        'host': os.getenv('IB_TWS_HOST', 'localhost'),
        'port': int(os.getenv('IB_TWS_PORT', '7497')),
        'client_id': int(os.getenv('IB_CLIENT_ID', '1')),
        'paper_trading': os.getenv('IB_PAPER', 'true').lower() == 'true'
    }


def get_td_ameritrade_config_from_env() -> dict[str, Any]:
    """
    Extract TD Ameritrade configuration from environment variables

    Returns:
        Configuration dictionary for TD Ameritrade
    """
    return {
        'client_id': os.getenv('TD_CLIENT_ID'),
        'refresh_token': os.getenv('TD_REFRESH_TOKEN'),
        'redirect_uri': os.getenv('TD_REDIRECT_URI', 'http://localhost'),
        'paper_trading': os.getenv('TD_PAPER', 'true').lower() == 'true'
    }


def validate_broker_environment(broker_type: str) -> tuple[bool, str]:
    """
    Validate that required environment variables are set for a broker

    Args:
        broker_type: Type of broker to validate

    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    if broker_type == 'alpaca':
        config = get_alpaca_config_from_env()
        if not config.get('api_key') or not config.get('secret_key'):
            return False, "Missing required Alpaca environment variables: ALPACA_API_KEY/PAPER_KEY and ALPACA_SECRET_KEY/PAPER_SECRET"
        return True, "Alpaca environment variables validated"

    elif broker_type in ['ibkr', 'IBKR', 'interactive-brokers', 'interactive_brokers']:
        config = get_interactive_brokers_config_from_env()
        if not config.get('port'):
            return False, "Missing required Interactive Brokers environment variable: IB_TWS_PORT"
        return True, "Interactive Brokers environment variables validated"

    elif broker_type == 'td_ameritrade':
        config = get_td_ameritrade_config_from_env()
        if not config.get('client_id'):
            return False, "Missing required TD Ameritrade environment variable: TD_CLIENT_ID"
        return True, "TD Ameritrade environment variables validated"

    else:
        return False, f"Unknown broker type: {broker_type}"


def get_broker_config_from_env(broker_type: str) -> dict[str, Any]:
    """
    Get broker configuration from environment variables

    Args:
        broker_type: Type of broker

    Returns:
        Configuration dictionary

    Raises:
        ValueError: If broker type is not supported
    """
    if broker_type == 'alpaca':
        return get_alpaca_config_from_env()
    elif broker_type in ['ibkr', 'IBKR', 'interactive-brokers', 'interactive_brokers']:
        return get_interactive_brokers_config_from_env()
    elif broker_type == 'td_ameritrade':
        return get_td_ameritrade_config_from_env()
    else:
        raise ValueError(f"Unsupported broker type: {broker_type}")


def normalize_symbol_for_broker(symbol: str, broker_type: str) -> str:
    """
    Normalize symbol format for specific broker requirements

    Args:
        symbol: Original symbol
        broker_type: Target broker type

    Returns:
        Normalized symbol
    """
    if broker_type == 'alpaca':
        # Alpaca specific normalization (crypto symbols)
        if symbol.upper() in ['BTC', 'BITCOIN']:
            return 'BTCUSD'
        elif symbol.upper() in ['ETH', 'ETHEREUM']:
            return 'ETHUSD'
        # Add more crypto mappings as needed
        return symbol.upper()

    elif broker_type in ['ibkr', 'IBKR', 'interactive-brokers', 'interactive_brokers']:
        # IB specific normalization
        return symbol.upper()

    elif broker_type == 'td_ameritrade':
        # TD Ameritrade specific normalization
        return symbol.upper()

    else:
        # Default: return uppercase
        return symbol.upper()


def log_broker_connection_info(broker_type: str, config: dict[str, Any]):
    """
    Log broker connection information (safely, without exposing credentials)

    Args:
        broker_type: Type of broker
        config: Broker configuration
    """
    safe_config = config.copy()

    # Remove sensitive information
    sensitive_keys = ['api_key', 'secret_key', 'refresh_token', 'password']
    for key in sensitive_keys:
        if key in safe_config:
            safe_config[key] = '***HIDDEN***'

    logger.info(f"Broker connection info for {broker_type}:")
    for key, value in safe_config.items():
        logger.info(f"  {key}: {value}")


def get_broker_environment_status() -> dict[str, dict[str, Any]]:
    """
    Get detailed status of broker environment variables

    Returns:
        Dictionary with broker status information
    """
    status = {}

    # Check Alpaca
    alpaca_status = {
        'broker_type': 'alpaca',
        'detected': False,
        'valid': False,
        'error_message': None,
        'config_available': False
    }

    try:
        if (os.getenv('ALPACA_API_KEY') or os.getenv('PAPER_KEY')) and \
           (os.getenv('ALPACA_SECRET_KEY') or os.getenv('PAPER_SECRET')):
            alpaca_status['detected'] = True
            alpaca_status['config_available'] = True

            is_valid, message = validate_broker_environment('alpaca')
            alpaca_status['valid'] = is_valid
            if not is_valid:
                alpaca_status['error_message'] = message
        else:
            alpaca_status['error_message'] = "No Alpaca credentials found in environment"
    except Exception as e:
        alpaca_status['error_message'] = str(e)

    status['alpaca'] = alpaca_status

    # Check Interactive Brokers
    ib_status = {
        'broker_type': 'ibkr',
        'detected': False,
        'valid': False,
        'error_message': None,
        'config_available': False
    }

    try:
        if os.getenv('IB_TWS_PORT') or os.getenv('IB_CLIENT_ID') or os.getenv('IB_TWS_HOST'):
            ib_status['detected'] = True
            ib_status['config_available'] = True

            is_valid, message = validate_broker_environment('ibkr')
            ib_status['valid'] = is_valid
            if not is_valid:
                ib_status['error_message'] = message
        else:
            ib_status['error_message'] = "No Interactive Brokers credentials found in environment"
    except Exception as e:
        ib_status['error_message'] = str(e)

    status['ibkr'] = ib_status

    # Check TD Ameritrade
    td_status = {
        'broker_type': 'td_ameritrade',
        'detected': False,
        'valid': False,
        'error_message': None,
        'config_available': False
    }

    try:
        if os.getenv('TD_CLIENT_ID') or os.getenv('TD_REFRESH_TOKEN'):
            td_status['detected'] = True
            td_status['config_available'] = True

            is_valid, message = validate_broker_environment('td_ameritrade')
            td_status['valid'] = is_valid
            if not is_valid:
                td_status['error_message'] = message
        else:
            td_status['error_message'] = "No TD Ameritrade credentials found in environment"
    except Exception as e:
        td_status['error_message'] = str(e)

    status['td_ameritrade'] = td_status

    return status


def print_broker_environment_status():
    """
    Print a detailed status of broker environment variables
    """
    print("\n🔍 Broker Environment Status")
    print("=" * 50)

    status = get_broker_environment_status()

    for broker_type, broker_status in status.items():
        print(f"\n{broker_type.upper().replace('_', ' ')}:")

        if broker_status['detected']:
            if broker_status['valid']:
                print("  ✅ Detected and valid")
            else:
                print(f"  ⚠️  Detected but invalid: {broker_status['error_message']}")
        else:
            print(f"  ❌ Not detected: {broker_status['error_message']}")

    # Summary
    detected_count = sum(1 for status in status.values() if status['detected'])
    valid_count = sum(1 for status in status.values() if status['valid'])

    print(f"\n📊 Summary: {valid_count} valid, {detected_count} detected, {len(status)} total brokers")


def suggest_environment_setup(broker_type: str) -> str:
    """
    Provide environment setup suggestions for a specific broker

    Args:
        broker_type: Type of broker

    Returns:
        Formatted setup instructions
    """
    if broker_type == 'alpaca':
        return """
Environment setup for Alpaca:

# Paper Trading (recommended for testing)
export PAPER_KEY="your_paper_key"
export PAPER_SECRET="your_paper_secret"
export PAPER_ENDPOINT="https://paper-api.alpaca.markets/v2"

# Live Trading (use with caution)
export ALPACA_API_KEY="your_live_key"
export ALPACA_SECRET_KEY="your_live_secret"
export ALPACA_BASE_URL="https://api.alpaca.markets"

Get keys from: https://alpaca.markets/
"""

    elif broker_type in ['ibkr', 'IBKR', 'interactive-brokers', 'interactive_brokers']:
        return """
Environment setup for Interactive Brokers:

export IB_TWS_HOST="localhost"
export IB_TWS_PORT="7497"  # Paper: 7497, Live: 7496
export IB_CLIENT_ID="1"
export IB_PAPER="true"  # or "false" for live trading

Requirements:
1. Install TWS or IB Gateway
2. Enable API access in TWS settings
3. Start TWS/Gateway before running the system
"""

    elif broker_type == 'td_ameritrade':
        return """
Environment setup for TD Ameritrade:

export TD_CLIENT_ID="your_client_id"
export TD_REFRESH_TOKEN="your_refresh_token"
export TD_REDIRECT_URI="http://localhost"
export TD_PAPER="true"  # or "false" for live trading

Get credentials from: https://developer.tdameritrade.com/
"""

    else:
        return f"No setup instructions available for broker type: {broker_type}"
