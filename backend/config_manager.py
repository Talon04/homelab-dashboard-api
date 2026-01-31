# =============================================================================
# CONFIG MANAGER - JSON-backed persistent configuration
# =============================================================================
"""
Simple JSON-backed configuration manager for the dashboard.

Provides read/write access to persistent settings stored in config.json.
"""

import json
import os
from typing import Any, Dict, Optional

from backend.paths import DATA_DIR


# =============================================================================
# CONFIG MANAGER CLASS
# =============================================================================


class ConfigManager:
    """Very simple JSON-backed config manager.

    - Loads config once at startup (or creates a default one).
    - Every `set`/`update` writes the whole file synchronously.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        # Use DATA_DIR which respects environment variables
        self.config_path = config_path or os.path.join(DATA_DIR, "config.json")
        self._config: Dict[str, Any] = {}
        self.load_config()

    # -------------------------------------------------------------------------
    # Config Loading
    # -------------------------------------------------------------------------

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
        """Get default configuration."""
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
                "monitor": {
                    "polling_rate": 10.0
                },
                "notifications": {
                    "polling_rate": 60.0
                }
            },
        }

    # -------------------------------------------------------------------------
    # Getters & Setters
    # -------------------------------------------------------------------------

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

    def get_all(self) -> Dict[str, Any]:
        """Get a shallow copy of all configuration values."""
        return self._config.copy()

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def save(self) -> None:
        """Write current configuration to disk in JSON format."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(self._config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

config_manager = ConfigManager()
