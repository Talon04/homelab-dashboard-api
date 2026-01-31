"""Pytest fixtures for the homelab dashboard test suite.

Provides:
- Flask test client with isolated test database
- Mocked Docker API
- Database session fixtures
- Sample data factories
"""

import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(scope="session")
def temp_data_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def test_db(temp_data_dir):
    """Create an isolated test database.

    Returns a DatabaseManager instance with a fresh database.
    """
    from backend.models import DatabaseManager

    db_path = os.path.join(temp_data_dir, f"test_{os.getpid()}.db")
    db = DatabaseManager(db_path=db_path)
    yield db

    # Cleanup - remove the test database file
    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def db_session(test_db):
    """Provide a database session that rolls back after each test."""
    session = test_db.get_session()
    yield session
    session.rollback()
    test_db.close_session(session)


@pytest.fixture
def mock_docker():
    """Mock the Docker client and API calls.

    Returns a mock that can be configured for specific test scenarios.
    """
    with patch("backend.docker_utils.docker") as mock:
        mock_client = MagicMock()
        mock.from_env.return_value = mock_client

        # Default: return empty container list
        mock_client.containers.list.return_value = []

        yield mock_client


@pytest.fixture
def mock_containers(mock_docker):
    """Provide mock container data for testing.

    Returns a list of mock container objects that behave like Docker containers.
    """
    containers = [
        _create_mock_container("abc123", "web-server", "running"),
        _create_mock_container("def456", "database", "running"),
        _create_mock_container("ghi789", "cache", "exited"),
    ]
    mock_docker.containers.list.return_value = containers
    return containers


def _create_mock_container(container_id: str, name: str, status: str):
    """Create a mock Docker container object."""
    mock = MagicMock()
    mock.id = container_id
    mock.name = name
    mock.status = status
    mock.attrs = {
        "NetworkSettings": {
            "Ports": {"80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]}
        },
        "Config": {"Labels": {"com.docker.compose.project": "test"}},
    }
    return mock


@pytest.fixture
def app(test_db, mock_docker):
    """Create a Flask test application with mocked dependencies.

    Patches the database and Docker connections to use test fixtures.
    """
    # Patch the database manager used by routes
    with patch("backend.routes_bps.event_routes._db_manager", test_db), patch(
        "backend.routes_bps.event_routes.get_db", return_value=test_db
    ):

        from app import app as flask_app

        flask_app.config.update(
            {
                "TESTING": True,
                "DEBUG": False,
            }
        )

        yield flask_app


@pytest.fixture
def client(app):
    """Create a Flask test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a Flask CLI test runner."""
    return app.test_cli_runner()


# =============================================================================
# Sample Data Factories
# =============================================================================


@pytest.fixture
def sample_event(db_session):
    """Create a sample event in the test database."""
    from backend.models import Event
    from datetime import datetime

    event = Event(
        severity=2,
        source="test",
        title="Test Event",
        message="This is a test event",
        fingerprint=f"test:event:{datetime.utcnow().timestamp()}",
        timestamp=datetime.utcnow(),
        acknowledged=False,
    )
    db_session.add(event)
    db_session.commit()
    return event


@pytest.fixture
def sample_events(db_session):
    """Create multiple sample events for testing pagination."""
    from backend.models import Event
    from datetime import datetime, timedelta

    events = []
    for i in range(5):
        event = Event(
            severity=(i % 4) + 1,
            source="test",
            title=f"Test Event {i}",
            message=f"Test message {i}",
            fingerprint=f"test:event:{i}:{datetime.utcnow().timestamp()}",
            timestamp=datetime.utcnow() - timedelta(minutes=i),
            acknowledged=(i % 2 == 0),
        )
        db_session.add(event)
        events.append(event)

    db_session.commit()
    return events


@pytest.fixture
def sample_container(db_session):
    """Create a sample container in the test database."""
    from backend.models import Container

    container = Container(
        docker_id="abc123",
        name="test-container",
        image="nginx:latest",
        status="running",
        is_exposed=True,
    )
    db_session.add(container)
    db_session.commit()
    return container


@pytest.fixture
def sample_monitor(db_session, sample_container):
    """Create a sample monitor configuration in the test database."""
    from backend.models import MonitorBodies

    monitor = MonitorBodies(
        name="Test Monitor",
        container_id=sample_container.id,
        monitor_type="container",
        enabled=True,
    )
    db_session.add(monitor)
    db_session.commit()
    return monitor
