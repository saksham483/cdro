# Cloud Disaster Recovery Orchestrator (CDRO)

> **"Automatic Failure Detection, Backup and Disaster Recovery for Cloud Applications."**

[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://python.org)
[![Framework](https://img.shields.io/badge/framework-Flask-black.svg)](https://flask.palletsprojects.com/)
[![Database](https://img.shields.io/badge/database-PostgreSQL%20%7C%20SQLite-336791.svg)](https://postgresql.org)
[![AWS](https://img.shields.io/badge/AWS-S3%20%7C%20SNS%20%7C%20CloudWatch%20%7C%20EC2-orange.svg)](https://aws.amazon.com)
[![Docker](https://img.shields.io/badge/docker-compose-2496ED.svg)](https://docker.com)
[![Tests](https://img.shields.io/badge/tests-15%2F15%20passed-brightgreen.svg)](#testing)

---

## 1. Project Overview & Core Product Concept

**CDRO** is an autonomous cloud disaster recovery platform designed to continuously monitor cloud applications, create cryptographic backups of state, detect outages with failure tolerance, and execute **100% automated disaster recovery without manual intervention**.

The system manages a sample cloud-hosted web application called **DemoApp** (which stores persistent customer and product catalog data).

### The Autonomous Recovery Workflow:

```
DemoApp Running (Healthy)
         ↓
Health Monitoring detects probe failure
         ↓
Threshold exceeded (3 consecutive failures)
         ↓
CDRO declares Disaster & acquires Lock
         ↓
Locates latest VALID backup candidate
         ↓
Verifies SHA-256 Cryptographic Checksum
   ├─ If Corrupted → Marks CORRUPTED, automatically falls back to previous valid backup
   └─ If Valid → Proceeds with verified archive
         ↓
Extracts archive into isolated Recovery Workspace
         ↓
Restores application database state & deactivates failure mode
         ↓
Executes recovery verification (3 consecutive health checks + data query)
         ↓
Computes RTO (Recovery Time Objective) and RPO (Recovery Point Objective)
         ↓
Marks state RECOVERED → Transitions to HEALTHY
         ↓
Dispatches Alert Notification & records Immutable Audit Log
```

> **IMPORTANT:** There is **NO manual restore button**. The defining hallmark of CDRO is autonomous recovery. The operations dashboard is an SRE console for observation, audit, and controlled demo simulations.

---

## 2. Key Features

- **Continuous Proactive Health Monitoring**: Evaluates target application health endpoints every 5 seconds (configurable) and records latency metrics.
- **Configurable Failure Tolerance**: Avoids false positives from transient network blips by enforcing a consecutive failure threshold (default: 3 checks) before declaring a disaster.
- **Cryptographic Backup Integrity**: Every backup archive is signed with a SHA-256 hash. Integrity is rigorously verified prior to extraction.
- **Intelligent Corrupted Backup Fallback**: If the latest backup fails checksum verification (e.g. storage bit rot or tampered file), CDRO automatically falls back through previous valid backups until a healthy backup is found.
- **Idempotent Recovery Locking**: Ensures that concurrent health check cycles or failure alarms cannot launch duplicate recovery jobs.
- **Recovery Verification**: Verifies recovery not just by command exit code, but by requiring 3 consecutive healthy HTTP probes and verifying that real business entities are queryable.
- **Real-time SRE Operations Dashboard**: Dark-mode engineering console with live status indicator, health latency chart (Chart.js), visual recovery timeline, and real-time polling every 2.5s.
- **Disaster Recovery SLA Metrics**: Real-time calculation of **RTO** (Recovery Time Objective duration) and **RPO** (Recovery Point Objective age of restored data), evaluated against configurable target thresholds (e.g. 60s).
- **Dual Storage Engine**: Local filesystem storage with hierarchical prefixing (`storage/backups/demoapp/YYYY/MM/DD/`) for zero-cost development, and AWS S3 integration with boto3.
- **Comprehensive Notification Engine**: Local console/database audit feed with AWS SNS publishing when configured.
- **AWS CloudWatch Metrics**: Publishes real operational metrics (`cdro_backup_success`, `cdro_health_failure`, `cdro_recovery_duration`, etc.).
- **Role-Based Access Control**: JWT-authenticated operations console with `admin` and `operator` roles.

---

## 3. Technology Stack

| Layer | Technology |
|---|---|
| **Frontend** | HTML5, CSS3, Vanilla JavaScript (ES6+), Chart.js (No React complexity) |
| **Backend** | Python 3.12, Flask, Flask-JWT-Extended, Flask-SQLAlchemy, Flask-Migrate |
| **Database** | PostgreSQL 15 (Docker) / SQLite (Standalone Local Mode) |
| **Cloud Storage** | AWS S3 via boto3 (Local filesystem fallback) |
| **Monitoring** | Native Python daemon threads, psutil, HTTP probes, AWS CloudWatch |
| **Notifications** | AWS SNS via boto3 (Console & Database fallback) |
| **Containerization**| Docker & Docker Compose |

---

## 4. Project Structure

```
cdro/
├── backend/
│   ├── app/
│   │   ├── __init__.py          # Flask App Factory & database bootstrap
│   │   ├── config.py            # Unified environment configuration
│   │   ├── extensions.py        # SQLAlchemy, JWT, Migrate instances
│   │   ├── models/              # Database models (User, App, Backup, DisasterEvent, etc.)
│   │   ├── routes/              # REST Blueprints (auth, health, backups, recovery, simulation)
│   │   ├── services/            # Core business services (backup, storage, recovery, monitor)
│   │   ├── workers/             # Background daemon workers (health monitor, backup scheduler)
│   │   └── utils/               # SHA-256 helpers & RBAC decorators
│   ├── tests/                   # 15 automated pytest tests
│   ├── Dockerfile               # Backend production container specification
│   ├── requirements.txt         # Python dependencies
│   └── run.py                   # Standalone application entrypoint
│
├── demoapp/
│   ├── app.py                   # Sample cloud production web application (users & products)
│   ├── models.py                # DemoApp SQLite data layer & automatic seed
│   ├── requirements.txt         # DemoApp dependencies
│   └── Dockerfile               # DemoApp container specification
│
├── frontend/
│   ├── index.html               # Entry router
│   ├── login.html               # Authentication portal with 1-click demo login
│   ├── dashboard.html           # Main SRE console, status banner, timeline, simulation
│   ├── backups.html             # Cryptographic backup catalog & corruption simulation
│   ├── recoveries.html          # Disaster history, RTO, and RPO records
│   ├── logs.html                # Searchable and filterable audit trail
│   ├── css/style.css            # Custom operations console dark theme
│   └── js/                      # Modular client-side scripts & live polling
│
├── aws/
│   ├── lambda/                  # Serverless scheduled backup trigger & README
│   ├── cloudwatch/              # CloudWatch dashboard and alarm templates
│   ├── iam/                     # Least-privilege IAM policy JSON
│   └── deployment/              # Production EC2 automated bash installer
│
├── docker-compose.yml           # Multi-container orchestration (Backend, DemoApp, Postgres)
├── .env.example                 # Configuration template
├── run_tests.sh                 # Pytest runner
└── docs/                        # Detailed architectural & demo documentation
    ├── architecture.md
    ├── state_machine.md
    ├── security.md
    └── demo.md
```

---

## 5. Quick Start: Local Standalone (Without Docker)

You can run CDRO locally without spending any money on AWS or installing PostgreSQL.

### Step 1: Clone and Create Virtual Environment
```bash
cd cdro
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### Step 2: Configure Environment
```bash
cp .env.example .env
# By default, local SQLite and filesystem storage are active
```

### Step 3: Run DemoApp (Terminal 1)
```bash
python demoapp/app.py
# DemoApp starts on http://localhost:5001
```

### Step 4: Run CDRO Backend & Workers (Terminal 2)
```bash
python backend/run.py
# CDRO Orchestrator starts on http://localhost:5000
```

### Step 5: Open Browser
Navigate to **http://localhost:5000**
- Click **Fill Admin** (`admin` / `admin123`) or **Fill Operator** (`operator` / `operator123`).
- Observe DemoApp in **HEALTHY** state with monitoring active!

---

## 6. Quick Start: Docker Compose

To run the complete production-style environment with PostgreSQL, DemoApp, and CDRO:

```bash
docker compose up --build
```

Access the services:
- **CDRO Dashboard**: `http://localhost:5000`
- **DemoApp Web API**: `http://localhost:5001`
- **PostgreSQL Database**: `localhost:5432` (`cdro` / `cdro_password`)

---

## 7. Testing

CDRO includes a comprehensive test suite of 15 automated tests covering authentication, RBAC, health check threshold transitions, SHA-256 checksum verification, corrupted backup fallback, RTO/RPO calculation, and the critical End-to-End autonomous disaster recovery workflow.

Run the test suite:
```bash
./run_tests.sh
```

Expected output:
```
============================== test session starts ==============================
backend/tests/test_auth.py::test_login_success PASSED
backend/tests/test_auth.py::test_login_invalid_credentials PASSED
backend/tests/test_auth.py::test_get_current_user_profile PASSED
backend/tests/test_auth.py::test_role_based_access_control PASSED
backend/tests/test_backup.py::test_backup_creation_and_checksum PASSED
backend/tests/test_backup.py::test_backup_retention_policy PASSED
backend/tests/test_checksum_and_fallback.py::test_backup_checksum_verification_success PASSED
backend/tests/test_checksum_and_fallback.py::test_backup_checksum_verification_detects_corruption PASSED
backend/tests/test_e2e_disaster_recovery.py::test_full_autonomous_disaster_recovery_workflow PASSED
backend/tests/test_health_monitoring.py::test_health_monitoring_healthy_state PASSED
backend/tests/test_health_monitoring.py::test_health_monitoring_failure_threshold_progression PASSED
backend/tests/test_metrics_and_rto.py::test_rto_and_rpo_calculations PASSED
backend/tests/test_metrics_and_rto.py::test_metrics_service_local_publishing PASSED
backend/tests/test_recovery_engine.py::test_idempotent_recovery_locking PASSED
backend/tests/test_recovery_engine.py::test_recovery_fallback_when_latest_backup_corrupted PASSED

============================== 15 passed in 39s ==============================
```

---

## 8. Failure Simulation & Autonomous Recovery Demonstration

1. Open the CDRO Dashboard at `http://localhost:5000`.
2. Notice DemoApp is **🟢 HEALTHY** and a backup is available.
3. Click the red button: **⚡ Simulate Failure** (marked `SIMULATION ONLY`).
4. **Watch hands-free**:
   - Continuous monitor detects Probe Failures (1/3 → 2/3 → 3/3).
   - Application status changes to **🟡 DEGRADED**, then **🔴 FAILURE DETECTED**.
   - Automatic disaster recovery initiates immediately: status changes to **🔄 RECOVERING**.
   - The **Lifecycle Timeline** illuminates each step in real time:
     - Checksum verified against stored SHA-256 hash.
     - Payload extracted into isolated temporary workspace.
     - Target database restored.
     - Application restarted and failure flag deactivated.
     - 3 consecutive health probes and data query verification pass.
   - Status changes to **✅ RECOVERED**, then transitions cleanly back to **🟢 HEALTHY**.
   - RTO (e.g. 18.2s, **PASS**) and RPO (e.g. 2.1 min) are calculated and displayed.
   - Navigate to `http://localhost:5001/api/data` to verify that customer data is 100% intact!

---

## 9. AWS Mode Configuration

When deploying to AWS (e.g. on EC2), update `.env`:

```ini
# Storage Backend
STORAGE_BACKEND=s3
S3_BUCKET=my-cdro-backups-bucket
AWS_REGION=us-east-1

# Notifications
NOTIFICATION_BACKEND=sns
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:123456789012:cdro-alerts
ADMIN_NOTIFICATION_EMAIL=sre-team@company.com
```

Attach the provided IAM policy in `aws/iam/cdro_policy.json` to the EC2 instance profile for credential-less authentication.

---

## 10. Documentation Index

- **[System Architecture](docs/architecture.md)**: End-to-end component dataflow and cloud infrastructure mapping.
- **[State Machine Specification](docs/state_machine.md)**: Formal lifecycle states, transitions, and locks.
- **[Security Architecture](docs/security.md)**: Cryptographic checksumming, RBAC, and least-privilege IAM.
- **[Student Demo Walkthrough](docs/demo.md)**: Step-by-step presentation script for evaluations and live demos.
