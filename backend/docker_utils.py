"""Docker integration utilities.

This module provides functions to interact with Docker containers.
"""

from typing import Dict, List
from datetime import datetime, timezone

import docker


# =============================================================================
# Docker API Functions
# =============================================================================


def list_containers() -> List[Dict]:
    """List all containers with their basic info.

    Returns:
        List of dicts with id, name, status, ports, labels keys.
    """
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True)
        return [
            {
                "id": c.id,
                "name": c.name,
                "status": c.status,
                "ports": c.attrs["NetworkSettings"]["Ports"],
                "labels": c.attrs.get("Config", {}).get("Labels", {}),
            }
            for c in containers
        ]
    except Exception as e:
        print(f"[docker_utils] Failed to list containers: {e}")
        return []


def get_container_ports(container_id: str) -> List[Dict]:
    """Get port mappings for a container.

    Args:
        container_id: Docker container ID.

    Returns:
        List of dicts with container_port, host_ip, host_port keys.
    """
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        ports = container.attrs["NetworkSettings"]["Ports"]
        port_list = []
        for container_port, mappings in ports.items():
            if mappings is None:
                continue
            for m in mappings:
                port_list.append(
                    {
                        "container_port": container_port,
                        "host_ip": m["HostIp"],
                        "host_port": m["HostPort"],
                    }
                )
        return port_list
    except Exception as e:
        print(f"[docker_utils] Failed to get ports for {container_id}: {e}")
        return []


def get_container_status_by_id(container_id: str) -> str:
    """Get the status of a container by its Docker ID.

    Args:
        container_id: Docker container ID.

    Returns:
        Status string (running, exited, etc.) or "unknown" if not found.
    """
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        return container.status
    except Exception as e:
        print(f"[docker_utils] Failed to get status for {container_id}: {e}")
        return "unknown"


def get_container_uptime(container_id: str) -> str:
    """Get the uptime of a container by its Docker ID.

    Args:
        container_id: Docker container ID.

    Returns:
        Uptime string (e.g., "2 days, 3 hours") or "unknown" if not found.
    """
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        started_at_str = container.attrs["State"]["StartedAt"]

        # Parse the ISO 8601 timestamp
        started_at = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        uptime_delta = now - started_at

        # Format the uptime
        days = uptime_delta.days
        hours, remainder = divmod(uptime_delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if days > 0:
            return f"{days} days, {hours} hours"
        elif hours > 0:
            return f"{hours} hours, {minutes} minutes"
        elif minutes > 0:
            return f"{minutes} minutes"
        else:
            return f"{seconds} seconds"
    except Exception as e:
        print(f"[docker_utils] Failed to get uptime for {container_id}: {e}")
        return "unknown"
