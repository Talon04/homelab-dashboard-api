import os
from flask import Flask, render_template, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix
import config_utils
import docker_utils
from log_parser import BackupLogParser, SmartDataParser

app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')

config_utils.tryGenerateConfig()

# Configure proxy fix based on config
proxy_count = config_utils.get_proxy_count()
if proxy_count > 0:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxy_count, x_proto=proxy_count, x_host=proxy_count, x_prefix=proxy_count)

@app.route("/")
def index():
    # Check if this is the first boot
    if config_utils.get_first_boot():
        from flask import redirect, url_for
        return redirect(url_for('settings'))
    return render_template("index.html")

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/backup")
def backup():
    # Check if backup view is enabled
    if not config_utils.get_backup_view_enabled():
        from flask import redirect, url_for
        return redirect(url_for('settings'))
    return render_template("backup.html")

@app.route("/api/containers")
def containers():
    return jsonify(docker_utils.list_containers())
@app.route("/api/containers/ports/<container_id>")
def container_ports(container_id):
    return jsonify(docker_utils.get_container_ports(container_id))
@app.route("/api/config/preferred_ports/<container_id>")
def get_preferred_port(container_id):
    port = config_utils.get_preferred_port(container_id)
    return jsonify({"preferred_port": port})
@app.route("/api/config/preferred_ports", methods=["POST"])
def set_preferred_port():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    container_id = data.get("container_id")
    port = data.get("port")

    if not container_id or not port:
        return jsonify({"error": "Missing data"}), 400


    config_utils.set_preferred_port(container_id, port)
    return jsonify({"message": "Port saved"}), 200
@app.route("/api/config/link_bodies/<container_id>")
def get_link_body(container_id):
    link_body = config_utils.get_link_body(container_id)
    return jsonify(link_body)

@app.route("/api/config/link_bodies", methods = ["POST"])
def set_link_body():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    
    container_id = data.get("container_id")
    link_body = data.get("link_body")

    if not container_id or not link_body:
        return jsonify({"error": "Missing data"}), 400
    
    config_utils.set_link_body(container_id,link_body)
    return jsonify({"message": "Internal Link Body saved"}), 200

@app.route("/api/config/external_link_bodies/<container_id>")
def get_external_link_body(container_id):
    link_body = config_utils.get_external_link_body(container_id)
    return jsonify(link_body)

@app.route("/api/config/external_link_bodies", methods = ["POST"])
def set_external_link_body():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    
    container_id = data.get("container_id")
    link_body = data.get("link_body")

    if not container_id or not link_body:
        return jsonify({"error": "Missing data"}), 400
    
    config_utils.set_external_link_body(container_id, link_body)
    return jsonify({"message": "External Link Body saved"}), 200
@app.route("/api/config/exposed_containers")
def get_exposed_containers():
    exposed_containers = config_utils.get_exposed_containers()
    return jsonify(exposed_containers)
@app.route("/api/config/exposed_containers", methods=["POST"])
def set_exposed_containers():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    container = data.get("container_id")
    exposed = data.get("exposed")

    if not container or exposed is None:
        return jsonify({"error": "Missing data"}), 400

    config_utils.set_exposed_containers(container, exposed)
    return jsonify({"message": "Exposed containers updated"}), 200

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

@app.route("/api/config/backup_view_enabled")
def get_backup_view_enabled():
    enabled = config_utils.get_backup_view_enabled()
    return jsonify({"backup_view_enabled": enabled})

@app.route("/api/config/backup_view_enabled", methods=["POST"])
def set_backup_view_enabled():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    enabled = data.get("backup_view_enabled")

    if enabled is None:
        return jsonify({"error": "Missing backup_view_enabled"}), 400

    config_utils.set_backup_view_enabled(enabled)
    return jsonify({"message": "Backup view enabled flag updated"}), 200

@app.route("/api/config/backup_config")
def get_backup_config():
    backup_config = config_utils.get_backup_config()
    return jsonify({"backup_config": backup_config})

@app.route("/api/config/backup_config", methods=["POST"])
def set_backup_config():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    backup_config = data.get("backup_config")

    if backup_config is None:
        return jsonify({"error": "Missing backup_config"}), 400

    config_utils.set_backup_config(backup_config)
    return jsonify({"message": "Backup configuration updated"}), 200

# Backup data endpoints
@app.route("/api/backup/summary")
def get_backup_summary():
    """Get backup summary statistics"""
    try:
        parser = BackupLogParser()
        summary = parser.get_backup_summary()
        return jsonify(summary)
    except Exception as e:
        import traceback
        print(f"Error getting backup summary: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "error": "Failed to get backup summary",
            "details": str(e),
            "total_backups": 0,
            "status": "error"
        }), 500

@app.route("/api/backup/logs")
def get_backup_logs():
    """Get all backup logs"""
    try:
        parser = BackupLogParser()
        logs = parser.parse_logs()
        return jsonify({"backups": logs})
    except Exception as e:
        print(f"Error getting backup logs: {e}")
        return jsonify({"error": "Failed to get backup logs"}), 500

@app.route("/api/backup/latest")
def get_latest_backup():
    """Get the latest backup information"""
    try:
        parser = BackupLogParser()
        latest = parser.get_latest_backup()
        if latest:
            return jsonify(latest)
        else:
            return jsonify({"message": "No backup data found"}), 404
    except Exception as e:
        print(f"Error getting latest backup: {e}")
        return jsonify({"error": "Failed to get latest backup"}), 500

# SMART data endpoints
@app.route("/api/smart/summary")
def get_smart_summary():
    """Get SMART data summary"""
    try:
        parser = SmartDataParser()
        summary = parser.get_drive_summary()
        return jsonify(summary)
    except Exception as e:
        print(f"Error getting SMART summary: {e}")
        return jsonify({"error": "Failed to get SMART data summary"}), 500

@app.route("/api/smart/drives")
def get_smart_drives():
    """Get all drive SMART data"""
    try:
        parser = SmartDataParser()
        drives = parser.parse_logs()
        return jsonify({"drives": drives})
    except Exception as e:
        print(f"Error getting SMART drives data: {e}")
        return jsonify({"error": "Failed to get SMART drives data"}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")