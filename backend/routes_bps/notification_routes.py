"""Flask routes for the notification system.

Channels and rules are stored in config.json via config_manager.
Events are stored in the database.
"""

from datetime import datetime
from flask import Blueprint, jsonify, request

from backend.models import DatabaseManager, Event, EventDelivery
from backend.config_manager import config_manager

notification_bp = Blueprint("notification", __name__)

# Shared database manager instance
_db_manager = None


def get_db():
    """Get or create the database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


# ─────────────────────────────────────────────────────────────────────────────
# Helper functions for config-based channels/rules
# ─────────────────────────────────────────────────────────────────────────────


def _get_notification_config():
    """Get the notifications module config."""
    return config_manager.get("modules", {}).get("notifications", {})


def _save_notification_config(notif_config):
    """Save the notifications module config."""
    modules = config_manager.get("modules", {})
    modules["notifications"] = notif_config
    config_manager.set("modules", modules)


def _get_channels():
    """Get all notification channels from config."""
    return _get_notification_config().get("channels", [])


def _save_channels(channels):
    """Save notification channels to config."""
    notif_config = _get_notification_config()
    notif_config["channels"] = channels
    _save_notification_config(notif_config)


def _get_rules():
    """Get all notification rules from config."""
    return _get_notification_config().get("rules", [])


def _save_rules(rules):
    """Save notification rules to config."""
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
# Events API (database-backed)
# ─────────────────────────────────────────────────────────────────────────────


@notification_bp.route("/api/notifications/events")
def get_events():
    """Return a list of events, optionally filtered by acknowledged status."""
    db = get_db()
    session = db.get_session()
    try:
        acknowledged = request.args.get("acknowledged")
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)

        query = session.query(Event).order_by(Event.timestamp.desc())

        if acknowledged is not None:
            ack_bool = acknowledged.lower() in ("true", "1", "yes")
            query = query.filter(Event.acknowledged == ack_bool)

        total = query.count()
        events = query.offset(offset).limit(limit).all()

        return jsonify(
            {
                "events": [
                    {
                        "id": e.id,
                        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                        "severity": e.severity,
                        "source": e.source,
                        "title": e.title,
                        "message": e.message,
                        "object_type": e.object_type,
                        "object_id": e.object_id,
                        "acknowledged": e.acknowledged,
                        "acknowledged_at": (
                            e.acknowledged_at.isoformat() if e.acknowledged_at else None
                        ),
                    }
                    for e in events
                ],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )
    finally:
        db.close_session(session)


@notification_bp.route("/api/notifications/events/unread_count")
def get_unread_count():
    """Return count of unacknowledged events."""
    db = get_db()
    session = db.get_session()
    try:
        count = session.query(Event).filter(Event.acknowledged == False).count()
        return jsonify({"count": count})
    finally:
        db.close_session(session)


@notification_bp.route(
    "/api/notifications/events/<int:event_id>/acknowledge", methods=["POST"]
)
def acknowledge_event(event_id):
    """Mark a single event as acknowledged."""
    db = get_db()
    session = db.get_session()
    try:
        event = session.query(Event).filter(Event.id == event_id).first()
        if not event:
            return jsonify({"error": "Event not found"}), 404

        event.acknowledged = True
        event.acknowledged_at = datetime.utcnow()
        session.commit()
        return jsonify({"message": "Event acknowledged"})
    finally:
        db.close_session(session)


@notification_bp.route("/api/notifications/events/acknowledge_all", methods=["POST"])
def acknowledge_all_events():
    """Mark all unacknowledged events as acknowledged."""
    db = get_db()
    session = db.get_session()
    try:
        now = datetime.utcnow()
        session.query(Event).filter(Event.acknowledged == False).update(
            {"acknowledged": True, "acknowledged_at": now}
        )
        session.commit()
        return jsonify({"message": "All events acknowledged"})
    finally:
        db.close_session(session)


@notification_bp.route("/api/notifications/events/delete_all", methods=["DELETE"])
def delete_all_events():
    """Delete all events and their deliveries."""
    db = get_db()
    session = db.get_session()
    try:
        # Delete all deliveries first
        session.query(EventDelivery).delete()
        # Delete all events
        count = session.query(Event).delete()
        session.commit()
        return jsonify({"message": f"{count} events deleted", "count": count})
    finally:
        db.close_session(session)


@notification_bp.route("/api/notifications/events/<int:event_id>", methods=["DELETE"])
def delete_event(event_id):
    """Delete an event and its deliveries."""
    db = get_db()
    session = db.get_session()
    try:
        # Delete related deliveries first
        session.query(EventDelivery).filter(EventDelivery.event_id == event_id).delete()
        # Delete the event
        deleted = session.query(Event).filter(Event.id == event_id).delete()
        session.commit()
        if deleted:
            return jsonify({"message": "Event deleted"})
        return jsonify({"error": "Event not found"}), 404
    finally:
        db.close_session(session)


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


# ─────────────────────────────────────────────────────────────────────────────
# Test Event Creation
# ─────────────────────────────────────────────────────────────────────────────


@notification_bp.route("/api/notifications/test", methods=["POST"])
def create_test_event():
    """Create a test notification event."""
    data = request.get_json() or {}

    severity = data.get("severity", 2)
    source = data.get("source", "test")
    title = data.get("title", "Test Notification")
    message = data.get("message", "This is a test notification message.")

    try:
        severity = int(severity)
        if severity < 1:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({"error": "severity must be a positive integer"}), 400

    db = get_db()
    session = db.get_session()
    try:
        fingerprint = f"{source}:{title}:{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"

        event = Event(
            severity=severity,
            source=source,
            title=title,
            message=message,
            fingerprint=fingerprint,
            timestamp=datetime.utcnow(),
            acknowledged=False,
        )

        session.add(event)
        session.commit()

        return (
            jsonify(
                {
                    "message": "Test event created",
                    "event": {
                        "id": event.id,
                        "severity": event.severity,
                        "source": event.source,
                        "title": event.title,
                        "message": event.message,
                    },
                }
            ),
            201,
        )
    finally:
        db.close_session(session)
