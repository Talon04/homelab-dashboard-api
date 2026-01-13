import json
import os
from typing import Any, Dict, Optional
from backend.paths import BASE_DIR


class ConfigManager:
    """Very simple JSON-backed config manager.

    - Loads config once at startup (or creates a default one).
    - Every `set`/`update` writes the whole file synchronously.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        self.config_path = config_path or os.path.join(BASE_DIR, "data", "config.json")
        self._config: Dict[str, Any] = {}
        self.load_config()

    def load_config(self) -> None:
        """Load configuration from file or create defaults if missing/broken."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    self._config = json.load(f)
            else:
                self._config = self._get_default_config()
                self.save()
        except Exception as e:
            print(f"Error loading config, using defaults: {e}")
            self._config = self._get_default_config()
            self.save()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "proxy_count": 0,
            "internal_ip": "127.0.0.1",
            "external_ip": "127.0.0.1",
            "first_boot": True,
            "enabled_modules": ["containers"],
            "modules_order": ["containers", "proxmox", "code_editor", "monitor"],
            "modules": {
                "proxmox": {
                    "api_url": "https://proxmox.example:8006/api2/json",
                    "token_id": "",
                    "token_secret": "",
                    "verify_ssl": True,
                    "node": "",
                },
                "code_editor": {
                    "custom_js": "",
                    "custom_css": "",
                    "pages": ["containers"],
                },
                "monitor": {},
            },
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value and immediately save to disk."""
        self._config[key] = value
        self.save()

    def update(self, updates: Dict[str, Any]) -> None:
        """Update multiple configuration values and immediately save to disk."""
        self._config.update(updates)
        self.save()

    def save(self) -> None:
        """Write current configuration to disk in JSON format."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(self._config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get_all(self) -> Dict[str, Any]:
        """Get a shallow copy of all configuration values."""
        return self._config.copy()


# Global instance
config_manager = ConfigManager()
