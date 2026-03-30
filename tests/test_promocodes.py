from datetime import datetime, timedelta, timezone

from ml_inference_service.config import get_settings
from ml_inference_service.models.user import User, UserRole


def _auth(client, email="p@example.com"):
    client.post("/api/auth/register", json={"email": email, "password": "password12"})
    r = client.post(
        "/api/auth/login",
        data={"username": email, "password": "password12"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_promocode_fixed_credits(client, db_session):
    h = _auth(client)
    db_session.query(User).filter(User.email == "p@example.com").update(
        {User.role: UserRole.admin}
    )
    db_session.commit()

    r = client.post(
        "/api/promocodes/admin",
        headers=h,
        json={"code": "WELCOME10", "kind": "fixed_credits", "value": 10},
    )
    assert r.status_code == 200

    r2 = client.post("/api/promocodes/activate", headers=h, json={"code": "welcome10"})
    assert r2.status_code == 200
    assert r2.json()["credits_granted"] == 10

    r3 = client.post("/api/promocodes/activate", headers=h, json={"code": "welcome10"})
    assert r3.status_code == 409


def test_promocode_expired(client, db_session):
    h = _auth(client, email="e@example.com")
    db_session.query(User).filter(User.email == "e@example.com").update(
        {User.role: UserRole.admin}
    )
    db_session.commit()

    past = datetime.now(timezone.utc) - timedelta(days=1)
    client.post(
        "/api/promocodes/admin",
        headers=h,
        json={"code": "OLD", "kind": "fixed_credits", "value": 5, "expires_at": past.isoformat()},
    )
    r = client.post("/api/promocodes/activate", headers=h, json={"code": "old"})
    assert r.status_code == 400


def test_topup_percent_promo(client, db_session):
    h = _auth(client, email="t@example.com")
    db_session.query(User).filter(User.email == "t@example.com").update(
        {User.role: UserRole.admin}
    )
    db_session.commit()
    client.post(
        "/api/promocodes/admin",
        headers=h,
        json={"code": "BONUS", "kind": "percent_next_topup", "value": 10},
    )
    assert client.post("/api/promocodes/activate", headers=h, json={"code": "bonus"}).status_code == 200
    secret = get_settings().mock_topup_secret
    r = client.post(
        "/api/billing/mock-topup",
        headers=h,
        json={"amount_money": "1.00", "credits_to_grant": 100, "secret": secret},
    )
    assert r.status_code == 200
    assert r.json()["credits_granted"] == 110


def test_promocode_max_activations_global_limit(client, db_session):
    """Второй пользователь не может активировать при max_activations=1 после первого."""
    h_admin = _auth(client, email="admin-limit@example.com")
    db_session.query(User).filter(User.email == "admin-limit@example.com").update({User.role: UserRole.admin})
    db_session.commit()

    assert (
        client.post(
            "/api/promocodes/admin",
            headers=h_admin,
            json={
                "code": "ONCE",
                "kind": "fixed_credits",
                "value": 7,
                "max_activations": 1,
            },
        ).status_code
        == 200
    )

    h_first = _auth(client, email="first-user@example.com")
    r_ok = client.post("/api/promocodes/activate", headers=h_first, json={"code": "once"})
    assert r_ok.status_code == 200
    assert r_ok.json()["credits_granted"] == 7

    h_second = _auth(client, email="second-user@example.com")
    r_fail = client.post("/api/promocodes/activate", headers=h_second, json={"code": "once"})
    assert r_fail.status_code == 400
    assert "limit" in r_fail.json()["detail"].lower()
