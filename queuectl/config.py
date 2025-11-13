"""
Configuration management for queuectl
Stores settings like max_retries and backoff_base
"""
import json
import os
from pathlib import Path
from typing import Any, Dict


class Config:
    """
    Manages queuectl configuration settings.
    Stores configuration in a JSON file in the user's home directory.
    """
    
    DEFAULT_CONFIG = {
        "max_retries": 3,
        "backoff_base": 2,  
        "worker_poll_interval": 1, 
        "db_path": "jobs.db", 
    }
    
    def __init__(self, config_path: str = None): #type:ignore
        """
        Initialize configuration manager.
        
        Args:
            config_path: Optional custom path for config file
        """
        if config_path is None:
            # Store config in user's home directory
            home = Path.home()
            self.config_dir = home / ".queuectl"
            self.config_dir.mkdir(exist_ok=True)
            self.config_path = self.config_dir / "config.json"
        else:
            self.config_path = Path(config_path)
        
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create with defaults"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults to handle new keys
                    return {**self.DEFAULT_CONFIG, **config}
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load config: {e}")
                return self.DEFAULT_CONFIG.copy()
        else:
            # Create new config file with defaults
            self._save_config(self.DEFAULT_CONFIG)
            return self.DEFAULT_CONFIG.copy()
    
    def _save_config(self, config: Dict[str, Any]):
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except IOError as e:
            print(f"Error: Could not save config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
        
        Returns:
            Configuration value
        """
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any):
        """
        Set a configuration value and persist to disk.
        
        Args:
            key: Configuration key
            value: Value to set
        """
        self._config[key] = value
        self._save_config(self._config)
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values"""
        return self._config.copy()
    
    def reset(self):
        """Reset configuration to defaults"""
        self._config = self.DEFAULT_CONFIG.copy()
        self._save_config(self._config)
    
    @property
    def max_retries(self) -> int:
        """Get max_retries setting"""
        return self._config["max_retries"]
    
    @property
    def backoff_base(self) -> int:
        """Get backoff_base setting"""
        return self._config["backoff_base"]
    
    @property
    def worker_poll_interval(self) -> int:
        """Get worker_poll_interval setting"""
        return self._config["worker_poll_interval"]
    
    @property
    def db_path(self) -> str:
        """Get database path setting"""
        return self._config["db_path"]


# Global config instance
_config_instance = None


def get_config() -> Config:
    """Get the global configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance