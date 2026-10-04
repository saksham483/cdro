from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models.disaster_event import DisasterEvent
from app.models.recovery_job import RecoveryJob

recovery_bp = Blueprint("recovery", __name__)

@recovery_bp.route("", methods=["GET"])
@jwt_required()
def list_recoveries():
    events = DisasterEvent.query.order_by(DisasterEvent.detected_at.desc()).all()
    return jsonify({"status": "success", "recoveries": [e.to_dict() for e in events]}), 200

@recovery_bp.route("/<int:event_id>", methods=["GET"])
@jwt_required()
def get_recovery(event_id):
    event = db.session.get(DisasterEvent, event_id)
    if not event:
        return jsonify({"error": "NOT_FOUND", "message": f"Disaster event {event_id} not found"}), 404

    jobs = RecoveryJob.query.filter_by(disaster_event_id=event_id).all()
    event_dict = event.to_dict()
    event_dict["jobs"] = [j.to_dict() for j in jobs]
    return jsonify({"status": "success", "recovery": event_dict}), 200

@recovery_bp.route("/active", methods=["GET"])
@jwt_required()
def get_active_recovery():
    job = RecoveryJob.query.filter_by(status="RUNNING").order_by(RecoveryJob.started_at.desc()).first()
    if not job:
        # Return latest completed job for timeline inspection
        job = RecoveryJob.query.order_by(RecoveryJob.started_at.desc()).first()
    return jsonify({
        "status": "success",
        "active_job": job.to_dict() if job else None
    }), 200
