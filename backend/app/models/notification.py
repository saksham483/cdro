from datetime import datetime, timezone
from app.extensions import db
from app.utils.helpers import serialize_utc

class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    channel = db.Column(db.String(30), nullable=False, default="CONSOLE") # CONSOLE, DATABASE, SNS
    recipient = db.Column(db.String(255), nullable=True)
    subject = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="SENT")
    sent_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": serialize_utc(self.timestamp),
            "channel": self.channel,
            "recipient": self.recipient,
            "subject": self.subject,
            "message": self.message,
            "status": self.status,
            "sent_at": serialize_utc(self.sent_at)
        }
