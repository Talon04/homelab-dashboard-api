# =============================================================================
# PAGES ROUTES - HTML page rendering endpoints
# =============================================================================
"""Flask routes for rendering HTML pages via Jinja2 templates."""

from flask import Blueprint, render_template

import backend.config_utils as config_utils


# =============================================================================
# BLUEPRINT REGISTRATION
# =============================================================================

pages_bp = Blueprint("pages", __name__)


# =============================================================================
# PAGE ROUTES
# =============================================================================


@pages_bp.route("/")
def index():
    return render_template("settings.html")


@pages_bp.route("/settings")
def settings():
    return render_template("settings.html")


@pages_bp.route("/containers")
def containers_page():
    """Containers overview page (gated by enabled modules)."""
    modules = config_utils.get_enabled_modules()
    if not modules or "containers" not in modules:
        from flask import redirect, url_for

        return redirect(url_for("pages.settings"))
    return render_template("containers.html")


@pages_bp.route("/proxmox")
def proxmox_page():
    """Proxmox overview page (gated by enabled modules)."""
    modules = config_utils.get_enabled_modules()
    if not modules or "proxmox" not in modules:
        from flask import redirect, url_for

        return redirect(url_for("pages.settings"))
    return render_template("proxmox.html")


@pages_bp.route("/monitor")
def monitor_page():
    """Monitor overview page (gated by enabled modules)."""
    modules = config_utils.get_enabled_modules()
    if not modules or "monitor" not in modules:
        from flask import redirect, url_for

        return redirect(url_for("pages.settings"))
    return render_template("monitor.html")


@pages_bp.route("/code")
def code_editor_page():
    """Code editor page (gated by enabled modules)."""
    modules = config_utils.get_enabled_modules()
    if not modules or "code_editor" not in modules:
        from flask import redirect, url_for

        return redirect(url_for("pages.settings"))
    return render_template("code_editor.html")
