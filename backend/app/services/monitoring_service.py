import time
import requests
from datetime import datetime, timezone
from app.config import Config
from app.extensions import db
from app.models.application import Application, ApplicationStatus
from app.models.health_check import HealthCheck
from app.models.audit_log import AuditLog
from app.services.notification_service import NotificationService
from app.services.metrics_service import MetricsService

class MonitoringService:
    def __init__(self, notification_service=None, metrics_service=None):
        self.notifier = notification_service or NotificationService()
        self.metrics = metrics_service or MetricsService()

    def perform_health_check(self, application_id: int) -> HealthCheck:
        app = db.session.get(Application, application_id)
        if not app:
            raise ValueError(f"Application {application_id} not found")

        # Do not disrupt if recovery is currently executing
        if app.status == ApplicationStatus.RECOVERING:
            return None

        timestamp = datetime.now(timezone.utc)
        start_time = time.time()
        healthy = False
        status_code = None
        error_msg = None

        try:
            resp = requests.get(app.health_url, timeout=3.0)
            status_code = resp.status_code
            elapsed_ms = (time.time() - start_time) * 1000.0

            if status_code == 200:
                data = resp.json()
                if data.get("status") == "healthy":
                    healthy = True
                else:
                    error_msg = f"Unexpected health payload: {data}"
            else:
                error_msg = f"Health check returned HTTP {status_code}"
        except requests.exceptions.RequestException as e:
            elapsed_ms = (time.time() - start_time) * 1000.0
            error_msg = f"Connection/timeout error: {type(e).__name__} ({str(e)})"

        # Record check
        hc = HealthCheck(
            application_id=app.id,
            timestamp=timestamp,
            response_time_ms=elapsed_ms,
            status_code=status_code,
            healthy=healthy,
            error_message=error_msg
        )
        db.session.add(hc)
        app.last_health_check = timestamp

        # Handle failure state transitions
        if healthy:
            if app.consecutive_failures > 0:
                app.consecutive_failures = 0
            if app.status in (ApplicationStatus.DEGRADED, ApplicationStatus.RECOVERED, ApplicationStatus.RECOVERY_FAILED):
                app.status = ApplicationStatus.HEALTHY
                audit = AuditLog(
                    timestamp=timestamp,
                    application_id=app.id,
                    event_type="APPLICATION_HEALTH_RESTORED",
                    severity="INFO",
                    message=f"Application {app.name} returned to HEALTHY state"
                )
                db.session.add(audit)
        else:
            app.consecutive_failures += 1
            self.metrics.publish_metric("cdro_health_failure", 1)

            audit = AuditLog(
                timestamp=timestamp,
                application_id=app.id,
                event_type="HEALTH_CHECK_FAILED",
                severity="WARNING",
                message=f"Health check failed ({app.consecutive_failures}/{Config.HEALTH_FAILURE_THRESHOLD}): {error_msg}"
            )
            db.session.add(audit)

            if app.consecutive_failures < Config.HEALTH_FAILURE_THRESHOLD:
                if app.status == ApplicationStatus.HEALTHY:
                    app.status = ApplicationStatus.DEGRADED
            elif app.consecutive_failures >= Config.HEALTH_FAILURE_THRESHOLD:
                if app.status not in (ApplicationStatus.FAILURE_DETECTED, ApplicationStatus.RECOVERING):
                    app.status = ApplicationStatus.FAILURE_DETECTED
                    critical_audit = AuditLog(
                        timestamp=timestamp,
                        application_id=app.id,
                        event_type="FAILURE_DETECTED",
                        severity="CRITICAL",
                        message=f"DISASTER DECLARED: {app.name} failed {app.consecutive_failures} consecutive health checks. Automatic disaster recovery triggered."
                    )
                    db.session.add(critical_audit)
                    db.session.commit()

                    self.notifier.send_notification(
                        subject=f"CRITICAL: {app.name} failure detected",
                        message=f"Health monitoring detected {app.consecutive_failures} consecutive failures on {app.name}. Automatic disaster recovery sequence initiated immediately.",
                        severity="CRITICAL",
                        app_id=app.id
                    )

                    # Trigger Automatic Recovery Engine
                    from app.services.recovery_service import RecoveryService
                    recovery_engine = RecoveryService(notifier=self.notifier, metrics=self.metrics)
                    recovery_engine.trigger_automatic_recovery(app.id, failure_type="HEALTH_THRESHOLD_EXCEEDED")
                    return hc

        db.session.commit()
        return hc
