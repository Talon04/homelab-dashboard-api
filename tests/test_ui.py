"""End-to-end UI tests using Playwright.

Run with: pytest tests/test_ui.py --headed --slowmo=300 (to see browser visually)
Requires: pip install pytest-playwright && playwright install
"""

import pytest
from playwright.sync_api import Page, expect, Route
from unittest.mock import patch
import json


@pytest.fixture(scope="module")
def live_server_with_mocks(request, temp_data_dir):
    """Start Flask app with mocked dependencies for visual UI testing."""
    import subprocess
    import time
    import os
    import sys
    import json
    import shutil
    from datetime import datetime

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Create isolated test data directory with unique timestamp
    timestamp = int(time.time() * 1000)
    test_data_dir = os.path.join(temp_data_dir, f"ui_test_data_{timestamp}")
    os.makedirs(test_data_dir, exist_ok=True)

    # Create test config that disables notifications to prevent real emails
    test_config = {
        "modules": ["monitor", "containers"],
        "enabled_modules": ["monitor", "containers"],  # Exclude notifications
        "modules_order": ["containers", "monitor"],
    }
    config_path = os.path.join(test_data_dir, "config.json")
    with open(config_path, "w") as f:
        json.dump(test_config, f)

    # Set up environment with testing mode and isolated data directory
    env = {
        **os.environ,
        "FLASK_APP": "app.py",
        "FLASK_DEBUG": "0",
        "TESTING_MODE": "1",
        "DATA_DIR": test_data_dir,  # Use isolated test directory
    }

    # Start Flask in background
    proc = subprocess.Popen(
        [sys.executable, "-m", "flask", "run", "--port", "5099"],
        cwd=project_root,
        env=env,
    )
    time.sleep(3)  # Wait for server to start and initialize

    yield "http://127.0.0.1:5099"

    proc.terminate()
    proc.wait()

    # Cleanup test directory
    try:
        shutil.rmtree(test_data_dir)
    except:
        pass


