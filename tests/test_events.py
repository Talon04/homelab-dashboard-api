"""Tests for event API routes.

Tests the /api/notifications/events endpoints for:
- Listing events with pagination and filtering
- Acknowledging events
- Deleting events
- Creating test events
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

class TestGetEvents:
    """Tests for GET /api/notifications/events."""

    def test_get_events_empty(self, client, test_db):
        """Returns empty list when no events exist."""
        response = client.get("/api/notifications/events")

        assert response.status_code == 200
        data = response.get_json()
        assert data["events"] == []
        assert data["total"] == 0

    def test_get_events_returns_events(self, client, sample_events):
        """Returns events in descending timestamp order."""
        response = client.get("/api/notifications/events")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["events"]) == 5
        assert data["total"] == 5

    def test_get_events_pagination(self, client, sample_events):
        """Respects limit and offset parameters."""
        response = client.get("/api/notifications/events?limit=2&offset=1")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["events"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 1
        assert data["total"] == 5

    def test_get_events_filter_acknowledged(self, client, sample_events):
        """Filters events by acknowledged status."""
        # Get only acknowledged events
        response = client.get("/api/notifications/events?acknowledged=true")
        data = response.get_json()

        for event in data["events"]:
            assert event["acknowledged"] is True

    def test_get_events_filter_unacknowledged(self, client, sample_events):
        """Filters events by unacknowledged status."""
        response = client.get("/api/notifications/events?acknowledged=false")
        data = response.get_json()

        for event in data["events"]:
            assert event["acknowledged"] is False


class TestUnreadCount:
    """Tests for GET /api/notifications/events/unread_count."""

    def test_unread_count_empty(self, client, test_db):
        """Returns zero when no events exist."""
        response = client.get("/api/notifications/events/unread_count")

        assert response.status_code == 200
        assert response.get_json()["count"] == 0

    def test_unread_count_with_events(self, client, sample_events):
        """Returns count of unacknowledged events."""
        response = client.get("/api/notifications/events/unread_count")

        assert response.status_code == 200
        # sample_events creates 5 events, alternating acknowledged status
        # Events 0, 2, 4 are acknowledged, 1, 3 are not
        assert response.get_json()["count"] == 2


class TestAcknowledgeEvent:
    """Tests for POST /api/notifications/events/<id>/acknowledge."""

    def test_acknowledge_event_success(self, client, sample_event):
        """Successfully acknowledges an event."""
        response = client.post(
            f"/api/notifications/events/{sample_event.id}/acknowledge"
        )

        assert response.status_code == 200
        assert "acknowledged" in response.get_json()["message"].lower()

    def test_acknowledge_event_not_found(self, client, test_db):
        """Returns 404 for non-existent event."""
        response = client.post("/api/notifications/events/99999/acknowledge")

        assert response.status_code == 404
        assert "not found" in response.get_json()["error"].lower()


class TestAcknowledgeAllEvents:
    """Tests for POST /api/notifications/events/acknowledge_all."""

    def test_acknowledge_all_events(self, client, sample_events):
        """Acknowledges all unacknowledged events."""
        response = client.post("/api/notifications/events/acknowledge_all")

        assert response.status_code == 200

        # Verify all events are now acknowledged
        response = client.get("/api/notifications/events/unread_count")
        assert response.get_json()["count"] == 0


class TestDeleteEvent:
    """Tests for DELETE /api/notifications/events/<id>."""

    def test_delete_event_success(self, client, sample_event):
        """Successfully deletes an event."""
        event_id = sample_event.id
        response = client.delete(f"/api/notifications/events/{event_id}")

        assert response.status_code == 200
        assert "deleted" in response.get_json()["message"].lower()

    def test_delete_event_not_found(self, client, test_db):
        """Returns 404 for non-existent event."""
        response = client.delete("/api/notifications/events/99999")

        assert response.status_code == 404


class TestDeleteAllEvents:
    """Tests for DELETE /api/notifications/events/delete_all."""

    def test_delete_all_events(self, client, sample_events):
        """Deletes all events."""
        response = client.delete("/api/notifications/events/delete_all")

        assert response.status_code == 200
        data = response.get_json()
        assert data["count"] == 5

        # Verify events are deleted
        response = client.get("/api/notifications/events")
        assert response.get_json()["total"] == 0


class TestCreateTestEvent:
    """Tests for POST /api/notifications/test."""

    def test_create_test_event_defaults(self, client, test_db):
        """Creates a test event with default values."""
        response = client.post(
            "/api/notifications/test", json={}  # Empty JSON body to use defaults
        )

        assert response.status_code == 201
        data = response.get_json()
        assert "event" in data
        assert data["event"]["severity"] == 2
        assert data["event"]["source"] == "test"

    def test_create_test_event_custom(self, client, test_db):
        """Creates a test event with custom values."""
        response = client.post(
            "/api/notifications/test",
            json={
                "severity": 3,
                "source": "custom",
                "title": "Custom Title",
                "message": "Custom message",
            },
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["event"]["severity"] == 3
        assert data["event"]["source"] == "custom"
        assert data["event"]["title"] == "Custom Title"

    def test_create_test_event_invalid_severity(self, client, test_db):
        """Returns error for invalid severity value."""
        response = client.post("/api/notifications/test", json={"severity": -1})

        assert response.status_code == 400
        assert "severity" in response.get_json()["error"].lower()
