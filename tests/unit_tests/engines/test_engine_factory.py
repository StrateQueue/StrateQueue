"""
Tests for EngineFactory class and bt engine registration
"""

import pytest
from unittest.mock import patch, MagicMock

from StrateQueue.engines.engine_factory import EngineFactory


class TestBtEngineFactoryIntegration:
    """Test bt engine integration with EngineFactory"""
    
    def setup_method(self):
        """Reset factory state before each test"""
        # Reset the factory state
        EngineFactory._engines = {}
        EngineFactory._all_known_engines = {}
        EngineFactory._unavailable_engines = {}
        EngineFactory._initialized = False
    
    def test_bt_engine_registration_when_available(self):
        """Test bt engine registration when dependencies are available"""
        # Mock bt engine as available
        mock_bt_engine_class = MagicMock()
        mock_bt_engine_class.dependencies_available.return_value = True
        
        # Patch the bt_engine module import
        mock_bt_module = MagicMock()
        mock_bt_module.BtEngine = mock_bt_engine_class
        
        with patch.dict('sys.modules', {'StrateQueue.engines.bt_engine': mock_bt_module}):
            # Initialize engines
            EngineFactory._initialize_engines()
            
            # Check that bt engine is registered as available
            assert 'bt' in EngineFactory._engines
            assert 'bt' in EngineFactory._all_known_engines
            assert 'bt' not in EngineFactory._unavailable_engines
            
            # Verify the mock class is stored
            assert EngineFactory._engines['bt'] == mock_bt_engine_class
            assert EngineFactory._all_known_engines['bt'] == mock_bt_engine_class
    
    def test_bt_engine_registration_when_unavailable(self):
        """Test bt engine registration when dependencies are not available"""
        # Mock bt engine as unavailable
        mock_bt_engine_class = MagicMock()
        mock_bt_engine_class.dependencies_available.return_value = False
        
        # Patch the bt_engine module import
        mock_bt_module = MagicMock()
        mock_bt_module.BtEngine = mock_bt_engine_class
        
        with patch.dict('sys.modules', {'StrateQueue.engines.bt_engine': mock_bt_module}):
            # Initialize engines
            EngineFactory._initialize_engines()
            
            # Check that bt engine is not in available engines
            assert 'bt' not in EngineFactory._engines
            
            # Check that bt engine is in known engines
            assert 'bt' in EngineFactory._all_known_engines
            
            # Check that bt engine is in unavailable engines
            assert 'bt' in EngineFactory._unavailable_engines
            assert 'bt library not installed' in EngineFactory._unavailable_engines['bt']
    
    def test_bt_engine_can_be_created_when_available(self):
        """Test that bt engine can be created when dependencies are available"""
        # Mock bt engine as available
        mock_bt_engine_class = MagicMock()
        mock_bt_engine_class.dependencies_available.return_value = True
        mock_instance = MagicMock()
        mock_bt_engine_class.return_value = mock_instance
        
        # Patch the bt_engine module import
        mock_bt_module = MagicMock()
        mock_bt_module.BtEngine = mock_bt_engine_class
        
        with patch.dict('sys.modules', {'StrateQueue.engines.bt_engine': mock_bt_module}):
            # Initialize engines
            EngineFactory._initialize_engines()
            
            # Create bt engine
            engine = EngineFactory.create_engine('bt')
            
            # Verify engine was created
            mock_bt_engine_class.assert_called_once()
            assert engine == mock_instance
    
    def test_bt_engine_cannot_be_created_when_unavailable(self):
        """Test that bt engine cannot be created when dependencies are unavailable"""
        # Mock bt engine as unavailable
        mock_bt_engine_class = MagicMock()
        mock_bt_engine_class.dependencies_available.return_value = False
        
        # Patch the bt_engine module import
        mock_bt_module = MagicMock()
        mock_bt_module.BtEngine = mock_bt_engine_class
        
        with patch.dict('sys.modules', {'StrateQueue.engines.bt_engine': mock_bt_module}):
            # Initialize engines
            EngineFactory._initialize_engines()
            
            # Try to create bt engine - should fail
            with pytest.raises(ValueError, match="Unsupported engine type 'bt'"):
                EngineFactory.create_engine('bt')
    
    def test_bt_engine_in_supported_engines_when_available(self):
        """Test that bt engine appears in supported engines list when available"""
        # Mock bt engine as available
        mock_bt_engine_class = MagicMock()
        mock_bt_engine_class.dependencies_available.return_value = True
        
        # Patch the bt_engine module import
        mock_bt_module = MagicMock()
        mock_bt_module.BtEngine = mock_bt_engine_class
        
        with patch.dict('sys.modules', {'StrateQueue.engines.bt_engine': mock_bt_module}):
            # Get supported engines
            supported = EngineFactory.get_supported_engines()
            
            # Check that bt is in supported engines
            assert 'bt' in supported
    
    def test_bt_engine_not_in_supported_engines_when_unavailable(self):
        """Test that bt engine does not appear in supported engines list when unavailable"""
        # Mock bt engine as unavailable
        mock_bt_engine_class = MagicMock()
        mock_bt_engine_class.dependencies_available.return_value = False
        
        # Patch the bt_engine module import
        mock_bt_module = MagicMock()
        mock_bt_module.BtEngine = mock_bt_engine_class
        
        with patch.dict('sys.modules', {'StrateQueue.engines.bt_engine': mock_bt_module}):
            # Get supported engines
            supported = EngineFactory.get_supported_engines()
            
            # Check that bt is not in supported engines
            assert 'bt' not in supported
    
    def test_bt_engine_in_all_known_engines(self):
        """Test that bt engine appears in all known engines regardless of availability"""
        # Mock bt engine as unavailable
        mock_bt_engine_class = MagicMock()
        mock_bt_engine_class.dependencies_available.return_value = False
        
        # Patch the bt_engine module import
        mock_bt_module = MagicMock()
        mock_bt_module.BtEngine = mock_bt_engine_class
        
        with patch.dict('sys.modules', {'StrateQueue.engines.bt_engine': mock_bt_module}):
            # Get all known engines
            all_known = EngineFactory.get_all_known_engines()
            
            # Check that bt is in all known engines
            assert 'bt' in all_known
    
    def test_bt_engine_is_engine_supported_methods(self):
        """Test is_engine_supported and is_engine_known methods for bt engine"""
        # Mock bt engine as available
        mock_bt_engine_class = MagicMock()
        mock_bt_engine_class.dependencies_available.return_value = True
        
        # Patch the bt_engine module import
        mock_bt_module = MagicMock()
        mock_bt_module.BtEngine = mock_bt_engine_class
        
        with patch.dict('sys.modules', {'StrateQueue.engines.bt_engine': mock_bt_module}):
            # Test when available
            assert EngineFactory.is_engine_supported('bt') is True
            assert EngineFactory.is_engine_known('bt') is True
            
            # Reset and test when unavailable
            EngineFactory._engines = {}
            EngineFactory._all_known_engines = {}
            EngineFactory._unavailable_engines = {}
            EngineFactory._initialized = False
            
            mock_bt_engine_class.dependencies_available.return_value = False
            
            assert EngineFactory.is_engine_supported('bt') is False
            assert EngineFactory.is_engine_known('bt') is True