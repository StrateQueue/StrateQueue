"""
Unit tests for bt strategy detection in engine helpers
"""

import pytest
from unittest.mock import patch, mock_open
from src.StrateQueue.engines.engine_helpers import (
    analyze_strategy_file,
    detect_engine_from_analysis,
    _detect_engine_indicators
)


class TestBtStrategyDetection:
    """Test bt strategy detection patterns"""
    
    def test_detect_bt_import_patterns(self):
        """Test detection of bt import statements"""
        # Test basic bt import
        content = "import bt\nfrom bt import algos"
        indicators = _detect_engine_indicators(content)
        
        assert 'imports bt' in indicators['bt']
        assert 'imports from bt' in indicators['bt']
        assert len(indicators['bt']) == 2
    
    def test_detect_bt_strategy_creation(self):
        """Test detection of bt.Strategy creation"""
        content = """
import bt

strategy = bt.Strategy('test', [
    bt.algos.SelectAll(),
    bt.algos.WeighEqually(),
    bt.algos.Rebalance()
])
"""
        indicators = _detect_engine_indicators(content)
        
        assert 'creates bt.Strategy' in indicators['bt']
        assert 'uses bt.algos' in indicators['bt']
        assert 'uses SelectAll algo' in indicators['bt']
        assert 'uses WeighEqually algo' in indicators['bt']
        assert 'uses Rebalance algo' in indicators['bt']
    
    def test_detect_bt_backtest_creation(self):
        """Test detection of bt.Backtest creation"""
        content = """
import bt

backtest = bt.Backtest(strategy, data)
result = backtest.run()
"""
        indicators = _detect_engine_indicators(content)
        
        assert 'creates bt.Backtest' in indicators['bt']
        assert 'calls run method' in indicators['bt']
    
    def test_detect_bt_explicit_marker(self):
        """Test detection of explicit bt strategy marker"""
        content = """
import bt

strategy = bt.Strategy('test', algos)
__bt_strategy__ = True
"""
        indicators = _detect_engine_indicators(content)
        
        assert 'marked as bt strategy' in indicators['bt']
    
    def test_detect_bt_security_weights_access(self):
        """Test detection of security_weights access"""
        content = """
import bt

backtest = bt.Backtest(strategy, data)
result = backtest.run()
weights = result.security_weights
"""
        indicators = _detect_engine_indicators(content)
        
        assert 'accesses security_weights' in indicators['bt']
    
    def test_detect_bt_common_algos(self):
        """Test detection of common bt algos"""
        content = """
import bt

algos = [
    bt.algos.SelectWhere(lambda x: x > 0),
    bt.algos.WeighEqually(),
    bt.algos.Rebalance(),
    bt.algos.RunMonthly(),
    bt.algos.RunDaily(),
    bt.algos.RunWeekly(),
    bt.algos.SelectAll(),
    bt.algos.SelectN(5),
    bt.algos.WeighTarget(0.5),
    bt.algos.WeighSpecified({'AAPL': 0.6, 'MSFT': 0.4})
]
"""
        indicators = _detect_engine_indicators(content)
        
        expected_algos = [
            'uses SelectWhere algo',
            'uses WeighEqually algo', 
            'uses Rebalance algo',
            'uses RunMonthly algo',
            'uses RunDaily algo',
            'uses RunWeekly algo',
            'uses SelectAll algo',
            'uses SelectN algo',
            'uses WeighTarget algo',
            'uses WeighSpecified algo'
        ]
        
        for algo in expected_algos:
            assert algo in indicators['bt']
    
    def test_detect_bt_algos_assignment(self):
        """Test detection of algos list assignment"""
        content = """
import bt

strategy_algos = [
    bt.algos.SelectAll(),
    bt.algos.WeighEqually()
]

strategy = bt.Strategy('test', strategy_algos)
strategy.algos = strategy_algos
"""
        indicators = _detect_engine_indicators(content)
        
        assert 'assigns algos list' in indicators['bt']
    
    def test_detect_bt_backtest_module_usage(self):
        """Test detection of bt.backtest module usage"""
        content = """
import bt

result = bt.backtest.run(strategy, data)
stats = bt.backtest.display_monthly_returns(result)
"""
        indicators = _detect_engine_indicators(content)
        
        assert 'uses bt.backtest module' in indicators['bt']
    
    def test_bt_strategy_file_analysis(self):
        """Test full file analysis for bt strategy"""
        bt_strategy_content = """
import bt
import pandas as pd

def create_strategy():
    algos = [
        bt.algos.SelectAll(),
        bt.algos.WeighEqually(),
        bt.algos.Rebalance()
    ]
    return bt.Strategy('equal_weight', algos)

__bt_strategy__ = True

if __name__ == '__main__':
    strategy = create_strategy()
    data = pd.read_csv('data.csv')
    backtest = bt.Backtest(strategy, data)
    result = backtest.run()
    weights = result.security_weights
"""
        
        with patch('builtins.open', mock_open(read_data=bt_strategy_content)):
            with patch('os.path.exists', return_value=True):
                analysis = analyze_strategy_file('test_bt_strategy.py')
        
        # Check that bt indicators were detected
        bt_indicators = analysis['engine_indicators']['bt']
        assert len(bt_indicators) > 0
        assert 'imports bt' in bt_indicators
        assert 'creates bt.Strategy' in bt_indicators
        assert 'marked as bt strategy' in bt_indicators
        assert 'creates bt.Backtest' in bt_indicators
        assert 'accesses security_weights' in bt_indicators
    
    def test_detect_engine_from_bt_analysis(self):
        """Test that bt is correctly identified as the primary engine"""
        bt_strategy_content = """
import bt

strategy = bt.Strategy('test', [
    bt.algos.SelectAll(),
    bt.algos.WeighEqually(),
    bt.algos.Rebalance()
])

__bt_strategy__ = True
"""
        
        with patch('builtins.open', mock_open(read_data=bt_strategy_content)):
            with patch('os.path.exists', return_value=True):
                analysis = analyze_strategy_file('test_bt_strategy.py')
                detected_engine = detect_engine_from_analysis(analysis)
        
        assert detected_engine == 'bt'
    
    def test_bt_vs_other_engines_scoring(self):
        """Test that bt scores higher than other engines for bt-specific content"""
        # Content with both bt and some generic patterns
        mixed_content = """
import bt
import pandas as pd

def next(self):  # This could match backtrader
    pass

strategy = bt.Strategy('test', [
    bt.algos.SelectAll(),
    bt.algos.WeighEqually()
])

__bt_strategy__ = True
"""
        
        indicators = _detect_engine_indicators(mixed_content)
        
        # bt should have more indicators than other engines
        bt_score = len(indicators['bt'])
        backtrader_score = len(indicators['backtrader'])
        backtesting_score = len(indicators['backtesting'])
        
        assert bt_score > backtrader_score
        assert bt_score > backtesting_score
    
    def test_no_bt_indicators_in_other_engine_content(self):
        """Test that non-bt content doesn't trigger bt indicators"""
        backtrader_content = """
import backtrader as bt

class TestStrategy(bt.Strategy):
    def next(self):
        self.buy()
"""
        
        indicators = _detect_engine_indicators(backtrader_content)
        
        # Should not detect bt library indicators
        assert len(indicators['bt']) == 0
        # Should detect backtrader indicators
        assert len(indicators['backtrader']) > 0
    
    def test_empty_content_no_bt_detection(self):
        """Test that empty content doesn't trigger bt detection"""
        indicators = _detect_engine_indicators("")
        assert len(indicators['bt']) == 0
    
    def test_bt_pattern_case_sensitivity(self):
        """Test that bt patterns are case sensitive where appropriate"""
        # bt import should be case sensitive
        content_wrong_case = "import BT\nfrom BT import algos"
        indicators = _detect_engine_indicators(content_wrong_case)
        assert len(indicators['bt']) == 0
        
        # Correct case should work
        content_correct_case = "import bt\nfrom bt import algos"
        indicators = _detect_engine_indicators(content_correct_case)
        assert len(indicators['bt']) == 2


if __name__ == '__main__':
    pytest.main([__file__])