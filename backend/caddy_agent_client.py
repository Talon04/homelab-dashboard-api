# =============================================================================
# CADDY AGENT CLIENT - Abstraction layer for Caddy config management
# =============================================================================
"""Client for communicating with the Caddy Agent.

The Caddy Agent handles file-based Caddyfile operations like validation,
staging, and reload. It manages the Caddyfile as the source of truth.

This module provides a clean abstraction so the dashboard doesn't need to
know about agent-specific implementation details.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from backend import api_helper, config_utils


def get_caddy_agent_url(cfg: Dict[str, Any]) -> Optional[str]:
    """Get the Caddy Agent base URL from config.
    
    Examples:
        http://192.168.1.50:9999
        https://caddy-host.example.com:9999
    """
    host = str(cfg.get("caddy_agent_host") or "").strip()
    port = int(cfg.get("caddy_agent_port") or 0)
    
    if not host or port <= 0:
        return None
    
    # Default to http if not specified
    scheme = str(cfg.get("caddy_agent_scheme") or "http").strip().lower()
    return f"{scheme}://{host}:{port}"


def is_caddy_agent_configured(cfg: Dict[str, Any]) -> bool:
    """Check if Caddy Agent is properly configured."""
    return get_caddy_agent_url(cfg) is not None


# =============================================================================
# GENERIC OPERATIONS - Called by api_helper
# =============================================================================


def fetch_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch current Caddyfile configuration from agent.
    
    Returns:
        {
            "ok": bool,
            "config": "raw caddyfile text",  # String, not dict!
            "error": str | None,
        }
    """
    agent_url = get_caddy_agent_url(cfg)
    if not agent_url:
        return {"ok": False, "error": "Caddy Agent not configured (host/port missing)"}
    
    result = api_helper.http_request(
        "GET",
        f"{agent_url}/config/current",
        headers=_build_agent_headers(cfg),
        parse_json=True,
        verify_ssl=bool(cfg.get("caddy_agent_verify_ssl", True)),
    )
    
    if not result.get("ok"):
        error_msg = result.get("error") or result.get("body") or "Failed to fetch Caddyfile config"
        print(f"ERROR [caddy_agent_client] fetch_config failed: {error_msg}")
        return {"ok": False, "error": error_msg}
    
    # Agent returns {"ok": true, "config": "raw text", "path": "..."}
    # Extract the config field from the agent response
    agent_response = result.get("json") or {}
    config_text = agent_response.get("config") or ""
    
    return {"ok": True, "config": config_text}


def save_config(cfg: Dict[str, Any], config_payload: Any) -> Dict[str, Any]:
    """Save Caddyfile configuration to agent (stage then apply).
    
    Args:
        cfg: Module configuration
        config_payload: The full config object to save
    
    Returns:
        {
            "ok": bool,
            "error": str | None,
        }
    """
    agent_url = get_caddy_agent_url(cfg)
    if not agent_url:
        return {"ok": False, "error": "Caddy Agent not configured (host/port missing)"}
    
    # Wrap payload in required format for agent endpoints
    wrapped_payload = {"config": config_payload} if isinstance(config_payload, str) else config_payload
    
    # Step 1: Stage the config (validates and writes to staged file)
    stage_result = api_helper.http_request(
        "POST",
        f"{agent_url}/config/stage",
        headers=_build_agent_headers(cfg),
        data=wrapped_payload,
        parse_json=True,
        verify_ssl=bool(cfg.get("caddy_agent_verify_ssl", True)),
    )
    
    if not stage_result.get("ok"):
        error_msg = stage_result.get("error") or stage_result.get("body") or "Failed to stage Caddyfile config"
        print(f"ERROR [caddy_agent_client] save_config (stage) failed: {error_msg}")
        return {"ok": False, "error": error_msg}
    
    # Check if staged config is valid
    json_data = stage_result.get("json") or {}
    if not json_data.get("valid"):
        errors = json_data.get("errors") or []
        error_msg = f"Caddyfile validation failed: {', '.join(errors) if errors else 'Unknown error'}"
        print(f"ERROR [caddy_agent_client] save_config (validation) failed: {error_msg}")
        return {"ok": False, "error": error_msg}
    
    # Step 2: Apply the staged config (no body needed, applies what was just staged)
    apply_result = api_helper.http_request(
        "POST",
        f"{agent_url}/config/apply",
        headers=_build_agent_headers(cfg),
        parse_json=True,
        verify_ssl=bool(cfg.get("caddy_agent_verify_ssl", True)),
    )
    
    if not apply_result.get("ok"):
        error_msg = apply_result.get("error") or apply_result.get("body") or "Failed to apply Caddyfile config"
        print(f"ERROR [caddy_agent_client] save_config (apply) failed: {error_msg}")
        return {"ok": False, "error": error_msg}
    
    return {"ok": True}


