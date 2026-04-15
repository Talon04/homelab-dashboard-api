"""
Logging utility for caddy-manager agent.
Follows the same schema as the dashboard: [MODULE_NAME] message
"""

import sys


def info(module: str, msg: str):
    """Log info message."""
    print(f"[{module}] {msg}", flush=True)
    sys.stdout.flush()


def debug(module: str, msg: str):
    """Log debug message."""
    print(f"DEBUG [{module}] {msg}", flush=True)
    sys.stdout.flush()


def error(module: str, msg: str):
    """Log error message."""
    print(f"ERROR [{module}] {msg}", flush=True)
    sys.stdout.flush()


def warn(module: str, msg: str):
    """Log warning message."""
    print(f"WARN [{module}] {msg}", flush=True)
    sys.stdout.flush()


