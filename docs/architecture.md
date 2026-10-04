# CDRO Architecture Specification

## 1. System Overview

The **Cloud Disaster Recovery Orchestrator (CDRO)** is structured around an event-driven control plane that decouples monitoring, backup creation, and automated disaster recovery.

```
                    OPERATOR / SRE
                          │
                          ▼
             ┌────────────────────────┐
             │ CDRO Operations Console│
             │   (HTML5 / Chart.js)   │
             └────────────┬───────────┘
                          │ Polling / REST
                          ▼
             ┌────────────────────────┐
             │    Flask REST API      │
             │ (Auth / RBAC / Events) │
             └────────────┬───────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
 ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
 │Health Monitor│  │Backup Engine │  │Recovery Engine
 │(Probe Worker)│  │ (Scheduler)  │  │(Orchestrator)│
 └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
        │                 │                 │
        │ Probes          │ Checksums       │ Restores
        ▼                 ▼                 ▼
 ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
 │   DemoApp    │  │Storage Layer │  │PostgreSQL DB │
 │(Target Cloud)│  │ (Local / S3) │  │(Audit/Events)│
 └──────────────┘  └──────────────┘  └──────────────┘
```

---

## 2. Component Breakdown

### 2.1 DemoApp (Target Application)
DemoApp simulates a cloud-hosted microservice with real persistent relational data (users and product catalog):
- `GET /health`: Responds with HTTP 200 during normal operation, and HTTP 500 when simulated outage is triggered.
- `GET /api/data`: Returns persistent JSON entities.
- `GET /internal/backup/export`: Authenticated endpoint that packages database tables into an exportable payload.
- `POST /internal/restore`: Restores relational state, resets table indexes, and clears failure flags.
- `POST /internal/failure/enable` & `POST /internal/failure/disable`: Safe simulation hooks guarded by `X-Internal-Token`.

### 2.2 CDRO Control Plane (Backend)
1. **Health Monitoring Service**:
   - Executes non-blocking HTTP GET requests to `DemoApp.health_url`.
   - Records latency and response codes in `health_checks`.
   - Evaluates consecutive failures against `HEALTH_FAILURE_THRESHOLD` (default: 3).
   - Upon threshold breach, sets application state to `FAILURE_DETECTED` and immediately triggers the recovery engine.
2. **Backup Service**:
   - Runs periodically via `BackupSchedulerWorker` or on-demand.
   - Collects exported data, archives it into a ZIP file with schema metadata.
   - Computes a SHA-256 hash across the archive.
   - Stores the archive in local storage (`storage/backups/demoapp/YYYY/MM/DD/`) or AWS S3.
   - Enforces retention policy by purging older archives beyond `BACKUP_RETENTION_COUNT`.
3. **Automatic Recovery Engine**:
   - Acquires recovery lock (preventing concurrent recovery jobs).
   - Sets state to `RECOVERING`.
   - Scans available backups in descending chronological order.
   - Computes and verifies SHA-256 checksum against database record.
   - If corrupted: marks backup `CORRUPTED` and automatically falls back to previous backup.
   - Extracts payload into an isolated temporary workspace.
   - Dispatches payload to DemoApp's restore endpoint.
   - Performs multi-stage verification: requires 3 consecutive healthy probes and valid `/api/data` payload.
   - Calculates RTO and RPO metrics.
   - Restores state to `HEALTHY`.
4. **Storage Abstraction Layer**:
   - Seamlessly switches between local filesystem storage and AWS S3 based on `STORAGE_BACKEND`.
5. **Notification Service**:
   - Formats human-readable and structured alerts.
   - Persists to database notifications log and logs to console.
   - Publishes to AWS SNS topic when configured.

---

## 3. Local vs AWS Deployment Architectures

### Local Architecture (Zero-Cost Development)
- **Host**: Linux / macOS / Windows.
- **Database**: PostgreSQL container or SQLite file.
- **Storage**: Local filesystem directory with YYYY/MM/DD hierarchy.
- **Notification**: Local stdout and database record.
- **Monitoring**: Local daemon threads probing `localhost:5001`.

### AWS Architecture (Production Cloud)
- **Compute**: AWS EC2 instance (Ubuntu LTS) with Docker Compose.
- **Storage**: Amazon S3 bucket (`s3://cdro-backups-<account>/applications/demoapp/...`).
- **Monitoring**: Amazon CloudWatch metrics and alarms.
- **Notifications**: Amazon SNS topic delivering SMS/Email to SRE on-call.
- **Scheduled Triggers**: Amazon EventBridge invoking AWS Lambda.
- **Security**: IAM Instance Profile with least-privilege permissions.
