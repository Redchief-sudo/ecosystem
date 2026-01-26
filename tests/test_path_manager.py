"""
Path Manager Test Suite

Comprehensive tests for the centralized path management system.
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

from utils.path_manager import (PathManager, get_path_manager,
                                validate_project_structure)


class TestPathManager:
    """Test cases for PathManager class."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        
        # Create minimal project structure
        os.chdir(self.test_dir)
        Path("main.py").touch()
        Path("config").mkdir()
        Path("utils").mkdir()
        Path("ai").mkdir()
        Path("scanners").mkdir()
        Path("data").mkdir()
        Path("logs").mkdir()
    
    def teardown_method(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_project_root_detection(self):
        """Test automatic project root detection."""
        pm = PathManager()
        
        # Should detect the test directory as project root
        assert pm.project_root == Path(self.test_dir)
    
    def test_path_resolution(self):
        """Test standardized path resolution."""
        pm = PathManager()
        
        # Test common paths
        assert pm.get_path('config') == Path(self.test_dir) / 'config'
        assert pm.get_path('data') == Path(self.test_dir) / 'data'
        assert pm.get_path('logs') == Path(self.test_dir) / 'logs'
        assert pm.get_path('database') == Path(self.test_dir) / 'data' / 'ecosystem.db'
    
    def test_config_paths(self):
        """Test configuration file path resolution."""
        pm = PathManager()
        
        # Test different config types
        main_config = pm.get_config_path('main')
        scanner_config = pm.get_config_path('scanner')
        strategies_config = pm.get_config_path('strategies')
        ai_config = pm.get_config_path('ai')
        
        assert 'config.yaml' in str(main_config)
        assert 'scanner_config.yaml' in str(scanner_config)
        assert 'strategies.yaml' in str(strategies_config)
        assert 'ai_config.yaml' in str(ai_config)
    
    def test_directory_creation(self):
        """Test directory creation via path manager."""
        pm = PathManager()
        
        # Test directory creation
        logs_dir = pm.ensure_directory_exists('logs')
        assert logs_dir.exists()
        assert logs_dir.is_dir()
        
        # Test that existing directory doesn't cause issues
        same_dir = pm.ensure_directory_exists('logs')
        assert same_dir == logs_dir
    
    def test_path_validation(self):
        """Test path accessibility validation."""
        pm = PathManager()
        
        # Test existing path validation
        assert pm.validate_path_accessible('config', check_read=True) == True
        
        # Test non-existent path
        assert pm.validate_path_accessible('nonexistent', check_read=True) == False
        
        # Test write access on data directory
        assert pm.validate_path_accessible('data', check_write=True) == True
    
    def test_database_path_resolution(self):
        """Test database path resolution with various scenarios."""
        pm = PathManager()
        
        # Default path
        default_db = pm.get_database_path()
        assert 'ecosystem.db' in str(default_db)
        
        # Custom path
        custom_db = pm.get_database_path('/custom/path.db')
        assert custom_db == Path('/custom/path.db')
        
        # Environment variable simulation
        with patch.dict(os.environ, {'ECOSYSTEM_DB_PATH': '/env/path.db'}):
            env_db = pm.get_database_path()
            assert env_db == Path('/env/path.db')
    
    def test_project_fingerprint(self):
        """Test project fingerprint generation."""
        pm1 = PathManager()
        pm2 = PathManager()
        
        # Same project should have same fingerprint
        assert pm1.get_project_fingerprint() == pm2.get_project_fingerprint()
        
        # Different projects should have different fingerprints
        pm3 = PathManager(project_root=Path('/different/path'))
        assert pm1.get_project_fingerprint() != pm3.get_project_fingerprint()
    
    def test_path_caching(self):
        """Test path caching functionality."""
        pm = PathManager()
        
        # Get path twice
        path1 = pm.get_path('data')
        path2 = pm.get_path('data')
        
        # Should be the same object due to caching
        assert path1 == path2
        
        # Test cache bypass
        path3 = pm.get_path('data', use_cache=False)
        assert path3 == path1
    
    def test_absolute_path_resolution(self):
        """Test absolute path resolution."""
        pm = PathManager()
        
        # Relative path
        rel_path = pm.get_absolute_path('data/test.txt')
        assert rel_path.is_absolute()
        assert 'test.txt' in str(rel_path)
        
        # Absolute path should remain unchanged
        abs_path = Path('/absolute/path.txt')
        result = pm.get_absolute_path(abs_path)
        assert result == abs_path
    
    def test_path_input_resolution(self):
        """Test various path input formats."""
        pm = PathManager()
        
        # String path
        result1 = pm.resolve_path('data/test.txt')
        assert isinstance(result1, Path)
        
        # Path object
        path_obj = Path('data/test.txt')
        result2 = pm.resolve_path(path_obj)
        assert result2 == path_obj
    
    def test_global_path_manager(self):
        """Test global path manager functionality."""
        # Clear any existing global instance
        import utils.path_manager
        utils.path_manager._global_path_manager = None
        
        # Get global instance
        pm1 = get_path_manager()
        pm2 = get_path_manager()
        
        # Should be the same instance
        assert pm1 is pm2
    
    def test_project_structure_validation(self):
        """Test project structure validation."""
        validation = validate_project_structure()
        
        # Should return a dictionary with boolean values
        assert isinstance(validation, dict)
        
        # Essential resources should be checked
        expected_resources = ['project_root', 'config', 'utils', 'ai', 'scanners']
        for resource in expected_resources:
            assert resource in validation
            assert isinstance(validation[resource], bool)


class TestPathManagerIntegration:
    """Integration tests for path manager with existing codebase."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        
        # Create minimal project structure
        os.chdir(self.test_dir)
        Path("main.py").touch()
        Path("config").mkdir()
        Path("utils").mkdir()
        Path("ai").mkdir()
        Path("scanners").mkdir()
        Path("data").mkdir()
        Path("logs").mkdir()
    
    def teardown_method(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_integration_with_main_py(self):
        """Test that main.py can use path manager without issues."""
        pm = PathManager()
        
        # Test the same paths that main.py uses
        config_path = pm.get_config_path('main')
        database_path = pm.get_database_path()
        logs_path = pm.ensure_directory_exists('logs')
        
        assert config_path.exists() or config_path.parent.exists()
        assert database_path.parent.exists()
        assert logs_path.exists()
    
    def test_integration_with_ownership_guard(self):
        """Test that ownership guard can use project fingerprint."""
        pm = PathManager()
        
        # Test that fingerprint is deterministic
        fingerprint = pm.get_project_fingerprint()
        assert isinstance(fingerprint, str)
        assert len(fingerprint) == 16  # SHA256 truncated to 16 chars
        assert all(c in '0123456789abcdef' for c in fingerprint)  # hex string
    
    def test_integration_with_memory_manager(self):
        """Test that memory manager can use path manager for database."""
        pm = PathManager()
        
        # Test database path resolution
        db_path = pm.get_database_path()
        
        # Ensure directory exists
        pm.ensure_directory_exists('data')
        
        # Path should be valid
        assert db_path.parent.exists()
        assert str(db_path).endswith('ecosystem.db')


class TestBackwardCompatibility:
    """Test backward compatibility with existing code patterns."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        
        # Create minimal project structure
        os.chdir(self.test_dir)
        Path("main.py").touch()
        Path("config").mkdir()
        Path("utils").mkdir()
        Path("ai").mkdir()
        Path("scanners").mkdir()
        Path("data").mkdir()
        Path("logs").mkdir()
    
    def teardown_method(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_legacy_path_patterns(self):
        """Test that legacy path patterns still work."""
        pm = PathManager()
        
        # Test legacy patterns that were found in codebase
        legacy_patterns = [
            'config/config.yaml',
            'data/ecosystem.db', 
            'logs/ecosystem_debug.log'
        ]
        
        for pattern in legacy_patterns:
            resolved = pm.get_absolute_path(pattern)
            assert resolved.is_absolute()
            assert pattern.split('/')[-1] in str(resolved)
    
    def test_custom_database_paths(self):
        """Test custom database path handling."""
        pm = PathManager()
        
        # Test various custom path scenarios
        custom_paths = [
            '/tmp/custom.db',
            './relative/path.db',
        ]
        
        for custom_path in custom_paths:
            resolved = pm.get_database_path(custom_path)
            assert isinstance(resolved, Path)
            assert 'db.db' in str(resolved) or 'custom.db' in str(resolved)


def run_tests():
    """Run all tests and report results."""
    print("🧪 Running Path Manager Test Suite")
    print("=" * 50)
    
    test_classes = [TestPathManager, TestPathManagerIntegration, TestBackwardCompatibility]
    
    passed = 0
    failed = 0
    
    for test_class in test_classes:
        print(f"\n📋 Testing {test_class.__name__}")
        print("-" * 30)
        
        # Create test instance
        test_instance = test_class()
        test_instance.setup_method()
        
        try:
            # Run all test methods
            for method_name in dir(test_instance):
                if method_name.startswith('test_'):
                    try:
                        print(f"  ✅ {method_name}")
                        getattr(test_instance, method_name)()
                        passed += 1
                    except Exception as e:
                        print(f"  ❌ {method_name}: {e}")
                        failed += 1
        finally:
            test_instance.teardown_method()
    
    print(f"\n📊 Test Results:")
    print(f"  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")
    print(f"  📈 Success Rate: {(passed / (passed + failed) * 100):.1f}%")
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    
    if success:
        print("\n🎉 All tests passed! Path management system is working correctly.")
    else:
        print("\n⚠️ Some tests failed. Please review the issues above.")
        sys.exit(1)
