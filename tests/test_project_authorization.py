from __future__ import annotations


def test_user_cannot_access_other_users_project(client, auth_headers):
    headers_a = auth_headers("owner@example.com")
    headers_b = auth_headers("intruder@example.com")

    r = client.post("/api/v1/projects", json={"name": "Owner's plant"}, headers=headers_a)
    project_id = r.json()["data"]["id"]

    r = client.get(f"/api/v1/projects/{project_id}", headers=headers_b)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "AUTHORIZATION_ERROR"


def test_user_can_access_own_project(client, auth_headers):
    headers = auth_headers("owner2@example.com")
    r = client.post("/api/v1/projects", json={"name": "My plant"}, headers=headers)
    project_id = r.json()["data"]["id"]

    r = client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "My plant"


def test_nonexistent_project_returns_404(client, auth_headers):
    headers = auth_headers("owner3@example.com")
    r = client.get("/api/v1/projects/00000000-0000-0000-0000-000000000000", headers=headers)
    assert r.status_code == 404


def test_project_list_scoped_to_user(client, auth_headers):
    headers_a = auth_headers("lister-a@example.com")
    headers_b = auth_headers("lister-b@example.com")
    client.post("/api/v1/projects", json={"name": "A1"}, headers=headers_a)
    client.post("/api/v1/projects", json={"name": "A2"}, headers=headers_a)
    client.post("/api/v1/projects", json={"name": "B1"}, headers=headers_b)

    r = client.get("/api/v1/projects", headers=headers_a)
    names = {p["name"] for p in r.json()["data"]}
    assert names == {"A1", "A2"}
