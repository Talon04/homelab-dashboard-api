"""Database models for the homelab dashboard.

Defines SQLAlchemy ORM models for:
- Containers and VMs (infrastructure)
- Monitoring configuration
- Events and delivery tracking
- Notification channels and rules
"""

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

from backend.paths import DATA_DIR

Base = declarative_base()


# =============================================================================
# Infrastructure Models
# =============================================================================


class Container(Base):
    """Docker container tracked by the dashboard."""

    __tablename__ = "containers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    docker_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    image = Column(String, nullable=False)
    status = Column(String, nullable=False)
    preferred_port = Column(String, nullable=True)
    internal_link_body = Column(Text, nullable=True)
    external_link_body = Column(Text, nullable=True)
    is_exposed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ports = relationship(
        "ContainerPort", back_populates="container", cascade="all, delete-orphan"
    )
    widgets = relationship(
        "ContainerWidget", back_populates="container", cascade="all, delete-orphan"
    )


class ContainerPort(Base):
    """Port mapping for a container."""

    __tablename__ = "container_ports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    container_id = Column(Integer, ForeignKey("containers.id"), nullable=False)
    internal_port = Column(Integer, nullable=False)
    external_port = Column(Integer, nullable=True)
    protocol = Column(String, default="tcp")

    container = relationship("Container", back_populates="ports")


class VM(Base):
    """Virtual machine tracked by the dashboard (Proxmox integration)."""

    __tablename__ = "vms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    proxmox_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False)
    cpu_cores = Column(Integer, nullable=True)
    memory_mb = Column(Integer, nullable=True)
    disk_gb = Column(Integer, nullable=True)
    ip_address = Column(String, nullable=True)
    preferred_port = Column(String, nullable=True)
    internal_link_body = Column(Text, nullable=True)
    external_link_body = Column(Text, nullable=True)
    is_exposed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ContainerWidget(Base):
    """Custom widget attached to a container in the UI."""

    __tablename__ = "container_widgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    container_id = Column(Integer, ForeignKey("containers.id"), nullable=False)
    type = Column(String, nullable=False)  # text | button
    size = Column(String, default="md")  # sm | md | lg
    label = Column(String, nullable=True)
    text = Column(Text, nullable=True)
    file_path = Column(String, nullable=True)
    update_interval = Column(Integer, nullable=True)  # seconds, None = no auto-refresh
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    container = relationship("Container", back_populates="widgets")


# =============================================================================
# Monitoring Models
# =============================================================================


class MonitorBodies(Base):
    """Monitor configuration entry for a container or VM."""

    __tablename__ = "monitor_bodies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    container_id = Column(Integer, ForeignKey("containers.id"), nullable=True)
    vm_id = Column(Integer, ForeignKey("vms.id"), nullable=True)
    monitor_type = Column(String, nullable=False)  # container | vm
    enabled = Column(Boolean, default=True)
    event_severity_settings = Column(Text, nullable=True)  # JSON config


class MonitorPoints(Base):
    """Historical monitoring data point."""

    __tablename__ = "monitor_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    monitor_body_id = Column(Integer, ForeignKey("monitor_bodies.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    value = Column(String, nullable=False)  # online | offline | unknown


# =============================================================================
# Event System Models
# =============================================================================


class Event(Base):
    """System event that can trigger notifications."""

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    severity = Column(Integer, nullable=False)  # 1=info, 2=warning, 3=critical, etc.
    source = Column(String, nullable=False)  # monitor | script | docker | system
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    object_type = Column(String, nullable=True)  # container | vm | monitor | script
    object_id = Column(Integer, nullable=True)
    fingerprint = Column(String, nullable=False)  # for deduplication
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime, nullable=True)


class EventDelivery(Base):
    """Tracks delivery of an event to a notification channel."""

    __tablename__ = "event_deliveries"

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("notification_channels.id"), nullable=False)
    status = Column(String, default="pending")  # pending | sent | failed
    last_attempt = Column(DateTime)
    error = Column(Text, nullable=True)


# =============================================================================
# Notification Channel Models
# =============================================================================


class NotificationChannel(Base):
    """Configuration for a notification delivery channel (Discord, email, etc.)."""

    __tablename__ = "notification_channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    channel_type = Column(String, nullable=False)  # discord | push | email | webhook
    enabled = Column(Boolean, default=True)
    config = Column(
        Text, nullable=True
    )  # JSON config (webhook_url, smtp settings, etc.)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotificationRule(Base):
    """Maps event severity levels to notification channels."""

    __tablename__ = "notification_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(Integer, ForeignKey("notification_channels.id"), nullable=False)
    min_severity = Column(
        Integer, nullable=False
    )  # events >= min_severity use this channel
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# =============================================================================
# Database Management
# =============================================================================


class DatabaseManager:
    """Handles database connection and session management."""

    def __init__(self, db_path=None):
        """Initialize the database manager.

        Args:
            db_path: Optional custom path for the SQLite database.
                     Defaults to DATA_DIR/data.db.
        """
        if db_path is None:
            os.makedirs(DATA_DIR, exist_ok=True)
            db_path = os.path.join(DATA_DIR, "data.db")
        else:
            abs_path = os.path.abspath(db_path)
            dir_name = os.path.dirname(abs_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            db_path = abs_path

        self.db_url = f"sqlite:///{db_path}"
        self.engine = create_engine(self.db_url, echo=False)
        self.Session = sessionmaker(bind=self.engine)

        Base.metadata.create_all(self.engine)

    def get_session(self):
        """Get a new database session."""
        return self.Session()

    def close_session(self, session):
        """Close a database session."""
        if session:
            session.close()
