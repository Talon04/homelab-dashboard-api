# =============================================================================
# CONTAINERS ROUTES - Container and widget API endpoints
# =============================================================================
"""API routes for containers, VMs and container widgets."""

import time

from flask import Blueprint, jsonify, request, current_app

import backend.config_utils as config_utils
import backend.docker_utils as docker_utils
import backend.code_editor_utils as code_editor_utils
from backend.save_manager import get_save_manager
from backend.routes_bps.code_routes import api_code_run


# =============================================================================
# BLUEPRINT REGISTRATION
# =============================================================================

containers_bp = Blueprint("containers", __name__)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _generate_widget_script_path(container_id: str, widget_type: str) -> str:
    """Generate a default script path for a widget.

    The name includes the widget type, a container identifier and a
    timestamp, e.g. ``text_mycontainer_1700000000.py`` stored under
    ``widgets/mycontainer/``. This keeps scripts grouped per container
    and makes it obvious which widget/container they belong to.
    """

    # Try to use the container's human-friendly name if available,
    # otherwise fall back to its ID from the URL.
    base_name = container_id
    try:
        containers = docker_utils.list_containers()
        cont = next((c for c in containers if c.get("id") == container_id), None)
        if cont and cont.get("name"):
            base_name = cont.get("name")
    except Exception:
        pass

    safe = "".join(
        ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(base_name)
    )
    wtype = (widget_type or "text").lower()
    if wtype not in ("text", "button"):
        wtype = "text"
    ts = int(time.time())
    filename = f"{wtype}_{safe}_{ts}.py"
    return f"widgets/{safe}/{filename}"


# =============================================================================
# CONTAINER & VM LISTING
# =============================================================================


@containers_bp.route("/api/containers")
@containers_bp.route("/api/data/containers")
def list_containers():
    """Return live Docker container data from docker_utils."""
    return jsonify(docker_utils.list_containers())


@containers_bp.route("/api/vms")
@containers_bp.route("/api/data/vms")
def list_vms():
    """Return all VMs stored in the database."""
    sm = get_save_manager()
    return jsonify(sm.get_all_vms())


# =============================================================================
# WIDGET CRUD
# =============================================================================


@containers_bp.route("/api/containers/<container_id>/widgets")
def get_container_widgets(container_id):
    """Return all widgets configured for a single container."""

    sm = get_save_manager()
    return jsonify(sm.get_widgets(container_id))


@containers_bp.route("/api/containers/<container_id>/widgets", methods=["POST"])
def add_container_widget(container_id):
    """Create a new widget for ``container_id``.

    If no explicit script path is provided, a sensible default under
    ``widgets/<container-name>/`` is generated and optionally scaffolded.
    """

    sm = get_save_manager()
    data = request.get_json() or {}
    # If no explicit script path is provided, generate a sensible
    # default that includes the container in the name.
    if not data.get("file_path"):
        widget_type = data.get("type") or "text"
        data["file_path"] = _generate_widget_script_path(container_id, widget_type)
    w = sm.add_widget(container_id, data)
    if not w:
        return jsonify({"error": "Failed to add widget"}), 400
    # Optional: scaffold default file if requested
    fp = w.get("file_path")
    if fp:
        try:
            code_editor_utils.ensure_scaffold(fp, w.get("type"))
        except Exception:
            pass
    return jsonify(w)


@containers_bp.route(
    "/api/containers/<container_id>/widgets/<int:widget_id>", methods=["PUT"]
)
def update_container_widget(container_id, widget_id):
    """Update widget settings such as label, text or script path."""

    sm = get_save_manager()
    data = request.get_json() or {}
    ok = sm.update_widget(container_id, widget_id, data)
    if not ok:
        return jsonify({"error": "Not found"}), 404

    # If the script path was changed (or newly assigned), ensure the
    # backing file exists, but do not overwrite existing content.
    fp = data.get("file_path")
    if fp:
        try:
            code_editor_utils.ensure_scaffold(fp, data.get("type"))
        except Exception:
            pass

    return jsonify({"ok": True})


@containers_bp.route(
    "/api/containers/<container_id>/widgets/<int:widget_id>", methods=["DELETE"]
)
def delete_container_widget(container_id, widget_id):
    """Delete a widget and detach it from its container."""

    sm = get_save_manager()
    ok = sm.delete_widget(container_id, widget_id)
    return jsonify({"ok": True}) if ok else (jsonify({"error": "Not found"}), 404)


