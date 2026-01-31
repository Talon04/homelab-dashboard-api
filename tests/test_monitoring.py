"""Tests for the monitoring service logic.

Tests the monitoring service's state evaluation and event creation
logic, decoupled from actual Docker API calls.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestStateEvaluation:
    """Tests for container state evaluation logic."""

    def test_get_event_type_offline(self):
        """Detects offline transition."""
        from backend.monitoring_service import _get_event_type_for_state

        # Running -> Exited = offline
        assert _get_event_type_for_state("exited", "running") == "offline"
        assert _get_event_type_for_state("stopped", "running") == "offline"
        assert _get_event_type_for_state("dead", "running") == "offline"

    def test_get_event_type_online(self):
        """Detects online transition."""
        from backend.monitoring_service import _get_event_type_for_state

        # Exited -> Running = online
        assert _get_event_type_for_state("running", "exited") == "online"
        assert _get_event_type_for_state("running", "stopped") == "online"
        assert _get_event_type_for_state("online", "offline") == "online"

    def test_get_event_type_unreachable(self):
        """Detects unreachable transition."""
        from backend.monitoring_service import _get_event_type_for_state

        # Running -> Unknown = unreachable
        assert _get_event_type_for_state("unknown", "running") == "unreachable"
        assert _get_event_type_for_state("paused", "running") == "unreachable"

    def test_get_event_type_no_change(self):
        """Returns None when no significant state change."""
        from backend.monitoring_service import _get_event_type_for_state

        # Same state = no event
        assert _get_event_type_for_state("running", "running") is None
        assert _get_event_type_for_state("exited", "exited") is None

        # Similar states = no event
        assert _get_event_type_for_state("exited", "stopped") is None
        assert _get_event_type_for_state("stopped", "dead") is None

    def test_get_event_type_case_insensitive(self):
        """Handles case variations."""
        from backend.monitoring_service import _get_event_type_for_state

        assert _get_event_type_for_state("RUNNING", "exited") == "online"
        assert _get_event_type_for_state("Exited", "Running") == "offline"

    def test_get_event_type_handles_none(self):
        """Handles None/empty states gracefully."""
        from backend.monitoring_service import _get_event_type_for_state

        # None treated as unknown
        assert _get_event_type_for_state(None, "running") == "unreachable"
        assert _get_event_type_for_state("running", None) == "online"


class TestContainerStatusEvaluation:
    """Tests for Docker container status evaluation."""

    def test_evaluate_status_running(self):
        """Returns status for running container."""
        from backend.monitoring_service import _evaluate_docker_container_status

        mock_container = MagicMock()
        mock_container.docker_id = "abc123"

        with patch("backend.monitoring_service.docker_utils") as mock_docker:
            mock_docker.get_container_status_by_id.return_value = "running"

            status = _evaluate_docker_container_status(mock_container)

            assert status == "running"
            mock_docker.get_container_status_by_id.assert_called_once_with("abc123")

    def test_evaluate_status_exited(self):
        """Returns status for stopped container."""
        from backend.monitoring_service import _evaluate_docker_container_status

        mock_container = MagicMock()
        mock_container.docker_id = "def456"

        with patch("backend.monitoring_service.docker_utils") as mock_docker:
            mock_docker.get_container_status_by_id.return_value = "exited"

            status = _evaluate_docker_container_status(mock_container)

            assert status == "exited"

    def test_evaluate_status_none_container(self):
        """Returns unknown for None container."""
        from backend.monitoring_service import _evaluate_docker_container_status

        status = _evaluate_docker_container_status(None)

        assert status == "unknown"

    def test_evaluate_status_not_found(self):
        """Returns unknown when Docker can't find container."""
        from backend.monitoring_service import _evaluate_docker_container_status

        mock_container = MagicMock()
        mock_container.docker_id = "notfound"

        with patch("backend.monitoring_service.docker_utils") as mock_docker:
            mock_docker.get_container_status_by_id.return_value = ""

            status = _evaluate_docker_container_status(mock_container)

            assert status == "unknown"


