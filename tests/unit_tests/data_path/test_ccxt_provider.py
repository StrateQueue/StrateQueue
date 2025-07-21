"""
CCXT Data Provider Tests

Tests for CCXTDataIngestion data provider focusing on:
1. Provider initialization and configuration
2. Exchange connection and validation
3. Data retrieval functionality
4. Error handling and edge cases
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime, timedelta

from StrateQueue.data.sources.ccxt_data import CCXTDataIngestion


class TestCCXTDataIngestion:
    """Test CCXT data provider functionality"""

    def test_ccxt_not_available_raises_import_error(self):
        """Test that missing CCXT library raises ImportError"""
        with patch('StrateQueue.data.sources.ccxt_data.CCXT_AVAILABLE', False):
            with pytest.raises(ImportError, match="CCXT library not available"):
                CCXTDataIngestion(exchange_id="binance")

    def test_missing_exchange_id_raises_error(self):
        """Test that missing exchange ID raises ValueError"""
        with patch('StrateQueue.data.sources.ccxt_data.CCXT_AVAILABLE', True):
            with patch.dict('os.environ', {}, clear=True):
                with pytest.raises(ValueError, match="Exchange ID required"):
                    CCXTDataIngestion()

    @patch('StrateQueue.data.sources.ccxt_data.ccxt')
    def test_initialization_with_exchange_id(self, mock_ccxt):
        """Test successful initialization with exchange ID"""
        # Mock CCXT module
        mock_exchange_class = Mock()
        mock_exchange_instance = Mock()
        mock_exchange_instance.load_markets.return_value = {}
        mock_exchange_class.return_value = mock_exchange_instance
        
        mock_ccxt.binance = mock_exchange_class
        
        with patch('StrateQueue.data.sources.ccxt_data.CCXT_AVAILABLE', True):
            provider = CCXTDataIngestion(
                exchange_id="binance",
                api_key="test_key",
                secret_key="test_secret"
            )
            
            assert provider.exchange_id == "binance"
            assert provider.granularity == "1m"
            assert provider.sandbox is True
            mock_exchange_class.assert_called_once()

    @patch('StrateQueue.data.sources.ccxt_data.ccxt')
    def test_initialization_from_environment(self, mock_ccxt):
        """Test initialization from environment variables"""
        mock_exchange_class = Mock()
        mock_exchange_instance = Mock()
        mock_exchange_instance.load_markets.return_value = {}
        mock_exchange_class.return_value = mock_exchange_instance
        
        mock_ccxt.kraken = mock_exchange_class
        
        env_vars = {
            'CCXT_EXCHANGE': 'kraken',
            'CCXT_API_KEY': 'env_key',
            'CCXT_SECRET_KEY': 'env_secret'
        }
        
        with patch('StrateQueue.data.sources.ccxt_data.CCXT_AVAILABLE', True):
            with patch.dict('os.environ', env_vars):
                provider = CCXTDataIngestion()
                
                assert provider.exchange_id == "kraken"
                mock_exchange_class.assert_called_once()

    @patch('StrateQueue.data.sources.ccxt_data.ccxt')
    def test_unsupported_exchange_raises_error(self, mock_ccxt):
        """Test that unsupported exchange raises ValueError"""
        mock_ccxt.exchanges = ['binance', 'coinbase', 'kraken']
        # Mock hasattr to return False for nonexistent exchange
        def mock_hasattr(obj, name):
            return name in ['binance', 'coinbase', 'kraken']
        
        with patch('StrateQueue.data.sources.ccxt_data.CCXT_AVAILABLE', True):
            with patch('builtins.hasattr', side_effect=mock_hasattr):
                with pytest.raises(ValueError, match="Unsupported exchange 'nonexistent'"):
                    CCXTDataIngestion(exchange_id="nonexistent")

    def test_dependencies_available_returns_correct_status(self):
        """Test dependencies_available static method"""
        with patch('StrateQueue.data.sources.ccxt_data.CCXT_AVAILABLE', True):
            assert CCXTDataIngestion.dependencies_available() is True
            
        with patch('StrateQueue.data.sources.ccxt_data.CCXT_AVAILABLE', False):
            assert CCXTDataIngestion.dependencies_available() is False

    @patch('StrateQueue.data.sources.ccxt_data.ccxt')
    def test_get_historical_data_success(self, mock_ccxt):
        """Test successful historical data retrieval"""
        # Setup mock exchange
        mock_exchange_class = Mock()
        mock_exchange_instance = Mock()
        mock_exchange_instance.load_markets.return_value = {}
        
        # Mock OHLCV data
        mock_ohlcv_data = [
            [1640995200000, 47000.0, 47500.0, 46500.0, 47200.0, 1.5],  # timestamp, o, h, l, c, v
            [1640995260000, 47200.0, 47300.0, 46800.0, 47000.0, 2.1],
        ]
        mock_exchange_instance.fetch_ohlcv.return_value = mock_ohlcv_data
        mock_exchange_class.return_value = mock_exchange_instance
        
        mock_ccxt.binance = mock_exchange_class
        
        with patch('StrateQueue.data.sources.ccxt_data.CCXT_AVAILABLE', True):
            provider = CCXTDataIngestion(exchange_id="binance")
            
            start_date = datetime(2022, 1, 1)
            df = provider.get_historical_data("BTC/USDT", start_date=start_date)
            
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
            assert list(df.columns) == ['Open', 'High', 'Low', 'Close', 'Volume']
            assert df.index.name == 'timestamp'
            
            # Verify exchange method was called correctly
            mock_exchange_instance.fetch_ohlcv.assert_called_once_with(
                symbol="BTC/USDT",
                timeframe="1m",
                since=int(start_date.timestamp() * 1000),
                limit=1000
            )

    @patch('StrateQueue.data.sources.ccxt_data.ccxt')
    def test_get_historical_data_empty_response(self, mock_ccxt):
        """Test handling of empty historical data response"""
        mock_exchange_class = Mock()
        mock_exchange_instance = Mock()
        mock_exchange_instance.load_markets.return_value = {}
        mock_exchange_instance.fetch_ohlcv.return_value = []
        mock_exchange_class.return_value = mock_exchange_instance
        
        mock_ccxt.binance = mock_exchange_class
        
        with patch('StrateQueue.data.sources.ccxt_data.CCXT_AVAILABLE', True):
            provider = CCXTDataIngestion(exchange_id="binance")
            
            df = provider.get_historical_data("BTC/USDT")
            
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 0

    @patch('StrateQueue.data.sources.ccxt_data.ccxt')
    def test_get_current_price_success(self, mock_ccxt):
        """Test successful current price retrieval"""
        mock_exchange_class = Mock()
        mock_exchange_instance = Mock()
        mock_exchange_instance.load_markets.return_value = {}
        mock_exchange_instance.fetch_ticker.return_value = {'last': 47000.0}
        mock_exchange_class.return_value = mock_exchange_instance
        
        mock_ccxt.binance = mock_exchange_class
        
        with patch('StrateQueue.data.sources.ccxt_data.CCXT_AVAILABLE', True):
            provider = CCXTDataIngestion(exchange_id="binance")
            
            price = provider.get_current_price("BTC/USDT")
            
            assert price == 47000.0
            mock_exchange_instance.fetch_ticker.assert_called_once_with("BTC/USDT")

    @patch('StrateQueue.data.sources.ccxt_data.ccxt')
    def test_get_available_symbols_success(self, mock_ccxt):
        """Test successful symbol list retrieval"""
        mock_exchange_class = Mock()
        mock_exchange_instance = Mock()
        mock_markets = {
            'BTC/USDT': {'symbol': 'BTC/USDT'},
            'ETH/USDT': {'symbol': 'ETH/USDT'},
            'ADA/USDT': {'symbol': 'ADA/USDT'}
        }
        mock_exchange_instance.load_markets.return_value = mock_markets
        mock_exchange_class.return_value = mock_exchange_instance
        
        mock_ccxt.binance = mock_exchange_class
        
        with patch('StrateQueue.data.sources.ccxt_data.CCXT_AVAILABLE', True):
            provider = CCXTDataIngestion(exchange_id="binance")
            
            symbols = provider.get_available_symbols()
            
            assert symbols == ['BTC/USDT', 'ETH/USDT', 'ADA/USDT']

    def test_granularity_conversion(self):
        """Test granularity to timeframe conversion"""
        with patch('StrateQueue.data.sources.ccxt_data.CCXT_AVAILABLE', True):
            with patch('StrateQueue.data.sources.ccxt_data.ccxt'):
                provider = CCXTDataIngestion(exchange_id="binance")
                
                # Test valid conversions
                assert provider._convert_granularity_to_timeframe("1m") == "1m"
                assert provider._convert_granularity_to_timeframe("5m") == "5m"
                assert provider._convert_granularity_to_timeframe("1h") == "1h"
                assert provider._convert_granularity_to_timeframe("1d") == "1d"
                
                # Test invalid granularity defaults to 1m
                assert provider._convert_granularity_to_timeframe("invalid") == "1m"

    @patch('StrateQueue.data.sources.ccxt_data.ccxt')
    def test_validate_symbol_success(self, mock_ccxt):
        """Test successful symbol validation"""
        mock_exchange_class = Mock()
        mock_exchange_instance = Mock()
        mock_markets = {'BTC/USDT': {'symbol': 'BTC/USDT'}}
        mock_exchange_instance.load_markets.return_value = mock_markets
        mock_exchange_class.return_value = mock_exchange_instance
        
        mock_ccxt.binance = mock_exchange_class
        
        with patch('StrateQueue.data.sources.ccxt_data.CCXT_AVAILABLE', True):
            provider = CCXTDataIngestion(exchange_id="binance")
            
            assert provider.validate_symbol("BTC/USDT") is True
            assert provider.validate_symbol("INVALID/PAIR") is False

    @patch('StrateQueue.data.sources.ccxt_data.ccxt')
    def test_get_exchange_info(self, mock_ccxt):
        """Test exchange information retrieval"""
        mock_exchange_class = Mock()
        mock_exchange_instance = Mock()
        mock_exchange_instance.load_markets.return_value = {'BTC/USDT': {}}
        mock_exchange_instance.id = 'binance'
        mock_exchange_instance.name = 'Binance'
        mock_exchange_instance.countries = ['CN']
        mock_exchange_instance.has = {'fetchOHLCV': True}
        mock_exchange_instance.timeframes = {'1m': '1m', '5m': '5m'}
        mock_exchange_instance.markets = {'BTC/USDT': {}}
        mock_exchange_class.return_value = mock_exchange_instance
        
        mock_ccxt.binance = mock_exchange_class
        
        with patch('StrateQueue.data.sources.ccxt_data.CCXT_AVAILABLE', True):
            provider = CCXTDataIngestion(exchange_id="binance", sandbox=True)
            
            info = provider.get_exchange_info()
            
            expected_info = {
                'id': 'binance',
                'name': 'Binance',
                'countries': ['CN'],
                'has': {'fetchOHLCV': True},
                'timeframes': {'1m': '1m', '5m': '5m'},
                'markets_count': 1,
                'sandbox': True
            }
            
            assert info == expected_info

    @patch('StrateQueue.data.sources.ccxt_data.ccxt')
    def test_error_handling_in_data_methods(self, mock_ccxt):
        """Test error handling in data retrieval methods"""
        mock_exchange_class = Mock()
        mock_exchange_instance = Mock()
        mock_exchange_instance.load_markets.return_value = {}
        mock_exchange_instance.fetch_ohlcv.side_effect = Exception("API Error")
        mock_exchange_instance.fetch_ticker.side_effect = Exception("API Error")
        mock_exchange_class.return_value = mock_exchange_instance
        
        mock_ccxt.binance = mock_exchange_class
        
        with patch('StrateQueue.data.sources.ccxt_data.CCXT_AVAILABLE', True):
            provider = CCXTDataIngestion(exchange_id="binance")
            
            # Test error handling returns appropriate defaults
            df = provider.get_historical_data("BTC/USDT")
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 0
            
            price = provider.get_current_price("BTC/USDT")
            assert price == 0.0