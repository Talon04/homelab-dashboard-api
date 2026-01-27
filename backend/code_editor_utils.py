# =============================================================================
# CODE EDITOR UTILS - File system helpers for embedded code editor
# =============================================================================
"""
Helper utilities for the built-in code editor.

All paths handled here are relative to ``CODE_DIR`` and are validated
through :func:`_safe_path` so that callers cannot escape the user_code
directory via ``..`` or absolute paths.
"""

import os
from typing import Dict, Any, List, Optional

from backend.paths import CODE_DIR


# =============================================================================
# PATH VALIDATION
# =============================================================================

# Normalize base directory to match normalized joined paths in _safe_path
ALLOWED_BASE = os.path.normpath(CODE_DIR)


def _safe_path(rel_path: str) -> str:
    """Resolve a relative path under ``CODE_DIR`` and validate it.

    Raises ``ValueError`` if the resulting path would escape the
    configured user_code directory.
    """

    rel_path = rel_path or ""
    joined = os.path.normpath(os.path.join(CODE_DIR, rel_path))
    if not joined.startswith(ALLOWED_BASE):
        raise ValueError("Invalid path")
    return joined


# =============================================================================
# DIRECTORY OPERATIONS
# =============================================================================


def list_tree(rel_path: str = "") -> Dict[str, Any]:
    """Return a simple directory tree rooted at ``rel_path``.

    The result contains ``dirs`` and ``files`` entries with names and
    paths relative to ``CODE_DIR``.
    """

    base = _safe_path(rel_path)
    tree = {"path": rel_path or "", "dirs": [], "files": []}
    try:
        for name in sorted(os.listdir(base)):
            full = os.path.join(base, name)
            rel = os.path.relpath(full, CODE_DIR)
            if os.path.isdir(full):
                tree["dirs"].append({"name": name, "path": rel})
            else:
                tree["files"].append({"name": name, "path": rel})
    except FileNotFoundError:
        pass
    return tree


# =============================================================================
# FILE OPERATIONS
# =============================================================================


def read_file(rel_path: str) -> Dict[str, Any]:
    """Read a text file below ``CODE_DIR`` and return its content."""

    full = _safe_path(rel_path)
    if not os.path.exists(full) or not os.path.isfile(full):
        raise FileNotFoundError("File not found")
    with open(full, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    return {"path": rel_path, "content": content}


def write_file(rel_path: str, content: str) -> Dict[str, Any]:
    """Write ``content`` to the given relative path under ``CODE_DIR``."""

    full = _safe_path(rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content or "")
    return {"path": rel_path, "ok": True}


def delete_path(rel_path: str) -> Dict[str, Any]:
    """Delete a file or (empty) directory under ``CODE_DIR``.

    Directories are only removed if they are empty to keep accidental
    data loss surface small.
    """

    full = _safe_path(rel_path)
    if os.path.isdir(full):
        # Only allow deletion of empty directories for safety
        try:
            os.rmdir(full)
        except OSError:
            return {"path": rel_path, "ok": False, "error": "Directory not empty"}
        return {"path": rel_path, "ok": True}
    if os.path.exists(full):
        os.remove(full)
        return {"path": rel_path, "ok": True}
    return {"path": rel_path, "ok": False, "error": "Path not found"}


# =============================================================================
# WIDGET SCAFFOLDING
# =============================================================================


def ensure_scaffold(rel_path: str, widget_type: Optional[str] = None) -> Dict[str, Any]:
    """Create a reasonable default script file if it does not exist.

    For ``.py`` files this writes a Python template that accepts the
    widget context via ``sys.argv[1]``. For ``.js`` files it writes a
    small IIFE that logs the provided context.
    """

    full = _safe_path(rel_path)
    if os.path.exists(full):
        return {"path": rel_path, "ok": True, "created": False}
    os.makedirs(os.path.dirname(full), exist_ok=True)
    content = ""
    # Provide sensible defaults depending on extension
    if rel_path.endswith(".py"):
        content = (
            "#!/usr/bin/env python3\n"
            '"""Widget script for container interaction.\n'
            "\n"
            "Context is passed as first argument (JSON string).\n"
            "The context contains:\n"
            "  - container: Docker container info (id, name, status, ports, labels, etc.)\n"
            "  - widget: Widget configuration (id, type, label, etc.)\n"
            '"""\n'
            "import sys\n"
            "import json\n"
            "\n"
            "# Parse context from first argument\n"
            "ctx = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}\n"
            "container = ctx.get('container', {})\n"
            "widget = ctx.get('widget', {})\n"
            "\n"
            "# Example: Print container info\n"
            "print(f\"Container: {container.get('name', 'unknown')}\")\n"
            "print(f\"Status: {container.get('status', 'unknown')}\")\n"
            "\n"
            "# Example: Execute command in container using docker exec\n"
            "# Uncomment and modify the following code to run commands:\n"
            "#\n"
            "# import docker\n"
            "# client = docker.from_env()\n"
            "# container_id = container.get('id')\n"
            "# if container_id:\n"
            "#     try:\n"
            "#         cont = client.containers.get(container_id)\n"
            "#         # Execute a command (e.g., check disk usage)\n"
            "#         result = cont.exec_run('df -h')\n"
            "#         print(result.output.decode('utf-8'))\n"
            "#     except Exception as e:\n"
            '#         print(f"Error: {e}")\n'
            "\n"
            "# Example: Get container stats\n"
            "# import docker\n"
            "# client = docker.from_env()\n"
            "# container_id = container.get('id')\n"
            "# if container_id:\n"
            "#     try:\n"
            "#         cont = client.containers.get(container_id)\n"
            "#         stats = cont.stats(stream=False)\n"
            "#         # Process stats here\n"
            "#         print(json.dumps(stats, indent=2))\n"
            "#     except Exception as e:\n"
            '#         print(f"Error: {e}")\n'
            "\n"
            "# For text widgets: print output to stdout\n"
            "# The output will be captured and displayed in the widget\n"
            'print("Widget executed successfully!")\n'
        )
    elif rel_path.endswith(".js"):
        content = (
            "// Widget script template\n"
            "// This will be executed in browser via new Function('context','api', code)\n"
            "// context.container contains the Docker container info\n"
            "// api provides helper functions specific to widget type\n"
            "(function(context, api){\n"
            "  console.log('Hello from JS widget script', context);\n"
            "  // For text widgets, you can call api.setText('New text');\n"
            "})(context, api);\n"
        )
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    return {"path": rel_path, "ok": True, "created": True}
