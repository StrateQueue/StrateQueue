"""
Polygon.io Data Source

Real-time and historical stock market data from Polygon.io
"""

import json
import logging
from datetime import datetime, timedelta

import pandas as pd
import requests
import websocket

from .data_source_base import BaseDataIngestion, MarketData
from ...core.resample import plan_base_granularity, resample_ohlcv

logger = logging.getLogger(__name__)


class PolygonDataIngestion(BaseDataIngestion):
    """Polygon.io data ingestion for live trading signals"""

    # Broad support; Polygon range endpoint is flexible
    SUPPORTED_GRANULARITIES = {
        "1s", "5s", "10s", "30s", "1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"
    }
    DEFAULT_GRANULARITY = "1m"

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        self.rest_base_url = "https://api.polygon.io"
        self.ws_url = "wss://socket.polygon.io/stocks"

        # WebSocket connection
        self.ws = None
        self.is_connected = False
        
        # Track subscribed symbols
        self.subscribed_symbols = set()

    async def fetch_historical_data(
        self, symbol: str, days_back: int = 30, granularity: str = "1m"
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data for backtesting compatibility

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            days_back: Number of days of historical data
            granularity: Data granularity (e.g., '1s', '1m', '5m', '1h', '1d')
        """
        # Parse granularity and plan resampling if needed
        parsed_granularity = self._parse_granularity(granularity)
        target_token = f"{parsed_granularity.multiplier}{parsed_granularity.unit.value}"
        # Polygon supports custom multiplier+timespan but underlying base is minute/day
        # Plan from base {1m,1d} to target when possible to enforce full bars.
        try:
            if parsed_granularity.unit in ():
                pass
        except Exception:
            pass
        timespan, multiplier = parsed_granularity.to_timespan_params()

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        url = f"{self.rest_base_url}/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"

        params = {"adjusted": "true", "sort": "asc", "apikey": self.api_key}

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if "results" not in data:
                logger.warning(f"No data returned for {symbol} with granularity {granularity}")
                return pd.DataFrame()

            # Convert to backtesting.py compatible format
            df_data = []
            for bar in data["results"]:
                df_data.append(
                    {
                        "Open": float(bar["o"]),
                        "High": float(bar["h"]),
                        "Low": float(bar["l"]),
                        "Close": float(bar["c"]),
                        "Volume": int(bar["v"]),
                        "timestamp": datetime.fromtimestamp(bar["t"] / 1000),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("timestamp", inplace=True)
            df.index = pd.to_datetime(df.index)

            # If target is a multiple of minute or day, resample in-core to ensure full bars
            try:
                base_supported = {"1m", "1d"}
                plan = None
                if target_token not in base_supported:
                    plan = plan_base_granularity(base_supported, target_token)
                if plan is not None and plan.target_granularity:
                    df = resample_ohlcv(df, plan.target_granularity)
            except Exception:
                pass

            # Cache the data
            self.historical_data[symbol] = df

            logger.info(
                f"Fetched {len(df)} historical bars for {symbol} with granularity {granularity}"
            )
            return df

        except Exception as e:
            logger.error(
                f"Error fetching historical data for {symbol} with granularity {granularity}: {e}"
            )
            return pd.DataFrame()

    def _on_ws_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)

            # Handle different message types
            for item in data:
                if item.get("ev") == "AM":  # Aggregate (OHLCV) message
                    market_data = MarketData(
                        symbol=item["sym"],
                        timestamp=datetime.fromtimestamp(item["s"] / 1000),
                        open=item["o"],
                        high=item["h"],
                        low=item["l"],
                        close=item["c"],
                        volume=item["v"],
                    )

                    # Update current data
                    self.current_bars[market_data.symbol] = market_data

                    # Notify callbacks
                    self._notify_callbacks(market_data)

        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")

    def _on_ws_error(self, ws, error):
        """Handle WebSocket errors"""
        logger.error(f"WebSocket error: {error}")
        self.is_connected = False

    def _on_ws_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        logger.info("WebSocket connection closed")
        self.is_connected = False

    def _on_ws_open(self, ws):
        """Handle WebSocket open"""
        logger.info("WebSocket connection opened")
        self.is_connected = True

        # Authenticate
        auth_message = {"action": "auth", "params": self.api_key}
        ws.send(json.dumps(auth_message))

    async def subscribe_to_symbol(self, symbol: str):
        """Subscribe to real-time data for a symbol"""
        self.subscribed_symbols.add(symbol)
        logger.info(f"Subscribed to {symbol} for real-time data")

    def start_realtime_feed(self):
        """Start the real-time WebSocket connection"""
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close,
            on_open=self._on_ws_open,
        )

        # Run in a separate thread
        self.ws.run_forever()
