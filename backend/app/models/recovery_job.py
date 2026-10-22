import json
from datetime import datetime, timezone
from app.extensions import db
from app.utils.helpers import serialize_utc

class RecoveryJob(db.Model):
    __tablename__ = "recovery_jobs"

    id = db.Column(db.Integer, primary_key=True)
    disaster_event_id = db.Column(db.Integer, db.ForeignKey("disaster_events.id"), nullable=False, index=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="RUNNING", index=True) # RUNNING, COMPLETED, FAILED
    current_step = db.Column(db.String(100), nullable=True)
    step_details_json = db.Column(db.Text, nullable=False, default="[]")
    error_message = db.Column(db.Text, nullable=True)
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    def add_step(self, step_name: str, status: str = "IN_PROGRESS", detail: str = ""):
        self.current_step = step_name
        steps = json.loads(self.step_details_json or "[]")
        steps.append({
            "step": step_name,
            "status": status,
            "detail": detail,
            "timestamp": serialize_utc(datetime.now(timezone.utc))
        })
        self.step_details_json = json.dumps(steps)

    def update_last_step(self, status: str, detail: str = ""):
        steps = json.loads(self.step_details_json or "[]")
        if steps:
            steps[-1]["status"] = status
            if detail:
                steps[-1]["detail"] = detail
            steps[-1]["updated_at"] = serialize_utc(datetime.now(timezone.utc))
            self.step_details_json = json.dumps(steps)

    def to_dict(self):
        return {
            "id": self.id,
            "disaster_event_id": self.disaster_event_id,
            "application_id": self.application_id,
            "status": self.status,
            "current_step": self.current_step,
            "steps": json.loads(self.step_details_json or "[]"),
            "error_message": self.error_message,
            "started_at": serialize_utc(self.started_at),
            "completed_at": serialize_utc(self.completed_at)
        }
