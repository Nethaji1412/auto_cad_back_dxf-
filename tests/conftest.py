from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Must be set before app.core.config.settings is imported anywhere.
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["RATE_LIMIT_ENABLED"] = "false"


@pytest.fixture(scope="session", autouse=True)
def _test_dirs(tmp_path_factory):
    base = tmp_path_factory.mktemp("solar_backend")
    os.environ["UPLOAD_DIR"] = str(base / "uploads")
    os.environ["OUTPUT_DIR"] = str(base / "outputs")
    yield


@pytest.fixture(scope="session")
def app():
    from app.db.database import Base, engine
    import app.db.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    from main import app as fastapi_app

    yield fastapi_app


@pytest.fixture()
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers(client):
    def _make(email: str, password: str = "TestPass123") -> dict:
        client.post("/api/v1/auth/register", json={"email": email, "password": password})
        r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        token = r.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture()
def sample_boundary_csv(tmp_path: Path) -> Path:
    p = tmp_path / "boundary.csv"
    p.write_text(
        "POINT,EASTING,NORTHING\n"
        "B-01,1000.0,1000.0\n"
        "B-02,1500.0,1000.0\n"
        "B-03,1500.0,1400.0\n"
        "B-04,1000.0,1400.0\n"
    )
    return p


SAMPLE_INPUTS_PAYLOAD = {
    "module": {
        "manufacturer": "Generic",
        "model": "532Wp Thin Film",
        "power_wp": 532,
        "length_mm": 2300,
        "width_mm": 1233.33,
        "technology": "THINFILM",
    },
    "table": {"type": "MMS-2x24", "rows": 2, "columns": 24, "portrait": True, "table_gap_m": 0.5},
    "layout": {
        "boundary_setback_m": 8.0,
        "row_angle": 0.0,
        "row_gap_m": 1.4,
        "minimum_row_length": 5.0,
        "minimum_gap_m": 0.0,
        "target_ac_mw": 7.0,
        "tilt_angle_deg": 0,
        "scb_block_placement": True,
        "arrester_radius_m": 107.0,
    },
    "electrical": {
        "inverter_rating_kw_25c": 1000,
        "inverter_rating_kw_50c": 910,
        "num_icr": 2,
        "modules_per_string": 6,
        "approved_string_size": 6,
        "dc_ac_ratio": 1.2,
        "inverter_architecture": "centralized_inverter",
        "strings_per_scb": 96,
        "scb_block_columns": 2,
        "scb_block_rows": 6,
    },
    "service_road": {"offset_from_panels_m": 2.0, "road_width_m": 3.0, "shoulder_m": 0.5},
}
