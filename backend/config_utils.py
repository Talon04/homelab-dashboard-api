import json
import os
import docker_utils
from config_manager import config_manager

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
    # Config manager handles initialization automatically
    print(f"Configuration loaded at {config_path}")

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
    port = config_manager.get_nested("preferred_ports", container_id)
    if port is None or port == "default_port":
        # Try to guess and set a preferred port
        port = guess_preferred_port(container_id)
        set_preferred_port(container_id, port)
    return port

def set_preferred_port(container_id, port):
    config_manager.set_nested("preferred_ports", container_id, port)
    print(f"Preferred port for {container_id} set to {port}")

def get_link_body(container_id):
    # Get the internal_link_bodies object first
    link_bodies = config_manager.get("internal_link_bodies", {})
    
    # Get the specific container's link, return None if not found
    result = link_bodies.get(container_id)
    
    print(f"DEBUG: get_link_body({container_id}) -> {result}")
    return result
    
def set_link_body(container_id, link_body):
    config_manager.set_nested("internal_link_bodies", container_id, link_body)
    print(f"Internal Link Body for {container_id} set to {link_body}")

def get_external_link_body(container_id):
    # Get the external_link_bodies object first
    link_bodies = config_manager.get("external_link_bodies", {})
    
    # Get the specific container's link, return None if not found
    result = link_bodies.get(container_id)
    
    print(f"DEBUG: get_external_link_body({container_id}) -> {result}")
    return result
    
def set_external_link_body(container_id, link_body):
    config_manager.set_nested("external_link_bodies", container_id, link_body)
    print(f"External Link Body for {container_id} set to {link_body}")

def get_exposed_containers():
    return config_manager.get("exposed_containers", [])

def set_exposed_containers(container, exposed):
    exposed_containers = config_manager.get("exposed_containers", [])
    if exposed:
        if container not in exposed_containers:
            exposed_containers.append(container)
    else:
        if container in exposed_containers:
            exposed_containers.remove(container)
    config_manager.set("exposed_containers", exposed_containers)
    print(f"Exposed containers updated: {exposed_containers}")

def get_proxy_count():
    return config_manager.get("proxy_count", 0)

def set_proxy_count(proxy_count):
    config_manager.set("proxy_count", int(proxy_count))
    print(f"Proxy count set to {proxy_count}")

def get_internal_ip():
    return config_manager.get("internal_ip", "127.0.0.1")

def set_internal_ip(ip):
    config_manager.set("internal_ip", ip)
    print(f"Internal IP set to {ip}")

def get_external_ip():
    return config_manager.get("external_ip", "127.0.0.1")

def set_external_ip(ip):
    config_manager.set("external_ip", ip)
    print(f"External IP set to {ip}")

def get_first_boot():
    return config_manager.get("first_boot", False)

def set_first_boot(is_first_boot):
    config_manager.set("first_boot", is_first_boot)
    print(f"First boot flag set to {is_first_boot}")