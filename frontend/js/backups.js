document.addEventListener("DOMContentLoaded", () => {
  fetchBackups();
  setInterval(fetchBackups, 4000);
});

async function fetchBackups() {
  try {
    const res = await Auth.fetchWithAuth("/api/backups");
    if (!res || !res.ok) return;
    const data = await res.json();
    renderBackups(data.backups || []);
  } catch (err) {
    console.error("Fetch backups error:", err);
  }
}

function renderBackups(backups) {
  const tbody = document.getElementById("backups-tbody");
  if (!backups.length) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">No backups found. Trigger a backup to begin.</td></tr>`;
    return;
  }

  tbody.innerHTML = backups.map(b => {
    const statusClass = b.status === 'VALID' ? 'badge-valid' : b.status === 'CORRUPTED' ? 'badge-corrupted' : 'badge-deleted';
    const storageClass = b.storage_type === 's3' ? 'badge-s3' : 'badge-local';

    return `
      <tr>
        <td style="font-family: var(--font-mono);">#${b.id}</td>
        <td style="font-family: var(--font-mono); font-weight: 600; color: var(--text-primary);">${b.filename}</td>
        <td style="font-family: var(--font-mono); font-size: 0.75rem;">${formatTimestamp(b.created_at)}</td>
        <td>${formatBytes(b.file_size)}</td>
        <td style="font-family: var(--font-mono); font-size: 0.7rem; color: var(--text-muted);" title="${b.checksum}">
          ${b.checksum.substring(0, 16)}...
        </td>
        <td><span class="tag-badge ${storageClass}">${b.storage_type.toUpperCase()}</span></td>
        <td><span class="tag-badge ${statusClass}">${b.status}</span></td>
        <td>
          ${b.status === 'VALID' ? `
            <button class="btn btn-secondary" style="font-size: 0.7rem; padding: 0.2rem 0.5rem;" onclick="corruptSpecificBackup(${b.id})">
              Corrupt Checksum (Demo)
            </button>
          ` : '<span style="color: var(--text-muted); font-size: 0.75rem;">None</span>'}
        </td>
      </tr>
    `;
  }).join("");
}

async function corruptSpecificBackup(backupId) {
  if (!confirm("Intentionally corrupt this backup checksum to test automated fallback?")) return;
  try {
    const res = await Auth.fetchWithAuth(`/api/backups/${backupId}/corrupt`, { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message, "success");
      fetchBackups();
    } else {
      showToast("Failed to corrupt: " + data.message, "error");
    }
  } catch (err) {
    showToast("Network error: " + err.message, "error");
  }
}

async function triggerImmediateBackup() {
  showToast("Triggering backup creation...", "info");
  try {
    const res = await Auth.fetchWithAuth("/api/backups/trigger", { method: "POST", body: JSON.stringify({}) });
    const data = await res.json();
    if (res.ok) {
      showToast(`Backup ${data.backup.filename} successfully created!`, "success");
      fetchBackups();
    } else {
      showToast("Backup failed: " + data.message, "error");
    }
  } catch (err) {
    showToast("Network error: " + err.message, "error");
  }
}
