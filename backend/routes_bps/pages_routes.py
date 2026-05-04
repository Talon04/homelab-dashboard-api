# =============================================================================
# PAGES ROUTES - HTML page rendering endpoints
# =============================================================================
"""Flask routes for rendering HTML pages via Jinja2 templates."""

from flask import Blueprint, render_template


# =============================================================================
# BLUEPRINT REGISTRATION
# =============================================================================

pages_bp = Blueprint("pages", __name__)


# =============================================================================
# PAGE ROUTES
# =============================================================================


@pages_bp.route("/")
def index():
    return render_template("services.html")


@pages_bp.route("/services")
def services_page():
    return render_template("services.html")


@pages_bp.route("/settings")
def settings():
    return render_template("settings.html")


@pages_bp.route("/containers")
def containers_page():
    return render_template("containers.html")


@pages_bp.route("/code")
def code_editor_page():
    return render_template("code_editor.html")


@pages_bp.route("/dns-reverse-proxy")
def dns_reverse_proxy_page():
    return render_template("dns_reverse_proxy.html")
