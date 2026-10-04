from datetime import datetime, timezone
from app.extensions import db

class HealthCheck(db.Model):
    __tablename__ = "health_checks"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    response_time_ms = db.Column(db.Float, nullable=False, default=0.0)
    status_code = db.Column(db.Integer, nullable=True)
    healthy = db.Column(db.Boolean, nullable=False, default=False)
    error_message = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "application_id": self.application_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "response_time_ms": round(self.response_time_ms, 2),
            "status_code": self.status_code,
            "healthy": self.healthy,
            "error_message": self.error_message
        }
