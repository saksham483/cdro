import os
import json
from app.models.application import Application
from app.models.backup import Backup, BackupStatus
from app.models.audit_log import AuditLog
from app.services.backup_service import BackupService
from app.extensions import db

def test_backup_creation_and_checksum(test_app, monkeypatch):
    app_record = Application.query.first()
    assert app_record is not None

    # Mock DemoApp export response
    fake_export = {
        "application": "DemoApp",
        "schema_version": "1.0",
        "database": {
            "users": [{"id": 1, "name": "Alice", "email": "alice@test.com"}],
            "products": [{"id": 1, "name": "Cloud Disk", "price": 49.99}]
        }
    }

    class MockResponse:
        status_code = 200
        def json(self):
            return fake_export

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())

    service = BackupService()
    backup = service.create_backup(app_record.id)

    assert backup is not None
    assert backup.status == BackupStatus.VALID
    assert len(backup.checksum) == 64 # SHA-256 length
    assert backup.file_size > 0
    assert os.path.exists(backup.storage_path)

    # Check that audit log recorded the backup
    audit = AuditLog.query.filter_by(event_type="BACKUP_COMPLETED").first()
    assert audit is not None
    assert backup.filename in audit.message

def test_backup_retention_policy(test_app, monkeypatch):
    app_record = Application.query.first()
    service = BackupService()

    class MockResponse:
        status_code = 200
        def json(self):
            return {"database": {"users": [], "products": []}}

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())

    # Create 12 backups (retention limit is 10)
    for _ in range(12):
        service.create_backup(app_record.id)

    valid_count = Backup.query.filter_by(
        application_id=app_record.id,
        status=BackupStatus.VALID
    ).count()
    deleted_count = Backup.query.filter_by(
        application_id=app_record.id,
        status=BackupStatus.DELETED
    ).count()

    assert valid_count == 10
    assert deleted_count == 2