class TestGetContainersIndex:
    """Tests for building container index from Docker API."""

    def test_builds_index_from_containers(self):
        """Builds ID -> container mapping."""
        from backend.monitoring_service import _get_containers_index

        mock_containers = [
            {"id": "abc123", "name": "web", "status": "running"},
            {"id": "def456", "name": "db", "status": "running"},
        ]

        with patch("backend.monitoring_service.docker_utils") as mock_docker:
            mock_docker.list_containers.return_value = mock_containers

            index = _get_containers_index()

            assert "abc123" in index
            assert "def456" in index
            assert index["abc123"]["name"] == "web"

    def test_returns_empty_on_docker_error(self):
        """Returns empty dict when Docker fails."""
        from backend.monitoring_service import _get_containers_index

        with patch("backend.monitoring_service.docker_utils") as mock_docker:
            mock_docker.list_containers.side_effect = Exception("Docker not available")

            index = _get_containers_index()

            assert index == {}

    def test_handles_empty_container_list(self):
        """Handles empty container list."""
        from backend.monitoring_service import _get_containers_index

        with patch("backend.monitoring_service.docker_utils") as mock_docker:
            mock_docker.list_containers.return_value = []

            index = _get_containers_index()

            assert index == {}

    def test_skips_containers_without_id(self):
        """Skips containers missing ID field."""
        from backend.monitoring_service import _get_containers_index

        mock_containers = [
            {"id": "abc123", "name": "web", "status": "running"},
            {"name": "invalid", "status": "running"},  # No ID
            {"id": None, "name": "null-id", "status": "running"},  # None ID
        ]

        with patch("backend.monitoring_service.docker_utils") as mock_docker:
            mock_docker.list_containers.return_value = mock_containers

            index = _get_containers_index()

            assert len(index) == 1
            assert "abc123" in index


