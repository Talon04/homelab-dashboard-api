"""Testing API routes for development and integration testing.

Provides programmatic access to modify mock container states, trigger
monitoring cycles, and manage test scenarios. Only available when
TESTING_MODE=1 environment variable is set.

Production deployment:
    1. Delete this file
    2. Remove testing_bp import and registration from app.py
"""

from flask import Blueprint, jsonify, request

from backend import docker_utils
from backend.docker_utils import is_testing_mode
from backend.monitoring_service import run_monitoring_cycle, _previous_states


testing_bp = Blueprint("testing", __name__)


def _require_testing_mode():
    """Return error response if not in testing mode."""
    if not is_testing_mode():
        return (
            jsonify(
                {"error": "Testing API only available in testing mode (TESTING_MODE=1)"}
            ),
            403,
        )
    return None


@testing_bp.route("/api/testing/status")
def testing_status():
    """Check if testing mode is enabled."""
    return jsonify(
        {
            "testing_mode": is_testing_mode(),
            "message": "Testing API is "
            + ("enabled" if is_testing_mode() else "disabled"),
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# Mock Container Management
# ─────────────────────────────────────────────────────────────────────────────


@testing_bp.route("/api/testing/containers")
def list_mock_containers():
    """List all mock containers with their current state."""
    error = _require_testing_mode()
    if error:
        return error

    containers = docker_utils.get_mock_containers()
    return jsonify(list(containers.values()))


@testing_bp.route("/api/testing/containers/<container_id>/status", methods=["POST"])
def set_container_status(container_id):
    """Set the status of a mock container.

    Request body: {"status": "running"|"exited"|"stopped"|"paused"|"dead"|etc.}
    """
    error = _require_testing_mode()
    if error:
        return error

    data = request.get_json() or {}
    status = data.get("status")

    if not status:
        return jsonify({"error": "Missing 'status' in request body"}), 400

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
        return (
            jsonify(
                {
                    "error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
                }
            ),
            400,
        )

    success = docker_utils.set_mock_container_status(container_id, status)

    if success:
        return jsonify(
            {
                "message": f"Container {container_id} status set to '{status}'",
                "container_id": container_id,
                "status": status,
            }
        )
    else:
        return jsonify({"error": f"Container '{container_id}' not found"}), 404


@testing_bp.route("/api/testing/containers", methods=["POST"])
def add_container():
    """Add a new mock container.

    Body: {
        "id": "container_id",
        "name": "container_name",
        "status": "running",  # optional, defaults to "running"
        "ports": {},          # optional
        "labels": {}          # optional
    }
    """
    error = _require_testing_mode()
    if error:
        return error

    data = request.get_json() or {}

    container_id = data.get("id")
    name = data.get("name")

    if not container_id or not name:
        return jsonify({"error": "Missing 'id' or 'name' in request body"}), 400

    container = docker_utils.add_mock_container(
        container_id=container_id,
        name=name,
        status=data.get("status", "running"),
        ports=data.get("ports"),
        labels=data.get("labels"),
    )

    return (
        jsonify({"message": f"Container '{name}' added", "container": container}),
        201,
    )


@testing_bp.route("/api/testing/containers/<container_id>", methods=["DELETE"])
def remove_container(container_id):
    """Remove a mock container."""
    error = _require_testing_mode()
    if error:
        return error

    success = docker_utils.remove_mock_container(container_id)

    if success:
        return jsonify({"message": f"Container '{container_id}' removed"})
    else:
        return jsonify({"error": f"Container '{container_id}' not found"}), 404


@testing_bp.route("/api/testing/containers/reset", methods=["POST"])
def reset_containers():
    """Reset all mock containers to their initial state."""
    error = _require_testing_mode()
    if error:
        return error

    docker_utils.reset_mock_containers()

    # Also clear monitoring previous states to trigger fresh events
    _previous_states.clear()

    return jsonify(
        {
            "message": "Mock containers reset to initial state",
            "containers": list(docker_utils.get_mock_containers().values()),
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# Monitoring Control
# ─────────────────────────────────────────────────────────────────────────────


@testing_bp.route("/api/testing/monitoring/cycle", methods=["POST"])
def trigger_monitoring_cycle():
    """Manually trigger a monitoring cycle.

    This runs the monitoring loop once immediately, checking all enabled
    monitors and creating events for state changes.
    """
    error = _require_testing_mode()
    if error:
        return error

    try:
        run_monitoring_cycle()
        return jsonify(
            {
                "message": "Monitoring cycle completed",
                "previous_states": dict(_previous_states),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@testing_bp.route("/api/testing/monitoring/states")
def get_monitoring_states():
    """Get the current tracked states for all monitors."""
    error = _require_testing_mode()
    if error:
        return error

    return jsonify({"previous_states": dict(_previous_states)})


@testing_bp.route("/api/testing/monitoring/states/clear", methods=["POST"])
def clear_monitoring_states():
    """Clear all tracked monitor states.

    This will cause the next monitoring cycle to treat all states as
    new (no state change events will be generated until states change again).
    """
    error = _require_testing_mode()
    if error:
        return error

    _previous_states.clear()

    return jsonify({"message": "Monitor states cleared"})


# ─────────────────────────────────────────────────────────────────────────────
# Test Scenarios
# ─────────────────────────────────────────────────────────────────────────────


@testing_bp.route("/api/testing/scenarios/container-crash", methods=["POST"])
def scenario_container_crash():
    """Simulate a container crash scenario.

    Body: {"container_id": "id"} or uses first running container

    This will:
    1. Set container status to 'exited'
    2. Trigger a monitoring cycle
    3. This should create an 'offline' event if monitoring is enabled
    """
    error = _require_testing_mode()
    if error:
        return error

    data = request.get_json() or {}
    container_id = data.get("container_id")

    # Find a running container if none specified
    if not container_id:
        containers = docker_utils.get_mock_containers()
        for cid, c in containers.items():
            if c["status"] == "running":
                container_id = cid
                break

    if not container_id:
        return jsonify({"error": "No running container found"}), 404

    # Set to exited
    success = docker_utils.set_mock_container_status(container_id, "exited")
    if not success:
        return jsonify({"error": f"Container '{container_id}' not found"}), 404

    # Run monitoring cycle
    run_monitoring_cycle()

    return jsonify(
        {
            "message": f"Container '{container_id}' crashed (status: exited)",
            "container_id": container_id,
            "new_status": "exited",
            "monitoring_states": dict(_previous_states),
        }
    )


@testing_bp.route("/api/testing/scenarios/container-recover", methods=["POST"])
def scenario_container_recover():
    """Simulate a container recovery scenario.

    Body: {"container_id": "id"} or uses first non-running container

    This will:
    1. Set container status to 'running'
    2. Trigger a monitoring cycle
    3. This should create an 'online' event if monitoring is enabled
    """
    error = _require_testing_mode()
    if error:
        return error

    data = request.get_json() or {}
    container_id = data.get("container_id")

    # Find a non-running container if none specified
    if not container_id:
        containers = docker_utils.get_mock_containers()
        for cid, c in containers.items():
            if c["status"] != "running":
                container_id = cid
                break

    if not container_id:
        return jsonify({"error": "No stopped container found"}), 404

    # Set to running
    success = docker_utils.set_mock_container_status(container_id, "running")
    if not success:
        return jsonify({"error": f"Container '{container_id}' not found"}), 404

    # Run monitoring cycle
    run_monitoring_cycle()

    return jsonify(
        {
            "message": f"Container '{container_id}' recovered (status: running)",
            "container_id": container_id,
            "new_status": "running",
            "monitoring_states": dict(_previous_states),
        }
    )


@testing_bp.route("/api/testing/scenarios/full-cycle", methods=["POST"])
def scenario_full_cycle():
    """Run a full test cycle: crash then recover a container.

    Body: {"container_id": "id"} or uses first running container

    This demonstrates the full event lifecycle.
    """
    error = _require_testing_mode()
    if error:
        return error

    data = request.get_json() or {}
    container_id = data.get("container_id")

    # Find a running container if none specified
    if not container_id:
        containers = docker_utils.get_mock_containers()
        for cid, c in containers.items():
            if c["status"] == "running":
                container_id = cid
                break

    if not container_id:
        return jsonify({"error": "No running container found"}), 404

    results = []

    # First: crash
    docker_utils.set_mock_container_status(container_id, "exited")
    run_monitoring_cycle()
    results.append(
        {"step": "crash", "status": "exited", "states": dict(_previous_states)}
    )

    # Second: recover
    docker_utils.set_mock_container_status(container_id, "running")
    run_monitoring_cycle()
    results.append(
        {"step": "recover", "status": "running", "states": dict(_previous_states)}
    )

    return jsonify(
        {
            "message": f"Full cycle completed for container '{container_id}'",
            "container_id": container_id,
            "steps": results,
        }
    )
