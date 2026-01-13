"""Shared filesystem paths used by the backend.

``BASE_DIR`` points at the project root, ``DATA_DIR`` at the persistent
data directory and ``CODE_DIR`` at the user_code folder used by the
embedded code editor.
"""

import os

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA_DIR = os.path.join(BASE_DIR, "data")
CODE_DIR = os.path.join(DATA_DIR, "user_code")
# Create the data and code directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CODE_DIR, exist_ok=True)
