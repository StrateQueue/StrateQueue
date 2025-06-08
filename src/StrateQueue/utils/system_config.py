import os
from dataclasses import dataclass


@dataclass
class DataConfig:
    """Configuration for data ingestion"""

    polygon_api_key: str
    cmc_api_key: str
    symbols: list[str]
    historical_days: int = 30
    timespan: str = "minute"  # minute, hour, day
    multiplier: int = 1  # 1 minute, 5 minute, etc.


@dataclass
class TradingConfig:
    """Basic trading configuration"""

    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_base_url: str = "https://paper-api.alpaca.markets"  # Paper trading by default


def load_config() -> tuple[DataConfig, TradingConfig]:
    """Load configuration from environment variables"""

    data_config = DataConfig(
        polygon_api_key=os.getenv("POLYGON_API_KEY", ""),
        cmc_api_key=os.getenv("CMC_API_KEY", ""),
        symbols=os.getenv("TRADING_SYMBOLS", "AAPL,MSFT,GOOGL").split(","),
        historical_days=int(os.getenv("HISTORICAL_DAYS", "30")),
        timespan=os.getenv("TIMESPAN", "minute"),
        multiplier=int(os.getenv("MULTIPLIER", "1")),
    )

    trading_config = TradingConfig(
        alpaca_api_key=os.getenv("ALPACA_API_KEY", ""),
        alpaca_secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
        alpaca_base_url=os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
    )

    return data_config, trading_config
