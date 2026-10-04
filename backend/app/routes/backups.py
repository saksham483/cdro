from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from app.models.backup import Backup
from app.models.application import Application
from app.services.backup_service import BackupService
from app.utils.security import role_required

backups_bp = Blueprint("backups", __name__)

@backups_bp.route("", methods=["GET"])
@jwt_required()
def list_backups():
    app_id = request.args.get("application_id", type=int)
    query = Backup.query
    if app_id:
        query = query.filter_by(application_id=app_id)
    backups = query.order_by(Backup.created_at.desc()).all()
    return jsonify({"status": "success", "backups": [b.to_dict() for b in backups]}), 200

@backups_bp.route("/<int:backup_id>", methods=["GET"])
@jwt_required()
def get_backup(backup_id):
    backup = db.session.get(Backup, backup_id)
    if not backup:
        return jsonify({"error": "NOT_FOUND", "message": f"Backup {backup_id} not found"}), 404
    return jsonify({"status": "success", "backup": backup.to_dict()}), 200

@backups_bp.route("/trigger", methods=["POST"])
@jwt_required()
def trigger_backup():
    data = request.get_json(silent=True) or {}
    app_id = data.get("application_id")
    if not app_id:
        app = Application.query.first()
        if app:
            app_id = app.id
        else:
            return jsonify({"error": "BAD_REQUEST", "message": "No application available"}), 400

    service = BackupService()
    try:
        backup = service.create_backup(app_id)
        return jsonify({"status": "success", "backup": backup.to_dict()}), 201
    except Exception as e:
        return jsonify({"error": "BACKUP_FAILED", "message": str(e)}), 500

@backups_bp.route("/<int:backup_id>/corrupt", methods=["POST"])
@jwt_required()
@role_required("admin")
def corrupt_backup(backup_id):
    """SIMULATION ONLY: deliberate corruption to demonstrate fallback logic"""
    service = BackupService()
    try:
        backup = service.corrupt_backup_for_simulation(backup_id)
        return jsonify({
            "status": "success",
            "message": f"Backup {backup.filename} checksum corrupted for simulation testing",
            "backup": backup.to_dict()
        }), 200
    except Exception as e:
        return jsonify({"error": "CORRUPT_FAILED", "message": str(e)}), 500
