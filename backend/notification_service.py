"""Background service for delivering notifications through configured channels.

This service periodically checks for undelivered events and sends them
through the appropriate channels based on configured rules.
"""

import smtplib
import ssl
import json
import threading
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List, Optional, Any

from backend.models import DatabaseManager, Event, EventDelivery
from backend.config_manager import config_manager


# Background thread handle
_worker_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()

# Check interval in seconds
CHECK_INTERVAL = 10


def _get_notification_config() -> Dict:
    """Get the notifications module config."""
    return config_manager.get("modules", {}).get("notifications", {})


def _get_channels() -> List[Dict]:
    """Get all notification channels from config."""
    return _get_notification_config().get("channels", [])


def _get_rules() -> List[Dict]:
    """Get all notification rules from config."""
    return _get_notification_config().get("rules", [])


def _get_db() -> DatabaseManager:
    """Get database manager instance."""
    return DatabaseManager()


def _get_matching_channels(severity: int) -> List[Dict]:
    """Get all enabled channels that should receive events of the given severity."""
    channels = _get_channels()
    rules = _get_rules()

    # Build channel lookup
    channel_map = {c["id"]: c for c in channels if c.get("enabled", True)}

    matching_channel_ids = set()
    for rule in rules:
        if not rule.get("enabled", True):
            continue

        min_sev = rule.get("min_severity", 1)
        max_sev = rule.get("max_severity")

        # Check if severity falls within rule range
        if severity >= min_sev:
            if max_sev is None or severity <= max_sev:
                channel_id = rule.get("channel_id")
                if channel_id in channel_map:
                    matching_channel_ids.add(channel_id)

    return [channel_map[cid] for cid in matching_channel_ids]


# ─────────────────────────────────────────────────────────────────────────────
# Email Delivery (SMTP)
# ─────────────────────────────────────────────────────────────────────────────


