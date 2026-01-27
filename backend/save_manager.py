# =============================================================================
# SAVE MANAGER - Database persistence layer
# =============================================================================
"""
Database persistence manager for the dashboard backend.

This module provides a SQLite-backed data layer via SQLAlchemy for storing
container metadata, widgets, monitor configurations and VM information.
Configuration (JSON) is handled separately by ConfigManager.
"""

import os
import json
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

try:

    from backend.models import (
        DatabaseManager,
        Container,
        ContainerPort,
        VM,
        ContainerWidget,
        MonitorBodies,
        MonitorPoints,
    )
    from sqlalchemy.orm import Session
    from sqlalchemy import and_
except ImportError:
    # Fallback for when SQLAlchemy is not installed
    DatabaseManager = None
    Container = None
    ContainerPort = None
    VM = None
    ContainerWidget = None
    MonitorBodies = None
    MonitorPoints = None
    Session = None


# =============================================================================
# SAVE MANAGER CLASS
# =============================================================================


class SaveManager:
    """Data persistence manager (SQLite only). Config JSON is handled elsewhere."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialise the underlying database manager.

        When ``db_path`` is omitted, the DatabaseManager will store the
        SQLite file under the app-wide DATA_DIR. If a custom path is
        provided, its parent directory will be created automatically.
        """
        self.db_manager = None
        if DatabaseManager is not None:
            try:
                self.db_manager = DatabaseManager(db_path)
            except Exception as e:
                print(f"Warning: Could not initialize database: {e}")

    # -------------------------------------------------------------------------
    # Session Management
    # -------------------------------------------------------------------------

    @contextmanager
    def get_db_session(self):
        """Context manager for database sessions."""
        if self.db_manager is None:
            yield None
            return

        session = self.db_manager.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            self.db_manager.close_session(session)

    # -------------------------------------------------------------------------
    # Container Lookup Helpers
    # -------------------------------------------------------------------------

    def _get_container_row_by_docker_id(self, session, docker_id: str):
        """Return the Container row for a given Docker ID, or None."""
        if not docker_id or Container is None:
            return None
        return (
            session.query(Container)
            .filter(Container.docker_id == str(docker_id))
            .first()
        )

    # -------------------------------------------------------------------------
    # Container CRUD
    # -------------------------------------------------------------------------

    def get_container(self, container_id: str) -> Optional[Dict]:
        """Get container data by Docker ID.

        ``container_id`` here refers to the Docker/container engine ID,
        not the internal database primary key.
        """
        if self.db_manager is None:
            return None

        with self.get_db_session() as session:
            if session is None:
                return None

            container = self._get_container_row_by_docker_id(session, container_id)
            if container:
                return {
                    # Expose Docker ID as "id" for backwards compatibility
                    "id": container.docker_id,
                    "db_id": container.id,
                    "name": container.name,
                    "image": container.image,
                    "status": container.status,
                    "preferred_port": container.preferred_port,
                    "internal_link_body": container.internal_link_body,
                    "external_link_body": container.external_link_body,
                    "is_exposed": container.is_exposed,
                    "created_at": (
                        container.created_at.isoformat()
                        if container.created_at
                        else None
                    ),
                    "updated_at": (
                        container.updated_at.isoformat()
                        if container.updated_at
                        else None
                    ),
                }
            return None

    def save_container(self, container_data: Dict):
        """Save or update container data"""
        if self.db_manager is None or Container is None:
            return

        with self.get_db_session() as session:
            if session is None:
                return

            docker_id = container_data.get("docker_id") or container_data.get("id")
            if not docker_id:
                return

            # Check if container exists
            container = self._get_container_row_by_docker_id(session, docker_id)

            if container:
                # Update existing container
                for key, value in container_data.items():
                    if key == "id":
                        # Never overwrite the internal PK from payload
                        continue
                    if key == "docker_id":
                        setattr(container, "docker_id", value)
                        continue
                    if hasattr(container, key):
                        setattr(container, key, value)
            else:
                # Create new container - ensure required fields have defaults
                required_defaults = {
                    "name": container_data.get(
                        "name", f"container_{str(docker_id)[:8]}"
                    ),
                    "image": container_data.get("image", "unknown"),
                    "status": container_data.get("status", "unknown"),
                }

                # Merge defaults with provided data
                full_container_data = {**required_defaults, **container_data}
                # Ensure we pass docker_id explicitly and never an "id" field
                full_container_data.pop("id", None)
                full_container_data.setdefault("docker_id", docker_id)
                container = Container(**full_container_data)
                session.add(container)

    # -------------------------------------------------------------------------
    # Container Ports & Link Bodies
    # -------------------------------------------------------------------------

    def get_preferred_port(self, container_id: str) -> Optional[str]:
        """Get preferred port for a container"""
        container = self.get_container(container_id)
        return container.get("preferred_port") if container else None

    def set_preferred_port(self, container_id: str, port: str):
        """Set preferred port for a container"""
        self.save_container({"id": container_id, "preferred_port": port})

    def get_link_body(self, container_id: str) -> Dict[str, str]:
        """Get internal link body for a container"""
        container = self.get_container(container_id)
        if container and container.get("internal_link_body"):
            return {"internal_link_body": container["internal_link_body"]}
        return {"internal_link_body": ""}

    def set_link_body(self, container_id: str, link_body: str):
        """Set internal link body for a container"""
        self.save_container({"id": container_id, "internal_link_body": link_body})

    def get_external_link_body(self, container_id: str) -> Dict[str, str]:
        """Get external link body for a container"""
        container = self.get_container(container_id)
        if container and container.get("external_link_body"):
            return {"external_link_body": container["external_link_body"]}
        return {"external_link_body": ""}

    def set_external_link_body(self, container_id: str, link_body: str):
        """Set external link body for a container"""
        self.save_container({"id": container_id, "external_link_body": link_body})

    # -------------------------------------------------------------------------
    # Exposed Containers
    # -------------------------------------------------------------------------

    def get_exposed_containers(self) -> List[str]:
        """Get all exposed containers as a list of IDs"""
        if self.db_manager is None or Container is None:
            return []

        with self.get_db_session() as session:
            if session is None:
                return []

            containers = session.query(Container).all()
            exposed_ids: List[str] = []
            for container in containers:
                if getattr(container, "is_exposed", False):
                    cid = getattr(container, "docker_id", None)
                    if cid:
                        exposed_ids.append(cid)
            return exposed_ids

    def set_exposed_containers(self, container_id: str, is_exposed: bool):
        """Set exposed status for a container"""
        if self.db_manager is None or Container is None:
            return

        with self.get_db_session() as session:
            if session is None:
                return

            # ``container_id`` here is the Docker ID; look up the row via docker_id
            container = self._get_container_row_by_docker_id(session, container_id)

            if container:
                # Update existing container
                setattr(container, "is_exposed", is_exposed)
            else:
                # Create a new container record with minimal required data
                # Try to get real container data from Docker first
                container_name = f"container_{container_id[:8]}"
                container_image = "unknown"
                container_status = "unknown"

                try:
                    import docker_utils

                    containers = docker_utils.list_containers()
                    docker_container = next(
                        (c for c in containers if c.get("id") == container_id), None
                    )

                    if docker_container:
                        container_name = docker_container.get("name", container_name)
                        container_image = docker_container.get("image", container_image)
                        container_status = docker_container.get(
                            "state", container_status
                        )
                except Exception as e:
                    print(
                        f"Warning: Could not get container data for {container_id}: {e}"
                    )

                # Create new container with required fields
                container = Container(
                    docker_id=container_id,
                    name=container_name,
                    image=container_image,
                    status=container_status,
                    is_exposed=is_exposed,
                )
                session.add(container)

    # -------------------------------------------------------------------------
    # Container Listing
    # -------------------------------------------------------------------------

    def get_all_containers(self) -> List[Dict]:
        """Get all containers"""
        if self.db_manager is None:
            return []

        with self.get_db_session() as session:
            if session is None:
                return []

            containers = session.query(Container).all()
            return [
                {
                    # Keep external ID as "id" for compatibility, and expose db_id separately
                    "id": container.docker_id,
                    "db_id": container.id,
                    "name": container.name,
                    "image": container.image,
                    "status": container.status,
                    "preferred_port": container.preferred_port,
                    "internal_link_body": container.internal_link_body,
                    "external_link_body": container.external_link_body,
                    "is_exposed": container.is_exposed,
                    "widgets": [
                        {
                            "id": w.id,
                            "type": w.type,
                            "size": w.size,
                            "label": w.label,
                            "text": w.text,
                            "file_path": w.file_path,
                            "update_interval": w.update_interval,
                            "sort_order": w.sort_order,
                        }
                        for w in sorted(
                            getattr(container, "widgets", []) or [],
                            key=lambda x: (x.sort_order or 0, x.id or 0),
                        )
                    ],
                    "created_at": (
                        container.created_at.isoformat()
                        if container.created_at
                        else None
                    ),
                    "updated_at": (
                        container.updated_at.isoformat()
                        if container.updated_at
                        else None
                    ),
                }
                for container in containers
            ]

    # -------------------------------------------------------------------------
    # VM Listing
    # -------------------------------------------------------------------------

    def get_all_vms(self) -> List[Dict]:
        """Get all VMs"""
        if self.db_manager is None:
            return []

        with self.get_db_session() as session:
            if session is None:
                return []

            vms = session.query(VM).all()
            return [
                {
                    # External Proxmox ID is the primary identifier for callers
                    "id": vm.proxmox_id,
                    "db_id": vm.id,
                    "proxmox_id": vm.proxmox_id,
                    "name": vm.name,
                    "status": vm.status,
                    "cpu_cores": vm.cpu_cores,
                    "memory_mb": vm.memory_mb,
                    "disk_gb": vm.disk_gb,
                    "ip_address": vm.ip_address,
                    "preferred_port": vm.preferred_port,
                    "internal_link_body": vm.internal_link_body,
                    "external_link_body": vm.external_link_body,
                    "is_exposed": vm.is_exposed,
                    "created_at": vm.created_at.isoformat() if vm.created_at else None,
                    "updated_at": vm.updated_at.isoformat() if vm.updated_at else None,
                }
                for vm in vms
            ]

    def get_containers_by_widget(self, widget_id: int) -> List[Dict]:
        """Return all containers that have the given widget attached."""

        if self.db_manager is None:
            return []

        with self.get_db_session() as session:
            if session is None:
                return []

            containers = (
                session.query(Container)
                .filter(Container.widgets.any(ContainerWidget.id == widget_id))
                .all()
            )
            return [
                {
                    # External Docker ID and internal DB ID
                    "id": container.docker_id,
                    "db_id": container.id,
                    "name": container.name,
                    "image": container.image,
                    "status": container.status,
                    "preferred_port": container.preferred_port,
                    "internal_link_body": container.internal_link_body,
                    "external_link_body": container.external_link_body,
                    "is_exposed": container.is_exposed,
                    "widgets": [
                        {
                            "id": w.id,
                            "type": w.type,
                            "size": w.size,
                            "label": w.label,
                            "text": w.text,
                            "file_path": w.file_path,
                            "update_interval": w.update_interval,
                            "sort_order": w.sort_order,
                        }
                        for w in sorted(
                            getattr(container, "widgets", []) or [],
                            key=lambda x: (x.sort_order or 0, x.id or 0),
                        )
                    ],
                    "created_at": (
                        container.created_at.isoformat()
                        if container.created_at
                        else None
                    ),
                    "updated_at": (
                        container.updated_at.isoformat()
                        if container.updated_at
                        else None
                    ),
                }
                for container in containers
            ]

    # -------------------------------------------------------------------------
    # Widget CRUD
    # -------------------------------------------------------------------------

    def get_widgets(self, container_id: str) -> List[Dict]:
        """Return all widgets attached to a specific container.

        ``container_id`` is the external Docker ID; the internal
        container PK is resolved inside this method.
        """

        if self.db_manager is None or ContainerWidget is None:
            return []
        with self.get_db_session() as session:
            if session is None:
                return []
            # container_id here is the Docker ID; resolve to internal PK
            cont = self._get_container_row_by_docker_id(session, container_id)
            if cont is None:
                return []
            qs = (
                session.query(ContainerWidget)
                .filter(ContainerWidget.container_id == cont.id)
                .order_by(ContainerWidget.sort_order, ContainerWidget.id)
                .all()
            )
            return [
                {
                    "container_id": container_id,
                    "id": w.id,
                    "type": w.type,
                    "size": w.size,
                    "label": w.label,
                    "text": w.text,
                    "file_path": w.file_path,
                    "update_interval": w.update_interval,
                    "sort_order": w.sort_order,
                }
                for w in qs
            ]

    def get_all_widgets(self) -> List[Dict]:
        """Return all widgets across all containers.

        The returned objects contain both the external ``container_id``
        (Docker ID) and ``container_db_id`` (internal PK).
        """

        if self.db_manager is None or ContainerWidget is None:
            return []
        with self.get_db_session() as session:
            if session is None:
                return []
            qs = (
                session.query(ContainerWidget)
                .order_by(ContainerWidget.sort_order, ContainerWidget.id)
                .all()
            )
            widgets: List[Dict[str, Any]] = []
            for w in qs:
                cont = getattr(w, "container", None)
                docker_id = (
                    getattr(cont, "docker_id", None) if cont is not None else None
                )
                db_id = getattr(cont, "id", None) if cont is not None else None
                widgets.append(
                    {
                        # For callers like the scheduler, container_id is the external Docker ID
                        "container_id": docker_id,
                        "container_db_id": db_id,
                        "id": w.id,
                        "type": w.type,
                        "size": w.size,
                        "label": w.label,
                        "text": w.text,
                        "file_path": w.file_path,
                        "update_interval": w.update_interval,
                        "sort_order": w.sort_order,
                    }
                )
            return widgets

    def add_widget(self, container_id: str, data: Dict[str, Any]) -> Optional[Dict]:
        """Create a new widget for the given container (Docker ID)."""

        if self.db_manager is None or ContainerWidget is None:
            return None
        with self.get_db_session() as session:
            if session is None:
                return None
            # container_id argument is Docker ID; convert to internal PK
            cont = self._get_container_row_by_docker_id(session, container_id)
            if cont is None:
                return None
            w = ContainerWidget(
                container_id=cont.id,
                type=str(data.get("type") or "text"),
                size=str(data.get("size") or "md"),
                label=(data.get("label") or None),
                text=(data.get("text") or None),
                file_path=(data.get("file_path") or None),
                update_interval=(
                    int(data.get("update_interval"))
                    if data.get("update_interval") is not None
                    else None
                ),
                sort_order=int(data.get("sort_order") or 0),
            )
            session.add(w)
            session.flush()
            return {
                "id": w.id,
                "type": w.type,
                "size": w.size,
                "label": w.label,
                "text": w.text,
                "file_path": w.file_path,
                "update_interval": w.update_interval,
                "sort_order": w.sort_order,
            }

    def update_widget(
        self, container_id: str, widget_id: int, data: Dict[str, Any]
    ) -> bool:
        """Update selected fields of an existing widget.

        The widget is looked up by its ID and the Docker ID of its
        parent container; unknown widgets return ``False``.
        """

        if self.db_manager is None or ContainerWidget is None:
            return False
        with self.get_db_session() as session:
            if session is None:
                return False
            cont = self._get_container_row_by_docker_id(session, container_id)
            if cont is None:
                return False
            w = (
                session.query(ContainerWidget)
                .filter(
                    ContainerWidget.id == widget_id,
                    ContainerWidget.container_id == cont.id,
                )
                .first()
            )
            if not w:
                return False
            for key in [
                "type",
                "size",
                "label",
                "text",
                "file_path",
                "update_interval",
                "sort_order",
            ]:
                if key in data:
                    setattr(w, key, data.get(key))
            return True

    def delete_widget(self, container_id: str, widget_id: int) -> bool:
        """Delete a widget belonging to the specified container."""

        if self.db_manager is None or ContainerWidget is None:
            return False
        with self.get_db_session() as session:
            if session is None:
                return False
            cont = self._get_container_row_by_docker_id(session, container_id)
            if cont is None:
                return False
            w = (
                session.query(ContainerWidget)
                .filter(
                    ContainerWidget.id == widget_id,
                    ContainerWidget.container_id == cont.id,
                )
                .first()
            )
            if not w:
                return False
            session.delete(w)
            return True

    # -------------------------------------------------------------------------
    # Monitor Configuration
    # -------------------------------------------------------------------------

    def get_monitor_for_container(self, container_id: str) -> Optional[Dict[str, Any]]:
        """Return monitor configuration for a given container, if any."""
        if self.db_manager is None or MonitorBodies is None:
            return None

        with self.get_db_session() as session:
            if session is None:
                return None
            # container_id argument is Docker ID; resolve to internal PK
            cont = self._get_container_row_by_docker_id(session, container_id)
            if cont is None:
                return None

            md = (
                session.query(MonitorBodies)
                .filter(MonitorBodies.container_id == cont.id)
                .first()
            )
            if not md:
                return None
            # Parse event_severity_settings from JSON if present
            event_severity_settings = None
            if md.event_severity_settings:
                try:
                    event_severity_settings = json.loads(md.event_severity_settings)
                except Exception:
                    pass
            return {
                "id": md.id,
                "name": md.name,
                "container_id": md.container_id,
                "vm_id": md.vm_id,
                "monitor_type": md.monitor_type,
                "enabled": bool(md.enabled),
                "event_severity_settings": event_severity_settings,
            }

    def set_monitor_for_container(
        self,
        container_id: str,
        enabled: bool,
        monitor_type: str = "docker",
        name: str = None,
        event_severity_settings: dict = None,
    ) -> Optional[Dict[str, Any]]:
        """Create or update monitor configuration for a container.

        A single MonitorData row is kept per container; this toggles the
        ``enabled`` flag and initialises sensible defaults on first use.
        """

        if self.db_manager is None or MonitorBodies is None:
            return None

        with self.get_db_session() as session:
            if session is None:
                return None
            cont = self._get_container_row_by_docker_id(session, container_id)
            if cont is None:
                # Auto-create container row if it doesn't exist
                if Container is None:
                    return None

                container_name = f"container_{container_id[:8]}"
                container_image = "unknown"
                container_status = "unknown"

                try:
                    from backend import docker_utils

                    containers = docker_utils.list_containers()
                    docker_container = next(
                        (c for c in containers if c.get("id") == container_id), None
                    )

                    if docker_container:
                        container_name = docker_container.get("name", container_name)
                        container_image = docker_container.get("image", container_image)
                        container_status = docker_container.get(
                            "state", container_status
                        )
                except Exception as e:
                    print(
                        f"Warning: Could not get container data for {container_id}: {e}"
                    )

                cont = Container(
                    docker_id=container_id,
                    name=container_name,
                    image=container_image,
                    status=container_status,
                )
                session.add(cont)
                session.flush()

            md = (
                session.query(MonitorBodies)
                .filter(MonitorBodies.container_id == cont.id)
                .first()
            )
            # Serialize event_severity_settings to JSON if provided
            event_severity_settings_json = None
            if event_severity_settings is not None:
                event_severity_settings_json = json.dumps(event_severity_settings)

            if md is None:
                md = MonitorBodies(
                    container_id=cont.id,
                    monitor_type=str(monitor_type or "docker"),
                    enabled=bool(enabled),
                    name=name or f"Monitor: {cont.name}",
                    event_severity_settings=event_severity_settings_json,
                )
                session.add(md)
                session.flush()
            else:
                md.enabled = bool(enabled)
                # Only set defaults if fields are missing
                if not md.monitor_type:
                    md.monitor_type = str(monitor_type or "docker")
                if name:
                    md.name = name
                if event_severity_settings_json is not None:
                    md.event_severity_settings = event_severity_settings_json

            # Parse back event_severity_settings for return
            parsed_settings = None
            if md.event_severity_settings:
                try:
                    parsed_settings = json.loads(md.event_severity_settings)
                except Exception:
                    pass

            return {
                "id": md.id,
                "name": md.name,
                "container_id": md.container_id,
                "vm_id": md.vm_id,
                "monitor_type": md.monitor_type,
                "enabled": bool(md.enabled),
                "event_severity_settings": parsed_settings,
            }

    def get_all_monitor_bodies(self) -> List[Dict[str, Any]]:
        """Get all monitor_bodies (monitor configurations for containers/VMs)."""
        if self.db_manager is None or MonitorBodies is None:
            return []

        with self.get_db_session() as session:
            if session is None:
                return []

            entries = session.query(MonitorBodies).all()
            result = []
            for md in entries:
                # Parse event_severity_settings from JSON
                event_severity_settings = None
                if md.event_severity_settings:
                    try:
                        event_severity_settings = json.loads(md.event_severity_settings)
                    except Exception:
                        pass
                result.append(
                    {
                        "id": md.id,
                        "name": md.name,
                        "container_id": md.container_id,
                        "vm_id": md.vm_id,
                        "monitor_type": md.monitor_type,
                        "enabled": bool(md.enabled),
                        "event_severity_settings": event_severity_settings,
                    }
                )
            return result

    # -------------------------------------------------------------------------
    # VM CRUD
    # -------------------------------------------------------------------------

    def _get_vm_row_by_proxmox_id(self, session, proxmox_id: str):
        """Return the VM row for a given Proxmox ID, or None."""
        if not proxmox_id or VM is None:
            return None
        return session.query(VM).filter(VM.proxmox_id == str(proxmox_id)).first()

    def get_vm(self, vm_id: str) -> Optional[Dict]:
        """Get VM data by Proxmox ID (external identifier)."""
        if self.db_manager is None:
            return None

        with self.get_db_session() as session:
            if session is None:
                return None

            vm = self._get_vm_row_by_proxmox_id(session, vm_id)
            if vm:
                return {
                    "id": vm.proxmox_id,
                    "db_id": vm.id,
                    "name": vm.name,
                    "status": vm.status,
                    "cpu_cores": vm.cpu_cores,
                    "memory_mb": vm.memory_mb,
                    "disk_gb": vm.disk_gb,
                    "ip_address": vm.ip_address,
                    "preferred_port": vm.preferred_port,
                    "internal_link_body": vm.internal_link_body,
                    "external_link_body": vm.external_link_body,
                    "is_exposed": vm.is_exposed,
                    "created_at": vm.created_at.isoformat() if vm.created_at else None,
                    "updated_at": vm.updated_at.isoformat() if vm.updated_at else None,
                }
            return None

    def save_vm(self, vm_data: Dict):
        """Save or update VM data"""
        if self.db_manager is None:
            return

        with self.get_db_session() as session:
            if session is None:
                return

            vm_ext_id = vm_data.get("proxmox_id") or vm_data.get("id")
            if not vm_ext_id:
                return

            # Check if VM exists
            vm = self._get_vm_row_by_proxmox_id(session, vm_ext_id)

            if vm:
                # Update existing VM
                for key, value in vm_data.items():
                    if key == "id":
                        # never overwrite internal PK
                        continue
                    if key == "proxmox_id":
                        setattr(vm, "proxmox_id", value)
                        continue
                    if hasattr(vm, key):
                        setattr(vm, key, value)
            else:
                # Create new VM
                clean_data = dict(vm_data)
                clean_data.pop("id", None)
                clean_data.setdefault("proxmox_id", vm_ext_id)
                vm = VM(**clean_data)
                session.add(vm)


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_save_manager = None


def get_save_manager() -> SaveManager:
    """Get the global SaveManager instance."""
    global _save_manager
    if _save_manager is None:
        _save_manager = SaveManager()
    return _save_manager
