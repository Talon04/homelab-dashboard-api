"""API routes for Services, Elements, Components and Relations.

Provides basic CRUD endpoints for the new modeling domain.
"""
from flask import Blueprint, jsonify, request

from backend.models import (
    DatabaseManager,
    Service,
    Element,
    Component,
    Relation,
)
from sqlalchemy.orm import Session


services_bp = Blueprint("services", __name__)


def _row_to_service(obj: Service) -> dict:
    return {
        "id": obj.id,
        "name": obj.name,
        "description": obj.description,
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }


def _row_to_element(obj: Element) -> dict:
    return {
        "id": obj.id,
        "service_id": obj.service_id,
        "key": obj.key,
        "title": obj.title,
        "description": obj.description,
        "x": obj.x,
        "y": obj.y,
        "width": obj.width,
        "height": obj.height,
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }


def _row_to_component(obj: Component) -> dict:
    return {
        "id": obj.id,
        "element_id": obj.element_id,
        "type": obj.type,
        "reference": obj.reference,
        "meta": obj.meta,
        "sort_order": obj.sort_order,
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }


def _row_to_relation(obj: Relation) -> dict:
    return {
        "id": obj.id,
        "source_type": obj.source_type,
        "source_id": obj.source_id,
        "target_type": obj.target_type,
        "target_id": obj.target_id,
        "label": obj.label,
        "meta": obj.meta,
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }


@services_bp.route("/api/services", methods=["GET"])
def list_services():
    dbm = DatabaseManager()
    session: Session = dbm.get_session()
    try:
        rows = session.query(Service).order_by(Service.name).all()
        return jsonify([_row_to_service(r) for r in rows])
    finally:
        dbm.close_session(session)


@services_bp.route("/api/services", methods=["POST"])
def create_service():
    data = request.get_json() or {}
    name = data.get("name")
    if not name:
        return (jsonify({"error": "Missing name"}), 400)
    desc = data.get("description")
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        s = Service(name=name, description=desc)
        session.add(s)
        session.flush()
        session.commit()
        return jsonify(_row_to_service(s))
    finally:
        dbm.close_session(session)


@services_bp.route("/api/services/<int:sid>", methods=["GET"])
def get_service(sid):
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        s = session.query(Service).filter(Service.id == sid).first()
        if not s:
            return (jsonify({"error": "Not found"}), 404)
        return jsonify(_row_to_service(s))
    finally:
        dbm.close_session(session)


@services_bp.route("/api/services/<int:sid>/elements", methods=["GET"])
def list_elements_for_service(sid):
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        rows = session.query(Element).filter(Element.service_id == sid).all()
        return jsonify([_row_to_element(r) for r in rows])
    finally:
        dbm.close_session(session)


@services_bp.route("/api/elements/<int:eid>/components", methods=["GET"])
def list_components_for_element(eid):
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        rows = session.query(Component).filter(Component.element_id == eid).all()
        return jsonify([_row_to_component(r) for r in rows])
    finally:
        dbm.close_session(session)


@services_bp.route("/api/services/<int:sid>/relations", methods=["GET"])
def list_relations_for_service(sid):
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        # Gather element ids for the service
        el_rows = session.query(Element.id).filter(Element.service_id == sid).all()
        el_ids = [r[0] for r in el_rows]
        qs = (
            session.query(Relation)
            .filter(
                (Relation.source_type == 'service') & (Relation.source_id == sid)
                | (Relation.target_type == 'service') & (Relation.target_id == sid)
                | ((Relation.source_type == 'element') & (Relation.source_id.in_(el_ids)))
                | ((Relation.target_type == 'element') & (Relation.target_id.in_(el_ids)))
            )
            .all()
        )
        return jsonify([_row_to_relation(r) for r in qs])
    finally:
        dbm.close_session(session)


@services_bp.route("/api/services/<int:sid>", methods=["PUT"])
def update_service(sid):
    data = request.get_json() or {}
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        s = session.query(Service).filter(Service.id == sid).first()
        if not s:
            return (jsonify({"error": "Not found"}), 404)
        if "name" in data:
            s.name = data.get("name")
        if "description" in data:
            s.description = data.get("description")
        session.flush()
        session.commit()
        return jsonify(_row_to_service(s))
    finally:
        dbm.close_session(session)


@services_bp.route("/api/services/<int:sid>", methods=["DELETE"])
def delete_service(sid):
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        s = session.query(Service).filter(Service.id == sid).first()
        if not s:
            return (jsonify({"error": "Not found"}), 404)
        session.delete(s)
        session.flush()
        session.commit()
        return jsonify({"ok": True})
    finally:
        dbm.close_session(session)


# Elements
@services_bp.route("/api/elements", methods=["GET"])
def list_elements():
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        rows = session.query(Element).all()
        return jsonify([_row_to_element(r) for r in rows])
    finally:
        dbm.close_session(session)


