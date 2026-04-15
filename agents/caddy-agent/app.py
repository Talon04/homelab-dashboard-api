# =============================================================================
# CADDY MANAGER SERVICE - Caddyfile staging and validation
# =============================================================================
"""Flask service for managing Caddyfile via staging and validation.

This service provides a clean REST API to:
1. Fetch the current Caddyfile
2. Stage changes to a temporary copy
3. Validate staged changes with `caddy validate`
4. Apply (atomic swap + reload)
5. Rollback to previous state

The Caddyfile is the source of truth. All operations are file-based.
"""

import json
import os
import traceback
from flask import Flask, jsonify, request

from managers import CaddyfileManager, CaddyValidator, StateManager
import logger


# =============================================================================
# CONFIGURATION
# =============================================================================

CADDYFILE_PATH = os.environ.get("CADDYFILE_PATH", "/etc/caddy/Caddyfile")
DATA_DIR = os.environ.get("CADDY_MANAGER_DATA", "/var/lib/caddy-manager")
CADDY_RELOAD_CMD = os.environ.get("CADDY_RELOAD_CMD", "systemctl reload caddy")

os.makedirs(DATA_DIR, exist_ok=True)

# =============================================================================
# INITIALIZATION
# =============================================================================

app = Flask(__name__)
caddyfile_mgr = CaddyfileManager(CADDYFILE_PATH, DATA_DIR)
validator = CaddyValidator(DATA_DIR)
state_mgr = StateManager(DATA_DIR)

# =============================================================================
# HEALTH / STATUS
# =============================================================================


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


@app.route("/status")
def get_status():
    """Get service and Caddyfile state."""
    state = state_mgr.get_state()
    return jsonify({
        "status": "healthy",
        "caddyfile_path": CADDYFILE_PATH,
        "data_dir": DATA_DIR,
        "state": state,
    }), 200


# =============================================================================
# CONFIG OPERATIONS
# =============================================================================


@app.route("/config/current")
def get_current_config():
    """Fetch current Caddyfile (source of truth)."""
    try:
        content = caddyfile_mgr.read_current()
        return jsonify({
            "ok": True,
            "config": content,
            "path": CADDYFILE_PATH,
        }), 200
    except FileNotFoundError:
        return jsonify({
            "ok": False,
            "error": f"Caddyfile not found at {CADDYFILE_PATH}",
        }), 404
    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": f"Failed to read Caddyfile: {exc}",
        }), 500


@app.route("/config/validate", methods=["POST"])
def validate_config():
    """Validate a config without staging it.
    
    Request body:
        {
            "config": "caddyfile content as string or JSON"
        }
    """
    data = request.get_json(silent=True) or {}
    config_content = data.get("config")
    
    if not config_content:
        logger.error("caddy_agent", "config required in request body")
        return jsonify({
            "ok": False,
            "error": "config is required in request body",
        }), 400
    
    try:
        logger.debug("caddy_agent", f"Validating config (length: {len(config_content)})")
        result = validator.validate(config_content)
        logger.debug("caddy_agent", f"Validation: valid={result.get('valid')}, errors={len(result.get('errors', []))}")
        return jsonify(result), (200 if result.get("valid") else 400)
    except Exception as exc:
        logger.error("caddy_agent", f"Validation failed: {exc}")
        return jsonify({
            "ok": False,
            "valid": False,
            "error": f"Validation failed: {exc}",
        }), 500


@app.route("/config/stage", methods=["POST"])
def stage_config():
    """Stage a config change for review.
    
    Request body:
        {
            "config": "caddyfile content"
        }
    
    Returns:
        {
            "ok": bool,
            "staged_path": str,
            "preview": str (human-readable),
            "valid": bool,
            "errors": [str],
            "warnings": [str],
        }
    """
    data = request.get_json(silent=True) or {}
    config_content = data.get("config")
    
    if not config_content:
        logger.error("caddy_agent", "config required in request body")
        return jsonify({
            "ok": False,
            "error": "config is required in request body",
        }), 400
    
    try:
        logger.debug("caddy_agent", f"Staging config (length: {len(config_content)})")
        # Stage the config
        staged_path = caddyfile_mgr.write_staged(config_content)
        logger.debug("caddy_agent", f"Config staged to: {staged_path}")
        
        # Validate
        validation = validator.validate(config_content)
        logger.debug("caddy_agent", f"Validation: valid={validation.get('valid')}, errors={len(validation.get('errors', []))}")
        
        # Generate preview
        preview = _generate_preview(config_content)
        
        result = {
            "ok": True,
            "staged_path": staged_path,
            "preview": preview,
            "valid": validation.get("valid", False),
            "errors": validation.get("errors", []),
            "warnings": validation.get("warnings", []),
        }
        
        return jsonify(result), 200
    except Exception as exc:
        logger.error("caddy_agent", f"Failed to stage config: {exc}")
        return jsonify({
            "ok": False,
            "error": f"Failed to stage config: {exc}",
        }), 500


