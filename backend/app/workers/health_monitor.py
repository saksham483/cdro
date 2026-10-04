import time
import threading
from app.config import Config
from app.extensions import db
from app.models.application import Application
from app.services.monitoring_service import MonitoringService

class HealthMonitorWorker:
    def __init__(self, app_factory):
        self.app_factory = app_factory
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True, name="HealthMonitorWorker")
        self.thread.start()
        print(f"[WORKER] HealthMonitorWorker started (interval: {Config.HEALTH_CHECK_INTERVAL_SECONDS}s)")

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)

    def _run(self):
        time.sleep(2) # Initial warmup delay
        while not self.stop_event.is_set():
            app = self.app_factory()
            with app.app_context():
                try:
                    monitoring_service = MonitoringService()
                    applications = Application.query.all()
                    for target_app in applications:
                        if self.stop_event.is_set():
                            break
                        try:
                            monitoring_service.perform_health_check(target_app.id)
                        except Exception as e:
                            print(f"[ERROR] Health check failed for {target_app.name}: {e}")
                except Exception as ex:
                    print(f"[ERROR] Error in HealthMonitorWorker loop: {ex}")
            self.stop_event.wait(Config.HEALTH_CHECK_INTERVAL_SECONDS)
