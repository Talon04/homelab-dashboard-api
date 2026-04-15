# =============================================================================
# DNS/REVERSE PROXY ROUTES - Unified DNS/Proxy mapping endpoints
# =============================================================================
"""Flask routes for DNS and reverse proxy mapping data."""

import json

from flask import Blueprint, jsonify, request

from backend import api_helper


dns_reverse_proxy_bp = Blueprint("dns_reverse_proxy", __name__)


@dns_reverse_proxy_bp.route("/api/dns-reverse-proxy/mappings")
def get_dns_reverse_proxy_mappings():
    """Return hostname-based mappings of reverse proxy targets and DNS records."""
    rows = api_helper.build_proxy_dns_mappings()
    return jsonify({"rows": rows})


@dns_reverse_proxy_bp.route("/api/dns-reverse-proxy/builder/defaults")
def get_builder_defaults():
    """Return prefill defaults for DNS/Reverse Proxy builder modal."""
    return jsonify(api_helper.get_dns_reverse_proxy_builder_defaults())


@dns_reverse_proxy_bp.route("/api/dns-reverse-proxy/builder/preview", methods=["POST"])
def preview_builder_payloads():
    """Build preview API payloads from user inputs."""
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "Invalid JSON body"}), 400

    result = api_helper.build_dns_reverse_proxy_preview(data)
    if not result.get("ok"):
        return jsonify(result), 400
    return jsonify(result)


@dns_reverse_proxy_bp.route("/api/dns-reverse-proxy/builder/send", methods=["POST"])
def send_builder_payloads():
    """Send builder-generated mappings to reverse proxy and DNS providers."""
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "Invalid JSON body"}), 400

    # Extract hostname and target from the builder form data
    hostname = str(data.get("hostname") or "").strip()
    domain = str(data.get("domain") or "").strip().strip(".")
    target_protocol = str(data.get("target_protocol") or "http").strip().lower()
    target_host = str(data.get("target_host") or "").strip()
    target_port = int(data.get("target_port") or (443 if target_protocol == "https" else 80))
    dns_record_type = str(data.get("dns_record_type") or "A").strip().upper()
    dns_record_value = str(data.get("dns_record_value") or "").strip()
    
    if not hostname or not target_host or target_port <= 0:
        return jsonify({"ok": False, "error": "hostname, target_host, and target_port are required"}), 400
    if not dns_record_type or not dns_record_value:
        return jsonify({"ok": False, "error": "DNS fields (record_type, record_value) are required"}), 400

    # Build the full hostname (including domain if provided)
    cfg = api_helper.config_utils.get_module_config("dns_reverse_proxy") or {}
    options = api_helper._get_mapping_options(cfg)
    
    caddy_host = api_helper._join_host_domain(hostname, domain)
    if options["reverse_proxy"]["normalize_hostnames"]:
        caddy_host = caddy_host.rstrip(".").lower()
    
    # Build the reverse proxy payload for Caddyfile text format
    dial = f"{target_host}:{target_port}"
    rp_payload = {
        "hostname": caddy_host,
        "target": dial,
    }
    
    # Build the DNS payload
    dns_payload = {
        "hostname": hostname,
        "rr": dns_record_type,
        "server": dns_record_value if dns_record_type in ("A", "AAAA") else "",
    }

    result = api_helper.send_dns_reverse_proxy_payloads(rp_payload, dns_payload)
    if not result.get("ok"):
        return jsonify(result), 400
    return jsonify(result)


@dns_reverse_proxy_bp.route("/api/dns-reverse-proxy/mappings/action/delete", methods=["POST"])
def delete_mapping_parts():
    """Delete reverse proxy and DNS parts for a mapping hostname."""
    data = request.get_json(silent=True) or {}
    hostname = str(data.get("hostname") or "").strip()
    result = api_helper.delete_mapping_parts(hostname)
    return jsonify(result), (200 if result.get("ok") else 400)


@dns_reverse_proxy_bp.route("/api/dns-reverse-proxy/mappings/action/edit-reverse-proxy", methods=["POST"])
def edit_reverse_proxy_mapping():
    """Edit reverse proxy target details for mapping hostname."""
    data = request.get_json(silent=True) or {}
    result = api_helper.edit_reverse_proxy_mapping(
        hostname=str(data.get("hostname") or "").strip(),
        target_protocol=str(data.get("target_protocol") or "http").strip(),
        target_host=str(data.get("target_host") or "").strip(),
        target_port=int(data.get("target_port") or 0),
    )
    return jsonify(result), (200 if result.get("ok") else 400)


@dns_reverse_proxy_bp.route("/api/dns-reverse-proxy/mappings/action/edit-dns", methods=["POST"])
def edit_dns_mapping():
    """Edit DNS record details for mapping hostname."""
    data = request.get_json(silent=True) or {}
    result = api_helper.edit_dns_mapping(
        hostname=str(data.get("hostname") or "").strip(),
        record_type=str(data.get("record_type") or "").strip(),
        record_value=str(data.get("record_value") or "").strip(),
    )
    return jsonify(result), (200 if result.get("ok") else 400)


@dns_reverse_proxy_bp.route("/api/dns-reverse-proxy/provider/reverse-proxy/config")
def get_reverse_proxy_provider_config():
    """Get reverse proxy provider config payload for editing."""
    result = api_helper.get_reverse_proxy_provider_config()
    return jsonify(result), (200 if result.get("ok") else 400)


@dns_reverse_proxy_bp.route("/api/dns-reverse-proxy/provider/reverse-proxy/config", methods=["POST"])
def save_reverse_proxy_provider_config():
    """Save edited reverse proxy provider config payload."""
    data = request.get_json(silent=True) or {}
    config_text = str(data.get("config_text") or "").strip()
    result = api_helper.save_reverse_proxy_provider_config(config_text)
    return jsonify(result), (200 if result.get("ok") else 400)


@dns_reverse_proxy_bp.route("/api/dns-reverse-proxy/provider/dns/config-link")
def get_dns_provider_config_link():
    """Get DNS provider config URL for external editing/viewing."""
    result = api_helper.get_dns_provider_config_link()
    return jsonify(result), (200 if result.get("ok") else 400)
