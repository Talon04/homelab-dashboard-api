import os
import sys
from flask import Flask, render_template, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix

import config_utils
import docker_utils
import code_editor_utils
from save_manager import get_save_manager


app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')

# Configure proxy fix based on config
proxy_count = config_utils.get_proxy_count()
if proxy_count > 0:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxy_count, x_proto=proxy_count, x_host=proxy_count, x_prefix=proxy_count)


@app.route("/")
def index():
    return render_template("settings.html")

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/containers")
def containers_page():
    # Gate access based on enabled modules
    modules = config_utils.get_enabled_modules()
    if not modules or "containers" not in modules:
        from flask import redirect, url_for
        return redirect(url_for('settings'))
    return render_template("containers.html")

@app.route("/api/containers")
@app.route("/api/data/containers")
def containers():
    return jsonify(docker_utils.list_containers())

# Widgets APIs for containers
@app.route("/api/containers/<container_id>/widgets")
def get_container_widgets(container_id):
    sm = get_save_manager()
    return jsonify(sm.get_widgets(container_id))

@app.route("/api/containers/<container_id>/widgets", methods=["POST"]) 
def add_container_widget(container_id):
    sm = get_save_manager()
    data = request.get_json() or {}
    w = sm.add_widget(container_id, data)
    if not w:
        return jsonify({"error": "Failed to add widget"}), 400
    # Optional: scaffold default file if requested
    fp = w.get('file_path')
    if fp:
        try:
            code_editor_utils.ensure_scaffold(fp, w.get('type'))
        except Exception:
            pass
    return jsonify(w)

@app.route("/api/containers/<container_id>/widgets/<int:widget_id>", methods=["PUT"]) 
def update_container_widget(container_id, widget_id):
    sm = get_save_manager()
    data = request.get_json() or {}
    ok = sm.update_widget(container_id, widget_id, data)
    return (jsonify({"ok": True}) if ok else (jsonify({"error": "Not found"}), 404))

@app.route("/api/containers/<container_id>/widgets/<int:widget_id>", methods=["DELETE"]) 
def delete_container_widget(container_id, widget_id):
    sm = get_save_manager()
    ok = sm.delete_widget(container_id, widget_id)
    return (jsonify({"ok": True}) if ok else (jsonify({"error": "Not found"}), 404))

@app.route("/api/containers/<container_id>/widgets/<int:widget_id>/run", methods=["POST"]) 
def run_container_widget(container_id, widget_id):
    sm = get_save_manager()
    # Find widget to get file path and type
    widgets = sm.get_widgets(container_id)
    widget = next((w for w in widgets if w.get('id') == widget_id), None)
    if not widget or not widget.get('file_path'):
        return jsonify({"error": "Widget or file not found"}), 404
    # Build context: include container info from docker_utils
    try:
        containers = docker_utils.list_containers()
        ctx_container = next((c for c in containers if c.get('id') == container_id), None)
    except Exception:
        ctx_container = None
    context = {
        "container": ctx_container,
        "widget": widget
    }
    path = widget.get('file_path')
    if isinstance(path, str) and path.endswith('.py'):
        # Run server-side python with context JSON passed via args
        # Call run endpoint internally via function to avoid HTTP roundtrip
        try:
            import json as _json
            data = { 'path': path, 'args': [_json.dumps(context)] }
            with app.test_request_context('/api/code/run', method='POST', json=data):
                resp = api_code_run()
            return resp
        except Exception as e:
            return jsonify({"error": str(e)}), 400
    else:
        # For JS, client should fetch and execute with provided context
        return jsonify({"message": "Client-run JS", "context": context, "path": path})
@app.route("/api/containers/ports/<container_id>")
@app.route("/api/data/containers/ports/<container_id>")
def container_ports(container_id):
    return jsonify(docker_utils.get_container_ports(container_id))
@app.route("/api/config/preferred_ports/<container_id>")
@app.route("/api/data/preferred_ports/<container_id>")
def get_preferred_port(container_id):
    port = config_utils.get_preferred_port(container_id)
    return jsonify({"preferred_port": port})
