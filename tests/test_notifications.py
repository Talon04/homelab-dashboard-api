"""Test utilities for the event system and monitoring.

Provides functions to create test events, modify mock container states,
and push events through the delivery pipeline.

Usage: python -m tests.test_notifications <command>

Commands:
  push           - Create and push a test event
  list           - List recent events
  channels       - List configured delivery channels
  rules          - List configured delivery rules
  sources        - List source severity overrides
  set-source     - Set severity for a source
  clear-source   - Clear severity for a source
  containers     - List mock containers (testing mode only)
  set-status     - Set container status (testing mode only)
  crash          - Simulate container crash (testing mode only)
  recover        - Simulate container recovery (testing mode only)
  cycle          - Run monitoring cycle (testing mode only)
  reset          - Reset mock containers to initial state
"""

import sys
import os
import argparse
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import DatabaseManager, Event, EventDelivery
from backend.config_manager import config_manager
from backend import docker_utils
from backend.docker_utils import is_testing_mode
from backend.monitoring_service import run_monitoring_cycle, _previous_states


def get_db():
    """Get database manager instance."""
    return DatabaseManager()


def create_test_event(
    severity: int = 2,
    source: str = "test",
    title: str = "Test Event",
    message: str = "This is a test event message.",
    object_type: str = None,
    object_id: int = None,
):
    """Create a test event in the database.

    Args:
        severity: Severity level (1=Info, 2=Warning, 3=Critical, 4=Emergency).
        source: Event source (test, monitor, docker, script).
        title: Event title.
        message: Event message/description.
        object_type: Optional type of related object (container, vm, etc.).
        object_id: Optional ID of related object.

    Returns:
        The created Event object.
    """
    db = get_db()
    session = db.get_session()

    try:
        # Create fingerprint for deduplication
        fingerprint = f"{source}:{title}:{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        event = Event(
            severity=severity,
            source=source,
            title=title,
            message=message,
            object_type=object_type,
            object_id=object_id,
            fingerprint=fingerprint,
            timestamp=datetime.utcnow(),
            acknowledged=False,
        )

        session.add(event)
        session.commit()

        print(f"✅ Created event #{event.id}: [{severity}] {source} - {title}")
        return event

    finally:
        db.close_session(session)


def push_to_channels(event_id: int):
    """Push an event to configured delivery channels based on rules.

    Checks the severity rules and creates EventDelivery records for
    matching channels.

    Args:
        event_id: ID of the event to push.

    Returns:
        List of channel names the event was queued for.
    """
    db = get_db()
    session = db.get_session()

    try:
        event = session.query(Event).filter(Event.id == event_id).first()
        if not event:
            print(f"❌ Event #{event_id} not found")
            return []

        # Get rules and channels from config
        notif_config = config_manager.get("modules", {}).get("notifications", {})
        rules = notif_config.get("rules", [])
        channels = notif_config.get("channels", [])

        # Get source severity config if it exists
        source_severities = notif_config.get("source_severities", {})
        source_severity = source_severities.get(event.source, event.severity)

        # Find matching rules (severity within min-max range)
        matching_channels = []
        for rule in rules:
            if not rule.get("enabled", True):
                continue

            min_sev = rule.get("min_severity", 1)
            max_sev = rule.get("max_severity", 999)  # Default to very high if not set

            if min_sev <= source_severity <= max_sev:
                channel_id = rule.get("channel_id")
                channel = next((c for c in channels if c.get("id") == channel_id), None)
                if channel and channel.get("enabled", True):
                    matching_channels.append(channel)

        # Create delivery records
        queued = []
        for channel in matching_channels:
            # Check if already queued
            existing = (
                session.query(EventDelivery)
                .filter(
                    EventDelivery.event_id == event_id,
                    EventDelivery.channel == channel["channel_type"],
                )
                .first()
            )

            if not existing:
                delivery = EventDelivery(
                    event_id=event_id, channel=channel["channel_type"], status="pending"
                )
                session.add(delivery)
                queued.append(channel["name"])

        session.commit()

        if queued:
            print(f"📤 Queued event #{event_id} for: {', '.join(queued)}")
        else:
            print(
                f"ℹ️  No matching channels for event #{event_id} (severity={source_severity})"
            )

        return queued

    finally:
        db.close_session(session)


