let latencyChart = null;

document.addEventListener("DOMContentLoaded", () => {
  initChart();
  fetchDashboard();
  fetchHealthHistory();
  setInterval(fetchDashboard, 2500);
  setInterval(fetchHealthHistory, 5000);
});

function initChart() {
  const ctx = document.getElementById("healthLatencyChart");
  if (!ctx) return;
  latencyChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [{
        label: "Latency (ms)",
        data: [],
        borderColor: "#3b82f6",
        backgroundColor: "rgba(59, 130, 246, 0.1)",
        tension: 0.2,
        fill: true,
        pointRadius: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { display: false },
        y: {
          beginAtZero: true,
          grid: { color: "#1f2937" },
          ticks: { color: "#9ca3af", font: { size: 10 } }
        }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });
}

async function fetchDashboard() {
  try {
    const res = await Auth.fetchWithAuth("/api/dashboard");
    if (!res || !res.ok) return;
    const data = await res.json();
    renderDashboard(data);
  } catch (err) {
    console.error("Dashboard poll error:", err);
  }
}

async function fetchHealthHistory() {
  try {
    const res = await Auth.fetchWithAuth("/api/applications/1/health-history");
    if (!res || !res.ok) return;
    const data = await res.json();
    if (latencyChart && data.history) {
      latencyChart.data.labels = data.history.map(h => formatTimestamp(h.timestamp));
      latencyChart.data.datasets[0].data = data.history.map(h => h.response_time_ms);
      latencyChart.update();
    }
  } catch (err) {
    console.error("Health history error:", err);
  }
}

function renderDashboard(data) {
  const app = data.application;
  const health = data.health;
  const backup = data.backup;
  const recovery = data.recovery;

  // App & Status
  document.getElementById("app-name").innerText = app.name;
  document.getElementById("app-url").innerText = app.health_url;

  const statusBadge = document.getElementById("app-status-badge");
  statusBadge.className = `status-badge-lg status-${app.status}`;
  statusBadge.innerText = `● ${app.status.replace("_", " ")}`;

  // Health probe card
  if (health.last_check) {
    document.getElementById("health-latency").innerText = `${health.last_check.response_time_ms} ms`;
    document.getElementById("card-health-indicator").innerText = health.last_check.healthy ? "🟢 200 OK" : "🔴 " + (health.last_check.status_code || "FAIL");
    document.getElementById("health-check-sub").innerText = `Checked: ${formatTimestamp(health.last_check.timestamp)} (Fails: ${health.consecutive_failures}/${health.failure_threshold})`;
  }

  // Backup card
  document.getElementById("backups-count").innerText = backup.total_available;
  if (backup.latest_backup) {
    document.getElementById("card-backup-badge").className = `tag-badge badge-${backup.latest_backup.status.toLowerCase()}`;
    document.getElementById("card-backup-badge").innerText = backup.latest_backup.status;
    document.getElementById("latest-backup-sub").innerText = `Latest: ${formatTimestamp(backup.latest_backup.created_at)} (${formatBytes(backup.latest_backup.file_size)})`;
  }

  // Recovery card
  if (recovery.latest_disaster) {
    const dis = recovery.latest_disaster;
    document.getElementById("recovery-rto").innerText = dis.rto_seconds !== null ? `${dis.rto_seconds}s` : (dis.status === 'RECOVERING' ? 'IN PROGRESS' : '--');
    const rtoBadge = document.getElementById("rto-status-badge");
    if (dis.rto_status) {
      rtoBadge.innerText = `RTO: ${dis.rto_status}`;
      rtoBadge.className = dis.rto_status === "PASS" ? "tag-badge badge-valid" : "tag-badge badge-corrupted";
    }
    const rpoMin = dis.rpo_seconds ? (dis.rpo_seconds / 60).toFixed(1) : "0";
    document.getElementById("recovery-rpo-sub").innerText = `RPO: ${rpoMin} min | Backup: ${dis.backup_used || 'N/A'}`;
  }

  // Recovery Engine Status
  const engStatus = document.getElementById("recovery-engine-status");
  if (recovery.active_recovery) {
    engStatus.innerText = "Engine: RECOVERING APPLICATION";
    engStatus.style.color = "var(--color-blue)";
  } else {
    engStatus.innerText = "Engine: Standby / Monitoring";
    engStatus.style.color = "var(--text-muted)";
  }

  // Timeline
  renderTimeline(recovery.timeline);

  // Recent logs
  renderRecentLogs(data.recent_events || []);
}