def send_email(channel_config: Dict, event: Event) -> Dict[str, Any]:
    """Send notification via email using SMTP.

    Gmail-compatible config example:
    {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "use_tls": true,
        "username": "your-email@gmail.com",
        "password": "your-app-password",
        "from_email": "your-email@gmail.com",
        "to_email": "recipient@example.com"
    }

    For Gmail, you need to use an App Password:
    1. Enable 2FA on your Google account
    2. Go to https://myaccount.google.com/apppasswords
    3. Generate an app password for "Mail"
    """
    try:
        smtp_server = channel_config.get("smtp_server", "smtp.gmail.com")
        smtp_port = channel_config.get("smtp_port", 587)
        use_tls = channel_config.get("use_tls", True)
        use_ssl = channel_config.get("use_ssl", False)
        username = channel_config.get("username", "")
        password = channel_config.get("password", "")
        from_email = channel_config.get("from_email", username)
        to_email = channel_config.get("to_email", "")

        if not to_email:
            return {"success": False, "error": "No recipient email configured"}

        # Severity labels
        severity_names = {1: "Info", 2: "Warning", 3: "Critical", 4: "Emergency"}
        severity_label = severity_names.get(event.severity, f"Level {event.severity}")

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{severity_label}] {event.title}"
        msg["From"] = from_email
        msg["To"] = to_email

        # Plain text version
        text_body = f"""
Homelab Dashboard Notification
==============================

Severity: {severity_label} (Level {event.severity})
Source: {event.source}
Time: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S') if event.timestamp else 'Unknown'}

Title: {event.title}

Message:
{event.message}
"""

        # HTML version
        severity_colors = {
            1: "#3B82F6",  # blue
            2: "#F59E0B",  # yellow/amber
            3: "#EF4444",  # red
            4: "#8B5CF6",  # purple
        }
        color = severity_colors.get(event.severity, "#EC4899")  # pink for unknown

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: {color}; color: white; padding: 15px 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9fafb; padding: 20px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px; }}
        .meta {{ color: #6b7280; font-size: 14px; margin-bottom: 15px; }}
        .message {{ background: white; padding: 15px; border-radius: 6px; border: 1px solid #e5e7eb; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2 style="margin: 0;">{event.title}</h2>
            <p style="margin: 5px 0 0 0; opacity: 0.9;">{severity_label} • {event.source}</p>
        </div>
        <div class="content">
            <div class="meta">
                <strong>Time:</strong> {event.timestamp.strftime('%Y-%m-%d %H:%M:%S') if event.timestamp else 'Unknown'}
            </div>
            <div class="message">
                {event.message}
            </div>
        </div>
    </div>
</body>
</html>
"""

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        # Send email
        context = ssl.create_default_context()

        if use_ssl:
            # SSL from the start (port 465)
            with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
                if username and password:
                    server.login(username, password)
                server.sendmail(from_email, to_email, msg.as_string())
        else:
            # STARTTLS (port 587)
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if use_tls:
                    server.starttls(context=context)
                if username and password:
                    server.login(username, password)
                server.sendmail(from_email, to_email, msg.as_string())

        return {"success": True}

    except smtplib.SMTPAuthenticationError as e:
        return {"success": False, "error": f"SMTP authentication failed: {e}"}
    except smtplib.SMTPException as e:
        return {"success": False, "error": f"SMTP error: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Discord Webhook Delivery
# ─────────────────────────────────────────────────────────────────────────────


def send_discord(channel_config: Dict, event: Event) -> Dict[str, Any]:
    """Send notification via Discord webhook.

    Config example:
    {
        "webhook_url": "https://discord.com/api/webhooks/..."
    }
    """
    try:
        import urllib.request
        import urllib.error

        webhook_url = channel_config.get("webhook_url", "")
        if not webhook_url:
            return {"success": False, "error": "No webhook URL configured"}

        severity_names = {1: "Info", 2: "Warning", 3: "Critical", 4: "Emergency"}
        severity_label = severity_names.get(event.severity, f"Level {event.severity}")

        severity_colors = {
            1: 0x3B82F6,  # blue
            2: 0xF59E0B,  # yellow
            3: 0xEF4444,  # red
            4: 0x8B5CF6,  # purple
        }
        color = severity_colors.get(event.severity, 0xEC4899)  # pink

        payload = {
            "embeds": [
                {
                    "title": event.title,
                    "description": event.message,
                    "color": color,
                    "fields": [
                        {"name": "Severity", "value": severity_label, "inline": True},
                        {"name": "Source", "value": event.source, "inline": True},
                    ],
                    "timestamp": (
                        event.timestamp.isoformat() if event.timestamp else None
                    ),
                    "footer": {"text": "Homelab Dashboard"},
                }
            ]
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status in (200, 204):
                return {"success": True}
            return {
                "success": False,
                "error": f"Discord returned status {response.status}",
            }

    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"Discord HTTP error: {e.code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Generic Webhook Delivery
# ─────────────────────────────────────────────────────────────────────────────


def send_webhook(channel_config: Dict, event: Event) -> Dict[str, Any]:
    """Send notification via generic webhook.

    Config example:
    {
        "url": "https://example.com/webhook",
        "method": "POST",
        "headers": {"Authorization": "Bearer token"}
    }
    """
    try:
        import urllib.request
        import urllib.error

        url = channel_config.get("url", "")
        if not url:
            return {"success": False, "error": "No webhook URL configured"}

        method = channel_config.get("method", "POST").upper()
        headers = channel_config.get("headers", {})
        headers["Content-Type"] = "application/json"

        payload = {
            "event_id": event.id,
            "title": event.title,
            "message": event.message,
            "severity": event.severity,
            "source": event.source,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status < 300:
                return {"success": True}
            return {
                "success": False,
                "error": f"Webhook returned status {response.status}",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Delivery Dispatcher
# ─────────────────────────────────────────────────────────────────────────────


DELIVERY_HANDLERS = {
    "email": send_email,
    "discord": send_discord,
    "webhook": send_webhook,
}


def deliver_to_channel(channel: Dict, event: Event) -> Dict[str, Any]:
    """Deliver an event to a specific channel."""
    channel_type = channel.get("channel_type", "")
    config = channel.get("config", {})

    # Parse config if it's a string
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except json.JSONDecodeError:
            config = {}

    handler = DELIVERY_HANDLERS.get(channel_type)
    if not handler:
        return {"success": False, "error": f"Unknown channel type: {channel_type}"}

    return handler(config, event)


def record_delivery(
    session,
    event_id: int,
    channel_id: int,
    success: bool,
    error_message: Optional[str] = None,
) -> None:
    """Record a delivery attempt in the database."""
    delivery = EventDelivery(
        event_id=event_id,
        channel_id=channel_id,
        last_attempt=datetime.utcnow() if success else None,
        status="delivered" if success else "failed",
        error=error_message,
    )
    session.add(delivery)


# ─────────────────────────────────────────────────────────────────────────────
# Main Worker Loop
# ─────────────────────────────────────────────────────────────────────────────


def process_pending_events() -> int:
    """Process all undelivered events. Returns count of deliveries attempted."""
    db = _get_db()
    session = db.get_session()
    delivery_count = 0

    try:
        # Get all unacknowledged events that haven't been processed
        # We'll use EventDelivery to track what's been sent where
        events = (
            session.query(Event)
            .filter(Event.acknowledged == False)
            .order_by(Event.timestamp.asc())
            .limit(50)
            .all()
        )

        for event in events:
            # Get channels that match this event's severity
            matching_channels = _get_matching_channels(event.severity)

            if not matching_channels:
                continue

            for channel in matching_channels:
                channel_id = channel.get("id")

                # Check if we've already delivered to this channel (check each time to avoid races)
                existing = (
                    session.query(EventDelivery)
                    .filter(
                        EventDelivery.event_id == event.id,
                        EventDelivery.channel_id == channel_id,
                    )
                    .first()
                )
                if existing:
                    continue  # Already attempted delivery to this channel

                # Attempt delivery
                result = deliver_to_channel(channel, event)
                record_delivery(
                    session,
                    event.id,
                    channel_id,
                    result["success"],
                    result.get("error"),
                )
                # Commit immediately after each delivery to prevent duplicates
                session.commit()
                delivery_count += 1

                if result["success"]:
                    print(
                        f"[notification_service] Delivered event {event.id} to channel {channel.get('name')}"
                    )
                else:
                    print(
                        f"[notification_service] Failed to deliver event {event.id} to channel {channel.get('name')}: {result.get('error')}"
                    )

    except Exception as e:
        print(f"[notification_service] Error processing events: {e}")
        session.rollback()
    finally:
        db.close_session(session)

    return delivery_count


def _worker_loop():
    """Background worker loop."""
    print("[notification_service] Worker started")

    while not _stop_event.is_set():
        try:
            process_pending_events()
        except Exception as e:
            print(f"[notification_service] Worker error: {e}")

        # Wait for next check interval or stop signal
        _stop_event.wait(timeout=CHECK_INTERVAL)

    print("[notification_service] Worker stopped")


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def start_notification_service():
    """Start the notification delivery background service."""
    global _worker_thread

    # Check if notifications module is enabled
    enabled_modules = config_manager.get("enabled_modules", [])
    if "notifications" not in enabled_modules:
        print(
            "[notification_service] Notifications module not enabled, skipping service start"
        )
        return

    if _worker_thread is not None and _worker_thread.is_alive():
        print("[notification_service] Service already running")
        return

    _stop_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()
    print("[notification_service] Service started")


def stop_notification_service():
    """Stop the notification delivery background service."""
    global _worker_thread

    if _worker_thread is None or not _worker_thread.is_alive():
        return

    _stop_event.set()
    _worker_thread.join(timeout=5)
    _worker_thread = None
    print("[notification_service] Service stopped")


def is_service_running() -> bool:
    """Check if the notification service is running."""
    return _worker_thread is not None and _worker_thread.is_alive()
