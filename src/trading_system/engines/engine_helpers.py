"""
Engine Detection Utilities

Functions to analyze strategy files and detect which trading engine they're designed for.
"""

import re
import os
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


def analyze_strategy_file(strategy_path: str) -> Dict[str, any]:
    """
    Analyze a strategy file to gather information about its engine compatibility
    
    Args:
        strategy_path: Path to the strategy file
        
    Returns:
        Dictionary with analysis results
    """
    if not os.path.exists(strategy_path):
        raise FileNotFoundError(f"Strategy file not found: {strategy_path}")
    
    try:
        with open(strategy_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Error reading strategy file {strategy_path}: {e}")
        raise
    
    analysis = {
        'file_path': strategy_path,
        'content_length': len(content),
        'imports': _extract_imports(content),
        'functions': _extract_functions(content),
        'classes': _extract_classes(content),
        'variables': _extract_variables(content),
        'engine_indicators': _detect_engine_indicators(content)
    }
    
    return analysis


def _extract_imports(content: str) -> List[str]:
    """Extract import statements from file content"""
    import_pattern = r'^(?:from\s+\S+\s+)?import\s+.+$'
    imports = re.findall(import_pattern, content, re.MULTILINE)
    return [imp.strip() for imp in imports]


def _extract_functions(content: str) -> List[str]:
    """Extract function definitions from file content"""
    function_pattern = r'^def\s+(\w+)\s*\('
    functions = re.findall(function_pattern, content, re.MULTILINE)
    return functions


def _extract_classes(content: str) -> List[str]:
    """Extract class definitions from file content"""
    class_pattern = r'^class\s+(\w+)\s*.*:'
    classes = re.findall(class_pattern, content, re.MULTILINE)
    return classes


def _extract_variables(content: str) -> List[str]:
    """Extract top-level variable assignments from file content"""
    # Look for LOOKBACK and other common strategy variables
    var_pattern = r'^([A-Z_][A-Z0-9_]*)\s*='
    variables = re.findall(var_pattern, content, re.MULTILINE)
    return variables


def _detect_engine_indicators(content: str) -> Dict[str, List[str]]:
    """
    Detect indicators that suggest which trading engine the strategy is for
    
    Returns:
        Dictionary mapping engine names to lists of detected indicators
    """
    indicators = {
        'backtesting': [],
        'zipline': [],
        'unknown': []
    }
    
    # backtesting.py indicators
    backtesting_patterns = [
        (r'from\s+backtesting\s+import', 'imports backtesting'),
        (r'from\s+backtesting\.lib\s+import', 'imports backtesting.lib'),
        (r'from\s+backtesting\.test\s+import', 'imports backtesting.test'),
        (r'class\s+\w+\(Strategy\)', 'inherits from Strategy'),
        (r'def\s+init\(self\)', 'has init method'),
        (r'def\s+next\(self\)', 'has next method'),
        (r'self\.I\(', 'uses self.I() for indicators'),
        (r'self\.buy\(', 'uses self.buy()'),
        (r'self\.sell\(', 'uses self.sell()'),
        (r'crossover\(', 'uses crossover function'),
        (r'LOOKBACK\s*=', 'has LOOKBACK variable')
    ]
    
    # Zipline indicators
    zipline_patterns = [
        (r'def\s+initialize\s*\(\s*context\s*\)', 'has initialize(context) function'),
        (r'def\s+handle_data\s*\(\s*context\s*,\s*data\s*\)', 'has handle_data(context, data) function'),
        (r'def\s+before_trading_start\s*\(\s*context\s*,\s*data\s*\)', 'has before_trading_start function'),
        (r'context\.\w+', 'uses context object'),
        (r'data\.history\(', 'uses data.history()'),
        (r'order_target_percent\(', 'uses order_target_percent()'),
        (r'order_target\(', 'uses order_target()'),
        (r'order\(', 'uses order() function'),
        (r'symbol\(', 'uses symbol() function'),
        (r'from\s+zipline', 'imports zipline'),
        (r'import\s+zipline', 'imports zipline')
    ]
    
    # Check backtesting.py patterns
    for pattern, description in backtesting_patterns:
        if re.search(pattern, content, re.MULTILINE):
            indicators['backtesting'].append(description)
    
    # Check Zipline patterns
    for pattern, description in zipline_patterns:
        if re.search(pattern, content, re.MULTILINE):
            indicators['zipline'].append(description)
    
    return indicators


def detect_engine_from_analysis(analysis: Dict[str, any]) -> str:
    """
    Determine the most likely engine based on file analysis
    
    Args:
        analysis: Result from analyze_strategy_file()
        
    Returns:
        Engine name ('backtesting', 'zipline', 'unknown')
    """
    indicators = analysis['engine_indicators']
    
    backtesting_score = len(indicators['backtesting'])
    zipline_score = len(indicators['zipline'])
    
    logger.debug(f"Engine detection scores - backtesting: {backtesting_score}, zipline: {zipline_score}")
    
    if backtesting_score > zipline_score and backtesting_score > 0:
        return 'backtesting'
    elif zipline_score > backtesting_score and zipline_score > 0:
        return 'zipline'
    else:
        return 'unknown'


def get_strategy_lookback_from_file(strategy_path: str) -> Optional[int]:
    """
    Extract LOOKBACK variable from strategy file if present
    
    Args:
        strategy_path: Path to the strategy file
        
    Returns:
        LOOKBACK value if found, None otherwise
    """
    try:
        with open(strategy_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Look for LOOKBACK = number pattern
        lookback_pattern = r'^LOOKBACK\s*=\s*(\d+)'
        match = re.search(lookback_pattern, content, re.MULTILINE)
        
        if match:
            return int(match.group(1))
            
    except Exception as e:
        logger.warning(f"Error extracting LOOKBACK from {strategy_path}: {e}")
    
    return None 