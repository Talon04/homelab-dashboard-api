import os
from flask import Flask, render_template, jsonify, request
import config_utils
import docker_utils
app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
config_utils.tryGenerateConfig()

INTERNAL_IP = os.getenv("INTERNAL_IP", "127.0.0.1")
EXTERNAL_IP = os.getenv("EXTERNAL_IP", "127.0.0.1")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/containers")
def containers():
    return jsonify(docker_utils.list_containers())
@app.route("/api/containers/ports/<container_name>")
def container_ports(container_name):
    return jsonify(docker_utils.get_container_ports(container_name))
@app.route("/api/config")
def get_config():
    return jsonify({
        "internal_ip": INTERNAL_IP,
        "external_ip": EXTERNAL_IP
    })
@app.route("/api/config/preferred_ports/<container_name>")
def get_preferred_port(container_name):
    port = config_utils.get_preferred_port(container_name)
    return jsonify({"preferred_port": port})
@app.route("/api/config/preferred_ports", methods=["POST"])
def set_preferred_port():
    data = request.get_json()
    container_name = data.get("container_name")
    port = data.get("port")

    if not container_name or not port:
        return jsonify({"error": "Missing data"}), 400

    config_utils.set_preferred_port(container_name, port)
    return jsonify({"message": "Port saved"}), 200