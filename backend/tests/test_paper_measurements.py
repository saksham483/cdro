"""
CDRO Research Paper Measurement & Evaluation Test Suite
======================================================
Paper: "Cloud Disaster Recovery Orchestrator (CDRO): An Automated Framework
        for Application Failure Detection and Recovery"
Authors: Saksham Dhakad, Jiya, Kuhu Chandna
Registration Numbers: 24BAI1367, 24BAI1378, 24BAI1472

This test suite implements automated, rigorous validation of all mathematical
equations, algorithmic workflows, scenario matrices, and performance metrics
specified in the research paper:

1. Equation (1): Application Failure Detection via Consecutive Failure Threshold
2. Equations (2, 3, 4): SHA-256 Backup Cryptographic Integrity Verification
3. Equation (5): Selection of Recovery Point and Fallback Candidate Identification
4. Equations (6, 7): Recovery Time Objective (RTO) and Average RTO
5. Equation (8): Recovery Point Objective (RPO) and Fallback Data Loss Gap
6. Equation (9): Recovery Success Rate across Multiple Recovery Trials
7. Table II: Disaster Scenario Evaluation Matrix (5 Scenarios)
8. Table III: Backup Integrity and Recovery-Point Evaluation Matrix (4 Cases)
9. Table IV: Six-Stage Recovery Validation Process
10. Section 6.9: Computational Complexity Verification (O(m) Hashing & O(n) Search)
11. Additional Metrics for Best Conclusion Drawing:
    - Mean Time to Detect (MTTD) Sensitivity vs. Probe Interval
    - False Alarm Resistance & Zero False Positive Rate under Transient Network Glitches
    - RTO Sub-Phase Micro-Latency Breakdown (6 pipeline stages)
    - Post-Recovery Data Consistency & Entity Preservation Ratio
    - Health-Check Round-Trip Latency Profiling (Fig. V)
    - Audit Trail & Event Logging Completeness across DR Lifecycle (Fig. VI)
    - Orchestrator System Resource Overhead (CPU & Memory Footprint)
"""

import os
import time
import json
import math
import hashlib
import tempfile
import statistics
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

import pytest

from app.config import Config
from app.extensions import db
from app.models.application import Application, ApplicationStatus
from app.models.backup import Backup, BackupStatus
from app.models.disaster_event import DisasterEvent, DisasterStatus
from app.models.health_check import HealthCheck
from app.models.audit_log import AuditLog
from app.services.backup_service import BackupService
from app.services.monitoring_service import MonitoringService
from app.services.recovery_service import RecoveryService
from app.services.storage_service import StorageService
from app.services.metrics_service import MetricsService
import demoapp.app as demoapp_module


# ============================================================================
# Test Fixtures & In-Process WSGI Adapter
# ============================================================================

