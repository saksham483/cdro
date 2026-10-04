import time
import threading
from datetime import datetime, timezone
from app.config import Config
from app.extensions import db
from app.models.application import Application, ApplicationStatus
from app.models.backup import Backup
from app.services.backup_service import BackupService

class BackupSchedulerWorker:
    def __init__(self, app_factory):
        self.app_factory = app_factory
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True, name="BackupSchedulerWorker")
        self.thread.start()
        print(f"[WORKER] BackupSchedulerWorker started (interval: {Config.BACKUP_INTERVAL_SECONDS}s)")

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)

    def _run(self):
        time.sleep(3) # Wait for initial bootstrap
        while not self.stop_event.is_set():
            app = self.app_factory()
            with app.app_context():
                try:
                    backup_service = BackupService()
                    applications = Application.query.all()
                    now = datetime.now(timezone.utc)
                    for target_app in applications:
                        if self.stop_event.is_set():
                            break
                        # Do not backup if recovering or failed
                        if target_app.status in (ApplicationStatus.RECOVERING, ApplicationStatus.FAILURE_DETECTED):
                            continue

                        # Check if application has no backup at all, or interval expired
                        should_backup = False
                        if not target_app.last_successful_backup:
                            should_backup = True
                        else:
                            last_backup_dt = target_app.last_successful_backup
                            if last_backup_dt.tzinfo is None:
                                last_backup_dt = last_backup_dt.replace(tzinfo=timezone.utc)
                            elapsed = (now - last_backup_dt).total_seconds()
                            if elapsed >= Config.BACKUP_INTERVAL_SECONDS:
                                should_backup = True

                        if should_backup:
                            try:
                                print(f"[SCHEDULER] Triggering scheduled backup for {target_app.name}...")
                                backup_service.create_backup(target_app.id)
                            except Exception as e:
                                print(f"[ERROR] Scheduled backup failed for {target_app.name}: {e}")
                except Exception as ex:
                    print(f"[ERROR] Error in BackupSchedulerWorker loop: {ex}")
            # Check every 10 seconds if any backup is due
            self.stop_event.wait(10)