function renderTimeline(job) {
  const container = document.getElementById("timeline-container");
  const jobLabel = document.getElementById("timeline-job-id");
  if (!job || !job.steps || job.steps.length === 0) {
    container.innerHTML = `
      <div style="padding: 1.5rem 0; color: var(--text-muted); text-align: center;">
        No disaster recovery event active. System is monitoring DemoApp health continuously.
      </div>`;
    jobLabel.innerText = "JOB: IDLE";
    return;
  }

  jobLabel.innerText = `JOB #${job.id} [${job.status}]`;
  container.innerHTML = job.steps.map((step, idx) => `
    <div class="timeline-step">
      <div class="step-marker marker-${step.status}">
        ${step.status === 'COMPLETED' ? '✓' : step.status === 'FAILED' ? '✗' : (idx + 1)}
      </div>
      <div class="step-content">
        <div class="step-title">${step.step}</div>
        <div class="step-detail">${step.detail || ''}</div>
      </div>
      <div class="step-time">${formatTimestamp(step.timestamp)}</div>
    </div>
  `).join("");
}

function renderRecentLogs(logs) {
  const tbody = document.getElementById("recent-logs-tbody");
  if (!logs.length) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No audit logs available</td></tr>`;
    return;
  }

  tbody.innerHTML = logs.map(l => {
    let sevColor = "var(--color-blue)";
    if (l.severity === "CRITICAL" || l.severity === "ERROR") sevColor = "var(--color-red)";
    if (l.severity === "WARNING") sevColor = "var(--color-yellow)";
    if (l.severity === "SUCCESS") sevColor = "var(--color-green)";

    return `
      <tr>
        <td style="font-family: var(--font-mono); font-size: 0.75rem;">${formatTimestamp(l.timestamp)}</td>
        <td><span style="color: ${sevColor}; font-weight: 700;">[${l.severity}]</span></td>
        <td style="font-family: var(--font-mono);">${l.event_type}</td>
        <td>${l.message}</td>
      </tr>
    `;
  }).join("");
}

// Simulation Actions
async function triggerSimulatedFailure() {
  const user = Auth.getUser();
  if (user && user.role !== "admin") {
    alert("Simulation commands require the 'admin' role.");
    return;
  }
  showToast("Injecting controlled failure into DemoApp...", "info");
  try {
    const res = await Auth.fetchWithAuth("/api/simulation/failure", { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      showToast("Failure injected! Health monitor will detect consecutive failures and trigger automatic recovery.", "success");
      fetchDashboard();
    } else {
      showToast("Simulation failed: " + data.message, "error");
    }
  } catch (err) {
    showToast("Network error: " + err.message, "error");
  }
}

async function triggerCorruptBackup() {
  showToast("Corrupting latest backup checksum for fallback testing...", "info");
  try {
    const res = await Auth.fetchWithAuth("/api/simulation/corrupt-latest-backup", { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      showToast("Latest backup corrupted! Next DR will automatically fallback to previous backup.", "success");
      fetchDashboard();
    } else {
      showToast("Corrupt backup failed: " + (data.message || data.error), "error");
    }
  } catch (err) {
    showToast("Network error: " + err.message, "error");
  }
}

async function triggerImmediateBackup() {
  showToast("Creating immediate backup of DemoApp data...", "info");
  try {
    const res = await Auth.fetchWithAuth("/api/backups/trigger", { method: "POST", body: JSON.stringify({}) });
    const data = await res.json();
    if (res.ok) {
      showToast(`Backup ${data.backup.filename} created & verified!`, "success");
      fetchDashboard();
    } else {
      showToast("Backup creation failed: " + data.message, "error");
    }
  } catch (err) {
    showToast("Network error: " + err.message, "error");
  }
}

async function triggerDemoReset() {
  showToast("Resetting demo state to HEALTHY...", "info");
  try {
    const res = await Auth.fetchWithAuth("/api/simulation/reset", { method: "POST" });
    if (res.ok) {
      showToast("System state reset to HEALTHY", "success");
      fetchDashboard();
    }
  } catch (err) {
    showToast("Error resetting: " + err.message, "error");
  }
}
