from app.models.application import Application
from app.models.backup import Backup, BackupStatus
from app.services.backup_service import BackupService

def test_backup_checksum_verification_success(test_app, monkeypatch):
    app_record = Application.query.first()
    service = BackupService()

    class MockResponse:
        status_code = 200
        def json(self):
            return {"database": {"users": [{"id": 1, "name": "Bob"}], "products": []}}

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())

    backup = service.create_backup(app_record.id)
    is_valid, msg = service.verify_backup_integrity(backup)
    assert is_valid is True
    assert "verified" in msg.lower()

def test_backup_checksum_verification_detects_corruption(test_app, monkeypatch):
    app_record = Application.query.first()
    service = BackupService()

    class MockResponse:
        status_code = 200
        def json(self):
            return {"database": {"users": [], "products": []}}

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())

    backup = service.create_backup(app_record.id)

    # Deliberately corrupt stored checksum
    service.corrupt_backup_for_simulation(backup.id)

    is_valid, msg = service.verify_backup_integrity(backup)
    assert is_valid is False
    assert backup.status == BackupStatus.CORRUPTED
