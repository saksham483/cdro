const Auth = {
  getToken() {
    return localStorage.getItem("cdro_token");
  },
  getUser() {
    const raw = localStorage.getItem("cdro_user");
    return raw ? JSON.parse(raw) : null;
  },
  setAuth(token, user) {
    localStorage.setItem("cdro_token", token);
    localStorage.setItem("cdro_user", JSON.stringify(user));
  },
  clearAuth() {
    localStorage.removeItem("cdro_token");
    localStorage.removeItem("cdro_user");
  },
  isAuthenticated() {
    return !!this.getToken();
  },
  requireAuth() {
    if (!this.isAuthenticated()) {
      window.location.href = "login.html";
    }
  },
  async fetchWithAuth(url, options = {}) {
    const token = this.getToken();
    const headers = options.headers || {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    headers["Content-Type"] = "application/json";
    options.headers = headers;

    const response = await fetch(url, options);
    if (response.status === 401) {
      this.clearAuth();
      window.location.href = "login.html";
      return null;
    }
    return response;
  }
};