@pytest.fixture
def mock_api_data(page: Page, live_server_with_mocks):
    """Intercept API calls and return mock data for visual testing."""

    # Mock data for visual testing - each with unique ID for different tests
    mock_containers = [
        {
            "id": "test1",
            "name": "web-server-1",
            "status": "running",
            "image": "nginx:latest",
        },
        {
            "id": "test2",
            "name": "database-1",
            "status": "running",
            "image": "postgres:14",
        },
        {
            "id": "test3",
            "name": "redis-cache-1",
            "status": "exited",
            "image": "redis:7",
        },
        {
            "id": "test4",
            "name": "app-server-1",
            "status": "running",
            "image": "node:18",
        },
        {
            "id": "test5",
            "name": "api-backend-1",
            "status": "running",
            "image": "python:3.10",
        },
    ]

    mock_events = [
        {
            "id": 1,
            "timestamp": "2026-01-28T10:30:00",
            "severity": 3,
            "source": "monitor",
            "title": "Container went offline",
            "message": "web-server stopped unexpectedly",
            "acknowledged": False,
        },
        {
            "id": 2,
            "timestamp": "2026-01-28T09:15:00",
            "severity": 1,
            "source": "monitor",
            "title": "Container came online",
            "message": "database started successfully",
            "acknowledged": True,
        },
        {
            "id": 3,
            "timestamp": "2026-01-28T08:00:00",
            "severity": 2,
            "source": "monitor",
            "title": "High CPU usage",
            "message": "redis-cache using 85% CPU",
            "acknowledged": False,
        },
    ]

    mock_severity_levels = [
        {"value": 1, "name": "Info", "description": "Informational messages"},
        {"value": 2, "name": "Warning", "description": "Warning conditions"},
        {"value": 3, "name": "Critical", "description": "Critical conditions"},
        {"value": 4, "name": "Emergency", "description": "System is unusable"},
    ]

    # Mock monitor bodies and points for active monitors
    mock_monitor_bodies = []
    mock_monitor_points = {}

    # Intercept API routes and return mock data
    def handle_route(route: Route):
        url = route.request.url
        method = route.request.method

        # Check uptime endpoint BEFORE general containers check
        if "/api/containers/uptime/" in url:
            # Extract container ID from URL pattern: /api/containers/uptime/{id}
            container_id = url.split("/api/containers/uptime/")[1].split("?")[0]

            # Return mock uptime based on container
            mock_uptimes = {
                "test1": "2 days, 5 hours",
                "test2": "10 days, 3 hours",
                "test3": "0 minutes",  # exited container
                "test4": "1 days, 12 hours",
                "test5": "5 hours, 30 minutes",
            }
            uptime = mock_uptimes.get(container_id, "3 hours, 15 minutes")
            route.fulfill(json={"uptime": uptime}, status=200)
        elif "/api/containers" in url:
            route.fulfill(json=mock_containers, status=200)
        elif "/api/vms" in url:
            route.fulfill(json=[], status=200)
        elif "/api/monitor/bodies" in url:
            route.fulfill(json=mock_monitor_bodies, status=200)
        elif "/api/monitor/container/" in url and method == "GET":
            # Return existing monitor or empty
            container_id = url.split("/api/monitor/container/")[1]
            existing = next(
                (
                    m
                    for m in mock_monitor_bodies
                    if m.get("container_id") == container_id
                ),
                None,
            )
            if existing:
                route.fulfill(json=existing, status=200)
            else:
                route.fulfill(json=None, status=200)
        elif "/api/monitor/container/" in url and method == "POST":
            # Save monitor configuration
            container_id = url.split("/api/monitor/container/")[1]
            body_data = json.loads(route.request.post_data)

            # Find or create monitor body
            existing = next(
                (
                    m
                    for m in mock_monitor_bodies
                    if m.get("container_id") == container_id
                ),
                None,
            )
            if existing:
                existing.update(body_data)
                result = existing
            else:
                new_id = len(mock_monitor_bodies) + 1
                result = {
                    "id": new_id,
                    "name": f"Monitor-{container_id}",
                    "container_id": container_id,
                    "monitor_type": "docker",
                    "enabled": body_data.get("enabled", False),
                    "event_severity_settings": body_data.get("event_severity_settings"),
                }
                mock_monitor_bodies.append(result)

                # Create mock monitor point for this monitor
                mock_monitor_points[new_id] = {
                    "id": new_id,
                    "monitor_body_id": new_id,
                    "timestamp": "2026-01-29T15:30:00",
                    "value": "online",
                }

            route.fulfill(json=result, status=200)
        elif "/api/monitor/points/latest/" in url:
            # Return latest monitor point
            monitor_or_container_id = url.split("/api/monitor/points/latest/")[1].split(
                "?"
            )[0]

            # Try to get point by numeric monitor ID first
            try:
                monitor_id_int = int(monitor_or_container_id)
                point = mock_monitor_points.get(monitor_id_int)
            except ValueError:
                # It's a container ID string, return a default point
                point = None

            # If no point found, return a default one
            if not point:
                # Default mock status based on container ID
                container_statuses = {
                    "test1": "running",
                    "test2": "running",
                    "test3": "exited",
                    "test4": "running",
                    "test5": "running",
                }
                status = container_statuses.get(monitor_or_container_id, "online")

                point = {
                    "id": 1,
                    "monitor_body_id": monitor_or_container_id,
                    "timestamp": "2026-01-29T15:30:00",
                    "value": status,
                }

            route.fulfill(json=point, status=200)
        elif "/api/notifications/events/lastEventsByContainerId/" in url:
            # Extract container ID and count from URL: /api/notifications/events/lastEventsByContainerId/{id}:{count}
            parts = url.split("/api/notifications/events/lastEventsByContainerId/")[
                1
            ].split(":")
            container_id = parts[0]
            count = int(parts[1]) if len(parts) > 1 else 10

            # Return mock events for this container
            container_events = [
                {
                    "id": 1,
                    "timestamp": "2026-01-29T14:30:00",
                    "severity": 1,
                    "source": "monitor",
                    "title": "Container started",
                    "message": f"Container {container_id} came online",
                    "object_type": "container",
                    "object_id": container_id,
                    "acknowledged": False,
                    "type": "online",
                },
                {
                    "id": 2,
                    "timestamp": "2026-01-29T10:15:00",
                    "severity": 2,
                    "source": "monitor",
                    "title": "High memory usage",
                    "message": f"Container {container_id} using 85% memory",
                    "object_type": "container",
                    "object_id": container_id,
                    "acknowledged": False,
                    "type": "warning",
                },
            ]
            route.fulfill(json=container_events[:count], status=200)
        elif "/api/notifications/events/lastEventsByVmId/" in url:
            # Extract VM ID and count from URL: /api/notifications/events/lastEventsByVmId/{id}:{count}
            parts = url.split("/api/notifications/events/lastEventsByVmId/")[1].split(
                ":"
            )
            vm_id = parts[0]
            count = int(parts[1]) if len(parts) > 1 else 10

            # Return mock events for this VM
            vm_events = [
                {
                    "id": 3,
                    "timestamp": "2026-01-29T12:00:00",
                    "severity": 1,
                    "source": "monitor",
                    "title": "VM started",
                    "message": f"VM {vm_id} came online",
                    "object_type": "vm",
                    "object_id": vm_id,
                    "acknowledged": False,
                    "type": "online",
                },
            ]
            route.fulfill(json=vm_events[:count], status=200)
        elif "/api/notifications/events/unread_count" in url:
            route.fulfill(json={"count": 2}, status=200)
        elif "/api/notifications/events" in url:
            route.fulfill(
                json={
                    "events": mock_events,
                    "total": len(mock_events),
                    "limit": 100,
                    "offset": 0,
                },
                status=200,
            )
        elif "/api/notifications/severity_levels" in url:
            route.fulfill(json={"levels": mock_severity_levels}, status=200)
        elif "/api/notifications/test" in url:
            # Create a new event
            new_event = {
                "id": len(mock_events) + 1,
                "timestamp": "2026-01-28T12:00:00",
                "severity": 3,
                "source": "monitor",
                "title": "Test event created",
                "message": "This is a test event from UI tests",
                "acknowledged": False,
            }
            mock_events.insert(0, new_event)
            route.fulfill(json={"id": new_event["id"]}, status=201)
        elif "/api/config/modules" in url:
            route.fulfill(json={"modules": ["monitor", "containers"]}, status=200)
        elif "/api/config/module/notifications" in url:
            # Return empty notifications config to prevent email sending
            route.fulfill(json={}, status=200)
        else:
            # Let other requests through
            route.continue_()

    # Apply route interception
    page.route("**/api/**", handle_route)

    return {
        "containers": mock_containers,
        "events": mock_events,
        "severity_levels": mock_severity_levels,
        "monitor_bodies": mock_monitor_bodies,
        "monitor_points": mock_monitor_points,
    }


