import os
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

try:
    from models import DatabaseManager, Container, ContainerPort, VM, ContainerWidget
    from sqlalchemy.orm import Session
    from sqlalchemy import and_
except ImportError:
    # Fallback for when SQLAlchemy is not installed
    DatabaseManager = None
    Container = None
    ContainerPort = None
    VM = None
    ContainerWidget = None
    Session = None


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

    @contextmanager
    def get_db_session(self):
        """Context manager for database sessions"""
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

    # No configuration (JSON) methods here. Use ConfigManager for config.

    # Container data methods (Database-based)
    def get_container(self, container_id: str) -> Optional[Dict]:
        """Get container data by ID"""
        if self.db_manager is None:
            return None

        with self.get_db_session() as session:
            if session is None:
                return None

            container = (
                session.query(Container).filter(Container.id == container_id).first()
            )
            if container:
                return {
                    "id": container.id,
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

            container_id = container_data.get("id")
            if not container_id:
                return

            # Check if container exists
            container = (
                session.query(Container).filter(Container.id == container_id).first()
            )

            if container:
                # Update existing container
                for key, value in container_data.items():
                    if hasattr(container, key) and key != "id":
                        setattr(container, key, value)
            else:
                # Create new container - ensure required fields have defaults
                required_defaults = {
                    "name": container_data.get("name", f"container_{container_id[:8]}"),
                    "image": container_data.get("image", "unknown"),
                    "status": container_data.get("status", "unknown"),
                }

                # Merge defaults with provided data
                full_container_data = {**required_defaults, **container_data}
                container = Container(**full_container_data)
                session.add(container)

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
                    cid = getattr(container, "id", None)
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

            # Check if container exists
            container = (
                session.query(Container).filter(Container.id == container_id).first()
            )

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
                    id=container_id,
                    name=container_name,
                    image=container_image,
                    status=container_status,
                    is_exposed=is_exposed,
                )
                session.add(container)

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
                    "id": container.id,
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

    def get_containers_by_widget(self, widget_id: int) -> List[Dict]:
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
                    "id": container.id,
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

    # Widgets CRUD
    def get_widgets(self, container_id: str) -> List[Dict]:
        if self.db_manager is None or ContainerWidget is None:
            return []
        with self.get_db_session() as session:
            if session is None:
                return []
            qs = (
                session.query(ContainerWidget)
                .filter(ContainerWidget.container_id == container_id)
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
            return [
                {
                    "container_id": w.container_id,
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

    def add_widget(self, container_id: str, data: Dict[str, Any]) -> Optional[Dict]:
        if self.db_manager is None or ContainerWidget is None:
            return None
        with self.get_db_session() as session:
            if session is None:
                return None
            w = ContainerWidget(
                container_id=container_id,
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
        if self.db_manager is None or ContainerWidget is None:
            return False
        with self.get_db_session() as session:
            if session is None:
                return False
            w = (
                session.query(ContainerWidget)
                .filter(
                    ContainerWidget.id == widget_id,
                    ContainerWidget.container_id == container_id,
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
        if self.db_manager is None or ContainerWidget is None:
            return False
        with self.get_db_session() as session:
            if session is None:
                return False
            w = (
                session.query(ContainerWidget)
                .filter(
                    ContainerWidget.id == widget_id,
                    ContainerWidget.container_id == container_id,
                )
                .first()
            )
            if not w:
                return False
            session.delete(w)
            return True

    # VM methods (for future use)
    def get_vm(self, vm_id: str) -> Optional[Dict]:
        """Get VM data by ID"""
        if self.db_manager is None:
            return None

        with self.get_db_session() as session:
            if session is None:
                return None

            vm = session.query(VM).filter(VM.id == vm_id).first()
            if vm:
                return {
                    "id": vm.id,
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

            vm_id = vm_data.get("id")
            if not vm_id:
                return

            # Check if VM exists
            vm = session.query(VM).filter(VM.id == vm_id).first()

            if vm:
                # Update existing VM
                for key, value in vm_data.items():
                    if hasattr(vm, key) and key != "id":
                        setattr(vm, key, value)
            else:
                # Create new VM
                vm = VM(**vm_data)
                session.add(vm)


# Global instance
_save_manager = None


def get_save_manager() -> SaveManager:
    """Get the global SaveManager instance"""
    global _save_manager
    if _save_manager is None:
        _save_manager = SaveManager()
    return _save_manager
