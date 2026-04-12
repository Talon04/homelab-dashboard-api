# =============================================================================
# PROXY SERVICE CLIENT - Abstraction layer for proxy provider interactions
# =============================================================================
"""Client for communicating with the proxy service.

The proxy service handles provider-specific logic (Caddy, Nginx, etc.)
and manages Caddyfile/config operations like validation, staging, and reload.

This module provides a clean abstraction so the dashboard doesn't need to
know about provider-specific APIs or implementations.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from backend import api_helper, config_utils


def get_proxy_service_url(cfg: Dict[str, Any]) -> Optional[str]:
    """Get the proxy service base URL from config.
    
    Examples:
        http://192.168.1.50:9999
        https://proxy-service.example.com:9999
    """
    host = str(cfg.get("proxy_service_host") or "").strip()
    port = int(cfg.get("proxy_service_port") or 0)
    
    if not host or port <= 0:
        return None
    
    # Default to http if not specified
    scheme = str(cfg.get("proxy_service_scheme") or "http").strip().lower()
    return f"{scheme}://{host}:{port}"


def is_proxy_service_configured(cfg: Dict[str, Any]) -> bool:
    """Check if proxy service is properly configured."""
    return get_proxy_service_url(cfg) is not None


# =============================================================================
# GENERIC OPERATIONS - Called by api_helper
# =============================================================================


def fetch_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch current proxy configuration from service.
    
    Returns:
        {
            "ok": bool,
            "config": {...},  # Full config object
            "error": str | None,
        }
    """
    service_url = get_proxy_service_url(cfg)
    if not service_url:
        return {"ok": False, "error": "Proxy service not configured (host/port missing)"}
    
    result = api_helper.http_request(
        "GET",
        f"{service_url}/config/current",
        headers=_build_service_headers(cfg),
        parse_json=True,
        verify_ssl=bool(cfg.get("proxy_service_verify_ssl", True)),
    )
    
    if not result.get("ok"):
        error_msg = result.get("error") or result.get("body") or "Failed to fetch proxy config"
        print(f"ERROR [proxy_service_client] fetch_config failed: {error_msg}")
        return {"ok": False, "error": error_msg}
    
    config_obj = result.get("json") or {}
    return {"ok": True, "config": config_obj}


def save_config(cfg: Dict[str, Any], config_payload: Any) -> Dict[str, Any]:
    """Save proxy configuration to service.
    
    Args:
        cfg: Module configuration
        config_payload: The full config object to save
    
    Returns:
        {
            "ok": bool,
            "error": str | None,
        }
    """
    service_url = get_proxy_service_url(cfg)
    if not service_url:
        return {"ok": False, "error": "Proxy service not configured (host/port missing)"}
    
    result = api_helper.http_request(
        "POST",
        f"{service_url}/config/apply",
        headers={**_build_service_headers(cfg), "Content-Type": "application/json"},
        data=config_payload,
        parse_json=True,
        verify_ssl=bool(cfg.get("proxy_service_verify_ssl", True)),
    )
    
    if not result.get("ok"):
        error_msg = result.get("error") or result.get("body") or "Failed to save proxy config"
        print(f"ERROR [proxy_service_client] save_config failed: {error_msg}")
        return {"ok": False, "error": error_msg}
    
    return {"ok": True}


def validate_config(cfg: Dict[str, Any], config_payload: Any) -> Dict[str, Any]:
    """Validate proxy configuration without applying it.
    
    Returns:
        {
            "ok": bool,
            "valid": bool,
            "errors": [str],
            "warnings": [str],
        }
    """
    service_url = get_proxy_service_url(cfg)
    if not service_url:
        return {"ok": False, "error": "Proxy service not configured (host/port missing)"}
    
    result = api_helper.http_request(
        "POST",
        f"{service_url}/config/validate",
        headers={**_build_service_headers(cfg), "Content-Type": "application/json"},
        data=config_payload,
        parse_json=True,
        verify_ssl=bool(cfg.get("proxy_service_verify_ssl", True)),
    )
    
    if not result.get("ok"):
        error_msg = result.get("error") or result.get("body") or "Failed to validate proxy config"
        print(f"ERROR [proxy_service_client] validate_config failed: {error_msg}")
        return {"ok": False, "error": error_msg}
    
    json_data = result.get("json") or {}
    return {
        "ok": True,
        "valid": json_data.get("valid", False),
        "errors": json_data.get("errors", []),
        "warnings": json_data.get("warnings", []),
    }


def stage_config(cfg: Dict[str, Any], config_payload: Any) -> Dict[str, Any]:
    """Stage proxy configuration for review before applying.
    
    Returns:
        {
            "ok": bool,
            "preview": str,  # Human-readable preview of changes
            "error": str | None,
        }
    """
    service_url = get_proxy_service_url(cfg)
    if not service_url:
        return {"ok": False, "error": "Proxy service not configured (host/port missing)"}
    
    result = api_helper.http_request(
        "POST",
        f"{service_url}/config/stage",
        headers={**_build_service_headers(cfg), "Content-Type": "application/json"},
        data=config_payload,
        parse_json=True,
        verify_ssl=bool(cfg.get("proxy_service_verify_ssl", True)),
    )
    
    if not result.get("ok"):
        error_msg = result.get("error") or result.get("body") or "Failed to stage proxy config"
        print(f"ERROR [proxy_service_client] stage_config failed: {error_msg}")
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
    service_url = get_proxy_service_url(cfg)
    if not service_url:
        return {"ok": False, "error": "Proxy service not configured (host/port missing)"}
    
    result = api_helper.http_request(
        "POST",
        f"{service_url}/config/rollback",
        headers=_build_service_headers(cfg),
        data={},
        parse_json=True,
        verify_ssl=bool(cfg.get("proxy_service_verify_ssl", True)),
    )
    
    if not result.get("ok"):
        error_msg = result.get("error") or result.get("body") or "Failed to rollback proxy config"
        print(f"ERROR [proxy_service_client] rollback_config failed: {error_msg}")
        return {"ok": False, "error": error_msg}
    
    return {"ok": True}


def get_status(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Get service and proxy health status.
    
    Returns:
        {
            "ok": bool,
            "status": str,  # e.g. "healthy", "degraded", "offline"
            "details": {...},
            "error": str | None,
        }
    """
    service_url = get_proxy_service_url(cfg)
    if not service_url:
        return {"ok": False, "error": "Proxy service not configured (host/port missing)"}
    
    result = api_helper.http_request(
        "GET",
        f"{service_url}/status",
        headers=_build_service_headers(cfg),
        parse_json=True,
        verify_ssl=bool(cfg.get("proxy_service_verify_ssl", True)),
    )
    
    if not result.get("ok"):
        return {"ok": False, "status": "offline", "error": result.get("error")}
    
    json_data = result.get("json") or {}
    return {"ok": True, "status": json_data.get("status", "unknown"), "details": json_data.get("details", {})}


# =============================================================================
# HELPERS
# =============================================================================


def _build_service_headers(cfg: Dict[str, Any]) -> Dict[str, str]:
    """Build HTTP headers for proxy service requests."""
    headers: Dict[str, str] = {"Accept": "application/json"}
    
    # Optional: Add authentication token if configured
    token = str(cfg.get("proxy_service_token") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    return headers
