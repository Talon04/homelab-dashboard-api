# =============================================================================
# API HELPER - Unified outbound API access
# =============================================================================
"""Centralized helper for outbound API calls.

This module provides:
- Generic HTTP/JSON request helpers used by internal services.
- Provider-specific adapters for the DNS/Reverse Proxy module.

App code should route outbound API calls through this module.
"""

from __future__ import annotations

import base64
import json
import ssl
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional
from urllib import error, request

from backend import config_utils, caddy_agent_client


def http_request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Any] = None,
    timeout: float = 10.0,
    parse_json: bool = True,
    verify_ssl: bool = True,
) -> Dict[str, Any]:
    """Execute an HTTP request and return a normalized response dict.

    Returns:
        {
            "ok": bool,
            "status": int,
            "body": str,
            "json": Any | None,
            "error": str | None,
        }
    """

    req_headers = dict(headers or {})

    raw_data: Optional[bytes] = None
    if data is not None:
        if isinstance(data, bytes):
            raw_data = data
        elif isinstance(data, str):
            raw_data = data.encode("utf-8")
        else:
            raw_data = json.dumps(data).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/json")

    req = request.Request(url=url, data=raw_data, headers=req_headers, method=method)

    try:
        context = None
        if not verify_ssl:
            context = ssl._create_unverified_context()

        with request.urlopen(req, timeout=timeout, context=context) as resp:
            body = resp.read().decode("utf-8")
            parsed = None
            if parse_json and body:
                try:
                    parsed = json.loads(body)
                except Exception:
                    parsed = None
            return {
                "ok": True,
                "status": int(resp.status),
                "body": body,
                "json": parsed,
                "error": None,
            }
    except error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            body = ""
        parsed = None
        if parse_json and body:
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = None
        data_str = json.dumps(data) if data else "(no data)"
        print(f"FAIL [api_helper] http_request {method} {url} data={data_str} error={str(exc)}")
        return {
            "ok": False,
            "status": int(exc.code),
            "body": body,
            "json": parsed,
            "error": str(exc),
        }
    except Exception as exc:
        data_str = json.dumps(data) if data else "(no data)"
        print(f"FAIL [api_helper] http_request {method} {url} data={data_str} error={str(exc)}")
        return {
            "ok": False,
            "status": 0,
            "body": "",
            "json": None,
            "error": str(exc),
        }


def _safe_call(fn, fallback):
    try:
        return fn()
    except Exception as exc:
        print(f"ERROR [dns_reverse_proxy] provider call failed: {exc}")
        return fallback


def _join_host_domain(host: str, domain: str) -> str:
    host = (host or "").strip().rstrip(".")
    domain = (domain or "").strip().rstrip(".")
    if not host:
        return domain
    if not domain:
        return host
    return f"{host}.{domain}"


