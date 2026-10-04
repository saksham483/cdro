import requests
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from app.config import Config
from app.extensions import db
from app.models.application import Application, ApplicationStatus
from app.models.backup import Backup, BackupStatus
from app.models.audit_log import AuditLog
from app.services.backup_service import BackupService
from app.utils.security import role_required

simulation_bp = Blueprint("simulation", __name__)

@simulation_bp.route("/failure", methods=["POST"])
@jwt_required()
@role_required("admin")
def simulate_failure():
    """
    SIMULATION ONLY: Triggers controlled simulated failure on DemoApp.
    Health monitoring will observe consecutive failures and automatically initiate disaster recovery.
    """
    app = Application.query.first()
    if not app:
        return jsonify({"error": "No application registered"}), 404

    target_url = f"{app.internal_url or Config.DEMOAPP_URL}/internal/failure/enable"
    headers = {"X-Internal-Token": Config.INTERNAL_SECRET}
    try:
        resp = requests.post(target_url, headers=headers, timeout=5)
        if resp.status_code != 200:
            return jsonify({"error": f"DemoApp responded with {resp.status_code}: {resp.text}"}), 500

        audit = AuditLog(
            timestamp=datetime.now(timezone.utc),
            application_id=app.id,
            event_type="SIMULATION_FAILURE_TRIGGERED",
            severity="WARNING",
            message="[SIMULATION ONLY] Controlled outage initiated on DemoApp. Continuous health monitor will detect outage and trigger automated recovery."
        )
        db.session.add(audit)
        db.session.commit()

        return jsonify({
            "status": "success",
            "simulation": "FAILURE_INJECTED",
            "message": "DemoApp failure mode enabled. CDRO health monitor will detect consecutive failures and trigger automatic recovery.",
            "target": app.name,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200
    except Exception as e:
        return jsonify({"error": "SIMULATION_FAILED", "message": str(e)}), 500

@simulation_bp.route("/corrupt-latest-backup", methods=["POST"])
@jwt_required()
@role_required("admin")
def simulate_corrupt_latest_backup():
    """
    SIMULATION ONLY: Corrupts the latest valid backup to test automatic fallback
    to the preceding valid backup during disaster recovery.
    """
    app = Application.query.first()
    if not app:
        return jsonify({"error": "No application registered"}), 404

    latest_backup = Backup.query.filter_by(
        application_id=app.id,
        status=BackupStatus.VALID
    ).order_by(Backup.created_at.desc()).first()

    if not latest_backup:
        return jsonify({"error": "No valid backup available to corrupt"}), 400

    service = BackupService()
    service.corrupt_backup_for_simulation(latest_backup.id)

    return jsonify({
        "status": "success",
        "simulation": "BACKUP_CORRUPTED",
        "corrupted_backup": latest_backup.filename,
        "message": f"Backup {latest_backup.filename} checksum corrupted. Next disaster recovery will automatically detect corruption, reject this backup, and fall back to the preceding valid backup.",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200

@simulation_bp.route("/reset", methods=["POST"])
@jwt_required()
@role_required("admin")
def simulate_reset():
    """Reset DemoApp failure mode and reset application state to HEALTHY"""
    app = Application.query.first()
    if app:
        target_url = f"{app.internal_url or Config.DEMOAPP_URL}/internal/failure/disable"
        headers = {"X-Internal-Token": Config.INTERNAL_SECRET}
        try:
            requests.post(target_url, headers=headers, timeout=5)
        except Exception:
            pass

        app.status = ApplicationStatus.HEALTHY
        app.consecutive_failures = 0
        db.session.commit()

    return jsonify({"status": "success", "message": "Demo state reset to HEALTHY"}), 200
