from app.models.application import Application, ApplicationStatus
from app.models.backup import Backup, BackupStatus
from app.models.disaster_event import DisasterStatus
from app.services.backup_service import BackupService
from app.services.recovery_service import RecoveryService

def test_idempotent_recovery_locking(test_app):
    app_record = Application.query.first()
    app_record.status = ApplicationStatus.RECOVERING

    engine = RecoveryService()
    # Attempting to start recovery on an already RECOVERING app should return None and not start duplicate
    res = engine.execute_recovery(app_record.id)
    assert res is None

def test_recovery_fallback_when_latest_backup_corrupted(test_app, monkeypatch):
    app_record = Application.query.first()
    backup_service = BackupService()

    class MockExportResponse:
        status_code = 200
        def json(self):
            return {"database": {"users": [{"id": 1, "name": "Valid Backup User"}], "products": []}}

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockExportResponse())

    # Create Backup 1 (Valid)
    backup1 = backup_service.create_backup(app_record.id)

    # Create Backup 2 (Latest, but will be corrupted)
    backup2 = backup_service.create_backup(app_record.id)
    backup_service.corrupt_backup_for_simulation(backup2.id)

    # Mock restore endpoint and health checks
    def mock_post(url, *args, **kwargs):
        class MockResp:
            status_code = 200
            def json(self):
                return {"status": "restored", "restored_records": {"users": 1}}
        return MockResp()

    def mock_get(url, *args, **kwargs):
        class MockResp:
            status_code = 200
            def json(self):
                if "health" in url:
                    return {"status": "healthy"}
                return {"data": {"users": [{"id": 1, "name": "Valid Backup User"}]}}
        return MockResp()

    monkeypatch.setattr("requests.post", mock_post)
    monkeypatch.setattr("requests.get", mock_get)

    engine = RecoveryService(backup_service=backup_service)
    disaster_event = engine.execute_recovery(app_record.id)

    assert disaster_event is not None
    assert disaster_event.status == DisasterStatus.SUCCESS
    # Confirms that Backup 2 was skipped due to corruption, and Backup 1 was restored!
    assert disaster_event.backup_used == backup1.filename
    assert backup2.status == BackupStatus.CORRUPTED
    assert app_record.status == ApplicationStatus.HEALTHY