def list_events(limit: int = 10, show_all: bool = False):
    """List recent events.

    Args:
        limit: Maximum number of events to show.
        show_all: If True, show acknowledged events too.
    """
    db = get_db()
    session = db.get_session()

    try:
        query = session.query(Event).order_by(Event.timestamp.desc())
        if not show_all:
            query = query.filter(Event.acknowledged == False)
        events = query.limit(limit).all()

        if not events:
            print("No events found.")
            return

        print(f"\n{'ID':>4} | {'Sev':>3} | {'Source':<12} | {'Title':<30} | {'Time'}")
        print("-" * 80)

        for e in events:
            time_str = e.timestamp.strftime("%Y-%m-%d %H:%M") if e.timestamp else "N/A"
            ack = "✓" if e.acknowledged else " "
            print(
                f"{e.id:>4}{ack}| {e.severity:>3} | {e.source:<12} | {e.title[:30]:<30} | {time_str}"
            )

    finally:
        db.close_session(session)


def list_channels():
    """List configured notification channels."""
    notif_config = config_manager.get("modules", {}).get("notifications", {})
    channels = notif_config.get("channels", [])

    if not channels:
        print("No channels configured.")
        return

    print(f"\n{'ID':>3} | {'Name':<20} | {'Type':<10} | {'Enabled'}")
    print("-" * 50)

    for c in channels:
        enabled = "✓" if c.get("enabled", True) else "✗"
        print(
            f"{c.get('id', '?'):>3} | {c.get('name', 'Unknown'):<20} | {c.get('channel_type', '?'):<10} | {enabled}"
        )


def list_rules():
    """List configured notification rules."""
    notif_config = config_manager.get("modules", {}).get("notifications", {})
    rules = notif_config.get("rules", [])
    channels = notif_config.get("channels", [])

    if not rules:
        print("No rules configured.")
        return

    print(f"\n{'ID':>3} | {'Severity Range':<15} | {'Channel':<20} | {'Enabled'}")
    print("-" * 60)

    for r in rules:
        channel = next(
            (c for c in channels if c.get("id") == r.get("channel_id")), None
        )
        channel_name = channel.get("name") if channel else "Unknown"
        enabled = "✓" if r.get("enabled", True) else "✗"
        min_sev = r.get("min_severity", 1)
        max_sev = r.get("max_severity", "∞")
        sev_range = f"{min_sev} - {max_sev}"
        print(
            f"{r.get('id', '?'):>3} | {sev_range:<15} | {channel_name:<20} | {enabled}"
        )


def list_source_severities():
    """List configured source severity overrides."""
    notif_config = config_manager.get("modules", {}).get("notifications", {})
    source_severities = notif_config.get("source_severities", {})

    if not source_severities:
        print("No source severity overrides configured.")
        return

    print(f"\n{'Source':<20} | {'Severity'}")
    print("-" * 35)

    for source, severity in source_severities.items():
        print(f"{source:<20} | {severity}")


def set_source_severity(source: str, severity: int):
    """Set the severity level for a specific source.

    Args:
        source: The source name (e.g., 'docker', 'monitor', 'test')
        severity: The severity level to assign
    """
    modules = config_manager.get("modules", {})
    notif_config = modules.get("notifications", {})

    if "source_severities" not in notif_config:
        notif_config["source_severities"] = {}

    notif_config["source_severities"][source] = severity
    modules["notifications"] = notif_config
    config_manager.set("modules", modules)

    print(f"✅ Set severity for source '{source}' to {severity}")


