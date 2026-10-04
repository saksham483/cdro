import os
import json
import zipfile
import tempfile
import requests
from datetime import datetime, timezone
from app.config import Config
from app.extensions import db
from app.models.application import Application
from app.models.backup import Backup, BackupStatus
from app.models.audit_log import AuditLog
from app.services.storage_service import StorageService
from app.services.metrics_service import MetricsService
from app.utils.helpers import calculate_sha256

class BackupService:
    def __init__(self, storage_service=None, metrics_service=None):
        self.storage = storage_service or StorageService()
        self.metrics = metrics_service or MetricsService()

    def create_backup(self, application_id: int) -> Backup:
        app = db.session.get(Application, application_id)
        if not app:
            raise ValueError(f"Application {application_id} not found")

        timestamp = datetime.now(timezone.utc)
        time_str = timestamp.strftime("%Y%m%d_%H%M%S") + f"_{timestamp.microsecond // 1000:03d}"
        filename = f"backup_{app.name.lower()}_{time_str}.zip"

        # 1. Fetch data from DemoApp's export endpoint
        export_url = f"{app.internal_url or Config.DEMOAPP_URL}/internal/backup/export"
        headers = {"X-Internal-Token": Config.INTERNAL_SECRET}
        try:
            resp = requests.get(export_url, headers=headers, timeout=10)
            if resp.status_code != 200:
                raise RuntimeError(f"DemoApp backup export returned HTTP {resp.status_code}: {resp.text}")
            exported_data = resp.json()
        except Exception as e:
            # Audit log failure
            audit = AuditLog(
                timestamp=timestamp,
                application_id=app.id,
                event_type="BACKUP_FAILED",
                severity="ERROR",
                message=f"Failed to export data from DemoApp: {str(e)}"
            )
            db.session.add(audit)
            db.session.commit()
            self.metrics.publish_metric("cdro_backup_failure", 1)
            raise RuntimeError(f"DemoApp export failed: {e}")

        # 2. Package into temporary zip archive
        with tempfile.TemporaryDirectory() as tmpdir:
            data_file_path = os.path.join(tmpdir, "database.json")
            with open(data_file_path, "w", encoding="utf-8") as f:
                json.dump(exported_data, f, indent=2)

            meta_file_path = os.path.join(tmpdir, "metadata.json")
            metadata = {
                "application": app.name,
                "version": "1.0.0",
                "created_at": timestamp.isoformat(),
                "users_count": len(exported_data.get("database", {}).get("users", [])),
                "products_count": len(exported_data.get("database", {}).get("products", []))
            }
            with open(meta_file_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            zip_path = os.path.join(tmpdir, filename)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(data_file_path, arcname="database.json")
                zf.write(meta_file_path, arcname="metadata.json")

            # 3. Calculate SHA-256 Checksum
            checksum = calculate_sha256(zip_path)
            file_size = os.path.getsize(zip_path)

            # 4. Save to Storage
            relative_key = self.storage.get_hierarchical_path(app.name, filename, timestamp)
            storage_type, storage_path = self.storage.save_file(zip_path, relative_key)

        # 5. Record metadata in Database
        backup = Backup(
            application_id=app.id,
            filename=filename,
            file_size=file_size,
            checksum=checksum,
            storage_type=storage_type,
            storage_path=storage_path,
            status=BackupStatus.VALID,
            data_summary=json.dumps(metadata),
            created_at=timestamp
        )
        db.session.add(backup)

        app.last_successful_backup = timestamp
        audit = AuditLog(
            timestamp=timestamp,
            application_id=app.id,
            event_type="BACKUP_COMPLETED",
            severity="INFO",
            message=f"Successfully created backup {filename} ({file_size} bytes, SHA-256: {checksum[:12]}...)",
            metadata_json=json.dumps({
                "backup_id": backup.id,
                "filename": filename,
                "storage_type": storage_type,
                "storage_path": storage_path,
                "checksum": checksum
            })
        )
        db.session.add(audit)
        db.session.commit()

        # 6. Apply Retention Policy
        self.apply_retention_policy(app.id)

        self.metrics.publish_metric("cdro_backup_success", 1)
        return backup

    def verify_backup_integrity(self, backup: Backup) -> tuple[bool, str]:
        """
        Verifies SHA-256 checksum of the backup archive.
        Returns: (is_valid: bool, message: str)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_zip = os.path.join(tmpdir, backup.filename)
            ok = self.storage.retrieve_file(backup.storage_type, backup.storage_path, temp_zip)
            if not ok or not os.path.exists(temp_zip):
                backup.status = BackupStatus.FAILED
                db.session.commit()
                return False, f"Could not retrieve backup file from {backup.storage_path}"

            actual_checksum = calculate_sha256(temp_zip)
            if actual_checksum != backup.checksum:
                backup.status = BackupStatus.CORRUPTED
                audit = AuditLog(
                    timestamp=datetime.now(timezone.utc),
                    application_id=backup.application_id,
                    event_type="BACKUP_VERIFICATION_FAILED",
                    severity="ERROR",
                    message=f"Backup {backup.filename} checksum mismatch! Stored: {backup.checksum[:16]}..., Actual: {actual_checksum[:16]}...",
                    metadata_json=json.dumps({
                        "backup_id": backup.id,
                        "stored_checksum": backup.checksum,
                        "actual_checksum": actual_checksum
                    })
                )
                db.session.add(audit)
                db.session.commit()
                self.metrics.publish_metric("cdro_backup_failure", 1)
                return False, f"Checksum mismatch: expected {backup.checksum}, calculated {actual_checksum}"

            return True, "Checksum successfully verified"

    def apply_retention_policy(self, application_id: int):
        retention_count = Config.BACKUP_RETENTION_COUNT
        valid_backups = Backup.query.filter_by(
            application_id=application_id,
            status=BackupStatus.VALID
        ).order_by(Backup.created_at.desc()).all()

        if len(valid_backups) > retention_count:
            excess = valid_backups[retention_count:]
            for old_b in excess:
                self.storage.delete_file(old_b.storage_type, old_b.storage_path)
                old_b.status = BackupStatus.DELETED
                audit = AuditLog(
                    timestamp=datetime.now(timezone.utc),
                    application_id=application_id,
                    event_type="BACKUP_DELETED",
                    severity="INFO",
                    message=f"Retention policy pruned old backup {old_b.filename}"
                )
                db.session.add(audit)
            db.session.commit()

    def corrupt_backup_for_simulation(self, backup_id: int) -> Backup:
        """Deliberately alters checksum or file to simulate corruption for test scenario"""
        backup = db.session.get(Backup, backup_id)
        if not backup:
            raise ValueError(f"Backup {backup_id} not found")

        # Invert/modify stored checksum
        backup.checksum = "corrupted_checksum_" + backup.checksum[19:]
        audit = AuditLog(
            timestamp=datetime.now(timezone.utc),
            application_id=backup.application_id,
            event_type="SIMULATION_BACKUP_CORRUPTED",
            severity="WARNING",
            message=f"[DEMO SIMULATION] Checksum corrupted intentionally for {backup.filename} to test fallback logic."
        )
        db.session.add(audit)
        db.session.commit()
        return backup
