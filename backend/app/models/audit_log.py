import json
from datetime import datetime, timezone
from app.extensions import db
from app.utils.helpers import serialize_utc

class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=True, index=True)
    event_type = db.Column(db.String(80), nullable=False, index=True)
    severity = db.Column(db.String(20), nullable=False, default="INFO", index=True) # INFO, WARNING, CRITICAL, ERROR, SUCCESS
    message = db.Column(db.Text, nullable=False)
    metadata_json = db.Column(db.Text, nullable=True)

    def to_dict(self):
        meta = None
        if self.metadata_json:
            try:
                meta = json.loads(self.metadata_json)
            except Exception:
                meta = self.metadata_json

        return {
            "id": self.id,
            "timestamp": serialize_utc(self.timestamp),
            "application_id": self.application_id,
            "event_type": self.event_type,
            "severity": self.severity,
            "message": self.message,
            "metadata": meta
        }
