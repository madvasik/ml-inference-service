from tests.helpers import auth_headers


def test_invalid_token_is_rejected(client):
    response = client.get("/api/v1/users/me", headers=auth_headers("not-a-real-token"))

    assert response.status_code == 401


def test_rate_limit_headers_are_present_on_excluded_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers

