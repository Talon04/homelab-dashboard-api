"""
Database models for homelab dashboard
"""
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

Base = declarative_base()

class Container(Base):
    """Model for Docker containers"""
    __tablename__ = 'containers'
    
    id = Column(String, primary_key=True)  # Docker container ID
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
    ports = relationship("ContainerPort", back_populates="container", cascade="all, delete-orphan")
    # Relationship to widgets
    widgets = relationship("ContainerWidget", back_populates="container", cascade="all, delete-orphan")

class ContainerPort(Base):
    """Model for container port mappings"""
    __tablename__ = 'container_ports'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    container_id = Column(String, ForeignKey('containers.id'), nullable=False)
    internal_port = Column(Integer, nullable=False)
    external_port = Column(Integer, nullable=True)
    protocol = Column(String, default='tcp')
    
    # Relationship back to container
    container = relationship("Container", back_populates="ports")

class VM(Base):
    """Model for Virtual Machines (future feature)"""
    __tablename__ = 'vms'
    
    id = Column(String, primary_key=True)  # VM identifier
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
    __tablename__ = 'container_widgets'

    id = Column(Integer, primary_key=True, autoincrement=True)
    container_id = Column(String, ForeignKey('containers.id'), nullable=False)
    type = Column(String, nullable=False)  # 'text' | 'button'
    size = Column(String, default='md')    # 'sm' | 'md' | 'lg'
    label = Column(String, nullable=True)  # for buttons
    text = Column(Text, nullable=True)     # for text widgets
    file_path = Column(String, nullable=True)  # associated script file under user_code
    update_interval = Column(Integer, nullable=True)  # seconds between auto-refresh for text widgets (None = no auto-refresh)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    container = relationship("Container", back_populates="widgets")

class DatabaseManager:
    """Database connection and session management"""
    
    def __init__(self, db_path=None):
        if db_path is None:
            # Default to backend/data/homelab.db
            data_dir = os.path.join(os.path.dirname(__file__), 'data')
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, 'homelab.db')
        
        self.db_url = f'sqlite:///{db_path}'
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