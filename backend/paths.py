# =============================================================================
# PATHS - Centralised file-system path definitions
# =============================================================================
"""
Centralised file-system path definitions for the dashboard backend.

``BASE_DIR`` points at the project root, ``DATA_DIR`` at the persistent
data directory and ``CODE_DIR`` at the user_code folder used by the
embedded code editor.

Environment Variables:
- DATA_DIR: Override the default data directory path (useful for testing)
"""

import os


# =============================================================================
# BASE DIRECTORIES
# =============================================================================

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# Check if DATA_DIR is overridden via environment variable (for testing)
DATA_DIR = os.environ.get("DATA_DIR")
if DATA_DIR is None:
    DATA_DIR = os.path.join(BASE_DIR, "data")

CODE_DIR = os.path.join(DATA_DIR, "user_code")


# =============================================================================
# DIRECTORY INITIALISATION
# =============================================================================

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CODE_DIR, exist_ok=True)