def clear_source_severity(source: str):
    """Clear the severity override for a specific source.

    Args:
        source: The source name to clear
    """
    modules = config_manager.get("modules", {})
    notif_config = modules.get("notifications", {})
    source_severities = notif_config.get("source_severities", {})

    if source in source_severities:
        del source_severities[source]
        notif_config["source_severities"] = source_severities
        modules["notifications"] = notif_config
        config_manager.set("modules", modules)
        print(f"✅ Cleared severity override for source '{source}'")
    else:
        print(f"ℹ️  No severity override found for source '{source}'")


# ─────────────────────────────────────────────────────────────────────────────
# Mock Container Testing Functions
# ─────────────────────────────────────────────────────────────────────────────


def list_mock_containers():
    """List all mock containers with their status."""
    if not is_testing_mode():
        print("⚠️  Not in testing mode. Set TESTING_MODE=1 to use mock containers.")
        return

    containers = docker_utils.get_mock_containers()

    if not containers:
        print("No mock containers found.")
        return

    print(f"\n{'ID':<25} | {'Name':<20} | {'Status':<10}")
    print("-" * 60)

    for cid, c in containers.items():
        status_icon = "🟢" if c["status"] == "running" else "🔴"
        print(f"{cid:<25} | {c['name']:<20} | {status_icon} {c['status']}")


