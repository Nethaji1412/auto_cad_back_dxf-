from __future__ import annotations


def test_register_and_login(client):
    r = client.post("/api/v1/auth/register", json={"email": "a@example.com", "password": "GoodPass123"})
    assert r.status_code == 200
    assert r.json()["data"]["email"] == "a@example.com"

    r = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "GoodPass123"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["user"]["email"] == "a@example.com"


def test_duplicate_registration_rejected(client):
    client.post("/api/v1/auth/register", json={"email": "dup@example.com", "password": "GoodPass123"})
    r = client.post("/api/v1/auth/register", json={"email": "dup@example.com", "password": "GoodPass123"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CONFLICT"


def test_invalid_password_rejected(client):
    r = client.post("/api/v1/auth/register", json={"email": "b@example.com", "password": "short"})
    assert r.status_code == 422


def test_wrong_password_login_rejected(client):
    client.post("/api/v1/auth/register", json={"email": "c@example.com", "password": "GoodPass123"})
    r = client.post("/api/v1/auth/login", json={"email": "c@example.com", "password": "WrongPass1"})
    assert r.status_code == 401


def test_unauthorized_endpoint_requires_token(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_expired_or_garbage_token_rejected(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401
