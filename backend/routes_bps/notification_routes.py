"""API routes for the notification system.

Handles notification channels and rules (config-backed).
"""

from flask import Blueprint, jsonify, request

from backend.config_manager import config_manager


notification_bp = Blueprint("notification", __name__)


# =============================================================================
# Configuration Helpers
# =============================================================================


def _get_notification_config():
    """Get the notifications module configuration."""
    return config_manager.get("modules", {}).get("notifications", {})


def _save_notification_config(notif_config):
    """Save the notifications module configuration."""
    modules = config_manager.get("modules", {})
    modules["notifications"] = notif_config
    config_manager.set("modules", modules)


def _get_channels():
    """Get all notification channels."""
    return _get_notification_config().get("channels", [])


def _save_channels(channels):
    """Save notification channels."""
    notif_config = _get_notification_config()
    notif_config["channels"] = channels
    _save_notification_config(notif_config)


def _get_rules():
    """Get all delivery rules."""
    return _get_notification_config().get("rules", [])


def _save_rules(rules):
    """Save delivery rules."""
    notif_config = _get_notification_config()
    notif_config["rules"] = rules
    _save_notification_config(notif_config)


def _next_channel_id():
    """Generate next channel ID."""
    channels = _get_channels()
    if not channels:
        return 1
    return max(c.get("id", 0) for c in channels) + 1


def _next_rule_id():
    """Generate next rule ID."""
    rules = _get_rules()
    if not rules:
        return 1
    return max(r.get("id", 0) for r in rules) + 1


# ─────────────────────────────────────────────────────────────────────────────
# Notification Channels API (config.json-backed)
# ─────────────────────────────────────────────────────────────────────────────


@notification_bp.route("/api/notifications/channels")
def get_channels():
    """Return all notification channels."""
    channels = _get_channels()
    return jsonify({"channels": channels})


@notification_bp.route("/api/notifications/channels", methods=["POST"])
def create_channel():
    """Create a new notification channel."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    name = data.get("name")
    channel_type = data.get("channel_type")

    if not name or not channel_type:
        return jsonify({"error": "name and channel_type are required"}), 400

    valid_types = ["discord", "push", "email", "webhook"]
    if channel_type not in valid_types:
        return (
            jsonify({"error": f"Invalid channel_type. Must be one of: {valid_types}"}),
            400,
        )

    channels = _get_channels()
    new_channel = {
        "id": _next_channel_id(),
        "name": name,
        "channel_type": channel_type,
        "enabled": data.get("enabled", True),
        "config": data.get("config", {}),
    }
    channels.append(new_channel)
    _save_channels(channels)

    return jsonify({"message": "Channel created", "id": new_channel["id"]}), 201


@notification_bp.route("/api/notifications/channels/<int:channel_id>", methods=["PUT"])
def update_channel(channel_id):
    """Update an existing notification channel."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    channels = _get_channels()
    channel = next((c for c in channels if c.get("id") == channel_id), None)

    if not channel:
        return jsonify({"error": "Channel not found"}), 404

    if "name" in data:
        channel["name"] = data["name"]
    if "channel_type" in data:
        valid_types = ["discord", "push", "email", "webhook"]
        if data["channel_type"] not in valid_types:
            return (
                jsonify(
                    {"error": f"Invalid channel_type. Must be one of: {valid_types}"}
                ),
                400,
            )
        channel["channel_type"] = data["channel_type"]
    if "enabled" in data:
        channel["enabled"] = bool(data["enabled"])
    if "config" in data:
        channel["config"] = data["config"]

    _save_channels(channels)
    return jsonify({"message": "Channel updated"})


@notification_bp.route(
    "/api/notifications/channels/<int:channel_id>", methods=["DELETE"]
)
def delete_channel(channel_id):
    """Delete a notification channel and its rules."""
    channels = _get_channels()
    original_len = len(channels)
    channels = [c for c in channels if c.get("id") != channel_id]

    if len(channels) == original_len:
        return jsonify({"error": "Channel not found"}), 404

    _save_channels(channels)

    # Also delete associated rules
    rules = _get_rules()
    rules = [r for r in rules if r.get("channel_id") != channel_id]
    _save_rules(rules)

    return jsonify({"message": "Channel deleted"})


