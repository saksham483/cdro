document.addEventListener("DOMContentLoaded", () => {
  fetchRecoveries();
  setInterval(fetchRecoveries, 4000);
});

async function fetchRecoveries() {
  try {
    const res = await Auth.fetchWithAuth("/api/recoveries");
    if (!res || !res.ok) return;
    const data = await res.json();
    renderRecoveries(data.recoveries || []);
  } catch (err) {
    console.error("Fetch recoveries error:", err);
  }
}

function renderRecoveries(events) {
  const tbody = document.getElementById("recoveries-tbody");
  if (!events.length) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">No disaster recovery events recorded yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = events.map(e => {
    const isSuccess = e.status === "SUCCESS";
    const statusClass = isSuccess ? "badge-valid" : e.status === "RECOVERING" ? "badge-local" : "badge-corrupted";
    const rtoClass = e.rto_status === "PASS" ? "badge-valid" : "badge-corrupted";
    const rpoMin = e.rpo_seconds !== null ? (e.rpo_seconds / 60).toFixed(1) + " min" : "N/A";

    return `
      <tr>
        <td style="font-family: var(--font-mono); font-weight: 700;">#${e.id}</td>
        <td style="font-family: var(--font-mono); font-size: 0.75rem;">${formatTimestamp(e.detected_at)}</td>
        <td>${e.failure_type}</td>
        <td style="font-family: var(--font-mono); font-size: 0.75rem;">${e.backup_used || 'None'}</td>
        <td style="font-family: var(--font-mono); font-weight: 600;">${e.recovery_duration_seconds !== null ? e.recovery_duration_seconds + 's' : (e.status === 'RECOVERING' ? 'Running' : '--')}</td>
        <td><span class="tag-badge ${rtoClass}">${e.rto_status || 'N/A'}</span></td>
        <td style="font-family: var(--font-mono);">${rpoMin}</td>
        <td><span class="tag-badge ${statusClass}">${e.status}</span></td>
      </tr>
    `;
  }).join("");
}
