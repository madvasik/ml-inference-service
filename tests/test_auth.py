def test_register_and_me(client):
    r = client.post("/api/auth/register", json={"email": "a@example.com", "password": "password12"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "a@example.com"


def test_login(client):
    client.post("/api/auth/register", json={"email": "b@example.com", "password": "password12"})
    r = client.post(
        "/api/auth/login",
        data={"username": "b@example.com", "password": "password12"},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()
