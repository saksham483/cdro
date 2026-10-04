from datetime import datetime, timezone
from app.extensions import db

class BackupStatus:
    CREATING = "CREATING"
    VALID = "VALID"
    CORRUPTED = "CORRUPTED"
    FAILED = "FAILED"
    DELETED = "DELETED"

class Backup(db.Model):
    __tablename__ = "backups"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False, default=0)
    checksum = db.Column(db.String(64), nullable=False) # SHA-256
    storage_type = db.Column(db.String(20), nullable=False, default="local") # 'local' or 's3'
    storage_path = db.Column(db.String(512), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=BackupStatus.CREATING, index=True)
    data_summary = db.Column(db.Text, nullable=True) # JSON summary of backed up entities
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "application_id": self.application_id,
            "filename": self.filename,
            "file_size": self.file_size,
            "checksum": self.checksum,
            "storage_type": self.storage_type,
            "storage_path": self.storage_path,
            "status": self.status,
            "data_summary": self.data_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
