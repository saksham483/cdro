from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from app.models.application import Application
from app.models.health_check import HealthCheck

health_bp = Blueprint("health", __name__)

@health_bp.route("/applications/<int:app_id>/health", methods=["GET"])
@jwt_required()
def get_app_health(app_id):
    app = db.session.get(Application, app_id)
    if not app:
        return jsonify({"error": "NOT_FOUND", "message": f"Application {app_id} not found"}), 404

    latest_check = HealthCheck.query.filter_by(application_id=app_id).order_by(HealthCheck.timestamp.desc()).first()
    return jsonify({
        "status": "success",
        "application_id": app_id,
        "application_status": app.status,
        "consecutive_failures": app.consecutive_failures,
        "latest_check": latest_check.to_dict() if latest_check else None
    }), 200

@health_bp.route("/applications/<int:app_id>/health-history", methods=["GET"])
@jwt_required()
def get_health_history(app_id):
    history = HealthCheck.query.filter_by(application_id=app_id).order_by(HealthCheck.timestamp.desc()).limit(50).all()
    # Return chronologically ascending for charts
    history.reverse()
    return jsonify({
        "status": "success",
        "history": [h.to_dict() for h in history]
    }), 200
