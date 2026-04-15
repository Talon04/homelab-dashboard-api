"""
Logging utility for caddy-manager agent using Python's logging module.
Follows the same schema as the dashboard: [MODULE_NAME] message
Outputs to stdout which is captured by systemd.
"""

import logging
import sys

# Create logger
_logger = logging.getLogger("caddy-manager")
_logger.setLevel(logging.DEBUG)

# Create console handler with stdout
_handler = logging.StreamHandler(sys.stdout)
_handler.setLevel(logging.DEBUG)

# Create formatter
_formatter = logging.Formatter("%(message)s")
_handler.setFormatter(_formatter)

# Add handler to logger
_logger.addHandler(_handler)


def info(module: str, msg: str):
    """Log info message."""
    _logger.info(f"[{module}] {msg}")


def debug(module: str, msg: str):
    """Log debug message."""
    _logger.debug(f"DEBUG [{module}] {msg}")


def error(module: str, msg: str):
    """Log error message."""
    _logger.error(f"ERROR [{module}] {msg}")


def warn(module: str, msg: str):
    """Log warning message."""
    _logger.warning(f"WARN [{module}] {msg}")

