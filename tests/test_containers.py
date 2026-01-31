"""Tests for container API routes.

Tests the /api/containers endpoints with mocked Docker API.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestListContainers:
    """Tests for GET /api/containers."""

    def test_list_containers_empty(self, client, mock_docker):
        """Returns empty list when no containers exist."""
        mock_docker.containers.list.return_value = []

        response = client.get("/api/containers")

        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_list_containers_returns_data(self, client, mock_containers):
        """Returns container data from Docker."""
        response = client.get("/api/containers")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 3

        # Verify container structure
        container = data[0]
        assert "id" in container
        assert "name" in container
        assert "status" in container

    def test_list_containers_docker_error(self, client, mock_docker):
        """Handles Docker API errors gracefully."""
        mock_docker.containers.list.side_effect = Exception("Docker unavailable")

        response = client.get("/api/containers")

        assert response.status_code == 200
        assert response.get_json() == []


class TestDockerUtils:
    """Tests for docker_utils module functions."""

    def test_list_containers_formats_data(self):
        """Formats Docker container data correctly."""
        from backend.docker_utils import list_containers

        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_container.name = "test-container"
        mock_container.status = "running"
        mock_container.attrs = {
            "NetworkSettings": {
                "Ports": {"80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]}
            },
            "Config": {"Labels": {"app": "test"}},
        }

        with patch("backend.docker_utils.docker") as mock_docker:
            mock_docker.from_env.return_value.containers.list.return_value = [
                mock_container
            ]

            result = list_containers()

            assert len(result) == 1
            assert result[0]["id"] == "abc123"
            assert result[0]["name"] == "test-container"
            assert result[0]["status"] == "running"
            assert result[0]["ports"] == {
                "80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]
            }
            assert result[0]["labels"] == {"app": "test"}

    def test_get_container_ports(self):
        """Gets port mappings for a container."""
        from backend.docker_utils import get_container_ports

        mock_container = MagicMock()
        mock_container.attrs = {
            "NetworkSettings": {
                "Ports": {
                    "80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}],
                    "443/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8443"}],
                }
            }
        }

        with patch("backend.docker_utils.docker") as mock_docker:
            mock_docker.from_env.return_value.containers.get.return_value = (
                mock_container
            )

            result = get_container_ports("abc123")

            assert len(result) == 2
            assert result[0]["container_port"] in ["80/tcp", "443/tcp"]
            assert result[0]["host_ip"] == "0.0.0.0"

    def test_get_container_ports_none_mappings(self):
        """Handles ports with no host mappings."""
        from backend.docker_utils import get_container_ports

        mock_container = MagicMock()
        mock_container.attrs = {
            "NetworkSettings": {
                "Ports": {
                    "80/tcp": None,  # Port exposed but not mapped
                    "443/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8443"}],
                }
            }
        }

        with patch("backend.docker_utils.docker") as mock_docker:
            mock_docker.from_env.return_value.containers.get.return_value = (
                mock_container
            )

            result = get_container_ports("abc123")

            # Should skip the None mapping
            assert len(result) == 1
            assert result[0]["container_port"] == "443/tcp"

    def test_get_container_status_by_id(self):
        """Gets container status by ID."""
        from backend.docker_utils import get_container_status_by_id

        mock_container = MagicMock()
        mock_container.status = "running"

        with patch("backend.docker_utils.docker") as mock_docker:
            mock_docker.from_env.return_value.containers.get.return_value = (
                mock_container
            )

            result = get_container_status_by_id("abc123")

            assert result == "running"

    def test_get_container_status_not_found(self):
        """Returns unknown for non-existent container."""
        from backend.docker_utils import get_container_status_by_id

        with patch("backend.docker_utils.docker") as mock_docker:
            mock_docker.from_env.return_value.containers.get.side_effect = Exception(
                "Container not found"
            )

            result = get_container_status_by_id("nonexistent")

            assert result == "unknown"
