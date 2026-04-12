# =============================================================================
# CADDY MANAGER CORE - File ops, validation, and state tracking
# =============================================================================
"""Core managers for Caddyfile handling: file ops, validation, state tracking."""

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional


# =============================================================================
# CADDYFILE MANAGER - File operations on Caddyfile
# =============================================================================


class CaddyfileManager:
    """Manages Caddyfile on disk."""
    
    def __init__(self, caddyfile_path: str, data_dir: str):
        """
        Args:
            caddyfile_path: Path to live Caddyfile (e.g., /etc/caddy/Caddyfile)
            data_dir: Directory for staging/backup (e.g., /var/lib/caddy-manager)
        """
        self.caddyfile_path = caddyfile_path
        self.data_dir = data_dir
        
        # Staged copy (pending changes)
        self.staged_path = os.path.join(data_dir, "Caddyfile.staged")
        
        # Backup directory (rolling snapshots)
        self.backup_dir = os.path.join(data_dir, "backups")
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def read_current(self) -> str:
        """Read the live Caddyfile."""
        with open(self.caddyfile_path, "r") as f:
            return f.read()
    
    def read_staged(self) -> str:
        """Read the staged Caddyfile."""
        if not os.path.exists(self.staged_path):
            raise FileNotFoundError(f"No staged config at {self.staged_path}")
        with open(self.staged_path, "r") as f:
            return f.read()
    
    def write_staged(self, content: str) -> str:
        """Write content to staged file.
        
        Returns:
            Path to staged file
        """
        with open(self.staged_path, "w") as f:
            f.write(content)
        return self.staged_path
    
    def staged_exists(self) -> bool:
        """Check if staged config exists."""
        return os.path.exists(self.staged_path)
    
    def backup_current(self) -> str:
        """Backup current Caddyfile with timestamp.
        
        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.backup_dir, f"Caddyfile.{timestamp}.bak")
        shutil.copy2(self.caddyfile_path, backup_path)
        return backup_path
    
    def apply_staged(self) -> None:
        """Apply staged config: delete current, move staged → current."""
        if not self.staged_exists():
            raise FileNotFoundError(f"No staged config at {self.staged_path}")
        
        # Move staged to live (atomic rename)
        shutil.move(self.staged_path, self.caddyfile_path)
    
    def rollback_to_backup(self) -> Optional[str]:
        """Restore from most recent backup.
        
        Returns:
            Path to backup that was restored, or None if no backups
        """
        # Get most recent backup
        backups = sorted(os.listdir(self.backup_dir), reverse=True)
        if not backups:
            return None
        
        # Restore
        latest_backup = os.path.join(self.backup_dir, backups[0])
        shutil.copy2(latest_backup, self.caddyfile_path)
        return latest_backup
    
    def clear_staged(self) -> None:
        """Remove staged file (cleanup)."""
        if os.path.exists(self.staged_path):
            os.remove(self.staged_path)


# =============================================================================
# CADDY VALIDATOR - Validate Caddyfile syntax
# =============================================================================


class CaddyValidator:
    """Validate Caddyfile syntax."""
    
    def __init__(self, data_dir: str):
        """
        Args:
            data_dir: Directory for temp validation files
        """
        self.data_dir = data_dir
        self.temp_dir = os.path.join(data_dir, "temp")
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def validate(self, config_content: str) -> Dict[str, Any]:
        """Validate Caddyfile content via `caddy validate`.
        
        Args:
            config_content: Caddyfile content as string
        
        Returns:
            {
                "ok": bool,
                "valid": bool,
                "errors": [str],
                "warnings": [str],
                "message": str,
            }
        """
        # Write to temp file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            dir=self.temp_dir,
            delete=False,
        ) as f:
            temp_path = f.name
            # Caddy validate expects JSON config, not Caddyfile
            # If content looks like Caddyfile, we'd need to convert or use -adapter flag
            f.write(config_content)
        
        try:
            # Run caddy validate
            result = subprocess.run(
                ["caddy", "validate", "--config", temp_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode == 0:
                return {
                    "ok": True,
                    "valid": True,
                    "errors": [],
                    "warnings": [],
                    "message": "Caddyfile is valid",
                }
            else:
                # Parse stderr for errors
                errors = self._parse_caddy_errors(result.stderr)
                return {
                    "ok": True,
                    "valid": False,
                    "errors": errors,
                    "warnings": [],
                    "message": "Caddyfile validation failed",
                }
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "valid": False,
                "errors": ["Validation timeout"],
                "warnings": [],
                "message": "Validation timed out",
            }
        except FileNotFoundError:
            return {
                "ok": False,
                "valid": False,
                "errors": ["caddy binary not found"],
                "warnings": [],
                "message": "Caddy not installed",
            }
        except Exception as exc:
            return {
                "ok": False,
                "valid": False,
                "errors": [str(exc)],
                "warnings": [],
                "message": "Validation error",
            }
        finally:
            # Cleanup
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    def _parse_caddy_errors(self, stderr: str) -> List[str]:
        """Parse errors from caddy validate stderr."""
        if not stderr:
            return []
        return [line.strip() for line in stderr.split("\n") if line.strip()]


# =============================================================================
# STATE MANAGER - Track service state and operation history
# =============================================================================


class StateManager:
    """Track service state and operations."""
    
    def __init__(self, data_dir: str):
        """
        Args:
            data_dir: Directory for state files
        """
        self.data_dir = data_dir
        self.state_file = os.path.join(data_dir, "state.json")
        self.history_file = os.path.join(data_dir, "history.jsonl")
        
        # Initialize state if not exists
        if not os.path.exists(self.state_file):
            self._init_state()
    
    def _init_state(self) -> None:
        """Initialize empty state."""
        state = {
            "last_apply": None,
            "last_rollback": None,
            "last_validate": None,
            "staged_exists": False,
            "uptime_start": datetime.now().isoformat(),
        }
        self._write_state(state)
    
    def get_state(self) -> Dict[str, Any]:
        """Get current state."""
        if not os.path.exists(self.state_file):
            self._init_state()
        
        with open(self.state_file, "r") as f:
            return json.load(f)
    
    def _write_state(self, state: Dict[str, Any]) -> None:
        """Write state to file."""
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)
    
    def record_apply(self) -> None:
        """Record a successful apply operation."""
        state = self.get_state()
        state["last_apply"] = datetime.now().isoformat()
        state["staged_exists"] = False
        self._write_state(state)
        self._append_history("apply", {"status": "success"})
    
    def record_rollback(self) -> None:
        """Record a rollback operation."""
        state = self.get_state()
        state["last_rollback"] = datetime.now().isoformat()
        state["staged_exists"] = False
        self._write_state(state)
        self._append_history("rollback", {"status": "success"})
    
    def record_stage(self, valid: bool = False) -> None:
        """Record a stage operation."""
        state = self.get_state()
        state["staged_exists"] = True
        state["last_validate"] = datetime.now().isoformat()
        self._write_state(state)
        self._append_history("stage", {"valid": valid})
    
    def _append_history(self, operation: str, details: Dict[str, Any]) -> None:
        """Append operation to history log."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "details": details,
        }
        with open(self.history_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get last N operations from history."""
        if not os.path.exists(self.history_file):
            return []
        
        history = []
        with open(self.history_file, "r") as f:
            for line in f:
                if line.strip():
                    history.append(json.loads(line))
        
        return history[-limit:]
