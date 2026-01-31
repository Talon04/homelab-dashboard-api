"""Tests for notification channels and rules API routes.

Tests the /api/notifications/channels and /api/notifications/rules endpoints.
"""

import pytest
from unittest.mock import patch


@pytest.fixture
def mock_config_manager():
    """Mock the config_manager for notification tests."""
    config_data = {"modules": {"notifications": {"channels": [], "rules": []}}}

    def get_config(key, default=None):
        return config_data.get(key, default)

    def set_config(key, value):
        config_data[key] = value

    with patch("backend.routes_bps.notification_routes.config_manager") as mock:
        mock.get.side_effect = get_config
        mock.set.side_effect = set_config
        yield mock, config_data


class TestGetChannels:
    """Tests for GET /api/notifications/channels."""

    def test_get_channels_empty(self, client, mock_config_manager):
        """Returns empty list when no channels exist."""
        response = client.get("/api/notifications/channels")

        assert response.status_code == 200
        assert response.get_json()["channels"] == []

    def test_get_channels_with_data(self, client, mock_config_manager):
        """Returns existing channels."""
        _, config_data = mock_config_manager
        config_data["modules"]["notifications"]["channels"] = [
            {"id": 1, "name": "Discord", "channel_type": "discord", "enabled": True}
        ]

        response = client.get("/api/notifications/channels")

        assert response.status_code == 200
        channels = response.get_json()["channels"]
        assert len(channels) == 1
        assert channels[0]["name"] == "Discord"


class TestCreateChannel:
    """Tests for POST /api/notifications/channels."""

    def test_create_channel_success(self, client, mock_config_manager):
        """Creates a new channel with valid data."""
        response = client.post(
            "/api/notifications/channels",
            json={
                "name": "Test Discord",
                "channel_type": "discord",
                "config": {"webhook_url": "https://discord.com/webhook/123"},
            },
        )

        assert response.status_code == 201
        assert "id" in response.get_json()

    def test_create_channel_missing_name(self, client, mock_config_manager):
        """Returns error when name is missing."""
        response = client.post(
            "/api/notifications/channels", json={"channel_type": "discord"}
        )

        assert response.status_code == 400
        assert "required" in response.get_json()["error"].lower()

    def test_create_channel_missing_type(self, client, mock_config_manager):
        """Returns error when channel_type is missing."""
        response = client.post("/api/notifications/channels", json={"name": "Test"})

        assert response.status_code == 400

    def test_create_channel_invalid_type(self, client, mock_config_manager):
        """Returns error for invalid channel type."""
        response = client.post(
            "/api/notifications/channels",
            json={"name": "Test", "channel_type": "invalid"},
        )

        assert response.status_code == 400
        assert "invalid" in response.get_json()["error"].lower()

    def test_create_channel_no_body(self, client, mock_config_manager):
        """Returns error when no JSON body provided."""
        response = client.post(
            "/api/notifications/channels",
            content_type="application/json",  # Send with content type but empty
        )

        assert response.status_code == 400


class TestUpdateChannel:
    """Tests for PUT /api/notifications/channels/<id>."""

    def test_update_channel_success(self, client, mock_config_manager):
        """Updates an existing channel."""
        _, config_data = mock_config_manager
        config_data["modules"]["notifications"]["channels"] = [
            {"id": 1, "name": "Old Name", "channel_type": "discord", "enabled": True}
        ]

        response = client.put(
            "/api/notifications/channels/1", json={"name": "New Name"}
        )

        assert response.status_code == 200
        assert "updated" in response.get_json()["message"].lower()

    def test_update_channel_not_found(self, client, mock_config_manager):
        """Returns 404 for non-existent channel."""
        response = client.put(
            "/api/notifications/channels/999", json={"name": "New Name"}
        )

        assert response.status_code == 404

    def test_update_channel_invalid_type(self, client, mock_config_manager):
        """Returns error for invalid channel type update."""
        _, config_data = mock_config_manager
        config_data["modules"]["notifications"]["channels"] = [
            {"id": 1, "name": "Test", "channel_type": "discord", "enabled": True}
        ]

        response = client.put(
            "/api/notifications/channels/1", json={"channel_type": "invalid"}
        )

        assert response.status_code == 400