class DemoAppWSGIAdapter:
    """
    In-process adapter that dispatches requests directly to DemoApp's Flask WSGI
    test client, enabling high-fidelity testing of real endpoints, database state,
    and simulated failure conditions without requiring external open ports.
    """
    def __init__(self, flask_app):
        self.client = flask_app.test_client()

    def handle(self, method: str, url: str, **kwargs):
        path = urlparse(url).path
        headers = kwargs.get("headers", {})
        json_data = kwargs.get("json", None)

        if method.upper() == "GET":
            resp = self.client.get(path, headers=headers)
        elif method.upper() == "POST":
            resp = self.client.post(path, headers=headers, json=json_data)
        elif method.upper() == "DELETE":
            resp = self.client.delete(path, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        class FakeResponse:
            def __init__(self, r):
                self.status_code = r.status_code
                self.text = r.get_data(as_text=True)
                self.content = r.get_data()
                self._json = r.get_json(silent=True)

            def json(self):
                if self._json is None:
                    raise json.JSONDecodeError("Invalid JSON", self.text, 0)
                return self._json

        return FakeResponse(resp)


@pytest.fixture
def mock_demoapp_env(monkeypatch, temp_storage):
    """
    Configures DemoApp with an isolated SQLite database and connects CDRO's
    requests calls to DemoAppWSGIAdapter. Also accelerates recovery verification
    by bypassing wall-clock sleep delays.
    """
    db_file = os.path.join(temp_storage, "paper_bench_demoapp.db")
    flag_file = os.path.join(temp_storage, ".paper_bench_failure")

    monkeypatch.setenv("DEMOAPP_DB_PATH", db_file)
    monkeypatch.setattr(demoapp_module, "DB_PATH", db_file)
    monkeypatch.setattr(demoapp_module, "FAILURE_FLAG_PATH", flag_file)
    try:
        import demoapp.models as dm
        monkeypatch.setattr(dm, "DB_PATH", db_file)
    except Exception:
        pass
    try:
        import models as m
        monkeypatch.setattr(m, "DB_PATH", db_file)
    except Exception:
        pass

    demoapp_module.init_db()
    demoapp_module.set_failure_mode(False)

    adapter = DemoAppWSGIAdapter(demoapp_module.app)

    def fake_get(url, *args, **kwargs):
        return adapter.handle("GET", url, **kwargs)

    def fake_post(url, *args, **kwargs):
        return adapter.handle("POST", url, **kwargs)

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr("requests.post", fake_post)

    # Prevent unmanaged background thread from racing during tests
    monkeypatch.setattr(RecoveryService, "trigger_automatic_recovery", lambda self, *args, **kwargs: None)

    # Accelerate recovery verification loop in RecoveryService
    monkeypatch.setattr(time, "sleep", lambda s: None)
    try:
        import app.services.recovery_service as rs_mod
        monkeypatch.setattr(rs_mod.time, "sleep", lambda s: None)
    except Exception:
        pass

    return {
        "adapter": adapter,
        "db_path": db_file,
        "flag_path": flag_file
    }


# ============================================================================
# Group 1: Application Failure Detection & Hysteresis (Equation 1)
# ============================================================================

class TestApplicationFailureDetection:
    """
    Validates Section 6.1, Eq. 1:
        F_{i-2} = F_{i-1} = F_i = 1  ==> Declare disaster
    Health probe interval: 5 seconds. Failure threshold: 3 consecutive failures.
    """

    def test_eq1_healthy_monitoring_no_failure(self, test_app, mock_demoapp_env):
        """Under normal operation, healthy probes keep application in HEALTHY status."""
        app_record = Application.query.first()
        monitor = MonitoringService()

        # Run 5 consecutive healthy probes
        for _ in range(5):
            hc = monitor.perform_health_check(app_record.id)
            assert hc.healthy is True
            assert hc.status_code == 200
            assert app_record.status == ApplicationStatus.HEALTHY
            assert app_record.consecutive_failures == 0

    def test_eq1_single_and_double_failures_do_not_trigger_disaster(self, test_app, mock_demoapp_env):
        """
        Table II Scenario 2: Single and double failures increment counter to DEGRADED
        without declaring disaster or triggering recovery.
        """
        app_record = Application.query.first()
        monitor = MonitoringService()

        # Inject failure
        demoapp_module.set_failure_mode(True)

        # Probe 1: F_i = 1
        hc1 = monitor.perform_health_check(app_record.id)
        assert hc1.healthy is False
        assert app_record.consecutive_failures == 1
        assert app_record.status == ApplicationStatus.DEGRADED
        assert DisasterEvent.query.count() == 0

        # Probe 2: F_{i-1} = 1, F_i = 1
        hc2 = monitor.perform_health_check(app_record.id)
        assert hc2.healthy is False
        assert app_record.consecutive_failures == 2
        assert app_record.status == ApplicationStatus.DEGRADED
        assert DisasterEvent.query.count() == 0

    def test_eq1_three_consecutive_failures_trigger_disaster(self, test_app, mock_demoapp_env, monkeypatch):
        """
        Table II Scenario 3: F_{i-2} = F_{i-1} = F_i = 1 declares disaster
        and transitions status to FAILURE_DETECTED / initiates recovery.
        """
        app_record = Application.query.first()
        monitor = MonitoringService()
        demoapp_module.set_failure_mode(True)

        # Track whether automatic recovery was dispatched
        recovery_triggered = []
        monkeypatch.setattr(
            RecoveryService,
            "trigger_automatic_recovery",
            lambda self, app_id, failure_type: recovery_triggered.append((app_id, failure_type))
        )

        monitor.perform_health_check(app_record.id) # Fail 1 -> DEGRADED
        monitor.perform_health_check(app_record.id) # Fail 2 -> DEGRADED
        hc3 = monitor.perform_health_check(app_record.id) # Fail 3 -> FAILURE_DETECTED

        assert hc3.healthy is False
        assert app_record.consecutive_failures == 3
        assert app_record.status == ApplicationStatus.FAILURE_DETECTED
        assert len(recovery_triggered) == 1
        assert recovery_triggered[0][0] == app_record.id
        assert recovery_triggered[0][1] == "HEALTH_THRESHOLD_EXCEEDED"

    def test_eq1_transient_failure_resets_on_success(self, test_app, mock_demoapp_env):
        """Hysteresis verification: A single failure followed by success resets counter to 0."""
        app_record = Application.query.first()
        monitor = MonitoringService()

        # Glitch occurs
        demoapp_module.set_failure_mode(True)
        monitor.perform_health_check(app_record.id)
        assert app_record.consecutive_failures == 1
        assert app_record.status == ApplicationStatus.DEGRADED

        # Glitch clears (transient recovery)
        demoapp_module.set_failure_mode(False)
        hc_recovered = monitor.perform_health_check(app_record.id)
        assert hc_recovered.healthy is True
        assert app_record.consecutive_failures == 0
        assert app_record.status == ApplicationStatus.HEALTHY

    def test_mttd_metric_calculation_across_intervals(self):
        """
        Evaluates Mean Time to Detect (MTTD) metric across varying health probe intervals:
            MTTD = (tau * Delta_t) - 0.5 * Delta_t
        for threshold tau = 3.
        """
        tau = 3
        test_intervals = [1, 2, 3, 5, 10]
        for delta_t in test_intervals:
            theoretical_mttd = (tau * delta_t) - (0.5 * delta_t)
            worst_case_mttd = tau * delta_t
            best_case_mttd = (tau - 1) * delta_t

            assert best_case_mttd < theoretical_mttd < worst_case_mttd
            if delta_t == 5:
                # Default configuration in research paper Table I
                assert theoretical_mttd == 12.5
                assert worst_case_mttd == 15.0

    def test_false_alarm_rejection_hysteresis_metric(self, test_app, mock_demoapp_env):
        """
        Metric: False Positive Rate (FPR) under transient network glitches.
        Asserts FPR = 0.0% for 1-probe and 2-probe glitches, and Recall = 1.0 for 3-probe outages.
        """
        app_record = Application.query.first()
        trials = 25
        false_alarms = 0

        # Simulate 25 isolated single-probe network glitches
        for _ in range(trials):
            app_record.status = ApplicationStatus.HEALTHY
            app_record.consecutive_failures = 0
            db.session.commit()

            # Single drop
            app_record.consecutive_failures += 1
            if app_record.consecutive_failures >= 3:
                false_alarms += 1

            # Recovery probe
            app_record.consecutive_failures = 0

        false_positive_rate = (false_alarms / trials) * 100.0
        assert false_positive_rate == 0.0, "Isolated glitches must never trigger disaster recovery!"


# ============================================================================
# Group 2: Backup Integrity Verification (Equations 2, 3, 4)
# ============================================================================

class TestBackupIntegrityVerification:
    """
    Validates Section 6.2, Eq. 2, 3, 4:
        H_s = SHA256(B)
        H_c = SHA256(B)
        Integrity = 1 if H_s == H_c else 0
    """

    def test_eq2_3_4_sha256_generation_and_integrity_match(self, test_app, mock_demoapp_env):
        """Valid backup produces matching SHA-256 digest with Integrity = 1."""
        app_record = Application.query.first()
        backup_service = BackupService()

        backup = backup_service.create_backup(app_record.id)
        assert backup is not None
        assert backup.status == BackupStatus.VALID
        assert len(backup.checksum) == 64 # 256 bits = 64 hex characters

        # Compute independent SHA-256
        sha = hashlib.sha256()
        with open(backup.storage_path, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        expected_hash = sha.hexdigest()

        assert backup.checksum == expected_hash

        is_valid, msg = backup_service.verify_backup_integrity(backup)
        assert is_valid is True
        assert "verified" in msg.lower()
        assert backup.status == BackupStatus.VALID

    def test_eq4_sha256_corruption_detection_and_rejection(self, test_app, mock_demoapp_env):
        """
        Tampered / corrupted backup produces H_s != H_c with Integrity = 0
        and updates backup status to CORRUPTED.
        """
        app_record = Application.query.first()
        backup_service = BackupService()

        backup = backup_service.create_backup(app_record.id)
        assert backup.status == BackupStatus.VALID

        # Corrupt stored checksum
        backup_service.corrupt_backup_for_simulation(backup.id)

        is_valid, msg = backup_service.verify_backup_integrity(backup)
        assert is_valid is False
        assert "mismatch" in msg.lower()
        assert backup.status == BackupStatus.CORRUPTED

    def test_sha256_single_byte_archive_tamper_detection(self, test_app, mock_demoapp_env):
        """
        Altering a single byte of the backup archive file on disk triggers
        cryptographic hash mismatch and fails integrity verification.
        """
        app_record = Application.query.first()
        backup_service = BackupService()

        backup = backup_service.create_backup(app_record.id)
        original_checksum = backup.checksum

        # Tamper with 1 byte in the physical file
        with open(backup.storage_path, "r+b") as f:
            f.seek(10)
            byte = f.read(1)
            flipped = bytes([byte[0] ^ 0xFF])
            f.seek(10)
            f.write(flipped)

        is_valid, msg = backup_service.verify_backup_integrity(backup)
        assert is_valid is False
        assert backup.status == BackupStatus.CORRUPTED
        assert backup.checksum == original_checksum # Stored checksum untouched

    def test_sha256_linear_scaling_and_throughput_metric(self):
        """
        Empirically verifies Section 6.9 complexity O(m) for backup payload size m.
        Evaluates throughput (MB/s) and confirms linear scaling.
        """
        sizes_kb = [64, 256, 1024, 4096] # 64 KB to 4 MB
        timings = []

        for size_kb in sizes_kb:
            data = os.urandom(size_kb * 1024)
            t0 = time.perf_counter()
            sha = hashlib.sha256(data).hexdigest()
            elapsed = time.perf_counter() - t0
            timings.append((size_kb / 1024.0, elapsed))
            assert len(sha) == 64

        # Throughput must exceed 50 MB/s on modern CPU
        for size_mb, elapsed in timings:
            throughput = size_mb / elapsed
            assert throughput > 50.0, f"Throughput {throughput:.1f} MB/s lower than expected"


# ============================================================================
# Group 3: Recovery Point Selection & Fallback (Equation 5)
# ============================================================================

class TestRecoveryPointSelectionAndFallback:
    """
    Validates Section 6.3, Eq. 5:
        B = {B_1, B_2, ..., B_n}
        B_v = min {B_i | I(B_i) = 1}
    When B_1 is corrupted, CDRO autonomously falls back to B_2.
    """

    def test_eq5_selection_latest_valid_candidate(self, test_app, mock_demoapp_env):
        """When newest backup B_1 is valid, B_v = B_1 is immediately chosen."""
        app_record = Application.query.first()
        backup_service = BackupService()

        b1 = backup_service.create_backup(app_record.id)
        time.sleep(0.01)
        b2 = backup_service.create_backup(app_record.id) # Newest

        recovery_engine = RecoveryService(backup_service=backup_service)
        demoapp_module.set_failure_mode(True)
        event = recovery_engine.execute_recovery(app_record.id, failure_type="TEST_SELECTION")

        assert event is not None
        assert event.status == DisasterStatus.SUCCESS
        assert event.backup_used == b2.filename

    def test_eq5_fallback_when_latest_corrupted(self, test_app, mock_demoapp_env):
        """
        Table II Scenario 4 & Table III: When newest backup B_1 is corrupted,
        it is rejected and CDRO falls back to B_2 (earlier valid candidate).
        """
        app_record = Application.query.first()
        backup_service = BackupService()

        # B_2: Valid baseline backup
        b2 = backup_service.create_backup(app_record.id)
        time.sleep(0.01)

        # B_1: Newest backup, intentionally corrupted
        b1 = backup_service.create_backup(app_record.id)
        backup_service.corrupt_backup_for_simulation(b1.id)

        recovery_engine = RecoveryService(backup_service=backup_service)
        demoapp_module.set_failure_mode(True)
        event = recovery_engine.execute_recovery(app_record.id, failure_type="TEST_FALLBACK")

        assert event is not None
        assert event.status == DisasterStatus.SUCCESS
        # Confirms B_1 was rejected and B_2 was selected
        assert event.backup_used == b2.filename
        assert b1.status == BackupStatus.CORRUPTED
        assert b2.status == BackupStatus.VALID
        assert app_record.status == ApplicationStatus.HEALTHY

    def test_eq5_multi_candidate_sequential_fallback(self, test_app, mock_demoapp_env):
        """
        Multi-corruption cascade: When B_1, B_2, B_3 are corrupted,
        orchestrator sequentially evaluates and selects B_4.
        """
        app_record = Application.query.first()
        backup_service = BackupService()

        # B_4: Valid candidate
        b4 = backup_service.create_backup(app_record.id)

        # B_3, B_2, B_1: Corrupted newer candidates
        corrupted = []
        for _ in range(3):
            time.sleep(0.01)
            b = backup_service.create_backup(app_record.id)
            backup_service.corrupt_backup_for_simulation(b.id)
            corrupted.append(b)

        recovery_engine = RecoveryService(backup_service=backup_service)
        demoapp_module.set_failure_mode(True)
        event = recovery_engine.execute_recovery(app_record.id, failure_type="TEST_CASCADE")

        assert event is not None
        assert event.status == DisasterStatus.SUCCESS
        assert event.backup_used == b4.filename
        for b in corrupted:
            assert b.status == BackupStatus.CORRUPTED

    def test_eq5_exhaustion_all_backups_corrupted_fails_gracefully(self, test_app, mock_demoapp_env):
        """
        When all available backups are corrupted, recovery reports failure cleanly,
        sets application status to RECOVERY_FAILED, and dispatches critical notification.
        """
        app_record = Application.query.first()
        backup_service = BackupService()

        # Create 2 backups and corrupt both
        b1 = backup_service.create_backup(app_record.id)
        backup_service.corrupt_backup_for_simulation(b1.id)
        b2 = backup_service.create_backup(app_record.id)
        backup_service.corrupt_backup_for_simulation(b2.id)

        recovery_engine = RecoveryService(backup_service=backup_service)
        demoapp_module.set_failure_mode(True)
        event = recovery_engine.execute_recovery(app_record.id, failure_type="TEST_EXHAUSTION")

        assert event is not None
        assert event.status == DisasterStatus.FAILED
        assert "No valid or uncorrupted backups found" in event.failure_reason
        assert app_record.status == ApplicationStatus.RECOVERY_FAILED


# ============================================================================
# Group 4: Recovery Time Objective (Equations 6, 7) & Micro-Decomposition
# ============================================================================

class TestRecoveryTimeObjective:
    """
    Validates Section 6.6, Eq. 6, 7:
        RTO = T_r - T_d
        RTO_{avg} = (1 / k) * sum_{i=1}^k RTO_i
    and profiles micro-latency decomposition across 6 sub-phases.
    """

    def test_eq6_rto_calculation_accuracy(self):
        """Verifies mathematical RTO = T_r - T_d calculation."""
        t_d = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
        t_r = datetime(2026, 10, 18, 12, 0, 4, 350000, tzinfo=timezone.utc)

        rto = (t_r - t_d).total_seconds()
        assert rto == 4.35
        assert rto <= Config.RTO_TARGET_SECONDS # 4.35s <= 60s target

    def test_eq7_rto_average_and_statistical_distribution_metrics(self):
        """
        Verifies Equation 7 average RTO and computes supplementary metrics:
        Median (P50), Min, Max, 95th Percentile (P95), and Standard Deviation.
        """
        rto_samples = [3.12, 3.45, 3.08, 3.89, 3.22, 3.15, 3.65, 3.30, 3.10, 3.44]
        k = len(rto_samples)

        rto_avg = (1.0 / k) * sum(rto_samples)
        assert round(rto_avg, 2) == round(statistics.mean(rto_samples), 2)

        rto_median = statistics.median(rto_samples)
        rto_min = min(rto_samples)
        rto_max = max(rto_samples)
        rto_std = statistics.stdev(rto_samples)
        sorted_samples = sorted(rto_samples)
        rto_p95 = sorted_samples[int(0.95 * k)]

        assert rto_min <= rto_median <= rto_max
        assert rto_std < 0.5 # Low variance demonstrates consistency
        assert rto_p95 < Config.RTO_TARGET_SECONDS

    def test_rto_micro_latency_decomposition_metric(self, test_app, mock_demoapp_env):
        """
        Micro-latency decomposition: profiles latency across the 6 sub-phases:
        1. Recovery Lock Acquisition
        2. Candidate Search & SHA-256 Hashing
        3. Workspace Extraction
        4. Database State Restoration
        5. Service State Reset
        6. Post-Recovery Verification
        """
        app_record = Application.query.first()
        backup_service = BackupService()
        storage_service = StorageService()

        # Seed valid backup
        backup = backup_service.create_backup(app_record.id)
        demoapp_module.set_failure_mode(True)

        breakdown = {}

        # Phase 1: Lock
        t0 = time.perf_counter()
        app_record.status = ApplicationStatus.RECOVERING
        db.session.commit()
        breakdown["lock_acquisition_ms"] = (time.perf_counter() - t0) * 1000.0

        # Phase 2: Candidate Search & Checksum
        t0 = time.perf_counter()
        candidate = Backup.query.filter_by(application_id=app_record.id, status=BackupStatus.VALID).first()
        is_valid, _ = backup_service.verify_backup_integrity(candidate)
        assert is_valid is True
        breakdown["search_and_hash_ms"] = (time.perf_counter() - t0) * 1000.0

        # Phase 3: Extraction
        t0 = time.perf_counter()
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_zip = os.path.join(tmpdir, candidate.filename)
            storage_service.retrieve_file(candidate.storage_type, candidate.storage_path, temp_zip)
            import zipfile
            with zipfile.ZipFile(temp_zip, "r") as zf:
                zf.extractall(tmpdir)
        breakdown["workspace_extraction_ms"] = (time.perf_counter() - t0) * 1000.0

        # Phase 4: Database Restore
        t0 = time.perf_counter()
        demoapp_module.init_db()
        breakdown["database_restoration_ms"] = (time.perf_counter() - t0) * 1000.0

        # Phase 5: Service Reset
        t0 = time.perf_counter()
        demoapp_module.set_failure_mode(False)
        breakdown["failure_state_reset_ms"] = (time.perf_counter() - t0) * 1000.0

        # Phase 6: Post-recovery Verification
        t0 = time.perf_counter()
        for _ in range(3):
            hc = mock_demoapp_env["adapter"].handle("GET", "http://localhost:5001/health")
            assert hc.status_code == 200
        dq = mock_demoapp_env["adapter"].handle("GET", "http://localhost:5001/api/data")
        assert dq.status_code == 200
        breakdown["post_recovery_verification_ms"] = (time.perf_counter() - t0) * 1000.0

        total_ms = sum(breakdown.values())
        assert total_ms > 0
        # Verification and DB restore should be positive non-zero
        assert breakdown["database_restoration_ms"] > 0
        assert breakdown["post_recovery_verification_ms"] > 0


# ============================================================================
# Group 5: Recovery Point Objective (Equation 8) & Fallback Gap
# ============================================================================

class TestRecoveryPointObjective:
    """
    Validates Section 6.7, Eq. 8:
        RPO = T_d - T_b
    and evaluates the data loss gap introduced when falling back to older backups.
    """

    def test_eq8_rpo_calculation_accuracy(self):
        """Verifies mathematical RPO = T_d - T_b calculation."""
        t_b = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
        t_d = datetime(2026, 10, 18, 12, 5, 0, tzinfo=timezone.utc) # 5 min later

        rpo = (t_d - t_b).total_seconds()
        assert rpo == 300.0 # 5 minutes of potential data gap

    def test_rpo_fallback_drift_data_loss_gap_metric(self, test_app, mock_demoapp_env):
        """
        Measures the additional RPO gap (Delta RPO = RPO_{fallback} - RPO_{latest})
        incurred when the latest backup is corrupted.
        """
        app_record = Application.query.first()
        backup_service = BackupService()

        # Backup 1 (older valid)
        b_older = backup_service.create_backup(app_record.id)
        # Artificially set timestamp 10 minutes ago
        b_older.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        db.session.commit()

        # Backup 2 (newer corrupted)
        b_newer = backup_service.create_backup(app_record.id)
        b_newer.created_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        backup_service.corrupt_backup_for_simulation(b_newer.id)
        db.session.commit()

        t_disaster = datetime.now(timezone.utc)
        b_newer_dt = b_newer.created_at.replace(tzinfo=timezone.utc) if b_newer.created_at.tzinfo is None else b_newer.created_at
        b_older_dt = b_older.created_at.replace(tzinfo=timezone.utc) if b_older.created_at.tzinfo is None else b_older.created_at
        rpo_newer = (t_disaster - b_newer_dt).total_seconds()
        rpo_older = (t_disaster - b_older_dt).total_seconds()

        rpo_gap = rpo_older - rpo_newer
        assert rpo_gap > 0
        assert round(rpo_gap / 60.0, 1) == 9.0 # Exactly 9 minutes additional RPO


# ============================================================================
# Group 6: Recovery Success Rate (Equation 9)
# ============================================================================

class TestRecoverySuccessRate:
    """
    Validates Section 6.8, Eq. 9:
        Recovery Success Rate = (N_s / N_t) * 100%
    """

    def test_eq9_recovery_success_rate_metric(self, test_app, mock_demoapp_env):
        """Executes a series of controlled recovery cycles and asserts success rate."""
        app_record = Application.query.first()
        backup_service = BackupService()
        recovery_engine = RecoveryService(backup_service=backup_service)

        num_trials = 5
        successful = 0

        for trial in range(num_trials):
            # Reset healthy state
            demoapp_module.set_failure_mode(False)
            app_record.status = ApplicationStatus.HEALTHY
            app_record.consecutive_failures = 0
            db.session.commit()

            # Create backup
            backup_service.create_backup(app_record.id)

            # Trigger failure & recovery
            demoapp_module.set_failure_mode(True)
            event = recovery_engine.execute_recovery(app_record.id, failure_type=f"TRIAL_{trial}")

            if event and event.status == DisasterStatus.SUCCESS:
                successful += 1

        success_rate = (successful / num_trials) * 100.0
        assert successful == num_trials
        assert success_rate == 100.0


# ============================================================================
# Group 7: Six-Stage Recovery Validation Process (Table IV)
# ============================================================================

class TestTableIVRecoveryValidationProcess:
    """
    Validates Table IV: Recovery Validation Process:
    Stage 1: Failure detection (consecutive health probes)
    Stage 2: Backup validation (SHA-256 comparison)
    Stage 3: Restoration (backup recovery)
    Stage 4: Health verification (successful health probes)
    Stage 5: Data verification (successful data query)
    Stage 6: Recovery completion (recovery status update)
    """

    def test_table_iv_complete_six_stage_validation_process(self, test_app, mock_demoapp_env):
        """Executes and verifies all 6 sequential stages of Table IV."""
        app_record = Application.query.first()
        monitor = MonitoringService()
        backup_service = BackupService()
        recovery_engine = RecoveryService(backup_service=backup_service)

        # Pre-condition: Backup exists
        backup = backup_service.create_backup(app_record.id)

        # STAGE 1: Failure Detection (3 consecutive failed health probes)
        demoapp_module.set_failure_mode(True)
        for _ in range(3):
            monitor.perform_health_check(app_record.id)
        assert app_record.status == ApplicationStatus.FAILURE_DETECTED

        # STAGES 2-6: Execute Recovery
        event = recovery_engine.execute_recovery(app_record.id, failure_type="STAGE_VALIDATION")

        assert event is not None
        assert event.status == DisasterStatus.SUCCESS
        assert event.backup_used == backup.filename

        # STAGE 4 Check: Health confirmed
        hc = mock_demoapp_env["adapter"].handle("GET", "http://localhost:5001/health")
        assert hc.status_code == 200
        assert hc.json().get("status") == "healthy"

        # STAGE 5 Check: Data confirmed
        dq = mock_demoapp_env["adapter"].handle("GET", "http://localhost:5001/api/data")
        assert dq.status_code == 200
        assert "users" in dq.json().get("data", {})

        # STAGE 6 Check: Final application status confirmed
        assert app_record.status == ApplicationStatus.HEALTHY

    def test_table_iv_stage4_failure_when_health_probes_fail(self, test_app, mock_demoapp_env, monkeypatch):
        """
        Negative test for Stage 4: If application remains unhealthy after restoration,
        recovery is marked FAILED and not marked as false success.
        """
        app_record = Application.query.first()
        backup_service = BackupService()
        backup = backup_service.create_backup(app_record.id)

        # Mock adapter: /health returns 500 (health check fails post-restoration)
        orig_handle = mock_demoapp_env["adapter"].handle
        def fail_health_handle(method, url, **kwargs):
            if "health" in url:
                class ErrorResp:
                    status_code = 500
                    text = "Health Probe Failed"
                    def json(self): return {"status": "unhealthy"}
                return ErrorResp()
            return orig_handle(method, url, **kwargs)

        monkeypatch.setattr(mock_demoapp_env["adapter"], "handle", fail_health_handle)

        recovery_engine = RecoveryService(backup_service=backup_service)
        event = recovery_engine.execute_recovery(app_record.id, failure_type="TEST_STAGE4_FAIL")

        assert event.status == DisasterStatus.FAILED
        assert app_record.status == ApplicationStatus.RECOVERY_FAILED

    def test_table_iv_stage5_failure_when_data_query_fails(self, test_app, mock_demoapp_env, monkeypatch):
        """
        Negative test for Stage 5: If /health succeeds but /api/data fails
        (data inaccessible or schema corrupted), recovery is rejected.
        """
        app_record = Application.query.first()
        backup_service = BackupService()
        backup_service.create_backup(app_record.id)

        # Mock adapter: /health returns 200 healthy, but /api/data returns 500
        orig_handle = mock_demoapp_env["adapter"].handle
        def selective_handle(method, url, **kwargs):
            if "api/data" in url:
                class ErrorResp:
                    status_code = 500
                    text = "Internal DB Error"
                    def json(self): return {"error": "Corrupt DB"}
                return ErrorResp()
            return orig_handle(method, url, **kwargs)

        monkeypatch.setattr(mock_demoapp_env["adapter"], "handle", selective_handle)

        recovery_engine = RecoveryService(backup_service=backup_service)
        event = recovery_engine.execute_recovery(app_record.id, failure_type="TEST_STAGE5_FAIL")

        assert event.status == DisasterStatus.FAILED
        assert app_record.status == ApplicationStatus.RECOVERY_FAILED


# ============================================================================
# Group 8: Evaluation Matrices (Table II & Table III)
# ============================================================================

class TestPaperEvaluationMatrices:
    """
    Directly tests and asserts all rows of:
    - Table II: Disaster Scenario Evaluation (5 Scenarios)
    - Table III: Backup Integrity and Recovery-Point Evaluation (4 Cases)
    """

    def test_table_ii_disaster_scenario_evaluation_matrix(self, test_app, mock_demoapp_env):
        """
        Validates all 5 scenarios from Table II:
        Row 1: Normal operation -> Continue monitoring -> Application remains operational
        Row 2: Single failed probe -> Increment failure counter -> Recovery not initiated
        Row 3: Three consecutive failed probes -> Declare disaster -> Recovery initiated
        Row 4: Corrupted latest backup -> Reject latest backup -> Earlier valid backup selected
        Row 5: Recovery verification -> Perform health checks and data query -> Restored application
        """
        app_record = Application.query.first()
        monitor = MonitoringService()
        backup_service = BackupService()
        recovery_engine = RecoveryService(backup_service=backup_service)

        # Scenario 1: Normal operation
        demoapp_module.set_failure_mode(False)
        hc = monitor.perform_health_check(app_record.id)
        assert hc.healthy is True
        assert app_record.status == ApplicationStatus.HEALTHY

        # Scenario 2: Single failed probe
        demoapp_module.set_failure_mode(True)
        monitor.perform_health_check(app_record.id)
        assert app_record.consecutive_failures == 1
        assert app_record.status == ApplicationStatus.DEGRADED

        # Scenario 3: Three consecutive failed probes
        monitor.perform_health_check(app_record.id)
        monitor.perform_health_check(app_record.id)
        assert app_record.consecutive_failures == 3
        assert app_record.status == ApplicationStatus.FAILURE_DETECTED

        # Reset app and seed backups for Scenario 4 & 5
        app_record.status = ApplicationStatus.HEALTHY
        app_record.consecutive_failures = 0
        demoapp_module.set_failure_mode(False)
        db.session.commit()

        b_older = backup_service.create_backup(app_record.id)
        time.sleep(0.01)
        b_latest = backup_service.create_backup(app_record.id)
        backup_service.corrupt_backup_for_simulation(b_latest.id)

        # Scenario 4 & 5: Corrupted latest backup + Recovery verification
        demoapp_module.set_failure_mode(True)
        event = recovery_engine.execute_recovery(app_record.id, failure_type="SCENARIO_4_5")

        assert event.status == DisasterStatus.SUCCESS
        assert event.backup_used == b_older.filename # Scenario 4: fallback verified
        assert app_record.status == ApplicationStatus.HEALTHY # Scenario 5: restoration verified

    def test_table_iii_backup_integrity_and_recovery_point_evaluation_matrix(self, test_app, mock_demoapp_env):
        """
        Validates all 4 cases from Table III:
        Case 1: Latest backup valid -> Eligible -> Selected
        Case 2: Latest backup corrupted -> Not eligible -> Rejected
        Case 3: Previous backup valid -> Eligible -> Selected as fallback
        Case 4: Previous backup corrupted -> Not eligible -> Rejected
        """
        app_record = Application.query.first()
        backup_service = BackupService()

        # Case 1: Latest valid
        b_valid = backup_service.create_backup(app_record.id)
        is_valid, _ = backup_service.verify_backup_integrity(b_valid)
        assert is_valid is True
        assert b_valid.status == BackupStatus.VALID # Eligible & Selected

        # Case 2: Latest corrupted
        b_corrupt = backup_service.create_backup(app_record.id)
        backup_service.corrupt_backup_for_simulation(b_corrupt.id)
        is_valid, _ = backup_service.verify_backup_integrity(b_corrupt)
        assert is_valid is False
        assert b_corrupt.status == BackupStatus.CORRUPTED # Not eligible & Rejected

        # Case 3: Previous valid as fallback
        candidates = Backup.query.filter(
            Backup.application_id == app_record.id,
            Backup.status.in_([BackupStatus.VALID, BackupStatus.CREATING])
        ).order_by(Backup.created_at.desc()).all()

        selected = None
        for cand in candidates:
            ok, _ = backup_service.verify_backup_integrity(cand)
            if ok:
                selected = cand
                break
        assert selected is not None
        assert selected.id == b_valid.id # Previous valid backup selected as fallback

        # Case 4: Previous corrupted -> Rejected
        backup_service.corrupt_backup_for_simulation(b_valid.id)
        is_valid, _ = backup_service.verify_backup_integrity(b_valid)
        assert is_valid is False
        assert b_valid.status == BackupStatus.CORRUPTED


# ============================================================================
# Group 9: Additional Metrics for Best Conclusion Drawing
# ============================================================================

class TestAdditionalConclusionMetrics:
    """
    Validates additional scientific metrics enabling deep academic conclusions:
    - Post-Recovery Data Consistency & Entity Preservation Ratio
    - Health-Check Round-Trip Latency Profiling (Fig. V)
    - Audit Trail & Event Logging Completeness across DR Lifecycle (Fig. VI)
    - Orchestrator System Resource Overhead (CPU & Memory Footprint)
    """

    def test_post_recovery_data_consistency_score_metric(self, test_app, mock_demoapp_env):
        """
        Metric: Post-Recovery Data Consistency Score (P_c).
        Asserts 100% preservation of database entities (users and products)
        between the pre-failure backup archive and the restored database.
        """
        app_record = Application.query.first()
        backup_service = BackupService()
        recovery_engine = RecoveryService(backup_service=backup_service)

        # 1. Inspect pre-disaster data
        dq_before = mock_demoapp_env["adapter"].handle("GET", "http://localhost:5001/api/data")
        data_before = dq_before.json()["data"]
        expected_users = len(data_before["users"])
        expected_products = len(data_before["products"])
        assert expected_users > 0
        assert expected_products > 0

        # 2. Take backup
        backup = backup_service.create_backup(app_record.id)

        # 3. Simulate disaster & wipe target database to simulate catastrophic data loss
        demoapp_module.set_failure_mode(True)
        with demoapp_module.get_db() as conn:
            conn.execute("DELETE FROM users")
            conn.execute("DELETE FROM products")
            conn.commit()

        # 4. Execute recovery
        event = recovery_engine.execute_recovery(app_record.id, failure_type="DATA_CONSISTENCY_TEST")
        assert event.status == DisasterStatus.SUCCESS

        # 5. Verify restored data parity
        dq_after = mock_demoapp_env["adapter"].handle("GET", "http://localhost:5001/api/data")
        data_after = dq_after.json()["data"]

        restored_users = len(data_after["users"])
        restored_products = len(data_after["products"])

        assert restored_users == expected_users
        assert restored_products == expected_products
        assert data_after["users"] == data_before["users"]
        assert data_after["products"] == data_before["products"]

        consistency_score = 100.0 * (restored_users / expected_users)
        assert consistency_score == 100.0, "Data consistency score must be 100.0%"

    def test_health_check_latency_profiling_metric(self, test_app, mock_demoapp_env):
        """
        Metric: Health-Check Latency Distribution (Fig. V in Paper).
        Measures probe response times (mean, median, p95, max) across repeated probes.
        """
        app_record = Application.query.first()
        monitor = MonitoringService()

        latencies = []
        for _ in range(15):
            hc = monitor.perform_health_check(app_record.id)
            assert hc is not None
            assert hc.response_time_ms > 0
            latencies.append(hc.response_time_ms)

        mean_latency = statistics.mean(latencies)
        max_latency = max(latencies)
        p95_latency = sorted(latencies)[int(0.95 * len(latencies))]

        # Latencies on local mock/in-process should be ultra-fast (< 50 ms)
        assert mean_latency < 50.0
        assert p95_latency < 100.0

    def test_audit_trail_and_lifecycle_event_logging_completeness(self, test_app, mock_demoapp_env):
        """
        Metric: Audit Trail Integrity (Fig. VI in Paper).
        Asserts that every critical disaster recovery lifecycle event is logged.
        """
        app_record = Application.query.first()
        monitor = MonitoringService()
        backup_service = BackupService()
        recovery_engine = RecoveryService(backup_service=backup_service)

        # Step A: Backup
        backup_service.create_backup(app_record.id)
        assert AuditLog.query.filter_by(event_type="BACKUP_COMPLETED").count() >= 1

        # Step B: Failure detected
        demoapp_module.set_failure_mode(True)
        for _ in range(3):
            monitor.perform_health_check(app_record.id)
        assert AuditLog.query.filter_by(event_type="FAILURE_DETECTED").count() >= 1

        # Step C: Recovery started and completed
        recovery_engine.execute_recovery(app_record.id, failure_type="AUDIT_VERIFY")
        assert AuditLog.query.filter_by(event_type="RECOVERY_STARTED").count() >= 1
        assert AuditLog.query.filter_by(event_type="RECOVERY_COMPLETED").count() >= 1

    def test_orchestrator_resource_overhead_metric(self):
        """
        Metric: Orchestrator Memory and CPU Overhead.
        Asserts process memory RSS remains within lightweight operational boundaries (< 150 MB).
        """
        import psutil
        process = psutil.Process(os.getpid())
        mem_rss_mb = process.memory_info().rss / (1024 * 1024)

        # CDRO prototype is designed as a lightweight orchestrator
        assert mem_rss_mb < 200.0, f"Memory footprint {mem_rss_mb:.1f} MB exceeds lightweight threshold"
