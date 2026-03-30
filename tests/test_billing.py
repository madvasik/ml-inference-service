from ml_inference_service.config import get_settings


def test_mock_topup(client):
    reg = client.post("/api/auth/register", json={"email": "c@example.com", "password": "password12"})
    token = reg.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    secret = get_settings().mock_topup_secret
    r = client.post(
        "/api/billing/mock-topup",
        headers=h,
        json={"amount_money": "10.00", "credits_to_grant": 50, "secret": secret},
    )
    assert r.status_code == 200
    assert r.json()["credits_granted"] == 50
    bal = client.get("/api/billing/balance", headers=h)
    assert bal.json()["balance_credits"] == 50
