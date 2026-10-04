from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from app.models.application import Application
from app.utils.security import role_required
from app.extensions import db

apps_bp = Blueprint("applications", __name__)

@apps_bp.route("", methods=["GET"])
@jwt_required()
def list_applications():
    apps = Application.query.order_by(Application.id.asc()).all()
    return jsonify({"status": "success", "applications": [a.to_dict() for a in apps]}), 200

@apps_bp.route("/<int:app_id>", methods=["GET"])
@jwt_required()
def get_application(app_id):
    app = db.session.get(Application, app_id)
    if not app:
        return jsonify({"error": "NOT_FOUND", "message": f"Application {app_id} not found"}), 404
    return jsonify({"status": "success", "application": app.to_dict()}), 200
