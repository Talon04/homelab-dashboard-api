"""Flask application entry point.

Initializes the Flask app, registers blueprints, and starts background
services (widget scheduler, monitoring, event delivery).
"""

import os
import sys
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from alembic.config import Config
from alembic import command
from sqlalchemy import inspect

import backend.config_utils
from backend.widget_service import start_widget_scheduler
from backend.monitoring_service import start_monitoring_service
from backend.notification_service import start_notification_service
from backend.management_service import start_management_service

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
# Database Initialization
# =============================================================================


def init_database():
    """Initialize database with Alembic migrations.

    Runs migrations on startup. For existing databases without version info,
    stamps them with the initial revision to avoid recreating tables.
    """
    from backend.models import DatabaseManager
    from backend.paths import DATA_DIR

    db_path = os.path.join(DATA_DIR, "data.db")
    db_exists = os.path.exists(db_path)

    # Get Alembic config
    alembic_ini = os.path.join(os.path.dirname(__file__), "alembic.ini")
    alembic_cfg = Config(alembic_ini)

    if db_exists:
        # Check if database has tables but no alembic version
        db_manager = DatabaseManager()
        inspector = inspect(db_manager.engine)
        tables = inspector.get_table_names()
        has_alembic_version = "alembic_version" in tables

        if tables and not has_alembic_version:
            # Existing database without migrations - stamp it with initial revision
            print("[app] Existing database detected without version info")
            print("[app] Stamping database with initial revision")
            command.stamp(alembic_cfg, "head")
        else:
            # Database has version info or is empty - run normal upgrade
            print("[app] Running database migrations")
            command.upgrade(alembic_cfg, "head")
    else:
        # New database - run migrations to create schema
        print("[app] Initializing new database with migrations")
        command.upgrade(alembic_cfg, "head")

    print("[app] Database initialization complete")


# =============================================================================
# Background Services
# =============================================================================


def start_background_tasks():
    """Start all background services on app startup."""
    try:
        start_management_service()
        print("[app] Management service started")
    except Exception as e:
        print(f"[app] Failed to start management service: {e}")

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

# Initialize database (run migrations)
init_database()

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