@app.route("/config/apply", methods=["POST"])
def apply_config():
    """Apply staged config (atomic: validate → backup → swap → reload).
    
    Returns:
        {
            "ok": bool,
            "message": str,
            "old_path": str,
            "new_path": str,
        }
    """
    try:
        # Check if staged config exists
        if not caddyfile_mgr.staged_exists():
            logger.error("caddy_agent", "No staged config exists")
            return jsonify({
                "ok": False,
                "error": "No staged config to apply",
            }), 400
        
        logger.debug("caddy_agent", "Staged config exists, reading...")
        # Validate staged
        staged_content = caddyfile_mgr.read_staged()
        logger.debug("caddy_agent", f"Staged content length: {len(staged_content)}")
        
        validation = validator.validate(staged_content)
        logger.debug("caddy_agent", f"Validation result: valid={validation.get('valid')}, errors={len(validation.get('errors', []))}")
        
        if not validation.get("valid"):
            error_list = validation.get("errors", [])
            error_msg = f"Staged config invalid: {', '.join(error_list) if error_list else 'Unknown error'}"
            logger.error("caddy_agent", error_msg)
            return jsonify({
                "ok": False,
                "error": error_msg,
            }), 400
        
        logger.debug("caddy_agent", "Validation passed, backing up current config...")
        # Backup current
        backup_path = caddyfile_mgr.backup_current()
        logger.debug("caddy_agent", f"Backed up to: {backup_path}")
        
        logger.debug("caddy_agent", "Applying staged config...")
        # Swap
        caddyfile_mgr.apply_staged()
        logger.debug("caddy_agent", "Staged config applied successfully")
        
        # Reload Caddy
        logger.debug("caddy_agent", "Reloading Caddy...")
        os.system(CADDY_RELOAD_CMD)
        logger.debug("caddy_agent", "Caddy reload command executed")
        
        # Update state
        state_mgr.record_apply()
        logger.info("caddy_agent", "Config applied successfully")
        
        return jsonify({
            "ok": True,
            "message": "Config applied successfully",
            "backup_path": backup_path,
        }), 200
    except Exception as exc:
        error_trace = traceback.format_exc()
        logger.error("caddy_agent", f"Exception: {exc}")
        logger.error("caddy_agent", f"Traceback:\n{error_trace}")
        return jsonify({
            "ok": False,
            "error": f"Failed to apply config: {exc}",
        }), 500


@app.route("/config/rollback", methods=["POST"])
def rollback_config():
    """Rollback to previous backup.
    
    Returns:
        {
            "ok": bool,
            "message": str,
        }
    """
    try:
        # Restore from backup
        backup_path = caddyfile_mgr.rollback_to_backup()
        if not backup_path:
            return jsonify({
                "ok": False,
                "error": "No backup available",
            }), 400
        
        # Reload Caddy
        os.system(CADDY_RELOAD_CMD)
        
        # Update state
        state_mgr.record_rollback()
        
        return jsonify({
            "ok": True,
            "message": "Rolled back to previous config",
            "restored_from": backup_path,
        }), 200
    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": f"Failed to rollback: {exc}",
        }), 500


# =============================================================================
# HELPERS
# =============================================================================


def _generate_preview(config_content: str) -> str:
    """Generate a human-readable preview of the config."""
    # For now, just return first 500 chars + summary
    lines = config_content.split("\n")
    num_blocks = sum(1 for line in lines if "{" in line)
    num_hosts = sum(1 for line in lines if ":" in line and not line.strip().startswith("#"))
    
    preview = f"Configuration preview:\n"
    preview += f"- {len(lines)} lines\n"
    preview += f"- {num_blocks} blocks\n"
    preview += f"- {num_hosts} hosts\n"
    preview += f"\nFirst 200 chars:\n{config_content[:200]}..."
    return preview


# =============================================================================
# ERROR HANDLERS
# =============================================================================


@app.errorhandler(404)
def not_found(e):
    return jsonify({"ok": False, "error": "Not found"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"ok": False, "error": "Internal server error"}), 500


# =============================================================================
# MAIN
# =============================================================================


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 9999))
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