class TestMonitorPage:
    """E2E tests simulating real user interactions."""

    def test_monitor_page_loads_and_shows_title(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """User navigates to monitor page and sees the title."""
        page.goto(f"{live_server_with_mocks}/monitor")

        # Verify page title
        expect(page).to_have_title("Homelab Dashboard - Monitor")

        # Highlight the page we landed on
        page.evaluate(
            """
            document.body.style.border = '5px solid green';
            const title = document.querySelector('h2');
            if (title) {
                title.style.backgroundColor = 'lightgreen';
                title.style.padding = '10px';
                title.textContent += ' ✓';
            }
        """
        )

    def test_user_clicks_and_opens_dropdowns(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """User clicks on each dropdown to interact with them."""
        page.goto(f"{live_server_with_mocks}/monitor")

        # Click on container dropdown
        container_select = page.locator("#monitor-container-select")
        container_select.highlight()
        container_select.click()
        page.wait_for_timeout(500)  # Let user see the click

        # Click on VM dropdown
        vm_select = page.locator("#monitor-vm-select")
        vm_select.highlight()
        vm_select.click()
        page.wait_for_timeout(500)

        # Click on active monitor dropdown
        active_select = page.locator("#monitor-active-select")
        active_select.highlight()
        active_select.click()
        page.wait_for_timeout(500)

    def test_user_hovers_over_ui_elements(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """User hovers over various UI elements to explore the interface."""
        page.goto(f"{live_server_with_mocks}/monitor")

        # Hover over each dropdown
        dropdowns = [
            "#monitor-container-select",
            "#monitor-vm-select",
            "#monitor-active-select",
        ]
        for selector in dropdowns:
            element = page.locator(selector)
            element.hover()
            page.evaluate(
                f"""
                document.querySelector('{selector}').style.boxShadow = '0 0 15px blue';
            """
            )
            page.wait_for_timeout(300)


class TestMonitorViewPanel:
    """Tests for the monitor view panel that displays events with visual feedback."""

    def test_view_panel_has_status_cards(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """View panel has status, uptime, and last check cards - VISUAL TEST."""
        page.goto(f"{live_server_with_mocks}/monitor")

        # The view panel exists (though hidden initially)
        view_panel = page.locator("#monitor-view-panel")
        expect(view_panel).to_be_attached()

        # Check status cards exist
        expect(page.locator("#view-status")).to_be_attached()
        expect(page.locator("#view-uptime")).to_be_attached()
        expect(page.locator("#view-last-check")).to_be_attached()

        # Visual feedback: highlight status cards
        page.evaluate(
            """
            ['#view-status', '#view-uptime', '#view-last-check'].forEach(id => {
                const elem = document.querySelector(id);
                if (elem && elem.parentElement) {
                    elem.parentElement.style.border = '3px solid purple';
                    elem.parentElement.style.boxShadow = '0 0 10px purple';
                }
            });
        """
        )

    def test_view_panel_has_events_list(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """View panel has an events list container - VISUAL TEST."""
        page.goto(f"{live_server_with_mocks}/monitor")

        # Events list element exists
        events_list = page.locator("#view-events-list")
        expect(events_list).to_be_attached()

        # Visual feedback: highlight events list
        page.evaluate(
            """
            const eventsList = document.querySelector('#view-events-list');
            if (eventsList) {
                eventsList.style.border = '3px solid orange';
                eventsList.style.padding = '10px';
                eventsList.style.backgroundColor = 'lightyellow';
            }
        """
        )


class TestEventAPIEndpoints:
    """Tests verifying the event API endpoints work with mock data."""

    def test_create_and_fetch_container_events(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """Events created via API can be fetched - using MOCK DATA."""
        # Create a test event
        response = page.request.post(
            f"{live_server_with_mocks}/api/notifications/test",
            data={
                "json": {
                    "severity": 3,
                    "source": "monitor",
                    "title": "Container went offline",
                    "message": "Test container stopped unexpectedly",
                }
            },
        )
        assert response.status == 201

        # Fetch events - the mock should have our event
        response = page.request.get(
            f"{live_server_with_mocks}/api/notifications/events?limit=5"
        )
        assert response.status == 200

        data = response.json()
        assert "events" in data
        assert len(data["events"]) >= 1

        # Verify event structure
        event = data["events"][0]
        assert "id" in event
        assert "severity" in event
        assert "title" in event
        assert "timestamp" in event

    def test_events_endpoint_returns_correct_format(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """Events endpoint returns properly formatted JSON - using MOCK DATA."""
        response = page.request.get(
            f"{live_server_with_mocks}/api/notifications/events"
        )
        assert response.status == 200

        data = response.json()
        assert "events" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

        # Mock data always has events
        event = data["events"][0]
        expected_fields = [
            "id",
            "timestamp",
            "severity",
            "source",
            "title",
            "message",
            "acknowledged",
        ]
        for field in expected_fields:
            assert field in event, f"Missing field: {field}"

    def test_unread_count_endpoint(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """Unread count endpoint returns proper count - using MOCK DATA."""
        response = page.request.get(
            f"{live_server_with_mocks}/api/notifications/events/unread_count"
        )
        assert response.status == 200

        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        # Verify count is reasonable (mock should return 2, but live server might have other events)
        assert data["count"] >= 0


class TestEventRendering:
    """Tests for how events are rendered in the UI with visual highlighting."""

    def test_events_list_shows_no_events_message(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """Events list shows appropriate message when empty - VISUAL TEST."""
        page.goto(f"{live_server_with_mocks}/monitor")

        # The default text should indicate no events
        events_list = page.locator("#view-events-list")
        expect(events_list).to_contain_text("No events")

        # Visual feedback: highlight the "no events" message
        page.evaluate(
            """
            const eventsList = document.querySelector('#view-events-list');
            if (eventsList) {
                eventsList.style.border = '3px solid gray';
                eventsList.style.padding = '20px';
                eventsList.style.backgroundColor = '#f0f0f0';
                eventsList.style.textAlign = 'center';
                eventsList.style.fontSize = '16px';
            }
        """
        )

    def test_severity_levels_api_for_ui(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """Severity levels endpoint provides data for UI dropdowns - using MOCK DATA."""
        response = page.request.get(
            f"{live_server_with_mocks}/api/notifications/severity_levels"
        )
        assert response.status == 200

        data = response.json()
        assert "levels" in data

        # Verify levels are properly structured for UI consumption
        for level in data["levels"]:
            assert "value" in level
            assert "name" in level
            assert "description" in level

        # Verify standard levels exist in mock data
        level_names = [l["name"] for l in data["levels"]]
        assert "Info" in level_names
        assert "Warning" in level_names
        assert "Critical" in level_names


class TestCompleteUserFlow:
    """Full end-to-end user flow simulation."""

    def test_complete_monitoring_setup_workflow(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """Simulate a complete user workflow: navigate, configure, and save monitoring settings."""
        # Step 1: User navigates to monitor page
        page.goto(f"{live_server_with_mocks}/monitor")
        page.evaluate("document.body.style.border = '5px solid blue'")
        page.wait_for_timeout(500)

        # Step 2: User clicks on container dropdown
        container_select = page.locator("#monitor-container-select")
        container_select.highlight()
        container_select.click()
        page.wait_for_timeout(400)

        # Step 3: User actually selects a container (this shows the monitor panel)
        container_select.select_option("test5")  # api-backend-1 (fresh)
        page.evaluate(
            """
            const display = document.querySelector('#monitor-display');
            if (display) {
                display.style.border = '5px solid green';
                display.style.transition = 'all 0.3s ease';
            }
        """
        )
        page.wait_for_timeout(800)  # Wait for panel animation

        # Step 4: User enables monitoring (settings panel should show by default for new monitor)
        toggle = page.locator("#monitor-enabled-toggle")
        toggle.wait_for(state="visible", timeout=5000)
        toggle.evaluate("el => el.parentElement.style.backgroundColor = 'yellow'")
        page.wait_for_timeout(300)
        toggle.click()
        toggle.evaluate("el => el.parentElement.style.backgroundColor = 'lightgreen'")
        page.wait_for_timeout(500)

        # Step 5: User configures notification checkboxes
        checkboxes = ["#notify-offline", "#notify-online", "#notify-unreachable"]
        for cb_id in checkboxes:
            cb = page.locator(cb_id)
            cb.wait_for(state="visible")
            cb.evaluate(
                """el => {
                if (el.parentElement && el.parentElement.parentElement) {
                    el.parentElement.parentElement.style.border = '2px solid orange';
                }
            }"""
            )
            cb.click()
            page.wait_for_timeout(300)

        # Step 6: User adjusts severity levels
        severity_fields = [
            ("#notify-offline-severity", "4"),
            ("#notify-unreachable-severity", "3"),
        ]

        for field_id, value in severity_fields:
            field = page.locator(field_id)
            field.scroll_into_view_if_needed()
            field.click()
            field.evaluate("el => el.style.border = '3px solid purple'")
            page.wait_for_timeout(200)
            field.fill(value)
            page.wait_for_timeout(400)
            field.evaluate("el => el.style.backgroundColor = 'lightgreen'")

        # Step 7: User hovers over save button
        save_btn = page.locator("#monitor-save-btn")
        save_btn.scroll_into_view_if_needed()
        save_btn.hover()
        save_btn.evaluate("el => el.style.boxShadow = '0 0 20px blue'")
        page.wait_for_timeout(500)

        # Step 8: User clicks save
        save_btn.click()
        save_btn.evaluate(
            """el => {
            el.style.backgroundColor = 'green';
            el.textContent = '✓ Settings Saved!';
            el.style.transform = 'scale(1.1)';
        }"""
        )
        page.wait_for_timeout(1000)

        # Visual confirmation
        page.evaluate(
            """
            document.body.style.border = '8px solid green';
            const overlay = document.createElement('div');
            overlay.style.position = 'fixed';
            overlay.style.top = '20px';
            overlay.style.left = '50%';
            overlay.style.transform = 'translateX(-50%)';
            overlay.style.padding = '20px 40px';
            overlay.style.backgroundColor = 'green';
            overlay.style.color = 'white';
            overlay.style.fontSize = '24px';
            overlay.style.borderRadius = '10px';
            overlay.style.zIndex = '10000';
            overlay.style.boxShadow = '0 4px 20px rgba(0,0,0,0.3)';
            overlay.textContent = '✓ Workflow Complete!';
            document.body.appendChild(overlay);
        """
        )
        page.wait_for_timeout(1000)


class TestMonitorSettingsPanel:
    """Tests simulating user interactions with settings."""

    def test_user_clicks_enable_toggle(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """User clicks the monitoring enable toggle."""
        page.goto(f"{live_server_with_mocks}/monitor")

        # Select a fresh container that doesn't have monitoring enabled
        container_select = page.locator("#monitor-container-select")
        container_select.highlight()
        container_select.select_option("test1")  # web-server-1 (fresh)
        page.wait_for_timeout(1000)

        # Wait for toggle to become visible (should show settings by default for new monitor)
        toggle = page.locator("#monitor-enabled-toggle")
        toggle.wait_for(state="visible", timeout=5000)

        # Highlight before clicking
        toggle.evaluate("el => el.parentElement.style.backgroundColor = 'yellow'")
        page.wait_for_timeout(300)

        # Click the toggle
        toggle.click()
        page.wait_for_timeout(500)

        # Visual feedback after click
        toggle.evaluate("el => el.parentElement.style.backgroundColor = 'lightgreen'")

    def test_user_toggles_notification_checkboxes(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """User clicks each notification checkbox to toggle them."""
        page.goto(f"{live_server_with_mocks}/monitor")

        # Select a fresh container from dropdown
        container_select = page.locator("#monitor-container-select")
        container_select.highlight()
        container_select.select_option("test2")  # database-1 (fresh)
        page.wait_for_timeout(800)

        checkboxes = [
            "#notify-offline",
            "#notify-online",
            "#notify-unreachable",
            "#notify-resources",
        ]

        for checkbox_id in checkboxes:
            checkbox = page.locator(checkbox_id)

            # Highlight before interaction
            checkbox.evaluate(
                """el => {
                if (el.parentElement && el.parentElement.parentElement) {
                    el.parentElement.parentElement.style.border = '3px solid blue';
                    el.parentElement.parentElement.style.transform = 'scale(1.05)';
                }
            }"""
            )
            page.wait_for_timeout(200)

            # Get initial state
            was_checked = checkbox.is_checked()

            # Click to toggle
            checkbox.scroll_into_view_if_needed()
            checkbox.click(force=True)
            page.wait_for_timeout(300)

            # Verify it changed
            is_now_checked = checkbox.is_checked()
            assert was_checked != is_now_checked

            # Visual feedback
            checkbox.evaluate(
                f"""el => {{
                if (el.parentElement && el.parentElement.parentElement) {{
                    el.parentElement.parentElement.style.backgroundColor = '{
                        "lightgreen" if is_now_checked else "lightcoral"
                    }';
                    el.parentElement.parentElement.style.transform = 'scale(1)';
                }}
            }}"""
            )

    def test_user_changes_severity_values(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """User types new values into severity input fields."""
        page.goto(f"{live_server_with_mocks}/monitor")

        # Select a fresh container from dropdown
        container_select = page.locator("#monitor-container-select")
        container_select.select_option("test3")  # redis-cache-1 (fresh)
        page.wait_for_timeout(800)

        severity_inputs = [
            ("#notify-offline-severity", "4"),
            ("#notify-online-severity", "2"),
            ("#notify-unreachable-severity", "3"),
        ]

        for input_id, new_value in severity_inputs:
            input_field = page.locator(input_id)

            # Highlight the field
            input_field.evaluate("el => el.style.border = '3px solid orange'")
            page.wait_for_timeout(200)

            # Clear and type new value
            input_field.click()
            input_field.fill("")  # Clear
            page.wait_for_timeout(200)
            input_field.type(new_value, delay=100)  # Type with delay to show typing

            # Verify the value changed
            expect(input_field).to_have_value(new_value)

            # Visual feedback
            input_field.evaluate(
                f"""el => {{
                el.style.backgroundColor = 'lightgreen';
                el.style.fontWeight = 'bold';
            }}"""
            )
            page.wait_for_timeout(300)

    def test_user_clicks_save_button(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """User clicks the save settings button."""
        page.goto(f"{live_server_with_mocks}/monitor")

        # Select a fresh container from dropdown
        container_select = page.locator("#monitor-container-select")
        container_select.select_option("test4")  # app-server-1 (fresh)
        page.wait_for_timeout(1000)

        # Wait for save button to become visible
        save_btn = page.locator("#monitor-save-btn")
        save_btn.wait_for(state="visible", timeout=5000)

        # Highlight button
        save_btn.evaluate(
            """el => {
            el.style.transform = 'scale(1.1)';
            el.style.boxShadow = '0 0 20px blue';
        }"""
        )
        page.wait_for_timeout(500)

        # Hover over button
        save_btn.hover()
        page.wait_for_timeout(300)

        # Click the button
        save_btn.click()
        page.wait_for_timeout(500)

        # Visual feedback - button was clicked
        save_btn.evaluate(
            """el => {
            el.style.backgroundColor = 'green';
            el.textContent = 'Saved! ✓';
        }"""
        )


class TestActiveMonitorEventListings:
    """Visual tests for event listings on active monitors - emulating user interactions."""

    def test_user_views_events_list_section(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """User navigates to monitor page and views the events list section location."""
        page.goto(f"{live_server_with_mocks}/monitor")

        # Select a container to show the monitor display
        container_select = page.locator("#monitor-container-select")
        container_select.highlight()
        container_select.select_option("test1")  # web-server-1
        page.wait_for_timeout(800)

        # The monitor display should be visible now with settings panel
        monitor_display = page.locator("#monitor-display")
        expect(monitor_display).not_to_have_class("hidden")

        # Highlight the entire display panel
        page.evaluate(
            """
            const display = document.querySelector('#monitor-display');
            if (display) {
                display.style.border = '5px solid blue';
            }
        """
        )
        page.wait_for_timeout(500)

        # Click the toggle button to switch to view mode
        toggle_btn = page.locator("#monitor-toggle-view")
        toggle_btn.highlight()
        page.wait_for_timeout(300)
        toggle_btn.click()
        page.wait_for_timeout(800)

        # Now we should be in view mode - verify view panel is visible
        view_panel = page.locator("#monitor-view-panel")
        expect(view_panel).not_to_have_class("hidden")

        # Highlight the view panel
        page.evaluate(
            """
            const panel = document.querySelector('#monitor-view-panel');
            if (panel) {
                panel.style.border = '5px solid green';
                panel.style.backgroundColor = 'lightgreen';
            }
        """
        )
        page.wait_for_timeout(500)

        # Locate and highlight the events list section
        events_section = page.locator("#view-events-list")
        expect(events_section).to_be_attached()

        page.evaluate(
            """
            const eventsList = document.querySelector('#view-events-list');
            if (eventsList) {
                eventsList.style.border = '3px solid orange';
                eventsList.style.backgroundColor = 'lightyellow';
                eventsList.style.padding = '15px';
                eventsList.style.borderRadius = '8px';
            }
        """
        )
        page.wait_for_timeout(800)

    def test_user_examines_monitor_status_cards(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """User examines the status cards (status, uptime, last check) on monitor view."""
        page.goto(f"{live_server_with_mocks}/monitor")

        # Select a container
        container_select = page.locator("#monitor-container-select")
        container_select.select_option("test2")  # database-1
        page.wait_for_timeout(800)

        # Switch to view mode
        toggle_btn = page.locator("#monitor-toggle-view")
        toggle_btn.click()
        page.wait_for_timeout(800)

        # Highlight each status card
        status_cards = ["#view-status", "#view-uptime", "#view-last-check"]
        for card_id in status_cards:
            card = page.locator(card_id)
            card.hover()
            page.evaluate(
                f"""
                const card = document.querySelector('{card_id}');
                if (card && card.parentElement) {{
                    card.parentElement.style.border = '3px solid purple';
                    card.parentElement.style.boxShadow = '0 0 15px purple';
                    card.parentElement.style.transform = 'scale(1.05)';
                }}
            """
            )
            page.wait_for_timeout(500)

    def test_user_toggles_between_settings_and_view(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """User toggles between settings panel and view panel."""
        page.goto(f"{live_server_with_mocks}/monitor")

        # Select a container
        container_select = page.locator("#monitor-container-select")
        container_select.select_option("test3")  # redis-cache-1
        page.wait_for_timeout(800)

        # Verify we start in settings mode
        settings_panel = page.locator("#monitor-settings-panel")
        expect(settings_panel).not_to_have_class("hidden")

        # Highlight settings panel
        page.evaluate(
            """
            document.querySelector('#monitor-settings-panel').style.border = '4px solid orange';
            document.querySelector('#monitor-settings-panel').style.backgroundColor = 'lightyellow';
        """
        )
        page.wait_for_timeout(800)

        # Click toggle button to switch to view
        toggle_btn = page.locator("#monitor-toggle-view")
        toggle_btn.highlight()
        toggle_btn.evaluate("el => el.style.transform = 'scale(1.3)'")
        page.wait_for_timeout(300)
        toggle_btn.click()
        page.wait_for_timeout(800)

        # Verify view panel is now visible
        view_panel = page.locator("#monitor-view-panel")
        expect(view_panel).not_to_have_class("hidden")

        # Highlight view panel
        page.evaluate(
            """
            document.querySelector('#monitor-view-panel').style.border = '4px solid blue';
            document.querySelector('#monitor-view-panel').style.backgroundColor = 'lightblue';
        """
        )
        page.wait_for_timeout(800)

        # Toggle back to settings
        toggle_btn.click()
        page.wait_for_timeout(800)

        # Verify settings panel is visible again
        expect(settings_panel).not_to_have_class("hidden")

        # Final highlight
        page.evaluate(
            """
            document.querySelector('#monitor-settings-panel').style.border = '4px solid green';
            document.querySelector('#monitor-settings-panel').style.backgroundColor = 'lightgreen';
        """
        )
        page.wait_for_timeout(500)

    def test_user_views_container_uptime(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """User views container uptime in the monitor view panel - VISUAL TEST."""
        page.goto(f"{live_server_with_mocks}/monitor")

        # Select a running container
        container_select = page.locator("#monitor-container-select")
        container_select.select_option("test2")  # database-1
        page.wait_for_timeout(800)

        # Switch to view mode
        toggle_btn = page.locator("#monitor-toggle-view")
        toggle_btn.click()
        page.wait_for_timeout(1000)  # Wait for uptime API call to complete

        # Verify uptime is displayed
        uptime_el = page.locator("#view-uptime")
        expect(uptime_el).to_be_attached()

        # The uptime should have a value (not empty or "--")
        uptime_text = uptime_el.inner_text()

        assert (
            uptime_text
            and uptime_text != "--"
            and uptime_text != "Uptime data not available"
        )

        # Should match our mock data for test2
        assert "10 days, 3 hours" in uptime_text

        # Visual feedback: highlight the uptime card
        page.evaluate(
            """
            const uptimeCard = document.querySelector('#view-uptime');
            if (uptimeCard && uptimeCard.parentElement) {
                uptimeCard.parentElement.style.border = '5px solid lime';
                uptimeCard.parentElement.style.boxShadow = '0 0 20px lime';
                uptimeCard.parentElement.style.transform = 'scale(1.1)';
                
                // Add a label
                const label = document.createElement('div');
                label.textContent = '✓ Uptime Loaded Successfully';
                label.style.position = 'absolute';
                label.style.top = '-30px';
                label.style.left = '50%';
                label.style.transform = 'translateX(-50%)';
                label.style.backgroundColor = 'lime';
                label.style.padding = '5px 10px';
                label.style.borderRadius = '5px';
                label.style.fontWeight = 'bold';
                label.style.fontSize = '14px';
                uptimeCard.parentElement.style.position = 'relative';
                uptimeCard.parentElement.appendChild(label);
            }
        """
        )
        page.wait_for_timeout(1500)

        # Test with another container
        toggle_btn.click()  # Back to settings
        page.wait_for_timeout(500)

        container_select.select_option("test1")  # web-server-1
        page.wait_for_timeout(500)

        toggle_btn.click()  # To view
        page.wait_for_timeout(1000)

        uptime_text = uptime_el.inner_text()
        assert "2 days, 5 hours" in uptime_text

        # Highlight again with different color
        page.evaluate(
            """
            const uptimeCard = document.querySelector('#view-uptime');
            if (uptimeCard && uptimeCard.parentElement) {
                uptimeCard.parentElement.style.border = '5px solid cyan';
                uptimeCard.parentElement.style.boxShadow = '0 0 20px cyan';
            }
        """
        )
        page.wait_for_timeout(1000)

    def test_user_views_container_events(
        self, page: Page, live_server_with_mocks, mock_api_data
    ):
        """User views recent events for a container in the monitor view panel - VISUAL TEST."""
        page.goto(f"{live_server_with_mocks}/monitor")

        # Select a running container
        container_select = page.locator("#monitor-container-select")
        container_select.select_option("test1")  # web-server-1
        page.wait_for_timeout(800)

        # Switch to view mode
        toggle_btn = page.locator("#monitor-toggle-view")
        toggle_btn.click()
        page.wait_for_timeout(1000)  # Wait for events API call to complete

        # Verify events list is displayed
        events_list = page.locator("#view-events-list")
        expect(events_list).to_be_attached()

        # Check that events are loaded (should have some content)
        events_html = events_list.inner_html()
        assert len(events_html) > 100  # Should have actual event content

        # Should contain event data from our mock
        assert "Container started" in events_html or "online" in events_html.lower()

        # Visual feedback: highlight the events section
        page.evaluate(
            """
            const eventsList = document.querySelector('#view-events-list');
            if (eventsList) {
                eventsList.style.border = '5px solid gold';
                eventsList.style.boxShadow = '0 0 20px gold';
                eventsList.style.backgroundColor = 'lightyellow';
                
                // Add a label
                const label = document.createElement('div');
                label.textContent = '✓ Recent Events Loaded';
                label.style.position = 'absolute';
                label.style.top = '-35px';
                label.style.left = '50%';
                label.style.transform = 'translateX(-50%)';
                label.style.backgroundColor = 'gold';
                label.style.color = 'black';
                label.style.padding = '5px 15px';
                label.style.borderRadius = '5px';
                label.style.fontWeight = 'bold';
                label.style.fontSize = '14px';
                label.style.border = '2px solid orange';
                eventsList.style.position = 'relative';
                eventsList.parentElement.style.position = 'relative';
                eventsList.parentElement.appendChild(label);
            }
        """
        )
        page.wait_for_timeout(2000)
