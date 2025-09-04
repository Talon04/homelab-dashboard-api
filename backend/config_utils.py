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
    return config_manager.get("external_ip", "127.0.0.1")

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
    return config_manager.get("first_boot", False)

def set_first_boot(is_first_boot):
    config_manager.set("first_boot", is_first_boot)
    print(f"First boot flag set to {is_first_boot}")

def get_backup_view_enabled():
    return config_manager.get("backup_view_enabled", False)

def set_backup_view_enabled(enabled):
    config_manager.set("backup_view_enabled", enabled)
    print(f"Backup view enabled set to {enabled}")

def get_backup_config():
    return config_manager.get("backup_config", {
        "datetime_format": "%Y-%m-%d %H:%M:%S",
        "keywords": {
            "archive_name": "Archive name",
            "repository": "Repository", 
            "location": "Location",
            "backup_size": "This archive",
            "original_size": "Original size",
            "compressed_size": "Compressed size",
            "deduplicated_size": "Deduplicated size",
            "number_files": "Number of files",
            "added_files": "Added files",
            "modified_files": "Modified files",
            "unchanged_files": "Unchanged files",
            "duration": "Duration",
            "start_time": "Start time",
            "end_time": "End time",
            "status": "terminating with"
        },
        "backup_auto_refresh": False,
        "backup_refresh_interval": 5,
        "smart_auto_refresh": False,
        "smart_refresh_interval": 10,
        "smart_log_format": "smartctl-json",
        "smart_datetime_format": "%Y-%m-%d %H:%M:%S",
        "smart_temp_monitoring": True,
        "smart_health_monitoring": True,
        "smart_attribute_monitoring": True
    })

def set_backup_config(backup_config):
    config_manager.set("backup_config", backup_config)
    print(f"Backup configuration updated: {backup_config}")

def _update_link_bodies_with_new_ip(link_bodies_key, old_ip, new_ip):
    """
    Helper function to update all link bodies that reference the old IP with the new IP.
    This handles both exact IP matches and common URL patterns.
    """
    # Get the current link bodies
    link_bodies = config_manager.get(link_bodies_key, {})
    
    updated_count = 0
    for container_id, link_body in link_bodies.items():
        if link_body and isinstance(link_body, str):
            # Check if the link body contains the old IP
            if old_ip in link_body:
                # Replace the old IP with the new IP
                updated_link_body = link_body.replace(old_ip, new_ip)
                
                # Update the link body in config
                config_manager.set_nested(link_bodies_key, container_id, updated_link_body)
                updated_count += 1
                print(f"Updated {container_id}: {link_body} -> {updated_link_body}")
    
    if updated_count > 0:
        print(f"Updated {updated_count} containers in {link_bodies_key}")
    else:
        print(f"No link bodies needed updating in {link_bodies_key}")