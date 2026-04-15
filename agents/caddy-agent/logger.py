"""
Simple logging utility for caddy-manager agent.
Follows the same schema as the dashboard: [MODULE_NAME] message
"""


def info(module: str, msg: str):
    """Log info message."""
    print(f"[{module}] {msg}")


def debug(module: str, msg: str):
    """Log debug message."""
    print(f"DEBUG [{module}] {msg}")


def error(module: str, msg: str):
    """Log error message."""
    print(f"ERROR [{module}] {msg}")


def warn(module: str, msg: str):
    """Log warning message."""
    print(f"WARN [{module}] {msg}")