def _extract_caddy_reverse_proxy_entries(caddy_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []

    def walk_routes(routes: Any, inherited_hostnames: Optional[List[str]] = None) -> None:
        if not isinstance(routes, list):
            return

        for route in routes:
            if not isinstance(route, dict):
                continue

            hostnames: List[str] = []
            for matcher in route.get("match", []) or []:
                if isinstance(matcher, dict) and isinstance(matcher.get("host"), list):
                    hostnames.extend([str(h).strip().rstrip(".") for h in matcher["host"] if h])
            if not hostnames and inherited_hostnames:
                hostnames = list(inherited_hostnames)

            handles = route.get("handle", []) or []
            target = None
            for handle in handles:
                if not isinstance(handle, dict):
                    continue
                if handle.get("handler") == "reverse_proxy":
                    upstreams = handle.get("upstreams", []) or []
                    if upstreams and isinstance(upstreams[0], dict):
                        target = str(upstreams[0].get("dial") or "")
                    break

            if hostnames and target:
                for hostname in hostnames:
                    entries.append(
                        {
                            "hostname": hostname,
                            "target": target,
                            "source": "caddy",
                            "raw": route,
                        }
                    )

            # Some Caddy configs nest routes via "subroute"
            for handle in handles:
                if isinstance(handle, dict) and handle.get("handler") == "subroute":
                    walk_routes(handle.get("routes"), hostnames)

    apps = caddy_config.get("apps", {}) if isinstance(caddy_config, dict) else {}
    http_app = apps.get("http", {}) if isinstance(apps, dict) else {}
    servers = http_app.get("servers", {}) if isinstance(http_app, dict) else {}

    if isinstance(servers, dict):
        for server_data in servers.values():
            if isinstance(server_data, dict):
                walk_routes(server_data.get("routes"))

    return entries


def _extract_caddy_reverse_proxy_entries_from_caddyfile_text(caddyfile_text: str) -> List[Dict[str, Any]]:
    """Parse raw Caddyfile text and extract reverse proxy entries.
    
    Handles multi-line blocks like:
        hostname.example.com {
            reverse_proxy 192.168.1.1:8080 {
                ...
            }
        }
    """
    entries: List[Dict[str, Any]] = []
    
    if not isinstance(caddyfile_text, str):
        return entries
    
    lines = caddyfile_text.split("\n")
    current_hostname = None
    block_depth = 0
    
    # Keywords that start a non-hostname block
    non_hostname_keywords = {
        "import", "basic_auth", "header", "transport", "tls", "admin", 
        "log", "respond", "request_body", "reverse_proxy", "global",
        "encode", "rewrite", "file", "uri", "query", "method", "protocol"
    }
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            continue
        
        # Skip snippet definitions (lines starting with parenthesis)
        if stripped.startswith("("):
            open_braces = stripped.count("{")
            close_braces = stripped.count("}")
            block_depth += open_braces - close_braces
            continue
        
        # Update block depth based on braces
        open_braces = stripped.count("{")
        close_braces = stripped.count("}")
        
        # Try to identify hostname block entry (when at depth 0 and opening a block)
        if block_depth == 0 and open_braces > close_braces:
            # Extract first token before {
            first_token = stripped.split("{")[0].strip().split()[0] if stripped.split("{")[0].strip() else ""
            
            # Check if it's a known non-hostname keyword
            if first_token and first_token.lower() not in non_hostname_keywords:
                current_hostname = stripped.split("{")[0].strip()
            
            block_depth += open_braces - close_braces
        elif block_depth > 0:
            # We're inside a block
            block_depth += open_braces - close_braces
            
            # Look for reverse_proxy directives
            if "reverse_proxy" in stripped and current_hostname:
                parts = stripped.split("reverse_proxy", 1)
                if len(parts) > 1:
                    target_part = parts[1].strip()
                    # Remove trailing { and anything after (for nested blocks)
                    target_part = target_part.split("{")[0].strip()
                    target_part = target_part.rstrip(";").strip()
                    
                    if target_part:
                        entries.append({
                            "hostname": current_hostname,
                            "target": target_part,
                            "source": "caddy",
                            "raw": stripped,
                        })
            
            # Check if we're exiting the hostname block
            if block_depth == 0:
                current_hostname = None
        else:
            # Update global depth when outside hostname blocks
            block_depth += open_braces - close_braces
    
    return entries


def _get_mapping_options(cfg: Dict[str, Any]) -> Dict[str, Any]:
    options = cfg.get("mapping_options")
    if not isinstance(options, dict):
        options = {}

    rp = options.get("reverse_proxy") if isinstance(options.get("reverse_proxy"), dict) else {}
    dns = options.get("dns") if isinstance(options.get("dns"), dict) else {}

    return {
        "reverse_proxy": {
            "include_wildcards": bool(rp.get("include_wildcards", False)),
            "normalize_hostnames": bool(rp.get("normalize_hostnames", True)),
            "skip_tls_verify": bool(rp.get("skip_tls_verify", False)),
        },
        "dns": {
            "include_wildcards": bool(dns.get("include_wildcards", False)),
            "include_disabled": bool(dns.get("include_disabled", False)),
            "normalize_hostnames": bool(dns.get("normalize_hostnames", True)),
        },
    }


def _get_reverse_proxy_entries_caddy(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Caddy Agent handles the API interaction. This function processes the response.
    fetch_result = caddy_agent_client.fetch_config(cfg)
    if not fetch_result.get("ok"):
        print(f"ERROR [dns_reverse_proxy] reverse proxy: {fetch_result.get('error')}")
        raise RuntimeError(fetch_result.get("error"))

    payload = fetch_result.get("config") or {}
    
    options = _get_mapping_options(cfg)
    
    # Handle both Caddyfile text (string) and JSON config (dict)
    if isinstance(payload, str):
        # Parse raw Caddyfile text
        entries = _extract_caddy_reverse_proxy_entries_from_caddyfile_text(payload)
    elif isinstance(payload, dict):
        # Parse JSON config
        entries = _extract_caddy_reverse_proxy_entries(payload)
    else:
        entries = []

    filtered: List[Dict[str, Any]] = []
    for entry in entries:
        hostname = str(entry.get("hostname") or "").strip()
        if not hostname:
            continue
        if not options["reverse_proxy"]["include_wildcards"] and "*" in hostname:
            continue
        if options["reverse_proxy"]["normalize_hostnames"]:
            hostname = hostname.rstrip(".").lower()
        fixed = dict(entry)
        fixed["hostname"] = hostname
        filtered.append(fixed)

    entries = filtered
    return entries


def _normalize_opnsense_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("rows"), list):
            return payload["rows"]
        if isinstance(payload.get("row"), list):
            return payload["row"]
        # /api/unbound/settings/get/ returns host overrides keyed by UUID.
        hosts = (((payload.get("unbound") or {}).get("hosts") or {}).get("host"))
        if isinstance(hosts, dict):
            normalized: List[Dict[str, Any]] = []
            for uuid, item in hosts.items():
                if isinstance(item, dict):
                    row = dict(item)
                    row.setdefault("uuid", str(uuid))
                    normalized.append(row)
            if normalized:
                return normalized
    if isinstance(payload, list):
        return payload
    return []


def _extract_opnsense_record_type(row: Dict[str, Any]) -> str:
    value = row.get("type")
    if isinstance(value, str) and value.strip():
        return value.strip().upper()

    rr = row.get("rr")
    if isinstance(rr, str) and rr.strip():
        return rr.strip().upper()

    if isinstance(rr, dict):
        for key, item in rr.items():
            if isinstance(item, dict) and int(item.get("selected", 0) or 0) == 1:
                return str(key).strip().upper()

    return "A"


def _extract_opnsense_record_value(row: Dict[str, Any], record_type: str) -> str:
    record_type = (record_type or "A").upper()

    if record_type in ("A", "AAAA"):
        return str(row.get("server") or row.get("ip") or row.get("value") or "")
    if record_type == "MX":
        return str(row.get("mx") or row.get("value") or "")
    if record_type == "TXT":
        return str(row.get("txtdata") or row.get("value") or "")

    return str(row.get("value") or row.get("server") or row.get("ip") or "")


def _extract_host_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        return str(parsed.hostname or "").strip()
    except Exception:
        return ""


def _build_opnsense_headers(cfg: Dict[str, Any]) -> Dict[str, str]:
    api_key = str(cfg.get("opnsense_api_key") or "").strip()
    api_secret = str(cfg.get("opnsense_api_secret") or "").strip()
    auth_raw = f"{api_key}:{api_secret}".encode("utf-8")
    auth_b64 = base64.b64encode(auth_raw).decode("ascii")
    return {
        "Authorization": f"Basic {auth_b64}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def get_dns_reverse_proxy_builder_defaults() -> Dict[str, Any]:
    """Return prefill values used by the DNS/Reverse Proxy builder modal."""
    cfg = config_utils.get_module_config("dns_reverse_proxy") or {}
    default_domain = str(cfg.get("default_domain") or "").strip().lstrip(".")
    proxy_host = str(cfg.get("caddy_agent_host") or "").strip()

    return {
        "hostname": "",
        "domain": default_domain,
        "target_protocol": "http",
        "target_host": "",
        "target_port": 80,
        "dns_record_type": "A",
        "dns_record_value": proxy_host,
    }


def build_dns_reverse_proxy_preview(data: Dict[str, Any]) -> Dict[str, Any]:
    """Build preview payloads for reverse proxy and DNS provider APIs."""
    cfg = config_utils.get_module_config("dns_reverse_proxy") or {}
    options = _get_mapping_options(cfg)

    hostname = str(data.get("hostname") or "").strip().rstrip(".")
    domain = str(data.get("domain") or "").strip().strip(".")
    target_protocol = str(data.get("target_protocol") or "http").strip().lower()
    target_host = str(data.get("target_host") or "").strip()
    target_port = int(data.get("target_port") or (443 if target_protocol == "https" else 80))
    dns_record_type = str(data.get("dns_record_type") or "A").strip().upper()
    dns_record_value = str(data.get("dns_record_value") or "").strip()

    if not hostname:
        return {"ok": False, "error": "hostname is required"}
    if not target_host:
        return {"ok": False, "error": "target_host is required"}
    if not dns_record_value:
        return {"ok": False, "error": "dns_record_value is required"}
    if not options["reverse_proxy"]["include_wildcards"] and "*" in hostname:
        return {"ok": False, "error": "wildcard hostnames are disabled in reverse proxy settings"}
    if not options["dns"]["include_wildcards"] and "*" in hostname:
        return {"ok": False, "error": "wildcard hostnames are disabled in DNS settings"}

    caddy_host = _join_host_domain(hostname, domain)
    dns_hostname = hostname if str(options["dns"].get("hostname_mode") or "host_plus_domain") == "hostname_only" else _join_host_domain(hostname, domain)

    if options["reverse_proxy"]["normalize_hostnames"]:
        caddy_host = caddy_host.rstrip(".").lower()
    if options["dns"]["normalize_hostnames"]:
        dns_hostname = dns_hostname.rstrip(".").lower()

    # Build Caddyfile text format for reverse proxy
    dial = f"{target_host}:{target_port}"
    caddyfile_block = f"\n{caddy_host} {{\n    reverse_proxy {dial}\n}}\n"

    dns_record = {
        "enabled": "1",
        "hostname": hostname,
        "domain": domain,
        "rr": dns_record_type,
        "server": dns_record_value,
        "description": "Created by homelab dashboard builder",
    }
    if dns_record_type == "MX":
        dns_record["mx"] = dns_record_value
        dns_record["mxprio"] = str(data.get("dns_mx_priority") or "10")
        dns_record["server"] = ""
    if dns_record_type == "TXT":
        dns_record["txtdata"] = dns_record_value
        dns_record["server"] = ""

    return {
        "ok": True,
        "derived": {
            "caddy_host": caddy_host,
            "dns_hostname": dns_hostname,
        },
        "reverse_proxy_payload": caddyfile_block,
        "dns_payload": dns_record,
        "reverse_proxy_payload_text": caddyfile_block,
        "dns_payload_text": json.dumps(dns_record, indent=2),
    }


def _append_caddyfile_reverse_proxy_block(caddyfile_text: str, hostname: str, target: str) -> str:
    """Append a new reverse_proxy block to Caddyfile text.
    
    Ensures the Caddyfile ends with a newline before appending.
    """
    # Ensure the text ends with a newline before appending
    if caddyfile_text and not caddyfile_text.endswith("\n"):
        caddyfile_text += "\n"
    
    # Generate new block with proper formatting
    new_block = f"\n{hostname} {{\n    reverse_proxy {target}\n}}\n"
    return caddyfile_text + new_block


def _remove_caddyfile_reverse_proxy_block(caddyfile_text: str, hostname: str) -> tuple[str, int]:
    """Remove reverse_proxy blocks for a hostname from Caddyfile text.
    
    Returns:
        (modified_text, count_of_blocks_removed)
    """
    import re
    # Escape hostname for regex
    escaped_hostname = re.escape(hostname)
    
    # Match hostname block: "hostname {" and find its closing brace
    # This is a simple implementation - more complex configs might need more sophisticated parsing
    pattern = rf'\n?^{escaped_hostname}\s*\{{\s*\n(?:.*?\n)*?\s*\}}\n?'
    
    matches = list(re.finditer(pattern, caddyfile_text, re.MULTILINE | re.DOTALL))
    removed_count = len(matches)
    
    # Remove matching blocks (process in reverse order to maintain positions)
    modified_text = caddyfile_text
    for match in reversed(matches):
        modified_text = modified_text[:match.start()] + modified_text[match.end():]
    
    return modified_text, removed_count


def _update_caddyfile_reverse_proxy_target(caddyfile_text: str, hostname: str, new_target: str) -> tuple[str, int]:
    """Update reverse_proxy target for a hostname in Caddyfile text.
    
    Returns:
        (modified_text, count_of_targets_updated)
    """
    import re
    escaped_hostname = re.escape(hostname)
    
    # Match the reverse_proxy line within a hostname block
    # Pattern: "reverse_proxy old_target" -> "reverse_proxy new_target"
    pattern = rf'(^{escaped_hostname}\s*\{{\s*\n\s*)reverse_proxy\s+[^\n]+(\n)'
    
    def replacer(match):
        return match.group(1) + f'reverse_proxy {new_target}' + match.group(2)
    
    modified_text, count = re.subn(pattern, replacer, caddyfile_text, flags=re.MULTILINE)
    return modified_text, count


def send_dns_reverse_proxy_payloads(reverse_proxy_payload: Any, dns_payload: Any) -> Dict[str, Any]:
    """Send generated/edited payloads to configured reverse proxy (via agent) and DNS APIs."""
    cfg = config_utils.get_module_config("dns_reverse_proxy") or {}
    rp_provider = str(cfg.get("reverse_proxy_provider") or "").strip().lower()
    dns_provider = str(cfg.get("dns_provider") or "").strip().lower()

    if rp_provider != "caddy":
        return {"ok": False, "error": f"Unsupported reverse proxy provider: {rp_provider}"}
    if dns_provider != "opnsense":
        return {"ok": False, "error": f"Unsupported DNS provider: {dns_provider}"}

    # Fetch current Caddyfile (as text)
    fetch_result = caddy_agent_client.fetch_config(cfg)
    if not fetch_result.get("ok"):
        return {"ok": False, "error": f"Failed reading Caddy config from agent: {fetch_result.get('error')}"}

    caddyfile_text = fetch_result.get("config") or ""
    if not isinstance(caddyfile_text, str):
        return {"ok": False, "error": "Expected Caddyfile text from agent"}
    
    # Extract hostname and target from reverse_proxy_payload
    # reverse_proxy_payload should have hostname matcher and target dial
    hostname = reverse_proxy_payload.get("hostname", "").strip() if isinstance(reverse_proxy_payload, dict) else ""
    target = reverse_proxy_payload.get("target", "").strip() if isinstance(reverse_proxy_payload, dict) else ""
    
    if not hostname or not target:
        return {"ok": False, "error": "reverse_proxy_payload must have hostname and target"}
    
    # Append new block to Caddyfile
    updated_caddyfile = _append_caddyfile_reverse_proxy_block(caddyfile_text, hostname, target)
    
    print(f"DEBUG [dns_reverse_proxy] Appending {hostname} -> {target}")
    print(f"DEBUG [dns_reverse_proxy] Current Caddyfile length: {len(caddyfile_text)}")
    print(f"DEBUG [dns_reverse_proxy] Updated Caddyfile length: {len(updated_caddyfile)}")

    # Send to agent
    rp_result = caddy_agent_client.save_config(cfg, updated_caddyfile)
    if not rp_result.get("ok"):
        return {"ok": False, "error": f"Caddy agent save failed: {rp_result.get('error')}"}

    # Handle DNS payload
    opnsense_base = str(cfg.get("opnsense_api_url") or "").strip().rstrip("/")
    if not opnsense_base:
        return {"ok": False, "error": "opnsense_api_url is required"}

    opnsense_verify_ssl = bool(cfg.get("opnsense_verify_ssl", True))

    dns_result = http_request(
        "POST",
        f"{opnsense_base}/api/unbound/settings/add_host_override",
        headers=_build_opnsense_headers(cfg),
        data={"host": dns_payload},
        parse_json=True,
        verify_ssl=opnsense_verify_ssl,
    )
    if not dns_result.get("ok"):
        return {"ok": False, "error": f"OPNsense add_host_override failed: {dns_result.get('error') or dns_result.get('body')}"}

    # Best-effort reconfigure for OPNsense unbound.
    reconfigure_result = http_request(
        "POST",
        f"{opnsense_base}/api/unbound/service/reconfigure",
        headers=_build_opnsense_headers(cfg),
        data={},
        parse_json=True,
        verify_ssl=opnsense_verify_ssl,
    )

    return {
        "ok": True,
        "message": "Reverse proxy and DNS records sent",
        "results": {
            "reverse_proxy": rp_result,
            "dns": dns_result,
            "dns_reconfigure": reconfigure_result,
        },
    }


def _get_dns_entries_opnsense(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    base_url = str(cfg.get("opnsense_api_url") or "").strip().rstrip("/")
    api_key = str(cfg.get("opnsense_api_key") or "").strip()
    api_secret = str(cfg.get("opnsense_api_secret") or "").strip()
    verify_ssl = bool(cfg.get("opnsense_verify_ssl", True))
    if not base_url or not api_key or not api_secret:
        print("ERROR [dns_reverse_proxy] opnsense dns: missing opnsense_api_url, opnsense_api_key, or opnsense_api_secret")
        return []

    auth_raw = f"{api_key}:{api_secret}".encode("utf-8")
    auth_b64 = base64.b64encode(auth_raw).decode("ascii")
    options = _get_mapping_options(cfg)
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Accept": "application/json",
    }

    # OPNsense API shape may vary by plugin version. Try common endpoints.
    candidates = [
        f"{base_url}/api/unbound/settings/get_host_override/",
        f"{base_url}/api/unbound/settings/get/",
    ]

    rows: List[Dict[str, Any]] = []
    last_error: Optional[str] = None
    last_endpoint: Optional[str] = None

    for endpoint in candidates:
        print(f"INFO [dns_reverse_proxy] opnsense dns: trying endpoint {endpoint}")
        result = http_request(
            "GET",
            endpoint,
            headers=headers,
            parse_json=True,
            verify_ssl=verify_ssl,
        )
        if result["ok"]:
            rows = _normalize_opnsense_rows(result.get("json"))
            if rows:
                print(f"INFO [dns_reverse_proxy] opnsense dns: endpoint {endpoint} returned {len(rows)} rows")
                break
            else:
                print(f"INFO [dns_reverse_proxy] opnsense dns: endpoint {endpoint} returned empty response")
        else:
            last_error = f"{result.get('status')} {result.get('error')}"
            last_endpoint = endpoint
            print(f"WARN [dns_reverse_proxy] opnsense dns: endpoint {endpoint} failed: {last_error}")

    if not rows and last_error is not None:
        msg = f"All endpoints failed. Last attempt: endpoint={last_endpoint} error={last_error}"
        print(f"ERROR [dns_reverse_proxy] opnsense dns: {msg}")
        raise RuntimeError(f"OPNsense DNS API error: {msg}")

    entries: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue

        enabled = str(row.get("enabled") or "1").strip()
        if not options["dns"]["include_disabled"] and enabled not in ("1", "true", "True"):
            continue

        host = str(row.get("hostname") or row.get("host") or "").strip()
        domain = str(row.get("domain") or "").strip()
        if not options["dns"]["include_wildcards"] and host == "*":
            continue
        fqdn = _join_host_domain(host, domain)
        if not fqdn:
            continue
        if options["dns"]["normalize_hostnames"]:
            fqdn = fqdn.rstrip(".").lower()

        record_type = _extract_opnsense_record_type(row)
        record_value = _extract_opnsense_record_value(row, record_type)

        entries.append(
            {
                "hostname": fqdn,
                "value": str(record_value or ""),
                "record_type": record_type,
                "source": "opnsense",
                "raw": row,
            }
        )

    print(f"INFO [dns_reverse_proxy] opnsense dns: normalized {len(entries)} entries from {len(rows)} rows")
    return entries


def get_reverse_proxy_entries_from_api() -> List[Dict[str, Any]]:
    """Unified reverse proxy getter using configured provider."""
    cfg = config_utils.get_module_config("dns_reverse_proxy") or {}
    provider = str(cfg.get("reverse_proxy_provider") or "").strip().lower()

    print(f"INFO [dns_reverse_proxy] fetching reverse proxy entries from provider: {provider}")
    if provider == "caddy":
        return _safe_call(lambda: _get_reverse_proxy_entries_caddy(cfg), [])

    if not provider:
        print("WARN [dns_reverse_proxy] no reverse_proxy_provider configured")
    else:
        print(f"WARN [dns_reverse_proxy] unsupported reverse_proxy_provider: {provider}")
    return []


def get_dns_entries_from_api() -> List[Dict[str, Any]]:
    """Unified DNS getter using configured provider."""
    cfg = config_utils.get_module_config("dns_reverse_proxy") or {}
    provider = str(cfg.get("dns_provider") or "").strip().lower()

    print(f"INFO [dns_reverse_proxy] fetching dns entries from provider: {provider}")
    if provider == "opnsense":
        return _safe_call(lambda: _get_dns_entries_opnsense(cfg), [])

    if not provider:
        print("WARN [dns_reverse_proxy] no dns_provider configured")
    else:
        print(f"WARN [dns_reverse_proxy] unsupported dns_provider: {provider}")
    return []


def build_proxy_dns_mappings() -> List[Dict[str, Any]]:
    """Return hostname-based mapping rows between reverse proxy and DNS entries."""
    print("INFO [dns_reverse_proxy] building proxy/dns mappings: fetching reverse proxy entries")
    reverse_proxy_entries = get_reverse_proxy_entries_from_api()
    print(f"INFO [dns_reverse_proxy] got {len(reverse_proxy_entries)} reverse proxy entries")

    print("INFO [dns_reverse_proxy] building proxy/dns mappings: fetching dns entries")
    dns_entries = get_dns_entries_from_api()
    print(f"INFO [dns_reverse_proxy] got {len(dns_entries)} dns entries")

    reverse_by_host = {
        str(entry.get("hostname") or "").strip().rstrip(".").lower(): entry
        for entry in reverse_proxy_entries
        if entry.get("hostname")
    }
    dns_by_host = {
        str(entry.get("hostname") or "").strip().rstrip(".").lower(): entry
        for entry in dns_entries
        if entry.get("hostname")
    }

    rows: List[Dict[str, Any]] = []
    all_hosts = sorted(set(reverse_by_host.keys()) | set(dns_by_host.keys()))

    for host in all_hosts:
        rp = reverse_by_host.get(host)
        dns = dns_by_host.get(host)

        status = "matched"
        if rp and not dns:
            status = "missing_dns"
        elif dns and not rp:
            status = "missing_reverse_proxy"

        rows.append(
            {
                "hostname": host,
                "status": status,
                "reverse_proxy_target": (rp or {}).get("target", ""),
                "reverse_proxy_source": (rp or {}).get("source", ""),
                "dns_value": (dns or {}).get("value", ""),
                "dns_record_type": (dns or {}).get("record_type", ""),
                "dns_source": (dns or {}).get("source", ""),
                "dns_uuid": ((dns or {}).get("raw") or {}).get("uuid", ""),
                "has_reverse_proxy": bool(rp),
                "has_dns": bool(dns),
            }
        )

    matched = sum(1 for r in rows if r["status"] == "matched")
    missing_dns = sum(1 for r in rows if r["status"] == "missing_dns")
    missing_rp = sum(1 for r in rows if r["status"] == "missing_reverse_proxy")
    print(f"INFO [dns_reverse_proxy] mapping complete: {len(rows)} total, {matched} matched, {missing_dns} missing_dns, {missing_rp} missing_reverse_proxy")
    return rows


def _normalize_hostname(value: str) -> str:
    return str(value or "").strip().rstrip(".").lower()


def _route_has_host(route: Any, hostname: str) -> bool:
    if not isinstance(route, dict):
        return False
    hostname = _normalize_hostname(hostname)
    for matcher in route.get("match", []) or []:
        if not isinstance(matcher, dict):
            continue
        hosts = matcher.get("host")
        if not isinstance(hosts, list):
            continue
        for host in hosts:
            if _normalize_hostname(str(host or "")) == hostname:
                return True
    return False


def _find_reverse_proxy_handle(route: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(route, dict):
        return None
    handles = route.get("handle", []) or []
    for handle in handles:
        if not isinstance(handle, dict):
            continue
        if handle.get("handler") == "reverse_proxy":
            return handle
        if handle.get("handler") == "subroute":
            sub_routes = handle.get("routes", []) or []
            if isinstance(sub_routes, list):
                for sub_route in sub_routes:
                    found = _find_reverse_proxy_handle(sub_route)
                    if found is not None:
                        return found
    return None


def _collect_caddyfile_like_blocks(caddy_config: Dict[str, Any]) -> List[str]:
    blocks: List[str] = []
    seen: set[tuple[str, str]] = set()

    def walk_routes(routes: Any, inherited_hosts: Optional[List[str]] = None) -> None:
        if not isinstance(routes, list):
            return

        for route in routes:
            if not isinstance(route, dict):
                continue

            hosts: List[str] = []
            for matcher in route.get("match", []) or []:
                if isinstance(matcher, dict) and isinstance(matcher.get("host"), list):
                    hosts.extend([str(h).strip().rstrip(".") for h in matcher["host"] if h])
            if not hosts and inherited_hosts:
                hosts = list(inherited_hosts)

            handle = _find_reverse_proxy_handle(route)
            if hosts and handle:
                upstreams = handle.get("upstreams", []) or []
                dial = str((upstreams[0] or {}).get("dial") or "") if upstreams else ""
                key = (_normalize_hostname(hosts[0]), dial)
                if key in seen:
                    continue
                seen.add(key)
                block_lines = []
                if len(hosts) > 1:
                    block_lines.append(f"# hosts: {', '.join(hosts)}")
                block_lines.append(f"{hosts[0]} {{")
                if len(hosts) > 1:
                    block_lines.append(f"    # aliases: {', '.join(hosts[1:])}")
                block_lines.append(f"    reverse_proxy {dial}")
                block_lines.append("}")
                blocks.append("\n".join(block_lines))

            for sub_handle in route.get("handle", []) or []:
                if isinstance(sub_handle, dict) and sub_handle.get("handler") == "subroute":
                    walk_routes(sub_handle.get("routes"), hosts)

    apps = caddy_config.get("apps", {}) if isinstance(caddy_config, dict) else {}
    http_app = apps.get("http", {}) if isinstance(apps, dict) else {}
    servers = http_app.get("servers", {}) if isinstance(http_app, dict) else {}

    if isinstance(servers, dict):
        for server_data in servers.values():
            if isinstance(server_data, dict):
                walk_routes(server_data.get("routes"))

    return blocks


def _parse_caddyfile_like_blocks(config_text: str) -> List[Dict[str, str]]:
    blocks: List[Dict[str, str]] = []
    current_host: Optional[str] = None
    inside_block = False

    for raw_line in str(config_text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("{"):
            current_host = line[:-1].strip()
            inside_block = True
            continue
        if line == "}":
            current_host = None
            inside_block = False
            continue
        if inside_block and line.startswith("reverse_proxy ") and current_host:
            target = line[len("reverse_proxy "):].strip()
            if target:
                blocks.append({"hostname": current_host, "target": target})

    return blocks


def _get_reverse_proxy_provider_config_caddy(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch and parse Caddy configuration for editing."""
    fetch_result = caddy_agent_client.fetch_config(cfg)
    if not fetch_result.get("ok"):
        return {"ok": False, "error": fetch_result.get("error")}
    return {"ok": True, "config": fetch_result.get("config") or {}}


def _update_caddy_reverse_proxy_targets(caddy_config: Dict[str, Any], updates: List[Dict[str, str]]) -> int:
    updated = 0
    update_map = { _normalize_hostname(item.get("hostname")): str(item.get("target") or "").strip() for item in updates if item.get("hostname") and item.get("target") }

    def walk_routes(routes: Any, inherited_hosts: Optional[List[str]] = None) -> None:
        nonlocal updated
        if not isinstance(routes, list):
            return

        for route in routes:
            if not isinstance(route, dict):
                continue

            hosts: List[str] = []
            for matcher in route.get("match", []) or []:
                if isinstance(matcher, dict) and isinstance(matcher.get("host"), list):
                    hosts.extend([str(h).strip().rstrip(".") for h in matcher["host"] if h])
            if not hosts and inherited_hosts:
                hosts = list(inherited_hosts)

            handle = _find_reverse_proxy_handle(route)
            if hosts and handle:
                for host in hosts:
                    target = update_map.get(_normalize_hostname(host))
                    if not target:
                        continue
                    handle["upstreams"] = [{"dial": target}]
                    updated += 1

            for sub_handle in route.get("handle", []) or []:
                if isinstance(sub_handle, dict) and sub_handle.get("handler") == "subroute":
                    walk_routes(sub_handle.get("routes"), hosts)

    apps = caddy_config.get("apps", {}) if isinstance(caddy_config, dict) else {}
    http_app = apps.get("http", {}) if isinstance(apps, dict) else {}
    servers = http_app.get("servers", {}) if isinstance(http_app, dict) else {}

    if isinstance(servers, dict):
        for server_data in servers.values():
            if isinstance(server_data, dict):
                walk_routes(server_data.get("routes"))

    return updated


def _find_opnsense_dns_entry_by_hostname(cfg: Dict[str, Any], hostname: str) -> Optional[Dict[str, Any]]:
    hostname = _normalize_hostname(hostname)
    entries = _get_dns_entries_opnsense(cfg)
    for entry in entries:
        if _normalize_hostname(entry.get("hostname")) == hostname:
            return entry
    return None


def _delete_opnsense_dns_entry(cfg: Dict[str, Any], hostname: str) -> Dict[str, Any]:
    base_url = str(cfg.get("opnsense_api_url") or "").strip().rstrip("/")
    if not base_url:
        return {"ok": False, "error": "opnsense_api_url is required"}
    entry = _find_opnsense_dns_entry_by_hostname(cfg, hostname)
    if not entry:
        return {"ok": True, "skipped": True, "message": "DNS entry not found"}
    uuid = str(((entry.get("raw") or {}).get("uuid") or "")).strip()
    if not uuid:
        return {"ok": False, "error": "DNS entry uuid not found"}

    headers = _build_opnsense_headers(cfg)
    verify_ssl = bool(cfg.get("opnsense_verify_ssl", True))

    delete_result = http_request(
        "POST",
        f"{base_url}/api/unbound/settings/del_host_override/{uuid}",
        headers=headers,
        data={},
        parse_json=True,
        verify_ssl=verify_ssl,
    )
    if not delete_result.get("ok"):
        return {"ok": False, "error": delete_result.get("error") or delete_result.get("body") or "DNS delete failed"}

    reconfigure_result = http_request(
        "POST",
        f"{base_url}/api/unbound/service/reconfigure",
        headers=headers,
        data={},
        parse_json=True,
        verify_ssl=verify_ssl,
    )

    return {"ok": True, "result": delete_result, "reconfigure": reconfigure_result}


def delete_mapping_parts(hostname: str) -> Dict[str, Any]:
    """Delete both reverse proxy and DNS parts for a mapping hostname."""
    cfg = config_utils.get_module_config("dns_reverse_proxy") or {}
    normalized = _normalize_hostname(hostname)
    if not normalized:
        return {"ok": False, "error": "hostname is required"}

    rp_provider = str(cfg.get("reverse_proxy_provider") or "").strip().lower()
    dns_provider = str(cfg.get("dns_provider") or "").strip().lower()
    out: Dict[str, Any] = {"ok": True, "hostname": normalized, "reverse_proxy": {}, "dns": {}}

    if rp_provider == "caddy":
        fetch_result = caddy_agent_client.fetch_config(cfg)
        if not fetch_result.get("ok"):
            return {"ok": False, "error": f"Failed reading reverse proxy config: {fetch_result.get('error')}"}
        caddyfile_text = fetch_result.get("config") or ""
        
        if not isinstance(caddyfile_text, str):
            return {"ok": False, "error": "Expected Caddyfile text from agent"}
        
        # Remove matching block from Caddyfile
        modified_caddyfile, removed_count = _remove_caddyfile_reverse_proxy_block(caddyfile_text, normalized)
        
        if removed_count > 0:
            save_result = caddy_agent_client.save_config(cfg, modified_caddyfile)
            if not save_result.get("ok"):
                return {"ok": False, "error": f"Failed saving reverse proxy config: {save_result.get('error')}"}
            out["reverse_proxy"] = {"ok": True, "removed": removed_count}
        else:
            out["reverse_proxy"] = {"ok": True, "removed": 0, "skipped": True}
    else:
        out["reverse_proxy"] = {"ok": True, "skipped": True, "message": f"Unsupported reverse proxy provider: {rp_provider}"}

    if dns_provider == "opnsense":
        dns_delete = _delete_opnsense_dns_entry(cfg, normalized)
        if not dns_delete.get("ok"):
            return {"ok": False, "error": dns_delete.get("error") or "Failed deleting DNS entry", "reverse_proxy": out.get("reverse_proxy")}
        out["dns"] = dns_delete
    else:
        out["dns"] = {"ok": True, "skipped": True, "message": f"Unsupported DNS provider: {dns_provider}"}

    return out


def edit_reverse_proxy_mapping(hostname: str, target_protocol: str, target_host: str, target_port: int) -> Dict[str, Any]:
    """Edit reverse proxy target for mapping hostname."""
    cfg = config_utils.get_module_config("dns_reverse_proxy") or {}
    normalized = _normalize_hostname(hostname)
    if not normalized:
        return {"ok": False, "error": "hostname is required"}
    if not target_host:
        return {"ok": False, "error": "target_host is required"}
    if int(target_port or 0) <= 0:
        return {"ok": False, "error": "target_port must be > 0"}

    rp_provider = str(cfg.get("reverse_proxy_provider") or "").strip().lower()
    if rp_provider != "caddy":
        return {"ok": False, "error": f"Unsupported reverse proxy provider: {rp_provider}"}

    fetch_result = caddy_agent_client.fetch_config(cfg)
    if not fetch_result.get("ok"):
        return {"ok": False, "error": fetch_result.get("error")}
    
    caddyfile_text = fetch_result.get("config") or ""
    if not isinstance(caddyfile_text, str):
        return {"ok": False, "error": "Expected Caddyfile text from agent"}
    
    dial = f"{target_host}:{int(target_port)}"
    
    # Update the target in Caddyfile
    modified_caddyfile, updated = _update_caddyfile_reverse_proxy_target(caddyfile_text, normalized, dial)
    
    if updated == 0:
        return {"ok": False, "error": "Reverse proxy route not found for hostname"}

    save_result = caddy_agent_client.save_config(cfg, modified_caddyfile)
    if not save_result.get("ok"):
        return {"ok": False, "error": save_result.get("error")}
    return {"ok": True, "updated": updated, "dial": dial}


def edit_dns_mapping(hostname: str, record_type: str, record_value: str) -> Dict[str, Any]:
    """Edit DNS record fields for mapping hostname."""
    cfg = config_utils.get_module_config("dns_reverse_proxy") or {}
    normalized = _normalize_hostname(hostname)
    if not normalized:
        return {"ok": False, "error": "hostname is required"}

    dns_provider = str(cfg.get("dns_provider") or "").strip().lower()
    if dns_provider != "opnsense":
        return {"ok": False, "error": f"Unsupported DNS provider: {dns_provider}"}

    entry = _find_opnsense_dns_entry_by_hostname(cfg, normalized)
    if not entry:
        return {"ok": False, "error": "DNS record not found for hostname"}
    raw = dict(entry.get("raw") or {})
    uuid = str(raw.get("uuid") or "").strip()
    if not uuid:
        return {"ok": False, "error": "DNS record uuid not found"}

    rr = str(record_type or "A").strip().upper()
    value = str(record_value or "").strip()
    if not value:
        return {"ok": False, "error": "record_value is required"}

    raw["rr"] = rr
    raw["server"] = ""
    raw["mx"] = ""
    raw["txtdata"] = ""
    if rr in ("A", "AAAA"):
        raw["server"] = value
    elif rr == "MX":
        raw["mx"] = value
        raw["mxprio"] = str(raw.get("mxprio") or "10")
    elif rr == "TXT":
        raw["txtdata"] = value
    else:
        raw["server"] = value

    base_url = str(cfg.get("opnsense_api_url") or "").strip().rstrip("/")
    headers = _build_opnsense_headers(cfg)
    verify_ssl = bool(cfg.get("opnsense_verify_ssl", True))
    set_result = http_request(
        "POST",
        f"{base_url}/api/unbound/settings/set_host_override/{uuid}",
        headers=headers,
        data={"host": raw},
        parse_json=True,
        verify_ssl=verify_ssl,
    )
    if not set_result.get("ok"):
        return {"ok": False, "error": set_result.get("error") or set_result.get("body") or "DNS update failed"}

    reconfigure_result = http_request(
        "POST",
        f"{base_url}/api/unbound/service/reconfigure",
        headers=headers,
        data={},
        parse_json=True,
        verify_ssl=verify_ssl,
    )
    return {"ok": True, "result": set_result, "reconfigure": reconfigure_result}


def get_reverse_proxy_provider_config() -> Dict[str, Any]:
    """Return provider-specific editable reverse proxy configuration payload."""
    cfg = config_utils.get_module_config("dns_reverse_proxy") or {}
    rp_provider = str(cfg.get("reverse_proxy_provider") or "").strip().lower()
    if rp_provider == "caddy":
        fetch_result = caddy_agent_client.fetch_config(cfg)
        if not fetch_result.get("ok"):
            return {"ok": False, "error": fetch_result.get("error")}
        payload = fetch_result.get("config") or {}
        return {
            "ok": True,
            "provider": rp_provider,
            "config_text": "\n\n".join(_collect_caddyfile_like_blocks(payload)),
        }
    return {"ok": False, "error": f"Unsupported reverse proxy provider: {rp_provider}"}


def save_reverse_proxy_provider_config(config_text: str) -> Dict[str, Any]:
    """Save provider-specific reverse proxy configuration (Caddyfile text)."""
    cfg = config_utils.get_module_config("dns_reverse_proxy") or {}
    rp_provider = str(cfg.get("reverse_proxy_provider") or "").strip().lower()
    if rp_provider != "caddy":
        return {"ok": False, "error": f"Unsupported reverse proxy provider: {rp_provider}"}
    
    if not config_text or not isinstance(config_text, str):
        return {"ok": False, "error": "config_text (Caddyfile content) is required"}
    
    # Save the raw Caddyfile text to agent (it will validate on staging)
    return caddy_agent_client.save_config(cfg, config_text)



def get_dns_provider_config_link() -> Dict[str, Any]:
    """Return provider-specific DNS config link for external UI editing."""
    cfg = config_utils.get_module_config("dns_reverse_proxy") or {}
    dns_provider = str(cfg.get("dns_provider") or "").strip().lower()
    if dns_provider == "opnsense":
        base_url = str(cfg.get("opnsense_api_url") or "").strip().rstrip("/")
        if not base_url:
            return {"ok": False, "error": "opnsense_api_url is required"}
        return {"ok": True, "provider": dns_provider, "url": f"{base_url}/ui/unbound/host_override"}
    return {"ok": False, "error": f"Unsupported DNS provider: {dns_provider}"}


def _build_proxmox_headers(cfg: Dict[str, Any]) -> Dict[str, str]:
    headers: Dict[str, str] = {"Accept": "application/json"}
    token_id = str(cfg.get("token_id") or "").strip()
    token_secret = str(cfg.get("token_secret") or "").strip()
    if token_id and token_secret:
        headers["Authorization"] = f"PVEAPIToken={token_id}={token_secret}"
    return headers


def test_proxmox_api(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Test Proxmox API reachability and authentication."""
    base_url = str(cfg.get("api_url") or "").strip().rstrip("/")
    if not base_url:
        result = {"ok": False, "message": "Missing Proxmox API URL", "error": "api_url is required"}
        print(f"FAIL [api_helper] test_proxmox_api missing api_url")
        return result

    verify_ssl = bool(cfg.get("verify_ssl", True))
    version_url = (
        f"{base_url}/version"
        if not base_url.endswith("/version")
        else base_url
    )

    result = http_request(
        "GET",
        version_url,
        headers=_build_proxmox_headers(cfg),
        parse_json=True,
        verify_ssl=verify_ssl,
    )

    if result.get("ok"):
        version = ""
        payload = result.get("json")
        if isinstance(payload, dict):
            version = str((payload.get("data") or {}).get("version") or "")
        msg = "Proxmox API reachable"
        if version:
            msg += f" (version {version})"
        out = {"ok": True, "message": msg, "status": result.get("status")}
        print(f"OK [api_helper] test_proxmox_api {msg}")
        return out

    status = int(result.get("status") or 0)
    # 401/403 still proves endpoint is reachable but credentials are wrong.
    if status in (401, 403):
        out = {
            "ok": False,
            "message": "Proxmox API reachable but authentication failed",
            "status": status,
            "error": result.get("error") or result.get("body"),
        }
        print(f"FAIL [api_helper] test_proxmox_api authentication failed: {out['error']}")
        return out

    out = {
        "ok": False,
        "message": "Failed to connect to Proxmox API",
        "status": status,
        "error": result.get("error") or result.get("body"),
    }
    print(f"FAIL [api_helper] test_proxmox_api failed to connect: {out['error']}")
    return out


def test_caddy_api(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Test Caddy Agent reachability and status."""
    status_result = caddy_agent_client.get_status(cfg)
    
    if not status_result.get("ok"):
        error = status_result.get("error") or "Failed to connect to Caddy Agent"
        print(f"FAIL [api_helper] test_caddy_agent: {error}")
        return {
            "ok": False,
            "message": "Failed to connect to Caddy Agent",
            "error": error
        }
    
    agent_status = status_result.get("status", "unknown")
    print(f"OK [api_helper] test_caddy_agent reachable, status: {agent_status}")
    return {
        "ok": True,
        "message": "Caddy Agent reachable",
        "status": agent_status,
        "details": status_result.get("details", {})
    }
    return out


def test_opnsense_api(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Test OPNsense DNS API reachability and credentials."""
    base_url = str(cfg.get("opnsense_api_url") or "").strip().rstrip("/")
    api_key = str(cfg.get("opnsense_api_key") or "").strip()
    api_secret = str(cfg.get("opnsense_api_secret") or "").strip()
    verify_ssl = bool(cfg.get("opnsense_verify_ssl", True))

    if not base_url:
        out = {"ok": False, "message": "Missing OPNsense API URL", "error": "opnsense_api_url is required"}
        print(f"FAIL [api_helper] test_opnsense_api missing opnsense_api_url")
        return out
    if not api_key or not api_secret:
        out = {"ok": False, "message": "Missing OPNsense API key/secret", "error": "opnsense_api_key and opnsense_api_secret are required"}
        print(f"FAIL [api_helper] test_opnsense_api missing api key/secret")
        return out

    auth_raw = f"{api_key}:{api_secret}".encode("utf-8")
    auth_b64 = base64.b64encode(auth_raw).decode("ascii")
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Accept": "application/json",
    }

    candidates = [
        f"{base_url}/api/unbound/service/status/",
        f"{base_url}/api/unbound/overview/totals/",
    ]

    last_error: Optional[str] = None

    for endpoint in candidates:
        result = http_request(
            "GET",
            endpoint,
            headers=headers,
            parse_json=True,
            verify_ssl=verify_ssl,
        )
        if result.get("ok"):
            out = {
                "ok": True,
                "message": "OPNsense API reachable",
                "status": result.get("status"),
            }
            print(f"OK [api_helper] test_opnsense_api reachable")
            return out

        status = int(result.get("status") or 0)
        last_error = result.get("error") or result.get("body") or f"HTTP {status}"
        if status in (401, 403):
            out = {
                "ok": False,
                "message": "OPNsense API reachable but credentials are invalid",
                "status": status,
                "error": result.get("error") or result.get("body"),
            }
            print(f"FAIL [api_helper] test_opnsense_api invalid credentials: {out['error']}")
            return out

    out = {
        "ok": False,
        "message": "Failed to connect to OPNsense API",
        "error": last_error or "unknown error",
    }
    print(f"FAIL [api_helper] test_opnsense_api failed to connect: {out['error']}")
    return out


def test_module_api(module_id: str, test_id: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch module-specific API tests used by the frontend settings page."""
    module_id = str(module_id or "").strip()
    test_id = str(test_id or "").strip()

    if module_id == "proxmox" and test_id == "proxmox":
        return test_proxmox_api(cfg)
    if module_id == "dns_reverse_proxy" and test_id == "caddy":
        return test_caddy_api(cfg)
    if module_id == "dns_reverse_proxy" and test_id == "opnsense":
        return test_opnsense_api(cfg)

    out = {"ok": False, "message": f"Unknown test target: {module_id}/{test_id}", "error": "unsupported module/test combination"}
    print(f"FAIL [api_helper] test_module_api unsupported target: {module_id}/{test_id}")
    return out
