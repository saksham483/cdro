from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from app.models.disaster_event import DisasterEvent
from app.models.audit_log import AuditLog

events_bp = Blueprint("events", __name__)

@events_bp.route("/events", methods=["GET"])
@jwt_required()
def list_disaster_events():
    events = DisasterEvent.query.order_by(DisasterEvent.detected_at.desc()).all()
    return jsonify({"status": "success", "events": [e.to_dict() for e in events]}), 200

@events_bp.route("/logs", methods=["GET"])
@jwt_required()
def list_audit_logs():
    severity = request.args.get("severity")
    event_type = request.args.get("event_type")
    limit = min(request.args.get("limit", default=100, type=int), 500)

    query = AuditLog.query
    if severity:
        query = query.filter_by(severity=severity.upper())
    if event_type:
        query = query.filter_by(event_type=event_type)

    logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return jsonify({"status": "success", "logs": [l.to_dict() for l in logs]}), 200
