document.addEventListener("DOMContentLoaded", () => {
  fetchLogs();
  setInterval(fetchLogs, 5000);
});

async function fetchLogs() {
  const sev = document.getElementById("severity-filter").value;
  const url = sev ? `/api/logs?severity=${sev}` : "/api/logs";

  try {
    const res = await Auth.fetchWithAuth(url);
    if (!res || !res.ok) return;
    const data = await res.json();
    renderLogs(data.logs || []);
  } catch (err) {
    console.error("Fetch logs error:", err);
  }
}

function renderLogs(logs) {
  const tbody = document.getElementById("logs-tbody");
  if (!logs.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No audit logs matching query.</td></tr>`;
    return;
  }

  tbody.innerHTML = logs.map(l => {
    let sevColor = "var(--color-blue)";
    if (l.severity === "CRITICAL" || l.severity === "ERROR") sevColor = "var(--color-red)";
    if (l.severity === "WARNING") sevColor = "var(--color-yellow)";
    if (l.severity === "SUCCESS") sevColor = "var(--color-green)";

    return `
      <tr>
        <td style="font-family: var(--font-mono);">#${l.id}</td>
        <td style="font-family: var(--font-mono); font-size: 0.75rem;">${formatTimestamp(l.timestamp)}</td>
        <td><span style="color: ${sevColor}; font-weight: 700;">[${l.severity}]</span></td>
        <td style="font-family: var(--font-mono);">${l.event_type}</td>
        <td>${l.message}</td>
      </tr>
    `;
  }).join("");
}
