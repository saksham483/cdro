from datetime import datetime, timezone
from app.extensions import db

class DisasterStatus:
    DETECTED = "DETECTED"
    RECOVERING = "RECOVERING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class DisasterEvent(db.Model):
    __tablename__ = "disaster_events"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False, index=True)
    detected_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    failure_type = db.Column(db.String(50), nullable=False, default="APPLICATION_DOWN")
    status = db.Column(db.String(20), nullable=False, default=DisasterStatus.DETECTED, index=True)
    recovery_started_at = db.Column(db.DateTime, nullable=True)
    recovery_completed_at = db.Column(db.DateTime, nullable=True)
    backup_used = db.Column(db.String(255), nullable=True)
    recovery_duration_seconds = db.Column(db.Float, nullable=True)
    rto_seconds = db.Column(db.Float, nullable=True)
    rpo_seconds = db.Column(db.Float, nullable=True)
    rto_status = db.Column(db.String(20), nullable=True) # 'PASS' or 'EXCEEDED'
    failure_reason = db.Column(db.Text, nullable=True)

    recovery_jobs = db.relationship("RecoveryJob", backref="disaster_event", cascade="all, delete-orphan", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "application_id": self.application_id,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "failure_type": self.failure_type,
            "status": self.status,
            "recovery_started_at": self.recovery_started_at.isoformat() if self.recovery_started_at else None,
            "recovery_completed_at": self.recovery_completed_at.isoformat() if self.recovery_completed_at else None,
            "backup_used": self.backup_used,
            "recovery_duration_seconds": round(self.recovery_duration_seconds, 2) if self.recovery_duration_seconds is not None else None,
            "rto_seconds": round(self.rto_seconds, 2) if self.rto_seconds is not None else None,
            "rpo_seconds": round(self.rpo_seconds, 2) if self.rpo_seconds is not None else None,
            "rto_status": self.rto_status,
            "failure_reason": self.failure_reason
        }
