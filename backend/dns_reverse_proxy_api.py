# =============================================================================
# DNS/REVERSE PROXY API COMPAT WRAPPER
# =============================================================================
"""Backward-compatible wrapper around backend.api_helper.

This module is intentionally thin so older imports keep working.
New code should import from ``backend.api_helper`` directly.
"""

from backend.api_helper import (  # noqa: F401
    get_reverse_proxy_entries_from_api,
    get_dns_entries_from_api,
    build_proxy_dns_mappings,
)
