"""Flask routes backing the embedded code editor UI."""

import sys

from flask import Blueprint, jsonify, request

import backend.code_editor_utils as code_editor_utils


code_bp = Blueprint("code", __name__)


@code_bp.route("/api/code/tree")
def api_code_tree():
    """Return a directory tree rooted at the optional ``path`` query."""

    path = request.args.get("path", "")
    try:
        return jsonify(code_editor_utils.list_tree(path))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@code_bp.route("/api/code/file")
def api_code_read_file():
    """Return the contents of a file specified by ``path`` query."""

    path = request.args.get("path")
    if not path:
        return jsonify({"error": "Missing path"}), 400
    try:
        return jsonify(code_editor_utils.read_file(path))
    except FileNotFoundError:
        return jsonify({"error": "Not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@code_bp.route("/api/code/file", methods=["POST"])
def api_code_write_file():
    """Create or overwrite a file with the provided ``content``."""

    data = request.get_json() or {}
    path = data.get("path")
    content = data.get("content", "")
    if not path:
        return jsonify({"error": "Missing path"}), 400
    try:
        return jsonify(code_editor_utils.write_file(path, content))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@code_bp.route("/api/code/file", methods=["DELETE"])
def api_code_delete_path():
    """Delete a file or empty directory specified by ``path`` query."""

    path = request.args.get("path")
    if not path:
        return jsonify({"error": "Missing path"}), 400
    try:
        result = code_editor_utils.delete_path(path)
        status = 200 if result.get("ok") else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@code_bp.route("/api/code/run", methods=["POST"])
def api_code_run():
    """Execute a Python file inside user_code and return its output."""

    data = request.get_json() or {}
    path = data.get("path")
    args = data.get("args", [])
    if not path:
        return jsonify({"error": "Missing path"}), 400
    try:
        full_path = code_editor_utils._safe_path(path)
        if not full_path.endswith(".py"):
            return jsonify({"error": "Only .py files can be executed on server"}), 400
        import subprocess

        cmd = [sys.executable or "python", full_path] + [
            str(a) for a in (args if isinstance(args, list) else [])
        ]
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        out, err = proc.communicate(timeout=60)
        return jsonify({"stdout": out, "stderr": err, "code": proc.returncode})
    except Exception as e:
        try:
            import subprocess as _sp

            if isinstance(e, _sp.TimeoutExpired):
                return jsonify({"error": "Execution timed out"}), 408
        except Exception:
            pass
        return jsonify({"error": str(e)}), 400
