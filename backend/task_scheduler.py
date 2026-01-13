import json
import subprocess
import sys
import time
from typing import Dict, Tuple

import backend.docker_utils as docker_utils
import backend.code_editor_utils as code_editor_utils
from backend.save_manager import get_save_manager


# (container_id, widget_id) -> last run timestamp (time.time())
_last_run: Dict[Tuple[str, int], float] = {}


def _should_run_widget(widget: Dict, now: float) -> bool:
    """Return True if this widget should be executed at ``now``.

    The decision is based on its configured ``update_interval`` and
    the last time it was executed.
    """
    interval = widget.get("update_interval")
    if not isinstance(interval, int) or interval <= 0:
        return False

    path = widget.get("file_path") or ""
    if not isinstance(path, str) or not path.endswith(".py"):
        return False

    key = int(widget.get("id"))
    last = _last_run.get(key)
    if last is None:
        return True
    return (now - last) >= interval


def _run_python_widget(widget: Dict) -> None:
    """Execute the widget's Python script and persist its output.

    This replicates what the frontend used to do with the
    /widgets/<id>/run endpoint + PUT update, but entirely on
    the server side.
    """
    sm = get_save_manager()

    container_id = widget.get("container_id")
    if not container_id:
        print("[task_scheduler] Widget missing container_id; skipping")
        return

    widget_id = int(widget.get("id"))
    path = widget.get("file_path") or ""

    # Build context (matches run_container_widget in app.py)
    try:
        containers_rt = docker_utils.list_containers()
        ctx_container = next(
            (c for c in containers_rt if c.get("id") == container_id), None
        )
    except Exception:
        ctx_container = None

    context = {"container": ctx_container, "widget": widget}

    try:
        full_path = code_editor_utils._safe_path(path)
        cmd = [sys.executable or "python", full_path, json.dumps(context)]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        out, err = proc.communicate(timeout=60)
    except Exception as exc:
        print(
            f"[task_scheduler] Error running widget {widget_id} for {container_id}: {exc}"
        )
        return

    if proc.returncode == 0 and out:
        text_val = out.strip()
        sm.update_widget(container_id, widget_id, {"text": text_val})
        name_for_log = (ctx_container or {}).get("name", container_id)
        print(
            f"[task_scheduler] Updated widget {widget_id} at {full_path} for container {name_for_log}"
        )
    else:
        err_msg = (err or "").strip()
        print(
            f"[task_scheduler] Widget {widget_id} script error for container {container_id}: "
            f"code={proc.returncode}, stderr={err_msg}"
        )


def run_widgets() -> None:
    """Run all eligible widgets whose timers are due.

    Call this periodically (e.g. from a background thread or
    an external scheduler). It is safe to call this function
    frequently; widgets are gated by their ``update_interval``.
    """
    sm = get_save_manager()
    widgets = sm.get_all_widgets()
    now = time.time()

    for widget in widgets:
        if not _should_run_widget(widget, now):
            continue

        key = int(widget.get("id"))
        _last_run[key] = now
        _run_python_widget(widget)


def start_widget_scheduler(poll_interval: float = 1.0) -> None:
    """Start a simple background loop that calls ``run_widgets``.

    This is optional; you can also call ``run_widgets`` from an
    external scheduler (cron, systemd timer, etc.).
    """
    import threading

    def _loop() -> None:
        while True:
            run_widgets()
            time.sleep(poll_interval)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
