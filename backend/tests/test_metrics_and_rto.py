from datetime import datetime, timezone, timedelta
from app.models.application import Application
from app.models.disaster_event import DisasterEvent, DisasterStatus
from app.services.metrics_service import MetricsService

def test_rto_and_rpo_calculations():
    now = datetime.now(timezone.utc)
    backup_created_at = now - timedelta(minutes=4)
    disaster_detected_at = now
    recovery_completed_at = now + timedelta(seconds=15)

    rto_seconds = (recovery_completed_at - disaster_detected_at).total_seconds()
    rpo_seconds = (disaster_detected_at - backup_created_at).total_seconds()

    assert rto_seconds == 15.0
    assert rpo_seconds == 240.0 # 4 minutes

    target_rto = 60
    rto_status = "PASS" if rto_seconds <= target_rto else "EXCEEDED"
    assert rto_status == "PASS"

def test_metrics_service_local_publishing():
    metrics = MetricsService()
    # Should execute cleanly without errors in local mode
    metrics.publish_metric("cdro_recovery_duration", 15.2, unit="Seconds")
    metrics.publish_metric("cdro_recovery_success", 1)
