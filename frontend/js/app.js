function showToast(message, type = "info") {
  const container = document.getElementById("toast-container") || createToastContainer();
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4000);
}

function createToastContainer() {
  const container = document.createElement("div");
  container.id = "toast-container";
  container.className = "toast-container";
  document.body.appendChild(container);
  return container;
}

function formatTimestamp(isoStr) {
  if (!isoStr) return "N/A";
  let s = String(isoStr);
  // Timestamps without a timezone designator ("Z" or +hh:mm) come from the
  // backend's UTC storage (SQLite drops tzinfo) — parse them as UTC, not local time.
  if (!/(Z|[+-]\d{2}:?\d{2})$/.test(s)) s += "Z";
  const dt = new Date(s);
  if (isNaN(dt.getTime())) return "Invalid Date";
  return dt.toLocaleTimeString();
}

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

// Global user bar update
document.addEventListener("DOMContentLoaded", () => {
  const user = Auth.getUser();
  const userElem = document.getElementById("header-user-display");
  if (user && userElem) {
    userElem.innerHTML = `
      <span>${user.username}</span>
      <span class="user-role-badge">${user.role}</span>
      <button class="btn-logout" onclick="logout()">Logout</button>
    `;
  }
});

function logout() {
  Auth.clearAuth();
  window.location.href = "login.html";
}
