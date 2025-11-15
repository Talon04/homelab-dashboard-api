import json
import os
import docker_utils
from save_manager import get_save_manager
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

def tryGeneratePreferredPorts():
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
    save_manager = get_save_manager()
    port = save_manager.get_preferred_port(container_id)
    if port is None or port == "default_port":
        # Try to guess and set a preferred port
        port = guess_preferred_port(container_id)
        set_preferred_port(container_id, port)
    return port

def set_preferred_port(container_id, port):
    save_manager = get_save_manager()
    save_manager.set_preferred_port(container_id, port)
    print(f"Preferred port for {container_id} set to {port}")

def get_link_body(container_id):
    save_manager = get_save_manager()
    result = save_manager.get_link_body(container_id)
    value = ""
    try:
        if isinstance(result, dict):
            value = result.get("internal_link_body", "")
        elif isinstance(result, str):
            value = result
    except Exception:
        value = ""
    print(f"DEBUG: get_link_body({container_id}) -> {value}")
    return value
    
def set_link_body(container_id, link_body):
    save_manager = get_save_manager()
    save_manager.set_link_body(container_id, link_body)
    print(f"Internal Link Body for {container_id} set to {link_body}")

def get_external_link_body(container_id):
    save_manager = get_save_manager()
    result = save_manager.get_external_link_body(container_id)
    value = ""
    try:
        if isinstance(result, dict):
            value = result.get("external_link_body", "")
        elif isinstance(result, str):
            value = result
    except Exception:
        value = ""
    print(f"DEBUG: get_external_link_body({container_id}) -> {value}")
    return value
    
def set_external_link_body(container_id, link_body):
    save_manager = get_save_manager()
    save_manager.set_external_link_body(container_id, link_body)
    print(f"External Link Body for {container_id} set to {link_body}")

def get_exposed_containers():
    save_manager = get_save_manager()
    return save_manager.get_exposed_containers()

def set_exposed_containers(container, exposed):
    save_manager = get_save_manager()
    save_manager.set_exposed_containers(container, exposed)
    print(f"Exposed containers updated for {container}: {exposed}")

def get_proxy_count():
    return int(config_manager.get("proxy_count", 0))

def set_proxy_count(proxy_count):
    config_manager.set("proxy_count", int(proxy_count))
    print(f"Proxy count set to {proxy_count}")

def get_internal_ip():
    return str(config_manager.get("internal_ip", default_ip))

def set_internal_ip(ip):
    # Get the old internal IP before changing it
    old_internal_ip = get_internal_ip()
    
    # Set the new internal IP
    config_manager.set("internal_ip", ip)
    print(f"Internal IP set to {ip}")
    
    # Update all internal link bodies that reference the old IP
    if old_internal_ip != ip:
        _update_link_bodies_with_new_ip("internal_link_bodies", old_internal_ip, ip)
        print(f"Updated internal link bodies from {old_internal_ip} to {ip}")

def get_external_ip():
    return str(config_manager.get("external_ip", default_ip))

def set_external_ip(ip):
    # Get the old external IP before changing it
    old_external_ip = get_external_ip()
    
    # Set the new external IP
    config_manager.set("external_ip", ip)
    print(f"External IP set to {ip}")
    
    # Update all external link bodies that reference the old IP
    if old_external_ip != ip:
        _update_link_bodies_with_new_ip("external_link_bodies", old_external_ip, ip)
        print(f"Updated external link bodies from {old_external_ip} to {ip}")

def get_first_boot():
    return bool(config_manager.get("first_boot", True))

def set_first_boot(is_first_boot):
    config_manager.set("first_boot", bool(is_first_boot))
    print(f"First boot flag set to {is_first_boot}")

def get_enabled_modules():
    mods = config_manager.get("enabled_modules", ["containers"]) or []
    return mods if isinstance(mods, list) else ["containers"]

def set_enabled_modules(modules_list):
    if not isinstance(modules_list, list):
        return
    config_manager.set("enabled_modules", modules_list)
    print(f"Enabled modules set to {modules_list}")

def get_modules_order():
    order = config_manager.get("modules_order", ["containers"]) or []
    if isinstance(order, list) and order:
        return order
    return get_enabled_modules()

def set_modules_order(order_list):
    if not isinstance(order_list, list):
        return
    config_manager.set("modules_order", order_list)
    print(f"Modules order set to {order_list}")

def get_module_config(module_id):
    if not module_id:
        return {}
    modules = config_manager.get("modules", {}) or {}
    return modules.get(module_id, {})

def set_module_config(module_id, config_dict):
    if not module_id or not isinstance(config_dict, dict):
        return
    modules = config_manager.get("modules", {}) or {}
    modules[module_id] = {**modules.get(module_id, {}), **config_dict}
    config_manager.set("modules", modules)
    print(f"Updated module config for {module_id}")

def _update_link_bodies_with_new_ip(link_bodies_key, old_ip, new_ip):
    """
    Helper function to update all link bodies that reference the old IP with the new IP.
    This handles both exact IP matches and common URL patterns.
    """
    save_manager = get_save_manager()
    
    # Get all containers and update their link bodies
    containers = save_manager.get_all_containers()
    updated_count = 0
    
    for container in containers:
        container_id = container.get("id")
        if not container_id:
            continue
            
        # Check and update the appropriate link body type
        if link_bodies_key == "internal_link_bodies":
            link_body = container.get("internal_link_body")
            if link_body and old_ip in link_body:
                updated_link_body = link_body.replace(old_ip, new_ip)
                save_manager.set_link_body(container_id, updated_link_body)
                updated_count += 1
                print(f"Updated {container_id}: {link_body} -> {updated_link_body}")
        elif link_bodies_key == "external_link_bodies":
            link_body = container.get("external_link_body")
            if link_body and old_ip in link_body:
                updated_link_body = link_body.replace(old_ip, new_ip)
                save_manager.set_external_link_body(container_id, updated_link_body)
                updated_count += 1
                print(f"Updated {container_id}: {link_body} -> {updated_link_body}")
    
    if updated_count > 0:
        print(f"Updated {updated_count} containers in {link_bodies_key}")
    else:
        print(f"No link bodies needed updating in {link_bodies_key}")