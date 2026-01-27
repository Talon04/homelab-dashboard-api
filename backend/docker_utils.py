"""Docker integration utilities with optional mock data for testing.

This module provides functions to interact with Docker containers. When
TESTING_MODE=1 is set, all operations use mutable mock data instead of
a real Docker daemon, enabling development and testing without Docker.

Production deployment:
    1. Delete sections between MOCK_START and MOCK_END markers
    2. Delete backend/routes_bps/testing_routes.py
    3. Remove testing_bp registration from app.py
"""

import os
from typing import Dict, List, Optional

import docker


# =============================================================================
# Testing Mode Detection
# =============================================================================


def is_testing_mode() -> bool:
    """Check if running in testing mode (mock Docker).

    Evaluated at runtime on each call, allowing dynamic switching
    during test scenarios.
    """
    return os.environ.get("TESTING_MODE", "0") == "1"


# =============================================================================
# MOCK_START - Delete this section for production deployment
# =============================================================================

# Mock container data - mutable for testing scenarios
_mock_containers: Dict[str, Dict] = {
    "dadkönfm": {
        "id": "dadkönfm",
        "name": "mock_container_1",
        "status": "running",
        "ports": {"80/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8080"}]},
        "labels": {
            "exposed": "true",
            "com.docker.compose.project": "mock_project",
        },
    },
    "dadköndanwlänfm": {
        "id": "dadköndanwlänfm",
        "name": "mock_container_2",
        "status": "exited",
        "ports": {},
        "labels": {"com.docker.compose.project": "mock_project"},
    },
    "dadköndanwlänfmdaw": {
        "id": "dadköndanwlänfmdaw",
        "name": "mock_container_3",
        "status": "exited",
        "ports": {},
        "labels": {},
    },
}

_mock_ports: Dict[str, List[Dict]] = {
    "dadkönfm": [
        {
            "container_port": "80/tcp",
            "host_ip": "127.0.0.1",
            "host_port": "8080",
        },
        {
            "container_port": "19/udp",
            "host_ip": "127.0.0.1",
            "host_port": "9090",
        },
    ],
    "dadköndanwlänfm": [],
    "dadköndanwlänfmdaw": [],
}


def get_mock_containers() -> Dict[str, Dict]:
    """Return the current mock containers state."""
    return _mock_containers.copy()


def set_mock_container_status(container_id: str, status: str) -> bool:
    """Update the status of a mock container.

    Args:
        container_id: The container ID to modify.
        status: New status (running, exited, stopped, paused, dead, etc.).

    Returns:
        True if updated, False if container not found.
    """
    if container_id in _mock_containers:
        _mock_containers[container_id]["status"] = status
        return True
    return False


def add_mock_container(
    container_id: str,
    name: str,
    status: str = "running",
    ports: Optional[Dict] = None,
    labels: Optional[Dict] = None,
) -> Dict:
    """Add a new mock container for testing.

    Args:
        container_id: Unique container identifier.
        name: Human-readable container name.
        status: Initial container status.
        ports: Port mappings dictionary.
        labels: Container labels dictionary.

    Returns:
        The created container dictionary.
    """
    container = {
        "id": container_id,
        "name": name,
        "status": status,
        "ports": ports or {},
        "labels": labels or {},
    }
    _mock_containers[container_id] = container
    _mock_ports[container_id] = []
    return container


def remove_mock_container(container_id: str) -> bool:
    """Remove a mock container.

    Returns:
        True if removed, False if not found
    """
    if container_id in _mock_containers:
        del _mock_containers[container_id]
        _mock_ports.pop(container_id, None)
        return True
    return False


def reset_mock_containers() -> None:
    """Reset all mock containers to their initial state."""
    global _mock_containers, _mock_ports
    _mock_containers = {
        "dadkönfm": {
            "id": "dadkönfm",
            "name": "mock_container_1",
            "status": "running",
            "ports": {"80/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8080"}]},
            "labels": {
                "exposed": "true",
                "com.docker.compose.project": "mock_project",
            },
        },
        "dadköndanwlänfm": {
            "id": "dadköndanwlänfm",
            "name": "mock_container_2",
            "status": "exited",
            "ports": {},
            "labels": {"com.docker.compose.project": "mock_project"},
        },
        "dadköndanwlänfmdaw": {
            "id": "dadköndanwlänfmdaw",
            "name": "mock_container_3",
            "status": "exited",
            "ports": {},
            "labels": {},
        },
    }
    _mock_ports = {
        "dadkönfm": [
            {"container_port": "80/tcp", "host_ip": "127.0.0.1", "host_port": "8080"},
            {"container_port": "19/udp", "host_ip": "127.0.0.1", "host_port": "9090"},
        ],
        "dadköndanwlänfm": [],
        "dadköndanwlänfmdaw": [],
    }


# =============================================================================
# MOCK_END
# =============================================================================


# =============================================================================
# Docker API Functions
# =============================================================================


def list_containers() -> List[Dict]:
    """List all containers with their basic info.

    Returns:
        List of dicts with id, name, status, ports, labels keys.
        Uses mock data when TESTING_MODE=1, otherwise queries Docker API.
    """
    if is_testing_mode():
        return list(_mock_containers.values())

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
    if is_testing_mode():
        return _mock_ports.get(container_id, [])

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
    if is_testing_mode():
        container = _mock_containers.get(container_id)
        return container["status"] if container else "unknown"

    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        return container.status
    except Exception as e:
        print(f"[docker_utils] Failed to get status for {container_id}: {e}")
        return "unknown"
