from __future__ import annotations

import io


def _make_project(client, headers) -> str:
    r = client.post("/api/v1/projects", json={"name": "CSV test project"}, headers=headers)
    return r.json()["data"]["id"]


def test_valid_boundary_csv_accepted(client, auth_headers, sample_boundary_csv):
    headers = auth_headers("csv-valid@example.com")
    project_id = _make_project(client, headers)

    with open(sample_boundary_csv, "rb") as f:
        r = client.post(
            f"/api/v1/projects/{project_id}/files/boundary",
            headers=headers,
            files={"files": ("boundary.csv", f, "text/csv")},
        )
    assert r.status_code == 200
    assert len(r.json()["data"]["uploaded"]) == 1


def test_csv_missing_easting_rejected(client, auth_headers):
    headers = auth_headers("csv-missing-easting@example.com")
    project_id = _make_project(client, headers)

    bad_csv = b"POINT,NORTHING\nB-01,1000.0\nB-02,1000.0\nB-03,1400.0\n"
    r = client.post(
        f"/api/v1/projects/{project_id}/files/boundary",
        headers=headers,
        files={"files": ("bad.csv", io.BytesIO(bad_csv), "text/csv")},
    )
    assert r.status_code == 422


def test_csv_missing_northing_rejected(client, auth_headers):
    headers = auth_headers("csv-missing-northing@example.com")
    project_id = _make_project(client, headers)

    bad_csv = b"POINT,EASTING\nB-01,1000.0\nB-02,1000.0\nB-03,1400.0\n"
    r = client.post(
        f"/api/v1/projects/{project_id}/files/boundary",
        headers=headers,
        files={"files": ("bad.csv", io.BytesIO(bad_csv), "text/csv")},
    )
    assert r.status_code == 422


def test_csv_with_invalid_coordinate_rejected(client, auth_headers):
    # Only 2 valid rows remain once the malformed one is skipped -> < 3 required.
    headers = auth_headers("csv-invalid-coord@example.com")
    project_id = _make_project(client, headers)

    bad_csv = b"POINT,EASTING,NORTHING\nB-01,not-a-number,1000.0\nB-02,1500.0,1000.0\nB-03,1500.0,1400.0\n"
    r = client.post(
        f"/api/v1/projects/{project_id}/files/boundary",
        headers=headers,
        files={"files": ("bad.csv", io.BytesIO(bad_csv), "text/csv")},
    )
    assert r.status_code == 422


def test_csv_with_fewer_than_three_points_rejected(client, auth_headers):
    headers = auth_headers("csv-too-few@example.com")
    project_id = _make_project(client, headers)

    bad_csv = b"POINT,EASTING,NORTHING\nB-01,1000.0,1000.0\nB-02,1500.0,1000.0\n"
    r = client.post(
        f"/api/v1/projects/{project_id}/files/boundary",
        headers=headers,
        files={"files": ("bad.csv", io.BytesIO(bad_csv), "text/csv")},
    )
    assert r.status_code == 422


def test_disallowed_extension_rejected(client, auth_headers):
    headers = auth_headers("csv-bad-ext@example.com")
    project_id = _make_project(client, headers)

    r = client.post(
        f"/api/v1/projects/{project_id}/files/boundary",
        headers=headers,
        files={"files": ("script.py", io.BytesIO(b"print('hi')"), "text/x-python")},
    )
    assert r.status_code == 422