def set_container_status(container_id: str, status: str):
    """Set the status of a mock container.

    Args:
        container_id: Container ID to modify.
        status: New status (running, exited, stopped, paused, dead).
    """
    if not is_testing_mode():
        print("⚠️  Not in testing mode. Set TESTING_MODE=1 to use mock containers.")
        return

    valid_statuses = [
        "running",
        "exited",
        "stopped",
        "paused",
        "dead",
        "restarting",
        "created",
    ]
    if status not in valid_statuses:
        print(f"❌ Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return

    success = docker_utils.set_mock_container_status(container_id, status)

    if success:
        print(f"✅ Container '{container_id}' status set to '{status}'")
    else:
        print(f"❌ Container '{container_id}' not found")


def simulate_crash(container_id: str = None):
    """Simulate a container crash and trigger monitoring.

    Args:
        container_id: Optional container ID. If not specified, uses first running container.
    """
    if not is_testing_mode():
        print("⚠️  Not in testing mode. Set TESTING_MODE=1 to use mock containers.")
        return

    # Find a running container if none specified
    if not container_id:
        containers = docker_utils.get_mock_containers()
        for cid, c in containers.items():
            if c["status"] == "running":
                container_id = cid
                break

    if not container_id:
        print("❌ No running container found to crash")
        return

    print(f"💥 Crashing container '{container_id}'...")
    docker_utils.set_mock_container_status(container_id, "exited")

    print("🔄 Running monitoring cycle...")
    run_monitoring_cycle()

    print(f"✅ Container '{container_id}' crashed. Check events for 'offline' event.")


def simulate_recover(container_id: str = None):
    """Simulate a container recovery and trigger monitoring.

    Args:
        container_id: Optional container ID. If not specified, uses first stopped container.
    """
    if not is_testing_mode():
        print("⚠️  Not in testing mode. Set TESTING_MODE=1 to use mock containers.")
        return

    # Find a stopped container if none specified
    if not container_id:
        containers = docker_utils.get_mock_containers()
        for cid, c in containers.items():
            if c["status"] != "running":
                container_id = cid
                break

    if not container_id:
        print("❌ No stopped container found to recover")
        return

    print(f"🔄 Recovering container '{container_id}'...")
    docker_utils.set_mock_container_status(container_id, "running")

    print("🔄 Running monitoring cycle...")
    run_monitoring_cycle()

    print(f"✅ Container '{container_id}' recovered. Check events for 'online' event.")


def run_cycle():
    """Manually run a monitoring cycle."""
    print("🔄 Running monitoring cycle...")
    run_monitoring_cycle()
    print(f"✅ Monitoring cycle complete. Tracked states: {dict(_previous_states)}")


def reset_mock():
    """Reset mock containers to initial state."""
    if not is_testing_mode():
        print("⚠️  Not in testing mode. Set TESTING_MODE=1 to use mock containers.")
        return

    docker_utils.reset_mock_containers()
    _previous_states.clear()
    print("✅ Mock containers reset to initial state")
    list_mock_containers()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Event system and monitoring test utilities"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # push command
    push_parser = subparsers.add_parser("push", help="Create and push a test event")
    push_parser.add_argument(
        "-s", "--severity", type=int, default=2, help="Severity level (default: 2)"
    )
    push_parser.add_argument(
        "--source", default="test", help="Event source (default: test)"
    )
    push_parser.add_argument("-t", "--title", default="Test Event", help="Event title")
    push_parser.add_argument(
        "-m", "--message", default="This is a test event.", help="Event message"
    )

    # list command
    list_parser = subparsers.add_parser("list", help="List recent events")
    list_parser.add_argument(
        "-n", "--limit", type=int, default=10, help="Number of events to show"
    )
    list_parser.add_argument(
        "-a", "--all", action="store_true", help="Show acknowledged events too"
    )

    # channels command
    subparsers.add_parser("channels", help="List configured channels")

    # rules command
    subparsers.add_parser("rules", help="List configured rules")

    # sources command
    subparsers.add_parser("sources", help="List source severity overrides")

    # set-source command
    set_source_parser = subparsers.add_parser(
        "set-source", help="Set severity for a source"
    )
    set_source_parser.add_argument("source", help="Source name")
    set_source_parser.add_argument("severity", type=int, help="Severity level")

    # clear-source command
    clear_source_parser = subparsers.add_parser(
        "clear-source", help="Clear severity for a source"
    )
    clear_source_parser.add_argument("source", help="Source name")

    # ─────────────────────────────────────────────────────────────────────────
    # Mock Container / Monitoring Commands
    # ─────────────────────────────────────────────────────────────────────────

    # containers command
    subparsers.add_parser("containers", help="List mock containers (mock mode only)")

    # set-status command
    status_parser = subparsers.add_parser(
        "set-status", help="Set container status (mock mode only)"
    )
    status_parser.add_argument("container_id", help="Container ID")
    status_parser.add_argument(
        "status",
        choices=[
            "running",
            "exited",
            "stopped",
            "paused",
            "dead",
            "restarting",
            "created",
        ],
        help="New status",
    )

    # crash command
    crash_parser = subparsers.add_parser(
        "crash", help="Simulate container crash (mock mode only)"
    )
    crash_parser.add_argument(
        "container_id",
        nargs="?",
        default=None,
        help="Container ID (optional, uses first running if not specified)",
    )

    # recover command
    recover_parser = subparsers.add_parser(
        "recover", help="Simulate container recovery (mock mode only)"
    )
    recover_parser.add_argument(
        "container_id",
        nargs="?",
        default=None,
        help="Container ID (optional, uses first stopped if not specified)",
    )

    # cycle command
    subparsers.add_parser("cycle", help="Run monitoring cycle")

    # reset command
    subparsers.add_parser("reset", help="Reset mock containers to initial state")

    args = parser.parse_args()

    if args.command == "push":
        event = create_test_event(
            severity=args.severity,
            source=args.source,
            title=args.title,
            message=args.message,
        )
        if event:
            push_to_channels(event.id)
    elif args.command == "list":
        list_events(limit=args.limit, show_all=args.all)
    elif args.command == "channels":
        list_channels()
    elif args.command == "rules":
        list_rules()
    elif args.command == "sources":
        list_source_severities()
    elif args.command == "set-source":
        set_source_severity(args.source, args.severity)
    elif args.command == "clear-source":
        clear_source_severity(args.source)
    elif args.command == "containers":
        list_mock_containers()
    elif args.command == "set-status":
        set_container_status(args.container_id, args.status)
    elif args.command == "crash":
        simulate_crash(args.container_id)
    elif args.command == "recover":
        simulate_recover(args.container_id)
    elif args.command == "cycle":
        run_cycle()
    elif args.command == "reset":
        reset_mock()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
