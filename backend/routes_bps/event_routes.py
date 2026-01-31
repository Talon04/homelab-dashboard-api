"""API routes for events (database-backed).

Handles event listing, acknowledgment, and deletion.
"""

from datetime import datetime
from flask import Blueprint, jsonify, request

from backend.models import DatabaseManager, Event, EventDelivery


event_bp = Blueprint("event", __name__)
_db_manager = None


def get_db():
    """Get or create the database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


# ─────────────────────────────────────────────────────────────────────────────
# Events API (database-backed)
# ─────────────────────────────────────────────────────────────────────────────


@event_bp.route("/api/notifications/events")
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


@event_bp.route("/api/notifications/events/unread_count")
def get_unread_count():
    """Return count of unacknowledged events."""
    db = get_db()
    session = db.get_session()
    try:
        count = session.query(Event).filter(Event.acknowledged == False).count()
        return jsonify({"count": count})
    finally:
        db.close_session(session)


@event_bp.route(
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


@event_bp.route("/api/notifications/events/acknowledge_all", methods=["POST"])
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


@event_bp.route("/api/notifications/events/delete_all", methods=["DELETE"])
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


@event_bp.route("/api/notifications/events/<int:event_id>", methods=["DELETE"])
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

@event_bp.route("/api/notifications/events/lastEventsByContainerId/<int:container_id>:<int:count>", methods=["GET"])
def get_last_events_by_container_id(container_id, count):
    """Return the last N events for a given container ID."""
    db = get_db()
    session = db.get_session()
    try:
        events = (
            session.query(Event)
            .filter(Event.object_type == "container", Event.object_id == container_id)
            .order_by(Event.timestamp.desc())
            .limit(count)
            .all()
        )

        return jsonify(
            [
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
            ]
        )
    finally:
        db.close_session(session)

@event_bp.route("/api/notifications/events/lastEventsByVmId/<int:vm_id>:<int:count>", methods=["GET"])
def get_last_events_by_vm_id(vm_id, count):
    """Return the last N events for a given VM ID."""
    db = get_db()
    session = db.get_session()
    try:
        events = (
            session.query(Event)
            .filter(Event.object_type == "vm", Event.object_id == vm_id)
            .order_by(Event.timestamp.desc())
            .limit(count)
            .all()
        )

        return jsonify(
            [
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
            ]
        )
    finally:
        db.close_session(session)



# ─────────────────────────────────────────────────────────────────────────────
# Test Event Creation
# ─────────────────────────────────────────────────────────────────────────────


@event_bp.route("/api/notifications/test", methods=["POST"])
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