@services_bp.route("/api/elements", methods=["POST"])
def create_element():
    data = request.get_json() or {}
    service_id = data.get("service_id")
    title = data.get("title") or "Untitled"
    if not service_id:
        return (jsonify({"error": "Missing service_id"}), 400)
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        el = Element(
            service_id=service_id,
            title=title,
            key=data.get("key"),
            description=data.get("description"),
            x=int(data.get("x") or 0),
            y=int(data.get("y") or 0),
            width=int(data.get("width") or 200),
            height=int(data.get("height") or 80),
        )
        session.add(el)
        session.flush()
        session.commit()
        return jsonify(_row_to_element(el))
    finally:
        dbm.close_session(session)


@services_bp.route("/api/elements/<int:eid>", methods=["GET"])
def get_element(eid):
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        el = session.query(Element).filter(Element.id == eid).first()
        if not el:
            return (jsonify({"error": "Not found"}), 404)
        return jsonify(_row_to_element(el))
    finally:
        dbm.close_session(session)


@services_bp.route("/api/elements/<int:eid>", methods=["PUT"])
def update_element(eid):
    data = request.get_json() or {}
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        el = session.query(Element).filter(Element.id == eid).first()
        if not el:
            return (jsonify({"error": "Not found"}), 404)
        for k in ("title", "key", "description", "x", "y", "width", "height"):
            if k in data:
                setattr(el, k, data.get(k))
        session.flush()
        session.commit()
        return jsonify(_row_to_element(el))
    finally:
        dbm.close_session(session)


@services_bp.route("/api/elements/<int:eid>", methods=["DELETE"])
def delete_element(eid):
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        el = session.query(Element).filter(Element.id == eid).first()
        if not el:
            return (jsonify({"error": "Not found"}), 404)
        session.delete(el)
        session.flush()
        session.commit()
        return jsonify({"ok": True})
    finally:
        dbm.close_session(session)


# Components
@services_bp.route("/api/components", methods=["GET"])
def list_components():
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        rows = session.query(Component).all()
        return jsonify([_row_to_component(r) for r in rows])
    finally:
        dbm.close_session(session)


@services_bp.route("/api/components", methods=["POST"])
def create_component():
    data = request.get_json() or {}
    element_id = data.get("element_id")
    ctype = data.get("type") or "component"
    if not element_id:
        return (jsonify({"error": "Missing element_id"}), 400)
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        c = Component(
            element_id=element_id,
            type=ctype,
            reference=data.get("reference"),
            meta=data.get("meta"),
            sort_order=int(data.get("sort_order") or 0),
        )
        session.add(c)
        session.flush()
        session.commit()
        return jsonify(_row_to_component(c))
    finally:
        dbm.close_session(session)


@services_bp.route("/api/components/<int:cid>", methods=["PUT"])
def update_component(cid):
    data = request.get_json() or {}
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        c = session.query(Component).filter(Component.id == cid).first()
        if not c:
            return (jsonify({"error": "Not found"}), 404)
        for k in ("type", "reference", "meta", "sort_order"):
            if k in data:
                setattr(c, k, data.get(k))
        session.flush()
        session.commit()
        return jsonify(_row_to_component(c))
    finally:
        dbm.close_session(session)


@services_bp.route("/api/components/<int:cid>", methods=["DELETE"])
def delete_component(cid):
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        c = session.query(Component).filter(Component.id == cid).first()
        if not c:
            return (jsonify({"error": "Not found"}), 404)
        session.delete(c)
        session.flush()
        session.commit()
        return jsonify({"ok": True})
    finally:
        dbm.close_session(session)


# Relations
@services_bp.route("/api/relations", methods=["GET"])
def list_relations():
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        rows = session.query(Relation).all()
        return jsonify([_row_to_relation(r) for r in rows])
    finally:
        dbm.close_session(session)


@services_bp.route("/api/relations", methods=["POST"])
def create_relation():
    data = request.get_json() or {}
    required = ("source_type", "source_id", "target_type", "target_id")
    if not all(k in data for k in required):
        return (jsonify({"error": "Missing relation endpoints"}), 400)
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        r = Relation(
            source_type=data.get("source_type"),
            source_id=int(data.get("source_id")),
            target_type=data.get("target_type"),
            target_id=int(data.get("target_id")),
            label=data.get("label"),
            meta=data.get("meta"),
        )
        session.add(r)
        session.flush()
        session.commit()
        return jsonify(_row_to_relation(r))
    finally:
        dbm.close_session(session)


@services_bp.route("/api/relations/<int:rid>", methods=["DELETE"])
def delete_relation(rid):
    dbm = DatabaseManager()
    session = dbm.get_session()
    try:
        r = session.query(Relation).filter(Relation.id == rid).first()
        if not r:
            return (jsonify({"error": "Not found"}), 404)
        session.delete(r)
        session.flush()
        session.commit()
        return jsonify({"ok": True})
    finally:
        dbm.close_session(session)
