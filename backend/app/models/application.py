from datetime import datetime, timezone
from app.extensions import db

class ApplicationStatus:
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILURE_DETECTED = "FAILURE_DETECTED"
    RECOVERING = "RECOVERING"
    RECOVERED = "RECOVERED"
    RECOVERY_FAILED = "RECOVERY_FAILED"

class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    health_url = db.Column(db.String(255), nullable=False)
    api_url = db.Column(db.String(255), nullable=True)
    internal_url = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(30), nullable=False, default=ApplicationStatus.HEALTHY, index=True)
    consecutive_failures = db.Column(db.Integer, default=0)
    last_health_check = db.Column(db.DateTime, nullable=True)
    last_successful_backup = db.Column(db.DateTime, nullable=True)
    last_recovery = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    backups = db.relationship("Backup", backref="application", cascade="all, delete-orphan", lazy="dynamic")
    health_checks = db.relationship("HealthCheck", backref="application", cascade="all, delete-orphan", lazy="dynamic")
    disaster_events = db.relationship("DisasterEvent", backref="application", cascade="all, delete-orphan", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "health_url": self.health_url,
            "api_url": self.api_url,
            "internal_url": self.internal_url,
            "status": self.status,
            "consecutive_failures": self.consecutive_failures,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "last_successful_backup": self.last_successful_backup.isoformat() if self.last_successful_backup else None,
            "last_recovery": self.last_recovery.isoformat() if self.last_recovery else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