class TestDeleteChannel:
    """Tests for DELETE /api/notifications/channels/<id>."""

    def test_delete_channel_success(self, client, mock_config_manager):
        """Deletes an existing channel and its rules."""
        _, config_data = mock_config_manager
        config_data["modules"]["notifications"]["channels"] = [
            {"id": 1, "name": "Test", "channel_type": "discord"}
        ]
        config_data["modules"]["notifications"]["rules"] = [
            {"id": 1, "channel_id": 1, "min_severity": 2}
        ]

        response = client.delete("/api/notifications/channels/1")

        assert response.status_code == 200
        assert "deleted" in response.get_json()["message"].lower()

    def test_delete_channel_not_found(self, client, mock_config_manager):
        """Returns 404 for non-existent channel."""
        response = client.delete("/api/notifications/channels/999")

        assert response.status_code == 404


class TestGetRules:
    """Tests for GET /api/notifications/rules."""

    def test_get_rules_empty(self, client, mock_config_manager):
        """Returns empty list when no rules exist."""
        response = client.get("/api/notifications/rules")

        assert response.status_code == 200
        assert response.get_json()["rules"] == []

    def test_get_rules_with_channel_info(self, client, mock_config_manager):
        """Returns rules with channel information."""
        _, config_data = mock_config_manager
        config_data["modules"]["notifications"]["channels"] = [
            {"id": 1, "name": "Discord", "channel_type": "discord"}
        ]
        config_data["modules"]["notifications"]["rules"] = [
            {"id": 1, "channel_id": 1, "min_severity": 2, "enabled": True}
        ]

        response = client.get("/api/notifications/rules")

        assert response.status_code == 200
        rules = response.get_json()["rules"]
        assert len(rules) == 1
        assert rules[0]["channel_name"] == "Discord"
        assert rules[0]["channel_type"] == "discord"


class TestCreateRule:
    """Tests for POST /api/notifications/rules."""

    def test_create_rule_success(self, client, mock_config_manager):
        """Creates a new rule for existing channel."""
        _, config_data = mock_config_manager
        config_data["modules"]["notifications"]["channels"] = [
            {"id": 1, "name": "Discord", "channel_type": "discord"}
        ]

        response = client.post(
            "/api/notifications/rules",
            json={
                "channel_id": 1,
                "min_severity": 2,
                "max_severity": 4,
            },
        )

        assert response.status_code == 201
        assert "id" in response.get_json()

    def test_create_rule_channel_not_found(self, client, mock_config_manager):
        """Returns error when channel doesn't exist."""
        response = client.post(
            "/api/notifications/rules", json={"channel_id": 999, "min_severity": 2}
        )

        assert response.status_code == 404

    def test_create_rule_missing_fields(self, client, mock_config_manager):
        """Returns error when required fields missing."""
        response = client.post("/api/notifications/rules", json={"channel_id": 1})

        assert response.status_code == 400


class TestUpdateRule:
    """Tests for PUT /api/notifications/rules/<id>."""

    def test_update_rule_success(self, client, mock_config_manager):
        """Updates an existing rule."""
        _, config_data = mock_config_manager
        config_data["modules"]["notifications"]["channels"] = [
            {"id": 1, "name": "Discord", "channel_type": "discord"}
        ]
        config_data["modules"]["notifications"]["rules"] = [
            {"id": 1, "channel_id": 1, "min_severity": 2, "enabled": True}
        ]

        response = client.put("/api/notifications/rules/1", json={"min_severity": 3})

        assert response.status_code == 200

    def test_update_rule_not_found(self, client, mock_config_manager):
        """Returns 404 for non-existent rule."""
        response = client.put("/api/notifications/rules/999", json={"min_severity": 3})

        assert response.status_code == 404


class TestDeleteRule:
    """Tests for DELETE /api/notifications/rules/<id>."""

    def test_delete_rule_success(self, client, mock_config_manager):
        """Deletes an existing rule."""
        _, config_data = mock_config_manager
        config_data["modules"]["notifications"]["rules"] = [
            {"id": 1, "channel_id": 1, "min_severity": 2}
        ]

        response = client.delete("/api/notifications/rules/1")

        assert response.status_code == 200

    def test_delete_rule_not_found(self, client, mock_config_manager):
        """Returns 404 for non-existent rule."""
        response = client.delete("/api/notifications/rules/999")

        assert response.status_code == 404


class TestSeverityLevels:
    """Tests for GET /api/notifications/severity_levels."""

    def test_get_severity_levels(self, client):
        """Returns severity level reference data."""
        response = client.get("/api/notifications/severity_levels")

        assert response.status_code == 200
        data = response.get_json()
        assert "levels" in data
        assert len(data["levels"]) == 4

        # Verify structure
        level = data["levels"][0]
        assert "value" in level
        assert "name" in level
        assert "description" in level
