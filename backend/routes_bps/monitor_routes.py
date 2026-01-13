from flask import Blueprint, jsonify, request

from backend.save_manager import get_save_manager


monitor_bp = Blueprint("monitor", __name__)


@monitor_bp.route("/api/monitor/container/<container_id>")
def api_get_container_monitor(container_id):
    """Return monitor configuration for a given container.

    If no monitor entry exists yet, this returns ``enabled: false`` so the
    frontend can treat it as simply "not monitored".
    """

    sm = get_save_manager()
    data = sm.get_monitor_for_container(container_id)
    if not data:
        return jsonify({"container_id": container_id, "enabled": False})
    return jsonify(data)


@monitor_bp.route("/api/monitor/container/<container_id>", methods=["POST"])
def api_set_container_monitor(container_id):
    """Create or update monitor configuration for a container.

    Body: {"enabled": true|false}
    """

    data = request.get_json() or {}
    if "enabled" not in data:
        return jsonify({"error": "Missing enabled"}), 400

    enabled = bool(data.get("enabled"))
    sm = get_save_manager()
    result = sm.set_monitor_for_container(container_id, enabled)
    if result is None:
        return jsonify({"error": "Failed to update monitor state"}), 400
    return jsonify(result)


@monitor_bp.route("/api/monitor/bodies")
@monitor_bp.route("/api/data/monitor_bodies")
def api_get_monitor_bodies():
    """Return all monitor_bodies entries (monitor configs for containers/VMs)."""

    sm = get_save_manager()
    data = sm.get_all_monitor_bodies()
    return jsonify(data)
