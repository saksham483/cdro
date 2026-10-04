# CDRO State Machine Specification

The core disaster recovery orchestrator enforces a deterministic state machine to ensure idempotency and prevent duplicate recovery operations.

## 1. State Diagram

```
         ┌────────────────────────────────────────────────────────┐
         │                                                        │
         ▼                                                        │
    ┌─────────┐      1 or 2 probe failures        ┌──────────┐   │ Consecutive
    │ HEALTHY ├──────────────────────────────────►│ DEGRADED │   │ check passes
    └────┬────┘                                   └────┬─────┘   │
         ▲                                             │         │
         │                               3 consecutive │         │
         │ Recovery passes               probe fails   ▼         │
         │                                    ┌──────────────────┴─┐
         │                                    │  FAILURE_DETECTED  │
         │                                    └────────┬───────────┘
         │                                             │
         │                                             │ Automatic trigger
         │                                             ▼
         │   Verification passes              ┌────────────────┐
         ├─── (3 checks + data) ──────────────┤   RECOVERING   │◄─── Duplicate triggers
         │                                    └────────┬───────┘     are DROPPED (Locked)
         │                                             │
         │                                             │ Verification fails or
         │                                             │ all backups corrupted
         │                                             ▼
         │                                    ┌─────────────────┐
         └────────────────────────────────────┤ RECOVERY_FAILED │
                   Manual Admin Reset         └─────────────────┘
```

---

## 2. State Descriptions

| State | Description | System Behavior |
|---|---|---|
| `HEALTHY` | Target application is operational. Health checks return HTTP 200. | Probes continue at 5s intervals. Backups scheduled normally. |
| `DEGRADED` | 1 or 2 health checks failed. Transient network/process stutter. | Consecutive failure counter increments. No disaster declared yet. |
| `FAILURE_DETECTED` | 3 consecutive health checks failed. Confirmed outage. | Disaster is declared. Alert sent. Automatic recovery triggered. |
| `RECOVERING` | Autonomous recovery engine is active. | Recovery lock held. Concurrent health check triggers dropped. Checksums verified, data restored. |
| `RECOVERED` | Verification probes (3 consecutive) and data queries confirmed. | RTO/RPO calculated. Notification sent. Transitions to `HEALTHY`. |
| `RECOVERY_FAILED` | Verification failed, timeout exceeded, or all backups corrupted. | CRITICAL alert sent. System halts recovery to await operator investigation. |

---

## 3. Idempotency & Concurrency Lock

To prevent a race condition where multiple health check cycles or alarms trigger parallel recovery jobs:

```python
if application.status == ApplicationStatus.RECOVERING:
    # Recovery already executing for this application
    log.info("Recovery lock active. Dropping duplicate recovery request.")
    return None
```

The lock is atomically stored in the database and released only upon entering `RECOVERED` or `RECOVERY_FAILED`.
