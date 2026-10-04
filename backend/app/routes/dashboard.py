from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime, timezone
from app.config import Config
from app.models.application import Application
from app.models.backup import Backup, BackupStatus
from app.models.health_check import HealthCheck
from app.models.disaster_event import DisasterEvent, DisasterStatus
from app.models.recovery_job import RecoveryJob
from app.models.audit_log import AuditLog

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("", methods=["GET"])
@jwt_required()
def get_dashboard_summary():
    app = Application.query.first()
    if not app:
        return jsonify({"status": "error", "message": "No application registered"}), 404

    # Latest Health Check
    latest_hc = HealthCheck.query.filter_by(application_id=app.id).order_by(HealthCheck.timestamp.desc()).first()

    # Backups Summary
    backups_count = Backup.query.filter_by(application_id=app.id).filter(Backup.status != BackupStatus.DELETED).count()
    latest_backup = Backup.query.filter_by(application_id=app.id).order_by(Backup.created_at.desc()).first()

    # Recovery / Disaster Summary
    latest_disaster = DisasterEvent.query.filter_by(application_id=app.id).order_by(DisasterEvent.detected_at.desc()).first()
    active_job = RecoveryJob.query.filter_by(application_id=app.id, status="RUNNING").first()
    timeline_job = active_job or RecoveryJob.query.filter_by(application_id=app.id).order_by(RecoveryJob.started_at.desc()).first()

    # Recent Audit Events
    recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(10).all()

    return jsonify({
        "status": "success",
        "system": {
            "name": "Cloud Disaster Recovery Orchestrator (CDRO)",
            "environment": Config.APP_ENV,
            "timestamp": datetime.now(timezone.utc).isoformat()
        },
        "application": app.to_dict(),
        "health": {
            "status": app.status,
            "consecutive_failures": app.consecutive_failures,
            "failure_threshold": Config.HEALTH_FAILURE_THRESHOLD,
            "last_check": latest_hc.to_dict() if latest_hc else None
        },
        "backup": {
            "total_available": backups_count,
            "latest_backup": latest_backup.to_dict() if latest_backup else None,
            "interval_seconds": Config.BACKUP_INTERVAL_SECONDS,
            "storage_backend": Config.STORAGE_BACKEND
        },
        "recovery": {
            "latest_disaster": latest_disaster.to_dict() if latest_disaster else None,
            "active_recovery": active_job is not None,
            "rto_target_seconds": Config.RTO_TARGET_SECONDS,
            "timeline": timeline_job.to_dict() if timeline_job else None
        },
        "automation": {
            "monitoring": "ACTIVE",
            "backup_scheduler": "ACTIVE",
            "recovery_engine": "RECOVERING" if active_job else "READY"
        },
        "recent_events": [log.to_dict() for log in recent_logs]
    }), 200
