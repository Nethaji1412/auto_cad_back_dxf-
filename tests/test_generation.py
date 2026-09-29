from __future__ import annotations

import time

from tests.conftest import SAMPLE_INPUTS_PAYLOAD


def _ready_project(client, headers, sample_boundary_csv):
    r = client.post("/api/v1/projects", json={"name": "Generation test"}, headers=headers)
    project_id = r.json()["data"]["id"]
    client.post(f"/api/v1/projects/{project_id}/inputs", json=SAMPLE_INPUTS_PAYLOAD, headers=headers)
    with open(sample_boundary_csv, "rb") as f:
        client.post(
            f"/api/v1/projects/{project_id}/files/boundary",
            headers=headers,
            files={"files": ("boundary.csv", f, "text/csv")},
        )
    return project_id


def test_validate_passes_with_complete_inputs(client, auth_headers, sample_boundary_csv):
    headers = auth_headers("gen-validate@example.com")
    project_id = _ready_project(client, headers, sample_boundary_csv)

    r = client.post(f"/api/v1/projects/{project_id}/validate", headers=headers)
    assert r.status_code == 200
    assert r.json()["data"]["valid"] is True


def test_validate_fails_without_inputs(client, auth_headers):
    headers = auth_headers("gen-no-inputs@example.com")
    r = client.post("/api/v1/projects", json={"name": "No inputs"}, headers=headers)
    project_id = r.json()["data"]["id"]

    r = client.post(f"/api/v1/projects/{project_id}/validate", headers=headers)
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["valid"] is False
    assert any("boundary" in e.lower() for e in body["errors"])


def test_generate_accepted_and_job_pollable(client, auth_headers, sample_boundary_csv):
    headers = auth_headers("gen-accept@example.com")
    project_id = _ready_project(client, headers, sample_boundary_csv)

    r = client.post(f"/api/v1/projects/{project_id}/generate", headers=headers)
    assert r.status_code == 202
    job_id = r.json()["data"]["job_id"]
    assert r.json()["data"]["status"] == "QUEUED"

    r = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["data"]["job_id"] == job_id


