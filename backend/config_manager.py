import json
import os
import threading
import time
from typing import Any, Dict, Optional

class ConfigManager:
    def __init__(self, config_path: str = "config/config.json"):
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._last_save = 0
        self._save_delay = 0.5  # 500ms delay for batching saves
        self._pending_save = False
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from file"""
        with self._lock:
            try:
                if os.path.exists(self.config_path):
                    with open(self.config_path, 'r') as f:
                        self._config = json.load(f)
                else:
                    self._config = self._get_default_config()
                    self._save_now()
            except Exception as e:
                print(f"Error loading config: {e}")
                self._config = self._get_default_config()
                self._save_now()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "preferred_ports": {},
            "internal_link_bodies": {},
            "external_link_bodies": {},
            "exposed_containers": [],
            "proxy_count": 0,
            "internal_ip": "127.0.0.1",
            "external_ip": "127.0.0.1",
            "first_boot": True,
            "backup_view_enabled": False,
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        with self._lock:
            return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value"""
        with self._lock:
            self._config[key] = value
            self._schedule_save()
    
    def update(self, updates: Dict[str, Any]) -> None:
        """Update multiple configuration values at once"""
        with self._lock:
            self._config.update(updates)
            self._schedule_save()
    
    def get_nested(self, *keys: str, default: Any = None) -> Any:
        """Get a nested configuration value (e.g., get_nested('preferred_ports', 'container_id'))"""
        with self._lock:
            current = self._config
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return default
            return current
    
    def set_nested(self, *keys_and_value) -> None:
        """Set a nested configuration value (e.g., set_nested('preferred_ports', 'container_id', '8080'))"""
        if len(keys_and_value) < 2:
            raise ValueError("Need at least one key and a value")
        
        keys = keys_and_value[:-1]
        value = keys_and_value[-1]
        
        with self._lock:
            current = self._config
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            current[keys[-1]] = value
            self._schedule_save()
    
    def delete_nested(self, *keys: str) -> bool:
        """Delete a nested configuration value"""
        with self._lock:
            current = self._config
            for key in keys[:-1]:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return False
            
            if isinstance(current, dict) and keys[-1] in current:
                del current[keys[-1]]
                self._schedule_save()
                return True
            return False
    
    def _schedule_save(self) -> None:
        """Schedule a delayed save to batch multiple updates"""
        current_time = time.time()
        self._last_save = current_time
        
        if not self._pending_save:
            self._pending_save = True
            threading.Timer(self._save_delay, self._delayed_save).start()
    
    def _delayed_save(self) -> None:
        """Perform delayed save if no recent updates"""
        current_time = time.time()
        if current_time - self._last_save >= self._save_delay:
            self._save_now()
            self._pending_save = False
        else:
            # Reschedule if there were recent updates
            threading.Timer(self._save_delay, self._delayed_save).start()
    
    def _save_now(self) -> None:
        """Immediately save configuration to file"""
        with self._lock:
            temp_path = None
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                
                # Atomic write: write to temp file then rename
                temp_path = self.config_path + '.tmp'
                with open(temp_path, 'w') as f:
                    json.dump(self._config, f, indent=4)
                
                # Atomic rename
                os.rename(temp_path, self.config_path)
                
            except Exception as e:
                print(f"Error saving config: {e}")
                # Clean up temp file if it exists
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
    
    def force_save(self) -> None:
        """Force immediate save"""
        self._save_now()
        self._pending_save = False
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values"""
        with self._lock:
            return self._config.copy()

# Global instance
config_manager = ConfigManager()
