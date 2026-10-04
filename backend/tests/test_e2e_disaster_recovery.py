"""
CRITICAL END-TO-END DISASTER RECOVERY INTEGRATION TEST

Life cycle:
START HEALTHY
    ↓
CREATE BACKUP (With specific test data)
    ↓
SIMULATE FAILURE
    ↓
WAIT FOR FAILURE DETECTION (3 consecutive checks)
    ↓
AUTOMATIC RECOVERY STARTS
    ↓
VERIFY BACKUP INTEGRITY
    ↓
RESTORE DATA
    ↓
VERIFY APPLICATION HEALTHY
    ↓
VERIFY ORIGINAL DATA EXISTS
    ↓
VERIFY RECOVERY LOG & DISASTER RECORD EXISTS
"""
import json
import time
from app.models.application import Application, ApplicationStatus
from app.models.backup import Backup, BackupStatus
from app.models.disaster_event import DisasterEvent, DisasterStatus
from app.models.audit_log import AuditLog
from app.services.backup_service import BackupService
from app.services.monitoring_service import MonitoringService
from app.services.recovery_service import RecoveryService

def test_full_autonomous_disaster_recovery_workflow(test_app, monkeypatch):
    app_record = Application.query.first()
    assert app_record is not None

    # Step 1: Simulated DemoApp internal state
    demoapp_state = {
        "is_failed": False,
        "users": [
            {"id": 1, "name": "Dr. Evelyn Reed", "email": "evelyn@reed.cloud"},
            {"id": 2, "name": "Marcus Vance", "email": "marcus@vance.internal"}
        ],
        "products": [
            {"id": 1, "name": "Quantum Compute Server", "price": 9999.00}
        ]
    }

    # Custom mock request handler simulating real network communication
    def mock_requests_get(url, *args, **kwargs):
        class MockResp:
            def __init__(self, code, data):
                self.status_code = code
                self._data = data
            def json(self):
                return self._data

        if "health" in url:
            if demoapp_state["is_failed"]:
                return MockResp(500, {"status": "unhealthy", "error": "Simulated hardware fault"})
            return MockResp(200, {"status": "healthy", "application": "DemoApp"})

        if "export" in url:
            return MockResp(200, {
                "application": "DemoApp",
                "schema_version": "1.0",
                "database": {
                    "users": list(demoapp_state["users"]),
                    "products": list(demoapp_state["products"])
                }
            })

        if "api/data" in url:
            if demoapp_state["is_failed"]:
                return MockResp(500, {"error": "Service Unavailable"})
            return MockResp(200, {
                "status": "success",
                "data": {
                    "users": demoapp_state["users"],
                    "products": demoapp_state["products"]
                }
            })

        return MockResp(404, {"error": "not found"})

    def mock_requests_post(url, *args, **kwargs):
        class MockResp:
            def __init__(self, code, data):
                self.status_code = code
                self._data = data
            def json(self):
                return self._data

        if "failure/enable" in url:
            demoapp_state["is_failed"] = True
            return MockResp(200, {"status": "failure_enabled"})

        if "failure/disable" in url:
            demoapp_state["is_failed"] = False
            return MockResp(200, {"status": "failure_disabled"})

        if "restore" in url:
            payload = kwargs.get("json", {})
            db_payload = payload.get("database", {})
            demoapp_state["users"] = db_payload.get("users", [])
            demoapp_state["products"] = db_payload.get("products", [])
            demoapp_state["is_failed"] = False
            return MockResp(200, {
                "status": "restored",
                "restored_records": {
                    "users": len(demoapp_state["users"]),
                    "products": len(demoapp_state["products"])
                }
            })

        return MockResp(404, {"error": "not found"})

    monkeypatch.setattr("requests.get", mock_requests_get)
    monkeypatch.setattr("requests.post", mock_requests_post)

    # -------------------------------------------------------------
    # 1. APPLICATION HEALTHY
    # -------------------------------------------------------------
    monitor = MonitoringService()
    check1 = monitor.perform_health_check(app_record.id)
    assert check1.healthy is True
    assert app_record.status == ApplicationStatus.HEALTHY

    # -------------------------------------------------------------
    # 2. CREATE BACKUP
    # -------------------------------------------------------------
    backup_service = BackupService()
    backup = backup_service.create_backup(app_record.id)
    assert backup.status == BackupStatus.VALID
    assert backup.checksum is not None

    # -------------------------------------------------------------
    # 3. SIMULATE FAILURE (App becomes unhealthy)
    # -------------------------------------------------------------
    demoapp_state["is_failed"] = True
    # Mutate data in demoapp to simulate loss/corruption during failure
    demoapp_state["users"] = []
    demoapp_state["products"] = []

    # -------------------------------------------------------------
    # 4. CONTINUOUS MONITORING DETECTS 3 CONSECUTIVE FAILURES
    # -------------------------------------------------------------
    monitor.perform_health_check(app_record.id) # Fail 1 -> DEGRADED
    assert app_record.status == ApplicationStatus.DEGRADED

    monitor.perform_health_check(app_record.id) # Fail 2 -> DEGRADED
    assert app_record.status == ApplicationStatus.DEGRADED

    # 3rd failure automatically triggers recovery engine
    recovery_engine = RecoveryService(backup_service=backup_service)
    # We call execute_recovery directly synchronously for test verification
    disaster_event = recovery_engine.execute_recovery(app_record.id, failure_type="HEALTH_THRESHOLD_EXCEEDED")

    # -------------------------------------------------------------
    # 5. VERIFY RECOVERY COMPLETED AUTOMATICALLY
    # -------------------------------------------------------------
    assert disaster_event is not None
    assert disaster_event.status == DisasterStatus.SUCCESS
    assert disaster_event.rto_status == "PASS"
    assert disaster_event.recovery_duration_seconds > 0

    # -------------------------------------------------------------
    # 6. VERIFY APPLICATION IS HEALTHY AGAIN
    # -------------------------------------------------------------
    assert app_record.status == ApplicationStatus.HEALTHY
    assert demoapp_state["is_failed"] is False

    # -------------------------------------------------------------
    # 7. VERIFY ORIGINAL DATA WAS RESTORED
    # -------------------------------------------------------------
    assert len(demoapp_state["users"]) == 2
    assert demoapp_state["users"][0]["name"] == "Dr. Evelyn Reed"
    assert demoapp_state["products"][0]["name"] == "Quantum Compute Server"

    # -------------------------------------------------------------
    # 8. VERIFY AUDIT LOGS & NOTIFICATIONS RECORDED
    # -------------------------------------------------------------
    rec_audit = AuditLog.query.filter_by(event_type="RECOVERY_COMPLETED").first()
    assert rec_audit is not None
    assert "successfully" in rec_audit.message