def test_generate_produces_real_dxf_end_to_end(client, auth_headers, sample_boundary_csv):
    """
    Full real generation: the actual core/pipeline.py now runs (not a
    stub), so this asserts genuine output -- a real DXF file with the
    expected layer set, actual/theoretical table counts kept separate
    (spec section 17), and a downloadable file_id appearing only after
    the job completes (never before).
    """
    headers = auth_headers("gen-real@example.com")
    project_id = _ready_project(client, headers, sample_boundary_csv)

    # No output file_id should exist before generation runs.
    r = client.get(f"/api/v1/projects/{project_id}/outputs", headers=headers)
    assert r.json()["data"]["files"] == []

    r = client.post(f"/api/v1/projects/{project_id}/generate", headers=headers)
    assert r.status_code == 202
    job_id = r.json()["data"]["job_id"]

    body = None
    for _ in range(100):
        r = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
        body = r.json()["data"]
        if body["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.1)

    assert body["status"] == "COMPLETED", body.get("error_message")
    result = body["result"]

    # Real numbers came back, not placeholders.
    assert result["table_count"] > 0
    assert result["module_count"] == result["table_count"] * 48
    assert result["land_area_acres"] > 0

    # Raw filesystem paths must never be returned by the API (spec 52) --
    # only availability flags. GET /outputs is the correct discovery
    # mechanism for the actual downloadable file_id.
    assert result["dxf_available"] is True
    assert "dxf_path" not in result
    assert "dwg_path" not in result

    # Theoretical (calculatePlant) vs actual (placed) stay separate and, for
    # this deliberately generous boundary, actual > theoretical because
    # fill_gaps() maximizes land use beyond the initial capacity target --
    # exactly the real pipeline's documented behavior.
    assert result["grouping"]["total_tables"] > 0
    assert result["table_count"] >= result["grouping"]["total_tables"]
    assert any("Tables Placed" in line for line in result["actual_layout_summary"])
    assert any("PROJECT SUMMARY" in line for line in result["theoretical_summary"])
    assert result["actual_layout_summary"] != result["theoretical_summary"]

    # file_id only shows up now that the job is COMPLETED (never before),
    # and only for the DXF -- no DWG entry, ever (download-only-dxf).
    r = client.get(f"/api/v1/projects/{project_id}/outputs", headers=headers)
    files = r.json()["data"]["files"]
    assert len(files) == 1
    assert files[0]["file_type"] == "DXF"
    dxf_file = files[0]

    r = client.get(f"/api/v1/projects/{project_id}/outputs/{dxf_file['file_id']}", headers=headers)
    assert r.status_code == 200

    # The downloaded bytes are a real DXF with the expected layer set and
    # INSERT (table block) count matching table_count exactly.
    import io

    import ezdxf

    doc = ezdxf.read(io.StringIO(r.content.decode("utf-8", errors="replace")))
    layer_names = {layer.dxf.name for layer in doc.layers}
    for expected in ("BOUNDARY", "PV_TABLES", "SETBACK", "SERVICE_ROAD", "TITLE_BLOCK"):
        assert expected in layer_names
    assert doc.modelspace().query("INSERT").__len__() == result["table_count"]


def test_outputs_and_download_reject_non_dxf_file_ids(client, auth_headers, sample_boundary_csv):
    """
    An uploaded input CSV's own file_id (returned by the upload endpoint)
    must NOT be fetchable through /outputs/{file_id} -- that endpoint
    serves only generated DXF output, never input uploads and never DWG,
    even though they share the same project_files table.
    """
    headers = auth_headers("gen-dxf-only@example.com")
    project_id = _ready_project(client, headers, sample_boundary_csv)

    with open(sample_boundary_csv, "rb") as f:
        upload_resp = client.post(
            f"/api/v1/projects/{project_id}/files/boundary",
            headers=headers,
            files={"files": ("boundary2.csv", f, "text/csv")},
        )
    boundary_file_id = upload_resp.json()["data"]["uploaded"][0]["file_id"]

    r = client.get(f"/api/v1/projects/{project_id}/outputs/{boundary_file_id}", headers=headers)
    assert r.status_code == 404


def test_actual_and_theoretical_stay_separate_in_normalize_result():
    """Unit-level check on the adapter's normalization contract (spec
    section 17): theoretical_summary and actual_layout_summary must never
    be merged into a single field. Uses a REAL PlantCalculation (via the
    real calculatePlant()) rather than a mock, so it also exercises the
    real actual_layout_report()."""
    from app.pipeline.adapter import normalize_result
    from existing_pipeline.calculation_engine import calculatePlant

    real_grouping = calculatePlant(
        plant_ac_mw=7.0,
        plant_dc_mwp=8.4,
        module_rating_wp=532,
        total_modules=15789,
        inverter_rating_kw=1000,
        approved_string_size=6,
        mms_rows=2,
        mms_columns=24,
        plant_type="centralized_inverter",
        strings_per_scb=96,
    )

    fake_result = {
        "table_count": 312,  # deliberately less than theoretical 329 -> shortfall path
        "module_count": 14976,
        "actual_dc_mwp": 7.967,
        "land_area_acres": 25.4,
        "dxf_path": "/tmp/does-not-matter.dxf",
        "dwg_path": None,
        "dwg_export_message": "DWG not generated: ODA File Converter not installed.",
        "grouping": real_grouping,
    }
    normalized = normalize_result(fake_result)
    assert any("PROJECT SUMMARY" in line for line in normalized["theoretical_summary"])
    assert any("Tables Placed" in line for line in normalized["actual_layout_summary"])
    assert any("Shortfall" in line for line in normalized["actual_layout_summary"])
    assert normalized["actual_layout_summary"] != normalized["theoretical_summary"]
    assert normalized["table_count"] == 312
    assert "Warning: Last SCB will contain fewer strings." in normalized["warnings"]
    assert normalized["grouping"]["total_tables"] == 329