# ─────────────────────────────────────────────────────────────────────────────
# Notification Rules API (config.json-backed)
# ─────────────────────────────────────────────────────────────────────────────


@notification_bp.route("/api/notifications/rules")
def get_rules():
    """Return all notification rules with channel info."""
    rules = _get_rules()
    channels = _get_channels()

    result = []
    for r in rules:
        channel = next(
            (c for c in channels if c.get("id") == r.get("channel_id")), None
        )
        result.append(
            {
                "id": r.get("id"),
                "channel_id": r.get("channel_id"),
                "channel_name": channel.get("name") if channel else None,
                "channel_type": channel.get("channel_type") if channel else None,
                "min_severity": r.get("min_severity"),
                "max_severity": r.get("max_severity"),
                "enabled": r.get("enabled", True),
            }
        )
    return jsonify({"rules": result})


@notification_bp.route("/api/notifications/rules", methods=["POST"])
def create_rule():
    """Create a new notification rule."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    channel_id = data.get("channel_id")
    min_severity = data.get("min_severity")
    max_severity = data.get("max_severity")

    if channel_id is None or min_severity is None:
        return jsonify({"error": "channel_id and min_severity are required"}), 400

    # Verify channel exists
    channels = _get_channels()
    channel = next((c for c in channels if c.get("id") == channel_id), None)
    if not channel:
        return jsonify({"error": "Channel not found"}), 404

    rules = _get_rules()
    new_rule = {
        "id": _next_rule_id(),
        "channel_id": channel_id,
        "min_severity": int(min_severity),
        "max_severity": int(max_severity) if max_severity is not None else None,
        "enabled": data.get("enabled", True),
    }
    rules.append(new_rule)
    _save_rules(rules)

    return jsonify({"message": "Rule created", "id": new_rule["id"]}), 201


@notification_bp.route("/api/notifications/rules/<int:rule_id>", methods=["PUT"])
def update_rule(rule_id):
    """Update an existing notification rule."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    rules = _get_rules()
    rule = next((r for r in rules if r.get("id") == rule_id), None)

    if not rule:
        return jsonify({"error": "Rule not found"}), 404

    if "channel_id" in data:
        # Verify new channel exists
        channels = _get_channels()
        channel = next((c for c in channels if c.get("id") == data["channel_id"]), None)
        if not channel:
            return jsonify({"error": "Channel not found"}), 404
        rule["channel_id"] = data["channel_id"]
    if "min_severity" in data:
        rule["min_severity"] = int(data["min_severity"])
    if "max_severity" in data:
        rule["max_severity"] = (
            int(data["max_severity"]) if data["max_severity"] is not None else None
        )
    if "enabled" in data:
        rule["enabled"] = bool(data["enabled"])

    _save_rules(rules)
    return jsonify({"message": "Rule updated"})


@notification_bp.route("/api/notifications/rules/<int:rule_id>", methods=["DELETE"])
def delete_rule(rule_id):
    """Delete a notification rule."""
    rules = _get_rules()
    original_len = len(rules)
    rules = [r for r in rules if r.get("id") != rule_id]

    if len(rules) == original_len:
        return jsonify({"error": "Rule not found"}), 404

    _save_rules(rules)
    return jsonify({"message": "Rule deleted"})


# ─────────────────────────────────────────────────────────────────────────────
# Severity Levels Reference
# ─────────────────────────────────────────────────────────────────────────────


@notification_bp.route("/api/notifications/severity_levels")
def get_severity_levels():
    """Return the suggested severity levels for reference."""
    return jsonify(
        {
            "levels": [
                {"value": 1, "name": "Info", "description": "Informational messages"},
                {"value": 2, "name": "Warning", "description": "Warning conditions"},
                {
                    "value": 3,
                    "name": "Critical",
                    "description": "Critical/error conditions",
                },
                {"value": 4, "name": "Emergency", "description": "System is unusable"},
            ],
            "note": "These are suggestions. Severity is any positive integer.",
        }
    )
