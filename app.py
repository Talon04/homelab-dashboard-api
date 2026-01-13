"""Flask application factory and blueprint wiring for the backend API."""

import os
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

import backend.config_utils
from backend.task_scheduler import start_widget_scheduler

from backend.routes_bps.pages_routes import pages_bp
from backend.routes_bps.containers_routes import containers_bp
from backend.routes_bps.config_routes import config_bp
from backend.routes_bps.code_routes import code_bp
from backend.routes_bps.monitor_routes import monitor_bp

app = Flask(
    __name__,
    template_folder="frontend/templates",
    static_folder="frontend/static",
)


def start_background_tasks():
    """Start background services such as the widget scheduler.

    This runs when the Flask app actually starts serving requests,
    which works both with ``flask run`` and with ``app.run(...)``.
    """
    try:
        start_widget_scheduler()
        print("[app] Widget scheduler started")
    except Exception as e:
        print(f"Warning: failed to start widget scheduler: {e}")


# Configure proxy fix based on config
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


"Blueprints are registered below; all route definitions now live in"
" pages_routes.py, containers_routes.py, config_routes.py,"
" code_routes.py and monitor_routes.py."

app.register_blueprint(pages_bp)
app.register_blueprint(containers_bp)
app.register_blueprint(config_bp)
app.register_blueprint(code_bp)
app.register_blueprint(monitor_bp)
