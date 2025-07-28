"""
Tests for configuration management functionality.
"""

import unittest
import tempfile
import os
import json
from pathlib import Path

from dispyplus.config import Config, ConfigManager


class TestConfig(unittest.TestCase):
    """Test cases for Config class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_data = {
            'bot': {
                'name': 'TestBot',
                'prefix': '!',
                'token': 'test_token'
            },
            'features': {
                'enabled': True,
                'count': 42
            },
            'simple_value': 'hello'
        }
        self.config = Config(self.test_data)
    
    def test_get_simple_value(self):
        """Test getting simple values."""
        self.assertEqual(self.config.get('simple_value'), 'hello')
        self.assertEqual(self.config.get('nonexistent'), None)
        self.assertEqual(self.config.get('nonexistent', 'default'), 'default')
    
    def test_get_nested_value(self):
        """Test getting nested values with dot notation."""
        self.assertEqual(self.config.get('bot.name'), 'TestBot')
        self.assertEqual(self.config.get('bot.prefix'), '!')
        self.assertEqual(self.config.get('features.enabled'), True)
        self.assertEqual(self.config.get('features.count'), 42)
    
    def test_get_nonexistent_nested(self):
        """Test getting nonexistent nested values."""
        self.assertEqual(self.config.get('bot.nonexistent'), None)
        self.assertEqual(self.config.get('nonexistent.key'), None)
        self.assertEqual(self.config.get('bot.nonexistent', 'default'), 'default')
    
    def test_set_simple_value(self):
        """Test setting simple values."""
        self.config.set('new_value', 'test')
        self.assertEqual(self.config.get('new_value'), 'test')
    
    def test_set_nested_value(self):
        """Test setting nested values with dot notation."""
        self.config.set('bot.new_setting', 'value')
        self.assertEqual(self.config.get('bot.new_setting'), 'value')
        
        # Test creating new nested structure
        self.config.set('new.nested.value', 'deep')
        self.assertEqual(self.config.get('new.nested.value'), 'deep')
    
    def test_has_value(self):
        """Test checking if values exist."""
        self.assertTrue(self.config.has('simple_value'))
        self.assertTrue(self.config.has('bot.name'))
        self.assertFalse(self.config.has('nonexistent'))
        self.assertFalse(self.config.has('bot.nonexistent'))
    
    def test_update(self):
        """Test updating configuration data."""
        new_data = {'new_key': 'new_value', 'bot': {'version': '1.0'}}
        self.config.update(new_data)
        
        self.assertEqual(self.config.get('new_key'), 'new_value')
        self.assertEqual(self.config.get('bot.version'), '1.0')
        # Original values should still exist
        self.assertEqual(self.config.get('bot.name'), 'TestBot')
    
    def test_to_dict(self):
        """Test converting to dictionary."""
        result = self.config.to_dict()
        self.assertEqual(result, self.test_data)
        # Should be a copy, not the same object
        self.assertIsNot(result, self.test_data)


class TestConfigManager(unittest.TestCase):
    """Test cases for ConfigManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_config.json"
        self.test_data = {
            'bot': {'name': 'TestBot', 'prefix': '!'},
            'features': {'enabled': True}
        }
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.config_path.exists():
            self.config_path.unlink()
        os.rmdir(self.temp_dir)
    
    def test_load_nonexistent_file(self):
        """Test loading from nonexistent file."""
        manager = ConfigManager(self.config_path)
        config = manager.load()
        
        self.assertIsInstance(config, Config)
        self.assertEqual(config.to_dict(), {})
    
    def test_save_and_load(self):
        """Test saving and loading configuration."""
        manager = ConfigManager(self.config_path)
        manager.config.update(self.test_data)
        manager.save()
        
        # Verify file was created
        self.assertTrue(self.config_path.exists())
        
        # Load in new manager
        new_manager = ConfigManager(self.config_path)
        loaded_config = new_manager.load()
        
        self.assertEqual(loaded_config.to_dict(), self.test_data)
    
    def test_get_set_methods(self):
        """Test get and set convenience methods."""
        manager = ConfigManager(self.config_path)
        
        # Test setting and getting
        manager.set('test.key', 'value')
        self.assertEqual(manager.get('test.key'), 'value')
        self.assertEqual(manager.get('nonexistent', 'default'), 'default')
    
    def test_auto_save(self):
        """Test auto-save functionality."""
        manager = ConfigManager(self.config_path)
        manager.set_auto_save(True)
        
        manager.set('auto.save', 'test')
        
        # File should exist after setting with auto-save
        self.assertTrue(self.config_path.exists())
        
        # Load in new manager to verify
        new_manager = ConfigManager(self.config_path)
        new_manager.load()
        self.assertEqual(new_manager.get('auto.save'), 'test')
    
    def test_from_env(self):
        """Test creating config from environment variables."""
        # Set test environment variables
        test_env = {
            'BOT_NAME': 'EnvBot',
            'BOT_PREFIX': '$',
            'BOT_ENABLED': 'true',
            'BOT_COUNT': '42',
            'BOT_RATE': '3.14'
        }
        
        # Temporarily set environment variables
        original_env = {}
        for key, value in test_env.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        try:
            manager = ConfigManager.from_env(prefix='BOT_')
            
            self.assertEqual(manager.get('name'), 'EnvBot')
            self.assertEqual(manager.get('prefix'), '$')
            self.assertEqual(manager.get('enabled'), True)  # Should be converted to bool
            self.assertEqual(manager.get('count'), 42)  # Should be converted to int
            self.assertEqual(manager.get('rate'), 3.14)  # Should be converted to float
        
        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == '__main__':
    unittest.main()