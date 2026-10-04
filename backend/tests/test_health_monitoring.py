from app.models.application import Application, ApplicationStatus
from app.models.health_check import HealthCheck
from app.services.monitoring_service import MonitoringService

def test_health_monitoring_healthy_state(test_app, monkeypatch):
    app_record = Application.query.first()
    service = MonitoringService()

    class MockResponse:
        status_code = 200
        def json(self):
            return {"status": "healthy", "application": "DemoApp"}

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())

    check = service.perform_health_check(app_record.id)
    assert check is not None
    assert check.healthy is True
    assert app_record.status == ApplicationStatus.HEALTHY
    assert app_record.consecutive_failures == 0

def test_health_monitoring_failure_threshold_progression(test_app, monkeypatch):
    app_record = Application.query.first()
    service = MonitoringService()

    class MockResponse:
        status_code = 500
        def json(self):
            return {"status": "unhealthy"}

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())

    # 1st failure -> DEGRADED
    service.perform_health_check(app_record.id)
    assert app_record.consecutive_failures == 1
    assert app_record.status == ApplicationStatus.DEGRADED

    # 2nd failure -> DEGRADED
    service.perform_health_check(app_record.id)
    assert app_record.consecutive_failures == 2
    assert app_record.status == ApplicationStatus.DEGRADED

    # 3rd failure -> FAILURE_DETECTED (threshold met!)
    service.perform_health_check(app_record.id)
    assert app_record.consecutive_failures >= 3
    assert app_record.status in (ApplicationStatus.FAILURE_DETECTED, ApplicationStatus.RECOVERING)
