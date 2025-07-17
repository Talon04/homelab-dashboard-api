import sys
print("PYTHONPATH:", sys.path)
from flask import Flask, render_template, jsonify
import docker_utils
app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/containers")
def containers():
    return jsonify(docker_utils.list_containers())
@app.route("/api/containers/ports/<container_name>")
def container_ports(container_name):
    return jsonify(docker_utils.get_container_ports(container_name))