def validate_config(cfg: Dict[str, Any], config_payload: Any) -> Dict[str, Any]:
    """Validate Caddyfile configuration without applying it.
    
    Returns:
        {
            "ok": bool,
            "valid": bool,
            "errors": [str],
            "warnings": [str],
        }
    """
    agent_url = get_caddy_agent_url(cfg)
    if not agent_url:
        return {"ok": False, "error": "Caddy Agent not configured (host/port missing)"}
    
    # Wrap payload in required format
    wrapped_payload = {"config": config_payload} if isinstance(config_payload, str) else config_payload
    
    result = api_helper.http_request(
        "POST",
        f"{agent_url}/config/validate",
        headers=_build_agent_headers(cfg),
        data=wrapped_payload,
        parse_json=True,
        verify_ssl=bool(cfg.get("caddy_agent_verify_ssl", True)),
    )
    
    if not result.get("ok"):
        error_msg = result.get("error") or result.get("body") or "Failed to validate Caddyfile config"
        print(f"ERROR [caddy_agent_client] validate_config failed: {error_msg}")
        return {"ok": False, "error": error_msg}
    
    json_data = result.get("json") or {}
    return {
        "ok": True,
        "valid": json_data.get("valid", False),
        "errors": json_data.get("errors", []),
        "warnings": json_data.get("warnings", []),
    }


def stage_config(cfg: Dict[str, Any], config_payload: Any) -> Dict[str, Any]:
    """Stage Caddyfile configuration for review before applying.
    
    Returns:
        {
            "ok": bool,
            "preview": str,  # Human-readable preview of changes
            "error": str | None,
        }
    """
    agent_url = get_caddy_agent_url(cfg)
    if not agent_url:
        return {"ok": False, "error": "Caddy Agent not configured (host/port missing)"}
    
    # Wrap payload in required format
    wrapped_payload = {"config": config_payload} if isinstance(config_payload, str) else config_payload
    
    result = api_helper.http_request(
        "POST",
        f"{agent_url}/config/stage",
        headers=_build_agent_headers(cfg),
        data=wrapped_payload,
        parse_json=True,
        verify_ssl=bool(cfg.get("caddy_agent_verify_ssl", True)),
    )
    
    if not result.get("ok"):
        error_msg = result.get("error") or result.get("body") or "Failed to stage Caddyfile config"
        print(f"ERROR [caddy_agent_client] stage_config failed: {error_msg}")
        return {"ok": False, "error": error_msg}
    
    json_data = result.get("json") or {}
    return {
        "ok": True,
        "preview": json_data.get("preview", ""),
    }


def rollback_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Rollback to previous known-good configuration.
    
    Returns:
        {
            "ok": bool,
            "error": str | None,
        }
    """
    agent_url = get_caddy_agent_url(cfg)
    if not agent_url:
        return {"ok": False, "error": "Caddy Agent not configured (host/port missing)"}
    
    result = api_helper.http_request(
        "POST",
        f"{agent_url}/config/rollback",
        headers=_build_agent_headers(cfg),
        data={},
        parse_json=True,
        verify_ssl=bool(cfg.get("caddy_agent_verify_ssl", True)),
    )
    
    if not result.get("ok"):
        error_msg = result.get("error") or result.get("body") or "Failed to rollback Caddyfile config"
        print(f"ERROR [caddy_agent_client] rollback_config failed: {error_msg}")
        return {"ok": False, "error": error_msg}
    
    return {"ok": True}


def get_status(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Get agent and Caddy health status.
    
    Returns:
        {
            "ok": bool,
            "status": str,  # e.g. "healthy", "degraded", "offline"
            "details": {...},
            "error": str | None,
        }
    """
    agent_url = get_caddy_agent_url(cfg)
    if not agent_url:
        return {"ok": False, "error": "Caddy Agent not configured (host/port missing)"}
    
    result = api_helper.http_request(
        "GET",
        f"{agent_url}/status",
        headers=_build_agent_headers(cfg),
        parse_json=True,
        verify_ssl=bool(cfg.get("caddy_agent_verify_ssl", True)),
    )
    
    if not result.get("ok"):
        return {"ok": False, "status": "offline", "error": result.get("error")}
    
    json_data = result.get("json") or {}
    return {"ok": True, "status": json_data.get("status", "unknown"), "details": json_data.get("details", {})}


# =============================================================================
# HELPERS
# =============================================================================


def _build_agent_headers(cfg: Dict[str, Any]) -> Dict[str, str]:
    """Build HTTP headers for Caddy Agent requests."""
    headers: Dict[str, str] = {"Accept": "application/json"}
    
    # Optional: Add authentication token if configured
    token = str(cfg.get("caddy_agent_token") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    return headers