@app.route("/api/config/preferred_ports", methods=["POST"])
@app.route("/api/data/preferred_ports", methods=["POST"])
def set_preferred_port():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    container_id = data.get("container_id")
    port = data.get("port")

    if not container_id:
        return jsonify({"error": "Missing container_id"}), 400
    
    if not port:
        return jsonify({"error": "Missing port"}), 400

    config_utils.set_preferred_port(container_id, port)
    return jsonify({"message": "Preferred port saved"}), 200
@app.route("/api/config/link_bodies/<container_id>")
@app.route("/api/data/link_bodies/<container_id>")
def get_link_body(container_id):
    link_body = config_utils.get_link_body(container_id)
    return jsonify(link_body)

@app.route("/api/config/link_bodies", methods=["POST"])
@app.route("/api/data/link_bodies", methods=["POST"])
def set_link_body():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    
    container_id = data.get("container_id")
    link_body = data.get("link_body")

    if not container_id:
        return jsonify({"error": "Missing container_id"}), 400
    
    if link_body is None:
        return jsonify({"error": "Missing link_body"}), 400
    
    config_utils.set_link_body(container_id, link_body)
    return jsonify({"message": "Internal Link Body saved"}), 200

@app.route("/api/config/external_link_bodies/<container_id>")
@app.route("/api/data/external_link_bodies/<container_id>")
def get_external_link_body(container_id):
    link_body = config_utils.get_external_link_body(container_id)
    return jsonify(link_body)

@app.route("/api/config/external_link_bodies", methods=["POST"])
@app.route("/api/data/external_link_bodies", methods=["POST"])
def set_external_link_body():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    
    container_id = data.get("container_id")
    link_body = data.get("link_body")

    if not container_id:
        return jsonify({"error": "Missing container_id"}), 400
    
    if link_body is None:
        return jsonify({"error": "Missing link_body"}), 400
    
    config_utils.set_external_link_body(container_id, link_body)
    return jsonify({"message": "External Link Body saved"}), 200
@app.route("/api/config/exposed_containers")
@app.route("/api/data/exposed_containers")
def get_exposed_containers():
    exposed_containers = config_utils.get_exposed_containers()
    return jsonify(exposed_containers)
@app.route("/api/config/exposed_containers", methods=["POST"])
@app.route("/api/data/exposed_containers", methods=["POST"])
def set_exposed_containers():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    container_id = data.get("container_id")
    exposed = data.get("exposed")

    if not container_id:
        return jsonify({"error": "Missing container_id"}), 400
    
    if exposed is None:
        return jsonify({"error": "Missing exposed status"}), 400

    config_utils.set_exposed_containers(container_id, exposed)
    return jsonify({"message": "Container exposure status updated"}), 200

@app.route("/api/config/proxy_count")
def get_proxy_count():
    proxy_count = config_utils.get_proxy_count()
    return jsonify({"proxy_count": proxy_count})

@app.route("/api/config/proxy_count", methods=["POST"])
def set_proxy_count():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    proxy_count = data.get("proxy_count")

    if proxy_count is None:
        return jsonify({"error": "Missing proxy_count"}), 400

    try:
        proxy_count = int(proxy_count)
        if proxy_count < 0:
            return jsonify({"error": "Proxy count must be non-negative"}), 400
    except ValueError:
        return jsonify({"error": "Proxy count must be a valid integer"}), 400

    config_utils.set_proxy_count(proxy_count)
    return jsonify({"message": "Proxy count updated"}), 200

@app.route("/api/config/internal_ip")
def get_internal_ip():
    internal_ip = config_utils.get_internal_ip()
    return jsonify({"internal_ip": internal_ip})

@app.route("/api/config/internal_ip", methods=["POST"])
def set_internal_ip():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    internal_ip = data.get("internal_ip")

    if not internal_ip:
        return jsonify({"error": "Missing internal_ip"}), 400

    config_utils.set_internal_ip(internal_ip)
    return jsonify({"message": "Internal IP updated"}), 200

@app.route("/api/config/external_ip")
def get_external_ip():
    external_ip = config_utils.get_external_ip()
    return jsonify({"external_ip": external_ip})

