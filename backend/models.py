"""Database models for the homelab dashboard.

Defines SQLAlchemy ORM models for containers, ports, and container widgets.
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
            db_path = os.path.join(DATA_DIR, "data.db")

        self.db_url = f"sqlite:///{db_path}"
        self.engine = create_engine(self.db_url, echo=False)
        self.Session = sessionmaker(bind=self.engine)
        # Note: Table creation is now handled by Alembic migrations in app.py

    def get_session(self):
        """Get a new database session."""
        return self.Session()

    def close_session(self, session):
        """Close a database session."""
        if session:
            session.close()


# =============================================================================
# Service Modeling Models
# =============================================================================


class Service(Base):
    """Top-level service model representing a conceptual service/project."""

    __tablename__ = "services"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    elements = relationship("Element", back_populates="service", cascade="all, delete-orphan")


class Element(Base):
    """An element is a node placed on the canvas that belongs to a Service.

    It has a position (x,y) and metadata. Elements can be connected by Relations.
    """

    __tablename__ = "elements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    key = Column(String, nullable=True)  # an internal key or label
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    x = Column(Integer, default=0)
    y = Column(Integer, default=0)
    width = Column(Integer, default=200)
    height = Column(Integer, default=80)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    service = relationship("Service", back_populates="elements")
    components = relationship("Component", back_populates="element", cascade="all, delete-orphan")


class Component(Base):
    """A component is a child of an Element, e.g., a linked container or resource."""

    __tablename__ = "components"

    id = Column(Integer, primary_key=True, autoincrement=True)
    element_id = Column(Integer, ForeignKey("elements.id"), nullable=False)
    type = Column(String, nullable=False)  # e.g., 'container', 'dns', 'proxy'
    reference = Column(String, nullable=True)  # e.g., docker id or external ref
    meta = Column(Text, nullable=True)  # JSON blob for extra metadata
    text = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    element = relationship("Element", back_populates="components")


class Relation(Base):
    """Represents a directed relation (edge) between two elements or services.

    source_type/target_type can be 'service' or 'element', and source_id/target_id
    refer to the corresponding PK.
    """

    __tablename__ = "relations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_type = Column(String, nullable=False)
    source_id = Column(Integer, nullable=False)
    target_type = Column(String, nullable=False)
    target_id = Column(Integer, nullable=False)
    label = Column(String, nullable=True)
    meta = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

