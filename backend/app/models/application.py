from datetime import datetime, timezone
from app.extensions import db
from app.utils.helpers import serialize_utc

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
            "last_health_check": serialize_utc(self.last_health_check),
            "last_successful_backup": serialize_utc(self.last_successful_backup),
            "last_recovery": serialize_utc(self.last_recovery),
            "created_at": serialize_utc(self.created_at),
            "updated_at": serialize_utc(self.updated_at)
        }
