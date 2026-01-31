"""Database management service - handles routine database maintenance.

Runs background tasks for database health:
- Cleanup of old data based on retention policy
- Runs daily and on application startup
- Always enabled (not a module)
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from backend.save_manager import get_save_manager
from backend.config_manager import config_manager

try:
    from backend.models import MonitorPoints, Event, EventDelivery
except Exception:
    MonitorPoints = None  # type: ignore
    Event = None  # type: ignore
    EventDelivery = None  # type: ignore


_worker_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()

# Run cleanup once per day (86400 seconds)
CLEANUP_INTERVAL = 86400


# =============================================================================
# Cleanup Functions
# =============================================================================


def cleanup_old_data():
    """Delete records older than retention_days from config.
    
    Removes old data from:
    - monitor_points (monitoring history)
    - events (system events)
    - event_deliveries (delivery tracking)
    """
    retention_days = config_manager.get("retention_days", 30)
    
    if retention_days <= 0:
        print("[management] Data retention disabled (retention_days <= 0)")
        return
    
    cutoff = datetime.now() - timedelta(days=retention_days)
    save_manager = get_save_manager()
    
    try:
        with save_manager.get_db_session() as session:
            # Delete old monitoring points
            if MonitorPoints:
                deleted_points = session.query(MonitorPoints).filter(
                    MonitorPoints.timestamp < cutoff
                ).delete()
                print(f"[management] Deleted {deleted_points} monitoring points older than {retention_days} days")
            
            # Delete old events
            if Event:
                deleted_events = session.query(Event).filter(
                    Event.timestamp < cutoff
                ).delete()
                print(f"[management] Deleted {deleted_events} events older than {retention_days} days")
            
            # Delete old event deliveries
            if EventDelivery:
                deleted_deliveries = session.query(EventDelivery).filter(
                    EventDelivery.last_attempt < cutoff
                ).delete()
                print(f"[management] Deleted {deleted_deliveries} event deliveries older than {retention_days} days")
        
        print(f"[management] Cleanup complete - kept last {retention_days} days of data")
    except Exception as e:
        print(f"[management] Error during cleanup: {e}")


# =============================================================================
# Service Control
# =============================================================================


def _management_worker():
    """Background worker that runs cleanup tasks daily."""
    print("[management] Management service worker started")
    
    # Run cleanup immediately on startup
    cleanup_old_data()
    
    # Then run daily
    while not _stop_event.is_set():
        # Wait for 24 hours or until stop event
        if _stop_event.wait(timeout=CLEANUP_INTERVAL):
            break
        
        # Run cleanup
        cleanup_old_data()
    
    print("[management] Management service worker stopped")


def start_management_service():
    """Start the management service background thread."""
    global _worker_thread
    
    if _worker_thread is not None and _worker_thread.is_alive():
        print("[management] Management service already running")
        return
    
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_management_worker, daemon=True)
    _worker_thread.start()
    print("[management] Management service started")


def stop_management_service():
    """Stop the management service background thread."""
    global _worker_thread
    
    if _worker_thread is None or not _worker_thread.is_alive():
        print("[management] Management service not running")
        return
    
    print("[management] Stopping management service...")
    _stop_event.set()
    _worker_thread.join(timeout=5)
    _worker_thread = None
    print("[management] Management service stopped")


def is_running() -> bool:
    """Check if the management service is currently running."""
    return _worker_thread is not None and _worker_thread.is_alive()