@containers_bp.route(
    "/api/containers/<container_id>/widgets/<int:widget_id>/run", methods=["POST"]
)
def run_container_widget(container_id, widget_id):
    """Execute a widget's backing script once and return its output."""

    sm = get_save_manager()
    # Find widget to get file path and type
    widgets = sm.get_widgets(container_id)
    widget = next((w for w in widgets if w.get("id") == widget_id), None)
    if not widget or not widget.get("file_path"):
        return jsonify({"error": "Widget or file not found"}), 404
    # Build context: include container info from docker_utils
    try:
        containers = docker_utils.list_containers()
        ctx_container = next(
            (c for c in containers if c.get("id") == container_id), None
        )
    except Exception:
        ctx_container = None
    context = {"container": ctx_container, "widget": widget}
    path = widget.get("file_path")
    if isinstance(path, str) and path.endswith(".py"):
        # Run server-side python with context JSON passed via args.
        try:
            import json as _json

            data = {"path": path, "args": [_json.dumps(context)]}
            with current_app.test_request_context(
                "/api/code/run", method="POST", json=data
            ):
                resp = api_code_run()
            return resp
        except Exception as e:
            return jsonify({"error": str(e)}), 400
    else:
        # For JS, client should fetch and execute with provided context
        return jsonify({"message": "Client-run JS", "context": context, "path": path})


# =============================================================================
# CONTAINER PORTS & LINKS
# =============================================================================


@containers_bp.route("/api/containers/ports/<container_id>")
@containers_bp.route("/api/data/containers/ports/<container_id>")
def container_ports(container_id):
    """Return live port mappings for a container from Docker."""

    return jsonify(docker_utils.get_container_ports(container_id))


@containers_bp.route("/api/config/preferred_ports/<container_id>")
@containers_bp.route("/api/data/preferred_ports/<container_id>")
def get_preferred_port(container_id):
    """Return the preferred port for a container from config_utils."""
    port = config_utils.get_preferred_port(container_id)
    return jsonify({"preferred_port": port})


@containers_bp.route("/api/config/preferred_ports", methods=["POST"])
@containers_bp.route("/api/data/preferred_ports", methods=["POST"])
def set_preferred_port():
    """Update the preferred port for a container.

    Expects JSON body with ``container_id`` and ``port``.
    """

    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    container_id = data.get("container_id")
    port = data.get("port")

    if not container_id:
        return jsonify({"error": "Missing container_id"}), 400

    if not port:
        return jsonify({"error": "Missing port"}), 400

    config_utils.set_preferred_port(container_id, port)
    return jsonify({"message": "Preferred port saved"}), 200


@containers_bp.route("/api/config/link_bodies/<container_id>")
@containers_bp.route("/api/data/link_bodies/<container_id>")
def get_link_body(container_id):
    """Return the internal link body for a container."""
    link_body = config_utils.get_link_body(container_id)
    return jsonify(link_body)


@containers_bp.route("/api/config/link_bodies", methods=["POST"])
@containers_bp.route("/api/data/link_bodies", methods=["POST"])
def set_link_body():
    """Set the internal link body for a container from JSON body."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    container_id = data.get("container_id")
    link_body = data.get("link_body")

    if not container_id:
        return jsonify({"error": "Missing container_id"}), 400

    if link_body is None:
        return jsonify({"error": "Missing link_body"}), 400

    config_utils.set_link_body(container_id, link_body)
    return jsonify({"message": "Internal Link Body saved"}), 200


@containers_bp.route("/api/config/external_link_bodies/<container_id>")
@containers_bp.route("/api/data/external_link_bodies/<container_id>")
def get_external_link_body(container_id):
    """Return the external link body for a container."""
    link_body = config_utils.get_external_link_body(container_id)
    return jsonify(link_body)


@containers_bp.route("/api/config/external_link_bodies", methods=["POST"])
@containers_bp.route("/api/data/external_link_bodies", methods=["POST"])
def set_external_link_body():
    """Set the external link body for a container from JSON body."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    container_id = data.get("container_id")
    link_body = data.get("link_body")

    if not container_id:
        return jsonify({"error": "Missing container_id"}), 400

    if link_body is None:
        return jsonify({"error": "Missing link_body"}), 400

    config_utils.set_external_link_body(container_id, link_body)
    return jsonify({"message": "External Link Body saved"}), 200


# =============================================================================
# EXPOSED CONTAINERS
# =============================================================================


@containers_bp.route("/api/config/exposed_containers")
@containers_bp.route("/api/data/exposed_containers")
def get_exposed_containers():
    """Return the list of exposed containers from config_utils."""
    exposed_containers = config_utils.get_exposed_containers()
    return jsonify(exposed_containers)


@containers_bp.route("/api/config/exposed_containers", methods=["POST"])
@containers_bp.route("/api/data/exposed_containers", methods=["POST"])
def set_exposed_containers():
    """Update the exposed status for a single container."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    container_id = data.get("container_id")
    exposed = data.get("exposed")

    if not container_id:
        return jsonify({"error": "Missing container_id"}), 400

    if exposed is None:
        return jsonify({"error": "Missing exposed status"}), 400

    config_utils.set_exposed_containers(container_id, exposed)
    return jsonify({"message": "Container exposure status updated"}), 200
# =============================================================================
# Other container-related routes could go here
# =============================================================================
@containers_bp.route("/api/containers/uptime/<container_id>", methods=["GET"])
def get_container_uptime(container_id):
    """Return the uptime of a specific container."""
    try:
        uptime = docker_utils.get_container_uptime(container_id)
        if uptime is None:
            return jsonify({"error": "Container not found"}), 404
        return jsonify({"uptime": uptime}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    