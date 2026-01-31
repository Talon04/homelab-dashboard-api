"""Flask application entry point.

Initializes the Flask app, registers blueprints, and starts background
services (widget scheduler, monitoring, event delivery).
"""

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

import backend.config_utils
from backend.widget_service import start_widget_scheduler
from backend.monitoring_service import start_monitoring_service
from backend.notification_service import start_notification_service

from backend.routes_bps.pages_routes import pages_bp
from backend.routes_bps.containers_routes import containers_bp
from backend.routes_bps.config_routes import config_bp
from backend.routes_bps.code_routes import code_bp
from backend.routes_bps.monitor_routes import monitor_bp
from backend.routes_bps.event_routes import event_bp
from backend.routes_bps.notification_routes import notification_bp


app = Flask(
    __name__,
    template_folder="frontend/templates",
    static_folder="frontend/static",
)


# =============================================================================
# Background Services
# =============================================================================


def start_background_tasks():
    """Start all background services on app startup."""
    try:
        start_widget_scheduler()
        print("[app] Widget scheduler started")
    except Exception as e:
        print(f"[app] Failed to start widget scheduler: {e}")

    try:
        start_monitoring_service()
        print("[app] Monitoring service started")
    except Exception as e:
        print(f"[app] Failed to start monitoring service: {e}")

    try:
        start_notification_service()
        print("[app] Event delivery service started")
    except Exception as e:
        print(f"[app] Failed to start event delivery service: {e}")


# =============================================================================
# App Configuration
# =============================================================================


# Apply proxy fix for reverse proxy deployments
proxy_count = backend.config_utils.get_proxy_count()
if proxy_count > 0:
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=proxy_count,
        x_proto=proxy_count,
        x_host=proxy_count,
        x_prefix=proxy_count,
    )

start_background_tasks()


# =============================================================================
# Blueprint Registration
# =============================================================================


app.register_blueprint(pages_bp)
app.register_blueprint(containers_bp)
app.register_blueprint(config_bp)
app.register_blueprint(code_bp)
app.register_blueprint(monitor_bp)
app.register_blueprint(event_bp)
app.register_blueprint(notification_bp)
# MOCK_END
