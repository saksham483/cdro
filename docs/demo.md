# CDRO Student Presentation & Demonstration Script

This script provides a 5-minute walkthrough to demonstrate CDRO for evaluations, presentations, or portfolio showcases.

---

## Demo Walkthrough (Step-by-Step)

### Step 1: Open the Operations Console
- Open browser to: `http://localhost:5000`
- Log in using one-click **Fill Admin** (`admin` / `admin123`).
- Point out the clean SRE dashboard:
  - Application Status: **🟢 HEALTHY**
  - Live probe latency chart updating every 5s.
  - Available backups count and latest backup status: **VALID**.
  - Automatic Recovery Badge: **Active (Autonomous recovery guaranteed)**.

### Step 2: Show Persistent DemoApp Data
- Open a second tab to: `http://localhost:5001/api/data`
- Show existing records (e.g. Alice, Bob, Charlie, Laptop, Phone, Keyboard).
- Explain: *"This is a real web application with persistent database records."*

### Step 3: Trigger Failure Simulation (Scenario 1)
- Return to CDRO Dashboard.
- Explain: *"We will now simulate an outage. Notice that there is NO restore button anywhere in the UI. Everything that happens next is completely autonomous."*
- Click: **⚡ Simulate Failure** (in the Simulation Panel).

### Step 4: Observe Autonomous Failure Detection
- Health check probes begin failing.
- Point out the consecutive failure counter incrementing: `1/3` → `2/3`.
- Application status changes to **🟡 DEGRADED**.
- At `3/3` failures, CDRO declares disaster: status turns to **🔴 FAILURE DETECTED**.

### Step 5: Observe Autonomous Recovery in Real Time
- State turns to **🔄 RECOVERING**.
- The **Disaster Recovery Lifecycle Timeline** begins animating:
  1. *Acquire recovery lock* → Completed
  2. *Search and verify backups* → Completed
  3. *Verify checksum (SHA-256)* → Completed
  4. *Extract to temporary recovery workspace* → Completed
  5. *Restore data into DemoApp* → Completed
  6. *Reset application operational state* → Completed
  7. *Recovery verification (3 consecutive health checks)* → Completed
  8. *Finalize recovery & SLA calculation* → Completed

### Step 6: Verify Final State & SLA Metrics
- Application status returns to **🟢 HEALTHY**.
- Point out the DR metrics:
  - **Recovery Time (RTO)**: e.g. `18.4s` (Target: 60s → **PASS**)
  - **Recovery Point (RPO)**: e.g. `2.0 min`
- Show the **Audit Logs Feed** displaying the chronological log trail.

### Step 7: Prove Data Integrity
- Switch back to `http://localhost:5001/api/data` and refresh.
- Show that all original users and products exist intact.

### Step 8 (Bonus): Demonstrate Corrupted Backup Fallback (Scenario 4)
- Click **🧪 Corrupt Latest Backup**.
- Click **⚡ Simulate Failure**.
- Watch the timeline:
  - Latest backup checksum fails!
  - CDRO automatically rejects it and logs corruption.
  - CDRO automatically falls back to the preceding backup.
  - Recovery completes successfully!