@app.route("/api/config/external_ip", methods=["POST"])
def set_external_ip():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    external_ip = data.get("external_ip")

    if not external_ip:
        return jsonify({"error": "Missing external_ip"}), 400

    config_utils.set_external_ip(external_ip)
    return jsonify({"message": "External IP updated"}), 200

@app.route("/api/config/first_boot")
def get_first_boot():
    first_boot = config_utils.get_first_boot()
    return jsonify({"first_boot": first_boot})

@app.route("/api/config/first_boot", methods=["POST"])
def set_first_boot():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    first_boot = data.get("first_boot")

    if first_boot is None:
        return jsonify({"error": "Missing first_boot"}), 400

    config_utils.set_first_boot(first_boot)
    return jsonify({"message": "First boot flag updated"}), 200

@app.route("/api/config/modules")
def get_modules():
    modules = config_utils.get_enabled_modules()
    return jsonify({"modules": modules})

@app.route("/api/config/modules", methods=["POST"])
def set_modules():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    modules = data.get("modules")
    if modules is None or not isinstance(modules, list):
        return jsonify({"error": "Missing or invalid modules (expected list)"}), 400

    config_utils.set_enabled_modules(modules)
    return jsonify({"message": "Modules updated"}), 200

@app.route("/api/config/modules_order")
def get_modules_order():
    order = config_utils.get_modules_order()
    return jsonify({"order": order})

@app.route("/api/config/modules_order", methods=["POST"])
def set_modules_order():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    order = data.get("order")
    if order is None or not isinstance(order, list):
        return jsonify({"error": "Missing or invalid order (expected list)"}), 400
    config_utils.set_modules_order(order)
    return jsonify({"message": "Modules order updated"}), 200

@app.route("/api/config/module/<module_id>")
def get_module_config(module_id):
    data = config_utils.get_module_config(module_id)
    return jsonify(data)

@app.route("/api/config/module/<module_id>", methods=["POST"])
def set_module_config(module_id):
    data = request.get_json()
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    config_utils.set_module_config(module_id, data)
    return jsonify({"message": f"Module {module_id} config updated"}), 200

@app.route("/proxmox")
def proxmox_page():
    modules = config_utils.get_enabled_modules()
    if not modules or "proxmox" not in modules:
        from flask import redirect, url_for
        return redirect(url_for('settings'))
    return render_template("proxmox.html")

@app.route("/code")
def code_editor_page():
    modules = config_utils.get_enabled_modules()
    if not modules or "code_editor" not in modules:
        from flask import redirect, url_for
        return redirect(url_for('settings'))
    return render_template("code_editor.html")

# Code editor APIs
@app.route("/api/code/tree")
def api_code_tree():
    path = request.args.get('path', '')
    try:
        return jsonify(code_editor_utils.list_tree(path))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/code/file")
def api_code_read_file():
    path = request.args.get('path')
    if not path:
        return jsonify({"error": "Missing path"}), 400
    try:
        return jsonify(code_editor_utils.read_file(path))
    except FileNotFoundError:
        return jsonify({"error": "Not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/code/file", methods=["POST"])
def api_code_write_file():
    data = request.get_json() or {}
    path = data.get('path')
    content = data.get('content', '')
    if not path:
        return jsonify({"error": "Missing path"}), 400
    try:
        return jsonify(code_editor_utils.write_file(path, content))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/code/file", methods=["DELETE"])
def api_code_delete_path():
    path = request.args.get('path')
    if not path:
        return jsonify({"error": "Missing path"}), 400
    try:
        result = code_editor_utils.delete_path(path)
        status = 200 if result.get('ok') else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/code/run", methods=["POST"])
def api_code_run():
    data = request.get_json() or {}
    path = data.get('path')
    args = data.get('args', [])
    if not path:
        return jsonify({"error": "Missing path"}), 400
    try:
        full_path = code_editor_utils._safe_path(path)
        if not full_path.endswith('.py'):
            return jsonify({"error": "Only .py files can be executed on server"}), 400
        import subprocess
        cmd = [sys.executable or 'python', full_path] + [str(a) for a in (args if isinstance(args, list) else [])]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")