class TestMonitoringCycleIntegration:
    """Integration tests for run_monitoring_cycle() with database fixtures."""

    @pytest.fixture
    def monitoring_setup(self, test_db):
        """Set up container and monitor body for testing."""
        from backend.models import Container, MonitorBodies
        from backend.save_manager import get_save_manager
        from backend import monitoring_service

        # Reset previous states between tests
        monitoring_service._previous_states.clear()

        session = test_db.get_session()

        # Create a container
        container = Container(
            docker_id="test123",
            name="test-web-server",
            image="nginx:latest",
            status="running",
        )
        session.add(container)
        session.commit()

        # Create a monitor body for that container
        monitor = MonitorBodies(
            name="Test Monitor",
            container_id=container.id,
            monitor_type="docker",
            enabled=True,
        )
        session.add(monitor)
        session.commit()

        # Patch save_manager to use our test database
        sm = get_save_manager()
        original_db = getattr(sm, "db_manager", None)
        sm.db_manager = test_db

        yield {
            "container": container,
            "monitor": monitor,
            "session": session,
            "test_db": test_db,
        }

        # Cleanup
        sm.db_manager = original_db
        session.close()

    def test_monitoring_cycle_creates_offline_event(self, monitoring_setup):
        """Creates an offline event when container goes from running to exited."""
        from backend.monitoring_service import run_monitoring_cycle, _previous_states
        from backend.models import Event

        setup = monitoring_setup
        monitor_id = setup["monitor"].id

        # Set initial state as "running"
        _previous_states[monitor_id] = "running"

        # Mock Docker to return "exited" status
        with patch("backend.monitoring_service.docker_utils") as mock_docker:
            mock_docker.get_container_status_by_id.return_value = "exited"

            run_monitoring_cycle()

        # Check that an event was created
        session = setup["test_db"].get_session()
        event = session.query(Event).filter(Event.source == "monitor").first()

        assert event is not None
        assert event.title == "test-web-server went offline"
        assert "exited" in event.message.lower()
        assert event.object_type == "container"
        assert event.object_id == setup["container"].id
        session.close()

    def test_monitoring_cycle_creates_online_event(self, monitoring_setup):
        """Creates an online event when container goes from exited to running."""
        from backend.monitoring_service import run_monitoring_cycle, _previous_states
        from backend.models import Event

        setup = monitoring_setup
        monitor_id = setup["monitor"].id

        # Set initial state as "exited"
        _previous_states[monitor_id] = "exited"

        # Mock Docker to return "running" status
        with patch("backend.monitoring_service.docker_utils") as mock_docker:
            mock_docker.get_container_status_by_id.return_value = "running"

            run_monitoring_cycle()

        # Check that an event was created
        session = setup["test_db"].get_session()
        event = session.query(Event).filter(Event.source == "monitor").first()

        assert event is not None
        assert event.title == "test-web-server came online"
        assert "running" in event.message.lower()
        session.close()

    def test_monitoring_cycle_no_event_on_same_state(self, monitoring_setup):
        """No event created when state doesn't change."""
        from backend.monitoring_service import run_monitoring_cycle, _previous_states
        from backend.models import Event

        setup = monitoring_setup
        monitor_id = setup["monitor"].id

        # Set initial state as "running"
        _previous_states[monitor_id] = "running"

        # Mock Docker to return same "running" status
        with patch("backend.monitoring_service.docker_utils") as mock_docker:
            mock_docker.get_container_status_by_id.return_value = "running"

            run_monitoring_cycle()

        # Check that no event was created
        session = setup["test_db"].get_session()
        event = session.query(Event).filter(Event.source == "monitor").first()

        assert event is None
        session.close()

    def test_monitoring_cycle_records_monitor_point(self, monitoring_setup):
        """Records a monitor point on each cycle."""
        from backend.monitoring_service import run_monitoring_cycle
        from backend.models import MonitorPoints

        setup = monitoring_setup

        with patch("backend.monitoring_service.docker_utils") as mock_docker:
            mock_docker.get_container_status_by_id.return_value = "running"

            run_monitoring_cycle()

        # Check that a monitor point was recorded
        session = setup["test_db"].get_session()
        point = (
            session.query(MonitorPoints)
            .filter(MonitorPoints.monitor_body_id == setup["monitor"].id)
            .first()
        )

        assert point is not None
        assert point.value == "running"
        session.close()

    def test_monitoring_cycle_creates_unreachable_event(self, monitoring_setup):
        """Creates an unreachable event when container state becomes unknown."""
        from backend.monitoring_service import run_monitoring_cycle, _previous_states
        from backend.models import Event

        setup = monitoring_setup
        monitor_id = setup["monitor"].id

        # Set initial state as "running"
        _previous_states[monitor_id] = "running"

        # Mock Docker to return "unknown" status (container not found)
        with patch("backend.monitoring_service.docker_utils") as mock_docker:
            mock_docker.get_container_status_by_id.return_value = "unknown"

            run_monitoring_cycle()

        # Check that an unreachable event was created
        session = setup["test_db"].get_session()
        event = session.query(Event).filter(Event.source == "monitor").first()

        assert event is not None
        assert event.title == "test-web-server is unreachable"
        session.close()

    def test_monitoring_cycle_updates_previous_state(self, monitoring_setup):
        """Updates _previous_states after each cycle."""
        from backend.monitoring_service import run_monitoring_cycle, _previous_states

        setup = monitoring_setup
        monitor_id = setup["monitor"].id

        with patch("backend.monitoring_service.docker_utils") as mock_docker:
            mock_docker.get_container_status_by_id.return_value = "running"

            run_monitoring_cycle()

        assert _previous_states.get(monitor_id) == "running"

        # Run again with different status
        with patch("backend.monitoring_service.docker_utils") as mock_docker:
            mock_docker.get_container_status_by_id.return_value = "exited"

            run_monitoring_cycle()

        assert _previous_states.get(monitor_id) == "exited"
