def test_login_success(client):
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    data = res.json
    assert "access_token" in data
    assert data["user"]["role"] == "admin"

def test_login_invalid_credentials(client):
    res = client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert res.status_code == 401
    assert res.json["error"] == "UNAUTHORIZED"

def test_get_current_user_profile(client, admin_token):
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert res.json["user"]["username"] == "admin"

def test_role_based_access_control(client, operator_token):
    # Operator should not be allowed to trigger simulation endpoint (admin-only)
    res = client.post("/api/simulation/failure", headers={"Authorization": f"Bearer {operator_token}"})
    assert res.status_code == 403
    assert res.json["error"] == "FORBIDDEN"
