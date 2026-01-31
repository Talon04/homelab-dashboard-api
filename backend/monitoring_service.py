"""Background monitoring service for containers and VMs.

Provides a database-backed monitoring loop that:
- Reads enabled monitor configurations from monitor_bodies
- Performs health checks (currently Docker container status)
- Persists data points to monitor_points
- Creates events when state changes occur (offline, online, unreachable)

Similar architecture to task_scheduler.py - lightweight background thread
that can also be driven manually via run_monitoring_cycle().
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional

from backend.save_manager import get_save_manager
from backend import config_utils
from backend import docker_utils

try:
    from backend.models import MonitorBodies, MonitorPoints, Container, Event
except Exception:
    MonitorBodies = None  # type: ignore
    MonitorPoints = None  # type: ignore
    Container = None  # type: ignore
    Event = None  # type: ignore


_worker_thread: Optional[threading.Thread] = None
_monitor_stop_flag = False
# Tracks previous states per monitor_body.id for detecting state changes
_previous_states: Dict[int, str] = {}
_stop_event = threading.Event()


# =============================================================================
# Status Evaluation
# =============================================================================


def _get_containers_index() -> Dict[str, Dict]:
    """Build a mapping of Docker container ID -> container info."""
    try:
        containers: List[Dict] = docker_utils.list_containers()
    except Exception as exc:
        print(f"[monitoring_service] Failed to list containers: {exc}")
        return {}

    index: Dict[str, Dict] = {}
    for c in containers or []:
        cid = c.get("id")
        if cid:
            index[str(cid)] = c
    return index


def _evaluate_docker_container_status(container_row) -> str:
    """Evaluate the health state of a Docker-backed monitor.

    Returns:
        Status string: online, offline, or unknown.
    """
    if container_row is None:
        return "unknown"

    container_status = docker_utils.get_container_status_by_id(container_row.docker_id)
    return container_status if container_status else "unknown"


# =============================================================================
# Event Creation
# =============================================================================


def _get_event_type_for_state(new_state: str, old_state: str) -> Optional[str]:
    """Determine event type based on state transition.

    Returns:
        Event type: offline, online, unreachable, or None if no event needed.
    """
    new_state = new_state.lower() if new_state else "unknown"
    old_state = old_state.lower() if old_state else "unknown"

    online_states = {"running", "online"}
    offline_states = {"exited", "offline", "stopped", "dead"}
    unreachable_states = {"unknown", "unreachable", "paused"}

    if new_state in offline_states and old_state not in offline_states:
        return "offline"
    elif new_state in online_states and old_state not in online_states:
        return "online"
    elif new_state in unreachable_states and old_state not in unreachable_states:
        return "unreachable"

    return None


def _create_state_change_event(
    session,
    md,
    container_name: str,
    event_type: str,
    new_state: str,
    old_state: str,
    severity: int,
) -> None:
    """Create an Event record for a state change."""
    if Event is None:
        return

    titles = {
        "offline": f"{container_name} went offline",
        "online": f"{container_name} came online",
        "unreachable": f"{container_name} is unreachable",
    }
    messages = {
        "offline": f"Container/VM '{container_name}' transitioned from {old_state} to {new_state}",
        "online": f"Container/VM '{container_name}' is now running (was {old_state})",
        "unreachable": f"Container/VM '{container_name}' state is {new_state} (was {old_state})",
    }

    title = titles.get(event_type, f"{container_name} state changed")
    message = messages.get(event_type, f"State changed from {old_state} to {new_state}")
    fingerprint = f"monitor:{md.id}:{event_type}:{new_state}"

    event = Event(
        severity=severity,
        source="monitor",
        title=title,
        message=message,
        object_type="container" if md.container_id else "vm",
        object_id=md.container_id or md.vm_id,
        fingerprint=fingerprint,
        timestamp=datetime.utcnow(),
        acknowledged=False,
    )
    session.add(event)


# =============================================================================
# Monitoring Cycle
# =============================================================================


def run_monitoring_cycle() -> None:
    """Run a single monitoring pass over all enabled monitor entries.

    Safe to call ad-hoc (e.g., from cron or tests) and also used by
    the background thread started via start_monitoring_service().
    """
    global _previous_states
    sm = get_save_manager()

    # Degrade gracefully if database layer not initialized
    if getattr(sm, "db_manager", None) is None:
        return
    if MonitorBodies is None or MonitorPoints is None or Container is None:
        return

    with sm.get_db_session() as session:
        if session is None:
            return

        monitors = (
            session.query(MonitorBodies).filter(MonitorBodies.enabled == True).all()
        )

        for md in monitors:
            value = "unknown"
            container_name = md.name or f"Monitor {md.id}"

            if md.monitor_type == "docker" and md.container_id:
                cont = (
                    session.query(Container)
                    .filter(Container.id == md.container_id)
                    .first()
                )
                value = _evaluate_docker_container_status(cont)
                if cont:
                    container_name = cont.name or container_name

            # Record the monitoring point
            point = MonitorPoints(
                monitor_body_id=md.id,
                value=value,
            )
            session.add(point)

            # Check for state changes and create events
            old_state = _previous_states.get(md.id)
            if old_state is not None and old_state != value:
                event_type = _get_event_type_for_state(value, old_state)

                if event_type:
                    settings = {}
                    if md.event_severity_settings:
                        try:
                            settings = json.loads(md.event_severity_settings)
                        except Exception:
                            pass

                    event_config = settings.get(event_type, {})
                    is_enabled = event_config.get("enabled", True)
                    severity = event_config.get("severity", 2)

                    if is_enabled and severity > 0:
                        _create_state_change_event(
                            session,
                            md,
                            container_name,
                            event_type,
                            value,
                            old_state,
                            severity,
                        )

            _previous_states[md.id] = value


# =============================================================================
# Background Service
# =============================================================================


def _monitor_loop() -> None:
    """Background loop that periodically runs the monitoring cycle."""
    global _monitor_stop_flag
    while not _stop_event.is_set():
        try:
            run_monitoring_cycle()
        except Exception as exc:
            print(f"[monitoring_service] Error in monitoring cycle: {exc}")
        _stop_event.wait(config_utils.get_monitoring_polling_rate())


def start_monitoring_service() -> None:
    """Start the monitoring background service."""
    global _worker_thread

    if _worker_thread is not None and _worker_thread.is_alive():
        print("[notification_service] Service already running")
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_monitor_loop, daemon=True)
    _worker_thread.start()
    print("[notification_service] Service started")


def stop_monitoring_service() -> None:
    """Stop the monitoring background service."""
    global _worker_thread

    if _worker_thread is None or not _worker_thread.is_alive():
        return

    _stop_event.set()
    _worker_thread.join(timeout=5)
    _worker_thread = None
    print("[monitoring_service] Service stopped")


def is_service_running() -> bool:
    """Check if the monitoring service is running."""
    return _worker_thread is not None and _worker_thread.is_alive()
