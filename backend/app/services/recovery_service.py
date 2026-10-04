import os
import json
import time
import zipfile
import tempfile
import requests
import threading
from datetime import datetime, timezone
from app.config import Config
from app.extensions import db
from app.models.application import Application, ApplicationStatus
from app.models.backup import Backup, BackupStatus
from app.models.disaster_event import DisasterEvent, DisasterStatus
from app.models.recovery_job import RecoveryJob
from app.models.audit_log import AuditLog
from app.services.backup_service import BackupService
from app.services.storage_service import StorageService
from app.services.notification_service import NotificationService
from app.services.metrics_service import MetricsService
class RecoveryService:
    def __init__(self, backup_service=None, storage_service=None, notifier=None, metrics=None):
        if backup_service and not storage_service:
            self.storage = getattr(backup_service, "storage", None) or StorageService()
        else:
            self.storage = storage_service or StorageService()
        self.backup_service = backup_service or BackupService(self.storage)
        self.notifier = notifier or NotificationService()
        self.metrics = metrics or MetricsService()

    def trigger_automatic_recovery(self, application_id: int, failure_type: str = "APPLICATION_DOWN"):
        """
        Asynchronously triggers the automatic recovery engine in a dedicated thread
        to ensure health monitor or web requests are not blocked.
        """
        thread = threading.Thread(
            target=self._run_recovery_wrapper,
            args=(application_id, failure_type),
            daemon=True
        )
        thread.start()
        return thread

    def _run_recovery_wrapper(self, application_id: int, failure_type: str):
        from app import create_app
        app = create_app()
        with app.app_context():
            self.execute_recovery(application_id, failure_type)

    def execute_recovery(self, application_id: int, failure_type: str = "APPLICATION_DOWN") -> DisasterEvent:
        app = db.session.get(Application, application_id)
        if not app:
            return None

        # -------------------------------------------------------------
        # STEP 1: Acquire Recovery Lock (Idempotency check)
        # -------------------------------------------------------------
        if app.status == ApplicationStatus.RECOVERING:
            print(f"[RECOVERY] Application {app.name} is already RECOVERING. Skipping redundant recovery request.")
            return None

        app.status = ApplicationStatus.RECOVERING
        db.session.commit()

        start_time = datetime.now(timezone.utc)
        disaster_event = DisasterEvent(
            application_id=app.id,
            detected_at=start_time,
            failure_type=failure_type,
            status=DisasterStatus.RECOVERING,
            recovery_started_at=start_time
        )
        db.session.add(disaster_event)
        db.session.commit()

        job = RecoveryJob(
            disaster_event_id=disaster_event.id,
            application_id=app.id,
            status="RUNNING"
        )
        db.session.add(job)
        job.add_step("Acquire recovery lock", "COMPLETED", "Recovery lock successfully acquired for DemoApp")
        db.session.commit()

        # Audit log
        audit = AuditLog(
            timestamp=start_time,
            application_id=app.id,
            event_type="RECOVERY_STARTED",
            severity="CRITICAL",
            message=f"Automatic disaster recovery started for {app.name} (Disaster #{disaster_event.id})"
        )
        db.session.add(audit)
        db.session.commit()

        # -------------------------------------------------------------
        # STEP 2: Find Latest VALID Backup with Fallback
        # -------------------------------------------------------------
        job.add_step("Search and verify backups", "IN_PROGRESS", "Locating latest valid backup candidate")
        db.session.commit()

        candidate_backups = Backup.query.filter(
            Backup.application_id == app.id,
            Backup.status.in_([BackupStatus.VALID, BackupStatus.CREATING])
        ).order_by(Backup.created_at.desc()).all()

        selected_backup = None
        for candidate in candidate_backups:
            job.add_step(
                f"Verify checksum for {candidate.filename}",
                "IN_PROGRESS",
                f"Checking SHA-256 against stored hash: {candidate.checksum[:16]}..."
            )
            db.session.commit()

            is_valid, msg = self.backup_service.verify_backup_integrity(candidate)
            if is_valid:
                selected_backup = candidate
                job.update_last_step("COMPLETED", f"Checksum verified: {candidate.checksum}")
                db.session.commit()
                break
            else:
                job.update_last_step("FAILED", f"Integrity check failed: {msg}. Falling back to previous backup.")
                db.session.commit()

        if not selected_backup:
            # All backups failed or no backups available!
            err = "Automatic recovery failed: No valid or uncorrupted backups found."
            job.add_step("Backup selection", "FAILED", err)
            job.status = "FAILED"
            job.error_message = err
            job.completed_at = datetime.now(timezone.utc)

            disaster_event.status = DisasterStatus.FAILED
            disaster_event.failure_reason = err
            disaster_event.recovery_completed_at = job.completed_at

            app.status = ApplicationStatus.RECOVERY_FAILED
            db.session.commit()

            self.notifier.send_notification(
                subject=f"CRITICAL: Automatic recovery failed for {app.name}",
                message="Disaster recovery could not proceed because no valid backup was found or all available backups failed integrity verification.",
                severity="CRITICAL",
                app_id=app.id
            )
            self.metrics.publish_metric("cdro_recovery_failure", 1)
            return disaster_event

        job.add_step("Backup selected", "COMPLETED", f"Using backup {selected_backup.filename}")
        disaster_event.backup_used = selected_backup.filename
        db.session.commit()

        # -------------------------------------------------------------
        # STEP 3: Create Temporary Recovery Workspace & Extract
        # -------------------------------------------------------------
        job.add_step("Prepare recovery workspace", "IN_PROGRESS", "Extracting backup archive")
        db.session.commit()

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_zip = os.path.join(tmpdir, selected_backup.filename)
            ok = self.storage.retrieve_file(selected_backup.storage_type, selected_backup.storage_path, temp_zip)
            if not ok:
                err = f"Failed to retrieve backup file from {selected_backup.storage_path}"
                job.update_last_step("FAILED", err)
                job.status = "FAILED"
                app.status = ApplicationStatus.RECOVERY_FAILED
                disaster_event.status = DisasterStatus.FAILED
                disaster_event.failure_reason = err
                db.session.commit()
                return disaster_event

            with zipfile.ZipFile(temp_zip, "r") as zf:
                zf.extractall(tmpdir)

            data_file = os.path.join(tmpdir, "database.json")
            if not os.path.exists(data_file):
                err = "Corrupt archive: database.json missing inside backup."
                job.update_last_step("FAILED", err)
                job.status = "FAILED"
                app.status = ApplicationStatus.RECOVERY_FAILED
                disaster_event.status = DisasterStatus.FAILED
                disaster_event.failure_reason = err
                db.session.commit()
                return disaster_event

            with open(data_file, "r", encoding="utf-8") as f:
                restored_data = json.load(f)

            job.update_last_step("COMPLETED", "Extracted backup payload into isolated recovery workspace")
            db.session.commit()

            # -------------------------------------------------------------
            # STEP 4: Restore Application Data into DemoApp
            # -------------------------------------------------------------
            job.add_step("Restore data to application", "IN_PROGRESS", "Invoking DemoApp restore endpoint")
            db.session.commit()

            restore_url = f"{app.internal_url or Config.DEMOAPP_URL}/internal/restore"
            headers = {
                "X-Internal-Token": Config.INTERNAL_SECRET,
                "Content-Type": "application/json"
            }
            try:
                resp = requests.post(restore_url, json=restored_data, headers=headers, timeout=15)
                if resp.status_code != 200:
                    raise RuntimeError(f"Restore endpoint returned HTTP {resp.status_code}: {resp.text}")
                job.update_last_step("COMPLETED", f"Application database state restored: {resp.json().get('restored_records')}")
            except Exception as e:
                err = f"Data restoration request failed: {str(e)}"
                job.update_last_step("FAILED", err)
                job.status = "FAILED"
                app.status = ApplicationStatus.RECOVERY_FAILED
                disaster_event.status = DisasterStatus.FAILED
                disaster_event.failure_reason = err
                db.session.commit()
                return disaster_event

            db.session.commit()

            # -------------------------------------------------------------
            # STEP 5: Restart / Reset DemoApp Service State
            # -------------------------------------------------------------
            job.add_step("Reset application operational state", "IN_PROGRESS", "Disabling failure state on DemoApp")
            db.session.commit()

            disable_url = f"{app.internal_url or Config.DEMOAPP_URL}/internal/failure/disable"
            try:
                requests.post(disable_url, headers={"X-Internal-Token": Config.INTERNAL_SECRET}, timeout=5)
                job.update_last_step("COMPLETED", "Simulated failure mode deactivated on target application")
            except Exception as e:
                print(f"[WARN] Failure disable endpoint error: {e}")

            db.session.commit()

        # -------------------------------------------------------------
        # STEP 6: Run Recovery Verification (3 consecutive health checks + data verification)
        # -------------------------------------------------------------
        job.add_step("Recovery verification", "IN_PROGRESS", "Executing 3 consecutive health checks and validating data integrity")
        db.session.commit()

        verified = False
        consecutive_success = 0
        max_attempts = 10

        for attempt in range(max_attempts):
            time.sleep(1.0)
            try:
                h_resp = requests.get(app.health_url, timeout=3.0)
                if h_resp.status_code == 200 and h_resp.json().get("status") == "healthy":
                    consecutive_success += 1
                    if consecutive_success >= 3:
                        verified = True
                        break
                else:
                    consecutive_success = 0
            except Exception:
                consecutive_success = 0

        # Validate that application data is actually queryable
        data_verified = False
        if verified:
            try:
                data_endpoint = app.api_url if app.api_url else f"{Config.DEMOAPP_URL}/api/data"
                d_resp = requests.get(data_endpoint, timeout=3.0)
                if d_resp.status_code == 200 and "users" in d_resp.json().get("data", {}):
                    data_verified = True
            except Exception:
                data_verified = False

        if not (verified and data_verified):
            err = "Recovery verification failed: DemoApp failed to pass consecutive health checks or data query."
            job.update_last_step("FAILED", err)
            job.status = "FAILED"
            app.status = ApplicationStatus.RECOVERY_FAILED
            disaster_event.status = DisasterStatus.FAILED
            disaster_event.failure_reason = err
            db.session.commit()
            self.notifier.send_notification(
                subject=f"CRITICAL: Recovery verification failed for {app.name}",
                message=err,
                severity="CRITICAL",
                app_id=app.id
            )
            self.metrics.publish_metric("cdro_recovery_failure", 1)
            return disaster_event

        job.update_last_step("COMPLETED", "All health checks and data integrity checks confirmed healthy")
        db.session.commit()

        # -------------------------------------------------------------
        # STEP 7: Calculate RTO, RPO & Finalize Disaster Event
        # -------------------------------------------------------------
        completed_time = datetime.now(timezone.utc)
        recovery_duration = (completed_time - start_time).total_seconds()
        rto_seconds = recovery_duration
        rpo_seconds = max(0.0, (disaster_event.detected_at - selected_backup.created_at).total_seconds())
        rto_status = "PASS" if rto_seconds <= Config.RTO_TARGET_SECONDS else "EXCEEDED"

        disaster_event.status = DisasterStatus.SUCCESS
        disaster_event.recovery_completed_at = completed_time
        disaster_event.recovery_duration_seconds = recovery_duration
        disaster_event.rto_seconds = rto_seconds
        disaster_event.rpo_seconds = rpo_seconds
        disaster_event.rto_status = rto_status

        job.status = "COMPLETED"
        job.completed_at = completed_time
        job.add_step(
            "Finalize recovery",
            "COMPLETED",
            f"RTO: {recovery_duration:.1f}s ({rto_status}), RPO: {rpo_seconds:.0f}s. Application restored to HEALTHY."
        )

        app.status = ApplicationStatus.RECOVERED
        app.consecutive_failures = 0
        app.last_recovery = completed_time
        db.session.commit()

        # Audit log
        audit = AuditLog(
            timestamp=completed_time,
            application_id=app.id,
            event_type="RECOVERY_COMPLETED",
            severity="SUCCESS",
            message=f"Automatic recovery completed successfully for {app.name} in {recovery_duration:.1f}s (RTO: {rto_status}, RPO: {rpo_seconds:.0f}s). Backup used: {selected_backup.filename}",
            metadata_json=json.dumps({
                "disaster_event_id": disaster_event.id,
                "backup_used": selected_backup.filename,
                "recovery_duration_seconds": recovery_duration,
                "rto_status": rto_status,
                "rpo_seconds": rpo_seconds
            })
        )
        db.session.add(audit)

        # Transition application to HEALTHY
        app.status = ApplicationStatus.HEALTHY
        db.session.commit()

        # Notification
        self.notifier.send_notification(
            subject=f"SUCCESS: {app.name} automatically recovered",
            message=f"DemoApp was automatically recovered from disaster #{disaster_event.id}.\nBackup used: {selected_backup.filename}\nRecovery Duration (RTO): {recovery_duration:.1f}s (Target: {Config.RTO_TARGET_SECONDS}s, Status: {rto_status})\nRecovery Point (RPO): {rpo_seconds / 60.0:.1f} min\nSystem state: HEALTHY.",
            severity="SUCCESS",
            app_id=app.id
        )

        self.metrics.publish_metric("cdro_recovery_success", 1)
        self.metrics.publish_metric("cdro_recovery_duration", recovery_duration, unit="Seconds")

        return disaster_event
