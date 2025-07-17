import os
from flask import Flask, render_template, jsonify
import docker_utils
app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')

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