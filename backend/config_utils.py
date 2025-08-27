import json
import os
import docker_utils

config_path = "config/config.json"
default_ip = "127.0.0.1"


def guess_preferred_port(container_id):
    ports = docker_utils.get_container_ports(container_id)
    # List of common web ports, in order of preference
    web_ports = ["80", "8080", "443", "8000", "5000", "3000"]
    for wp in web_ports:
        for p in ports:
            # Match both tcp and udp, but prefer tcp
            if p["container_port"].startswith(wp + "/tcp"):
                return p["host_port"]
    # Fallback to first port if available
    if ports and isinstance(ports, list) and len(ports) > 0:
        return ports[0].get("host_port", "default_port")
    return "null"

def tryGenerateConfig():
    preferred_ports = tryGeneratePrefferedPorts()
    internal_link_bodies = tryGenerateInternalLinkBodies()
    if not os.path.exists(config_path):
        default_config = {
            "preferred_ports": {},
            "internal_link_bodies": {},  # Make sure this key matches what's used elsewhere
            "exposed_containers": [],
            "proxy_count": 0,  # Number of proxies (0 = no proxy)
            "internal_ip": default_ip,
            "external_ip": default_ip
        }
        with open(config_path, 'w') as config_file:
            json.dump(default_config, config_file, indent=4)
        print(f"Default configuration created at {config_path}")
    else:
        print(f"Configuration file already exists at {config_path}")

def tryGeneratePrefferedPorts():
    containers = docker_utils.list_containers()
    preferred_ports = {}
    for container in containers:
        container_id = container.get("id")
        ports = docker_utils.get_container_ports(container_id)
        if ports and isinstance(ports, list) and len(ports) > 0:
            port = ports[0].get("host_port")
        else:
            port = "default_port"
        preferred_ports[container_id] = port
    return preferred_ports
def tryGenerateInternalLinkBodies():
    containers = docker_utils.list_containers()
    link_bodies = {}
    for container in containers:
        container_id = container.get("id")
        networks = container.get("NetworkSettings", {}).get("Networks", {})
        if "mclan" in networks:
            # Example: mclan network
            ip = networks["mclan"].get("IPAddress", "unknown")
            link_body = "http://{ip}"
        else:
            link_body = "http://{default_ip}"
        link_bodies[container_id] = link_body
    return link_bodies

def get_preferred_port(container_id):
    with open(config_path) as config_file:
        config = json.load(config_file)
    port = config["preferred_ports"].get(container_id)
    if port is None or port == "default_port":
        # Try to guess and set a preferred port
        port = guess_preferred_port(container_id)
        set_preferred_port(container_id, port)
    return port

def set_preferred_port(container_id, port):
    with open(config_path) as config_file:
        config = json.load(config_file)
        config["preferred_ports"][container_id] = port
    with open(config_path, 'w') as config_file:
        json.dump(config, config_file, indent=4)
    print(f"Preferred port for {container_id} set to {port}")    

def get_link_body(container_id):
    with open(config_path) as config_file:
        config = json.load(config_file)
        return config["internal_link_bodies"].get(container_id, "default_port")
    
def set_link_body(container_id, link_body):
    with open(config_path) as config_file:
        config = json.load(config_file)
        config["internal_link_bodies"][container_id] = link_body
    with open(config_path, 'w') as config_file:
        json.dump(config, config_file, indent=4)
    print(f"Link Body for {container_id} set to {link_body}")

def get_exposed_containers():
    with open(config_path) as config_file:
        config = json.load(config_file)
        return config["exposed_containers"]
def set_exposed_containers(container, exposed):
    with open(config_path) as config_file:
        config = json.load(config_file)
        if exposed:
            if container not in config["exposed_containers"]:
                config["exposed_containers"].append(container)
        else:
            if container in config["exposed_containers"]:
                config["exposed_containers"].remove(container)
    with open(config_path, 'w') as config_file:
        json.dump(config, config_file, indent=4)
    print(f"Exposed containers updated: {config['exposed_containers']}")

def get_proxy_count():
    with open(config_path) as config_file:
        config = json.load(config_file)
        return config.get("proxy_count", 0)

def set_proxy_count(proxy_count):
    with open(config_path) as config_file:
        config = json.load(config_file)
        config["proxy_count"] = int(proxy_count)
    with open(config_path, 'w') as config_file:
        json.dump(config, config_file, indent=4)
    print(f"Proxy count set to {proxy_count}")

def get_internal_ip():
    with open(config_path) as config_file:
        config = json.load(config_file)
        return config.get("internal_ip", "127.0.0.1")

def set_internal_ip(ip):
    with open(config_path) as config_file:
        config = json.load(config_file)
        config["internal_ip"] = ip
    with open(config_path, 'w') as config_file:
        json.dump(config, config_file, indent=4)
    print(f"Internal IP set to {ip}")

def get_external_ip():
    with open(config_path) as config_file:
        config = json.load(config_file)
        return config.get("external_ip", "127.0.0.1")

def set_external_ip(ip):
    with open(config_path) as config_file:
        config = json.load(config_file)
        config["external_ip"] = ip
    with open(config_path, 'w') as config_file:
        json.dump(config, config_file, indent=4)
    print(f"External IP set to {ip}")