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
@app.route("/api/containers/ports/<container_id>")
def container_ports(container_id):
    return jsonify(docker_utils.get_container_ports(container_id))
@app.route("/api/config")
def get_config():
    return jsonify({
        "internal_ip": INTERNAL_IP,
        "external_ip": EXTERNAL_IP
    })
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
    data = request.json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    
    container_id = data.get("container_id")
    link_body = data.get("link_body")

    if not container_id or not link_body:
        return jsonify({"error": "Missing data"}), 400
    
    config_utils.set_link_body(container_id,link_body)
    return jsonify({"message": "Link Body saved"}), 200
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