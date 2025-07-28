"""
Configuration management utilities for Discord bots.
"""

import json
import os
from typing import Any, Dict, Optional, Union
from pathlib import Path


class Config:
    """
    A simple configuration class that supports nested access and type conversion.
    """
    
    def __init__(self, data: Dict[str, Any] = None):
        self._data = data or {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key. Supports dot notation for nested access.
        
        Args:
            key: The configuration key (supports dot notation)
            default: Default value if key is not found
            
        Returns:
            The configuration value or default
        """
        keys = key.split('.')
        current = self._data
        
        try:
            for k in keys:
                current = current[k]
            return current
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value by key. Supports dot notation for nested access.
        
        Args:
            key: The configuration key (supports dot notation)
            value: The value to set
        """
        keys = key.split('.')
        current = self._data
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
    
    def has(self, key: str) -> bool:
        """
        Check if a configuration key exists.
        
        Args:
            key: The configuration key to check
            
        Returns:
            True if key exists, False otherwise
        """
        return self.get(key) is not None
    
    def update(self, data: Dict[str, Any]) -> None:
        """
        Update configuration with new data.
        
        Args:
            data: Dictionary of configuration data to merge
        """
        self._data.update(data)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.
        
        Returns:
            Dictionary representation of configuration
        """
        return self._data.copy()


class ConfigManager:
    """
    Configuration manager that handles loading and saving configuration files.
    """
    
    def __init__(self, config_path: Union[str, Path] = "config.json"):
        self.config_path = Path(config_path)
        self.config = Config()
        self._auto_save = False
    
    def load(self) -> Config:
        """
        Load configuration from file.
        
        Returns:
            The loaded configuration
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.config = Config(data)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load config from {self.config_path}: {e}")
                self.config = Config()
        else:
            self.config = Config()
        
        return self.config
    
    def save(self) -> None:
        """
        Save configuration to file.
        """
        try:
            # Create directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config.to_dict(), f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error: Failed to save config to {self.config_path}: {e}")
    
    def set_auto_save(self, enabled: bool) -> None:
        """
        Enable or disable automatic saving when configuration changes.
        
        Args:
            enabled: Whether to enable auto-save
        """
        self._auto_save = enabled
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: The configuration key
            default: Default value if key is not found
            
        Returns:
            The configuration value or default
        """
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.
        
        Args:
            key: The configuration key
            value: The value to set
        """
        self.config.set(key, value)
        if self._auto_save:
            self.save()
    
    @classmethod
    def from_env(cls, prefix: str = "BOT_") -> 'ConfigManager':
        """
        Create a configuration manager from environment variables.
        
        Args:
            prefix: Prefix for environment variables
            
        Returns:
            ConfigManager instance with environment variables loaded
        """
        manager = cls()
        config_data = {}
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower().replace('_', '.')
                # Try to convert to appropriate type
                if value.lower() in ('true', 'false'):
                    value = value.lower() == 'true'
                elif value.isdigit():
                    value = int(value)
                elif value.replace('.', '').isdigit():
                    value = float(value)
                
                config_data[config_key] = value
        
        manager.config.update(config_data)
        return manager