"""Background monitoring service for containers/VMs.

This module provides a very small, database-backed "monitoring loop"
which can be expanded over time.  The goal for now is to:

- Read enabled monitor configurations from ``monitor_bodies``
- Perform a simple health check for each (currently: Docker containers)
- Persist a point into ``monitor_points`` with the resulting state

The design mirrors :mod:`backend.task_scheduler` – a lightweight
background thread that can also be driven manually by calling
``run_monitoring_cycle`` from an external scheduler.
"""

from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional

from backend.save_manager import get_save_manager
from backend import docker_utils

try:  # Import models directly so we can use the ORM session
    from backend.models import MonitorBodies, MonitorPoints, Container
except Exception:  # pragma: no cover - defensive; service becomes a no-op
    MonitorBodies = None  # type: ignore
    MonitorPoints = None  # type: ignore
    Container = None  # type: ignore


_monitor_thread: Optional[threading.Thread] = None
_monitor_stop_flag = False


def _get_containers_index() -> Dict[str, Dict]:
    """Return a mapping of Docker container ID -> container info.

    Uses :func:`backend.docker_utils.list_containers` which already
    handles the mock/real Docker split.
    """

    try:
        containers: List[Dict] = docker_utils.list_containers()
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[monitoring_service] Failed to list containers: {exc}")
        return {}

    index: Dict[str, Dict] = {}
    for c in containers or []:
        cid = c.get("id")
        if not cid:
            continue
        index[str(cid)] = c
    return index


def _evaluate_docker_container_status(container_row) -> str:
    """Return a coarse health state for a Docker-backed monitor.

    States are simple strings for now: ``online``, ``offline`` or
    ``unknown``.  This can be enriched later with latency, CPU, etc.
    """

    if container_row is None:
        return "unknown"

    container_status = docker_utils.get_container_status_by_id(container_row.docker_id)
    return container_status if container_status else "unknown"


def run_monitoring_cycle() -> None:
    """Run a single monitoring pass over all enabled monitor entries.

    This is safe to call ad-hoc (e.g. from a cron job) and is also
    used by the background thread started via ``start_monitoring_service``.
    """

    sm = get_save_manager()

    # If the database layer is not initialised (e.g. SQLAlchemy missing),
    # degrade gracefully into a no-op.
    if getattr(sm, "db_manager", None) is None:
        return
    if MonitorBodies is None or MonitorPoints is None or Container is None:
        return

    with sm.get_db_session() as session:
        if session is None:
            return

        # Only look at enabled monitor bodies for now.
        monitors = session.query(MonitorBodies).filter(MonitorBodies.enabled == True).all()  # type: ignore[comparison-overlap]

        for md in monitors:
            value = "unknown"

            if md.monitor_type == "docker" and md.container_id:
                # ``container_id`` here is the internal containers.id PK.
                cont = (
                    session.query(Container)
                    .filter(Container.id == md.container_id)
                    .first()
                )
                value = _evaluate_docker_container_status(cont)

            # Future monitor types (VMs, ping, HTTP, etc.) can be
            # implemented here by branching on ``md.monitor_type``.

            point = MonitorPoints(  # type: ignore[call-arg]
                monitor_data_id=md.id,
                value=value,
            )
            session.add(point)


def _monitor_loop(poll_interval: float) -> None:
    """Background loop that periodically runs the monitoring cycle."""

    global _monitor_stop_flag
    while not _monitor_stop_flag:
        try:
            run_monitoring_cycle()
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[monitoring_service] Error in monitoring cycle: {exc}")
        time.sleep(poll_interval)


def start_monitoring_service(poll_interval: float = 10.0) -> None:
    """Start the monitoring background thread if not already running.

    This is invoked from :mod:`app` at startup, but can also be
    called manually in scripts or tests.
    """

    global _monitor_thread, _monitor_stop_flag

    if _monitor_thread is not None and _monitor_thread.is_alive():
        return

    _monitor_stop_flag = False

    t = threading.Thread(target=_monitor_loop, args=(poll_interval,), daemon=True)
    _monitor_thread = t
    t.start()


def stop_monitoring_service() -> None:
    """Signal the monitoring background thread to stop.

    This is mainly useful for tests or when running under an
    external process supervisor that wants to shut down cleanly.
    """

    global _monitor_stop_flag
    _monitor_stop_flag = True
