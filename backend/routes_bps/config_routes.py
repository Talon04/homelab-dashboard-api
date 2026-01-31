# =============================================================================
# CONFIG ROUTES - Configuration API endpoints
# =============================================================================
"""Flask routes that expose configuration values over HTTP."""

from flask import Blueprint, jsonify, request

import backend.config_utils as config_utils


# =============================================================================
# BLUEPRINT REGISTRATION
# =============================================================================

config_bp = Blueprint("config", __name__)


# =============================================================================
# PROXY CONFIGURATION
# =============================================================================


@config_bp.route("/api/config/proxy_count")
def get_proxy_count():
    """Return the currently configured proxy hop count."""

    proxy_count = config_utils.get_proxy_count()
    return jsonify({"proxy_count": proxy_count})


@config_bp.route("/api/config/proxy_count", methods=["POST"])
def set_proxy_count():
    """Set the proxy hop count used to configure ProxyFix."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    proxy_count = data.get("proxy_count")

    if proxy_count is None:
        return jsonify({"error": "Missing proxy_count"}), 400

    try:
        proxy_count = int(proxy_count)
        if proxy_count < 0:
            return jsonify({"error": "Proxy count must be non-negative"}), 400
    except ValueError:
        return jsonify({"error": "Proxy count must be a valid integer"}), 400

    config_utils.set_proxy_count(proxy_count)
    return jsonify({"message": "Proxy count updated"}), 200


@config_bp.route("/api/config/internal_ip")
def get_internal_ip():
    """Return the internal IP used for generated URLs."""

    internal_ip = config_utils.get_internal_ip()
    return jsonify({"internal_ip": internal_ip})


@config_bp.route("/api/config/internal_ip", methods=["POST"])
def set_internal_ip():
    """Update the internal IP and rewrite existing internal link bodies."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    internal_ip = data.get("internal_ip")

    if not internal_ip:
        return jsonify({"error": "Missing internal_ip"}), 400

    config_utils.set_internal_ip(internal_ip)
    return jsonify({"message": "Internal IP updated"}), 200


@config_bp.route("/api/config/external_ip")
def get_external_ip():
    """Return the external IP used for public URLs."""

    external_ip = config_utils.get_external_ip()
    return jsonify({"external_ip": external_ip})


@config_bp.route("/api/config/external_ip", methods=["POST"])
def set_external_ip():
    """Update the external IP and rewrite existing external link bodies."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    external_ip = data.get("external_ip")

    if not external_ip:
        return jsonify({"error": "Missing external_ip"}), 400

    config_utils.set_external_ip(external_ip)
    return jsonify({"message": "External IP updated"}), 200


@config_bp.route("/api/config/first_boot")
def get_first_boot():
    """Return whether the app still considers this the first boot."""

    first_boot = config_utils.get_first_boot()
    return jsonify({"first_boot": first_boot})


@config_bp.route("/api/config/first_boot", methods=["POST"])
def set_first_boot():
    """Set or clear the first-boot flag."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    first_boot = data.get("first_boot")

    if first_boot is None:
        return jsonify({"error": "Missing first_boot"}), 400

    config_utils.set_first_boot(first_boot)
    return jsonify({"message": "First boot flag updated"}), 200


# =============================================================================
# DATABASE RETENTION CONFIGURATION
# =============================================================================


@config_bp.route("/api/config/retention_days")
def get_retention_days():
    """Return the number of days to retain historical data."""

    retention_days = config_utils.get_retention_days()
    return jsonify({"retention_days": retention_days})


@config_bp.route("/api/config/retention_days", methods=["POST"])
def set_retention_days():
    """Set the data retention period in days."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    retention_days = data.get("retention_days")

    if retention_days is None:
        return jsonify({"error": "Missing retention_days"}), 400

    try:
        retention_days = int(retention_days)
        if retention_days < 0:
            return jsonify({"error": "Retention days must be non-negative"}), 400
    except ValueError:
        return jsonify({"error": "Retention days must be a valid integer"}), 400

    config_utils.set_retention_days(retention_days)
    return jsonify({"message": "Retention days updated"}), 200


# =============================================================================
# MODULE CONFIGURATION
# =============================================================================


@config_bp.route("/api/config/modules")
def get_modules():
    """Return the list of enabled feature modules."""

    modules = config_utils.get_enabled_modules()
    return jsonify({"modules": modules})


@config_bp.route("/api/config/modules", methods=["POST"])
def set_modules():
    """Enable or disable feature modules from a JSON list."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    modules = data.get("modules")
    if modules is None or not isinstance(modules, list):
        return jsonify({"error": "Missing or invalid modules (expected list)"}), 400

    config_utils.set_enabled_modules(modules)
    return jsonify({"message": "Modules updated"}), 200


@config_bp.route("/api/config/modules_order")
def get_modules_order():
    """Return the desired dashboard module order."""

    order = config_utils.get_modules_order()
    return jsonify({"order": order})


@config_bp.route("/api/config/modules_order", methods=["POST"])
def set_modules_order():
    """Persist the display order for dashboard modules."""

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    order = data.get("order")
    if order is None or not isinstance(order, list):
        return jsonify({"error": "Missing or invalid order (expected list)"}), 400
    config_utils.set_modules_order(order)
    return jsonify({"message": "Modules order updated"}), 200


@config_bp.route("/api/config/module/<module_id>")
def get_module_config(module_id):
    """Return configuration for a single module by ID."""

    data = config_utils.get_module_config(module_id)
    return jsonify(data)


@config_bp.route("/api/config/module/<module_id>", methods=["POST"])
def set_module_config(module_id):
    """Replace or extend configuration for a single module."""

    data = request.get_json()
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    config_utils.set_module_config(module_id, data)
    return jsonify({"message": f"Module {module_id} config updated"}), 200
