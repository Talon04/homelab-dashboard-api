"""Database models for homelab dashboard."""

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

from paths import DATA_DIR

Base = declarative_base()


class Container(Base):
    """Model for Docker containers"""

    __tablename__ = "containers"

    id = Column(Integer, primary_key=True, autoincrement=True)  # internal DB ID
    docker_id = Column(String, unique=True, nullable=False)  # Docker container ID
    name = Column(String, nullable=False)
    image = Column(String, nullable=False)
    status = Column(String, nullable=False)
    preferred_port = Column(String, nullable=True)
    internal_link_body = Column(Text, nullable=True)
    external_link_body = Column(Text, nullable=True)
    is_exposed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to container ports
    ports = relationship(
        "ContainerPort", back_populates="container", cascade="all, delete-orphan"
    )
    # Relationship to widgets
    widgets = relationship(
        "ContainerWidget", back_populates="container", cascade="all, delete-orphan"
    )


class ContainerPort(Base):
    """Model for container port mappings"""

    __tablename__ = "container_ports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    container_id = Column(Integer, ForeignKey("containers.id"), nullable=False)
    internal_port = Column(Integer, nullable=False)
    external_port = Column(Integer, nullable=True)
    protocol = Column(String, default="tcp")

    # Relationship back to container
    container = relationship("Container", back_populates="ports")


class VM(Base):
    """Model for Virtual Machines (future feature)"""

    __tablename__ = "vms"

    id = Column(Integer, primary_key=True, autoincrement=True)  # internal DB ID
    proxmox_id = Column(
        String, unique=True, nullable=False
    )  # VM identifier from Proxmox
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
    """Widgets attached to a container box in UI"""

    __tablename__ = "container_widgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    container_id = Column(Integer, ForeignKey("containers.id"), nullable=False)
    type = Column(String, nullable=False)  # 'text' | 'button'
    size = Column(String, default="md")  # 'sm' | 'md' | 'lg'
    label = Column(String, nullable=True)  # for buttons
    text = Column(Text, nullable=True)  # for text widgets
    file_path = Column(String, nullable=True)  # associated script file under user_code
    update_interval = Column(
        Integer, nullable=True
    )  # seconds between auto-refresh for text widgets (None = no auto-refresh)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    container = relationship("Container", back_populates="widgets")


class MonitorData(Base):
    """Model for monitor configuration entries ("monitor_bodies")."""

    __tablename__ = "monitor_bodies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    container_id = Column(Integer, ForeignKey("containers.id"), nullable=True)
    vm_id = Column(Integer, ForeignKey("vms.id"), nullable=True)
    monitor_type = Column(
        String, nullable=False
    )  # monitoring types, like 'docker','tcp', 'ping'
    notification_type = Column(String, nullable=False)  # 'mail', 'push', etc.
    enabled = Column(Boolean, default=True)


class MonitorPoints(Base):
    """Model for monitoring data points"""

    __tablename__ = "monitor_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    monitor_data_id = Column(Integer, ForeignKey("monitor_bodies.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    value = Column(String, nullable=False)  # e.g. went offline/online/unknown


class DatabaseManager:
    """Database connection and session management"""

    def __init__(self, db_path=None):
        # If no explicit path is provided, place the DB under the shared
        # data directory used by the rest of the app.
        if db_path is None:
            os.makedirs(DATA_DIR, exist_ok=True)
            db_path = os.path.join(DATA_DIR, "data.db")
        else:
            # Ensure the target directory exists for custom paths as well,
            # otherwise SQLite raises "unable to open database file".
            abs_path = os.path.abspath(db_path)
            dir_name = os.path.dirname(abs_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            db_path = abs_path

        self.db_url = f"sqlite:///{db_path}"
        self.engine = create_engine(self.db_url, echo=False)
        self.Session = sessionmaker(bind=self.engine)

        # Create all tables
        Base.metadata.create_all(self.engine)

    def get_session(self):
        """Get a new database session"""
        return self.Session()

    def close_session(self, session):
        """Close a database session"""
        if session:
            session.close()
