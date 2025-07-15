from flask import Flask, render_template, jsonify
import docker_utils
app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/containers")
def containers():
    return jsonify(docker_utils.list_containers())