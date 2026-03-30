def test_patch_me_email(client):
    client.post("/api/auth/register", json={"email": "old@example.com", "password": "password12"})
    r = client.post(
        "/api/auth/login",
        data={"username": "old@example.com", "password": "password12"},
    )
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    up = client.patch(
        "/api/users/me",
        headers=h,
        json={"email": "new@example.com"},
    )
    assert up.status_code == 200
    assert up.json()["email"] == "new@example.com"

    me = client.get("/api/users/me", headers=h)
    assert me.json()["email"] == "new@example.com"

    login_new = client.post(
        "/api/auth/login",
        data={"username": "new@example.com", "password": "password12"},
    )
    assert login_new.status_code == 200


def test_patch_me_password(client):
    client.post("/api/auth/register", json={"email": "pw@example.com", "password": "password12"})
    r = client.post(
        "/api/auth/login",
        data={"username": "pw@example.com", "password": "password12"},
    )
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    up = client.patch(
        "/api/users/me",
        headers=h,
        json={"password": "newpass99"},
    )
    assert up.status_code == 200

    bad = client.post(
        "/api/auth/login",
        data={"username": "pw@example.com", "password": "password12"},
    )
    assert bad.status_code == 401

    ok = client.post(
        "/api/auth/login",
        data={"username": "pw@example.com", "password": "newpass99"},
    )
    assert ok.status_code == 200


def test_patch_me_email_conflict(client):
    client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password12"})
    client.post("/api/auth/register", json={"email": "taken@example.com", "password": "password12"})

    r = client.post(
        "/api/auth/login",
        data={"username": "owner@example.com", "password": "password12"},
    )
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    conflict = client.patch(
        "/api/users/me",
        headers=h,
        json={"email": "taken@example.com"},
    )
    assert conflict.status_code == 400
    assert conflict.json()["detail"] == "Email taken"

    me = client.get("/api/users/me", headers=h)
    assert me.json()["email"] == "owner@example.com"
