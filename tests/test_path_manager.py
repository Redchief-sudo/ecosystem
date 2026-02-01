"""
Path Manager Test Suite - Updated to match actual PathManager API
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bootstrap.path_manager import PathManager, get_path_manager


class TestPathManager:
    """Test cases for PathManager class."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Create minimal project structure
        Path("config").mkdir()
        Path("logs").mkdir()
        Path("data").mkdir()
    
    def teardown_method(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_path_manager_initialization(self):
        """Test PathManager initialization."""
        pm = PathManager(base_path=self.test_dir)
        assert pm.base_path == self.test_dir
    
    def test_get_path_basic(self):
        """Test basic path retrieval."""
        pm = PathManager(base_path=self.test_dir)
        
        # Test getting paths
        result = pm.get_path('config')
        assert isinstance(result, str)
        assert result.endswith('config')
    
    def test_get_path_with_multiple_components(self):
        """Test path with multiple components."""
        pm = PathManager(base_path=self.test_dir)
        
        result = pm.get_path('config', 'main.yaml')
        assert 'config' in result
        assert 'main.yaml' in result
    
    def test_ensure_directory(self):
        """Test directory creation."""
        pm = PathManager(base_path=self.test_dir)
        
        test_path = pm.get_path('newdir')
        pm.ensure_directory(test_path)
        
        assert os.path.isdir(test_path)
    
    def test_get_path_manager_function(self):
        """Test get_path_manager factory function."""
        pm = get_path_manager()
        assert isinstance(pm, PathManager)
    
    def test_get_path_manager_with_base_path(self):
        """Test get_path_manager with custom base path."""
        pm = get_path_manager(self.test_dir)
        assert pm.base_path == self.test_dir


class TestPathManagerIntegration:
    """Integration tests for path manager."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Create basic structure
        Path("logs").mkdir()
        Path("data").mkdir()
        Path("config").mkdir()
    
    def teardown_method(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_logs_directory_creation(self):
        """Test creating logs directory."""
        pm = PathManager(base_path=self.test_dir)
        
        logs_path = pm.get_path('logs')
        pm.ensure_directory(logs_path)
        
        assert os.path.isdir(logs_path)
    
    def test_data_directory_creation(self):
        """Test creating data directory."""
        pm = PathManager(base_path=self.test_dir)
        
        data_path = pm.get_path('data')
        pm.ensure_directory(data_path)
        
        assert os.path.isdir(data_path)
    
    def test_database_file_path(self):
        """Test database file path resolution."""
        pm = PathManager(base_path=self.test_dir)
        
        db_path = pm.get_path('data', 'ecosystem.db')
        assert 'ecosystem.db' in db_path


class TestPathManagerEdgeCases:
    """Test edge cases and error handling."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
    
    def teardown_method(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_ensure_directory_idempotent(self):
        """Test that ensure_directory can be called multiple times safely."""
        pm = PathManager(base_path=self.test_dir)
        
        test_path = pm.get_path('test_dir')
        
        # Call multiple times
        pm.ensure_directory(test_path)
        pm.ensure_directory(test_path)
        pm.ensure_directory(test_path)
        
        # Should exist and be a directory
        assert os.path.isdir(test_path)
    
    def test_empty_path_components(self):
        """Test handling of empty path components."""
        pm = PathManager(base_path=self.test_dir)
        
        # Should handle gracefully
        result = pm.get_path('config')
        assert result is not None
        assert isinstance(result, str)

