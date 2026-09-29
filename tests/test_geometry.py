from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from existing_pipeline import csv_loader
from existing_pipeline.offset import JoinStyle, OffsetEngine


def _write_csv(tmp_path, name, rows):
    p = tmp_path / name
    lines = ["POINT,EASTING,NORTHING"] + [f"{pt},{x},{y}" for pt, x, y in rows]
    p.write_text("\n".join(lines) + "\n")
    return p


def test_load_boundary_from_csv(tmp_path):
    path = _write_csv(
        tmp_path,
        "boundary.csv",
        [("B-01", 0, 0), ("B-02", 100, 0), ("B-03", 100, 100), ("B-04", 0, 100)],
    )
    result = csv_loader.load_boundary_from_csv(str(path))
    assert len(result["boundary"]) == 4
    assert result["boundary"][0] == {"x": 0.0, "y": 0.0}


def test_load_exclusion_from_csv_control_room(tmp_path):
    path = _write_csv(
        tmp_path,
        "control_room.csv",
        [("CR-01", 10, 10), ("CR-02", 20, 10), ("CR-03", 20, 20), ("CR-04", 10, 20)],
    )
    polygon = csv_loader.load_exclusion_from_csv(str(path), name="control_room")
    assert polygon.is_valid
    assert polygon.area == pytest.approx(100.0)


def test_load_exclusion_from_csv_inverter_room(tmp_path):
    path = _write_csv(
        tmp_path,
        "inverter_room.csv",
        [("IR-01", 0, 0), ("IR-02", 5, 0), ("IR-03", 5, 5), ("IR-04", 0, 5)],
    )
    polygon = csv_loader.load_exclusion_from_csv(str(path), name="inverter_room")
    assert polygon.area == pytest.approx(25.0)


def test_boundary_csv_requires_three_points(tmp_path):
    path = _write_csv(tmp_path, "too_few.csv", [("B-01", 0, 0), ("B-02", 100, 0)])
    with pytest.raises(ValueError):
        csv_loader.read_coordinate_csv(str(path))


def test_boundary_setback_offset():
    boundary = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    engine = OffsetEngine()
    setback = engine.create_internal_offset(boundary, distance=8.0, join_style=JoinStyle.MITRE)
    assert setback.area < boundary.area
    # An 8m inward offset on a 100x100 square should leave an 84x84 square.
    assert setback.area == pytest.approx(84 * 84, rel=0.01)


def test_apply_exclusions_removes_area():
    boundary = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    exclusion = Polygon([(10, 10), (20, 10), (20, 20), (10, 20)])
    engine = OffsetEngine()
    developable = engine.apply_exclusions(boundary, [exclusion])
    assert developable.area == pytest.approx(boundary.area - exclusion.area)


def test_private_area_exclusion_loading(tmp_path):
    path = _write_csv(
        tmp_path,
        "private_area.csv",
        [("P-01", 50, 50), ("P-02", 60, 50), ("P-03", 60, 60), ("P-04", 50, 60)],
    )
    polygon = csv_loader.load_exclusion_from_csv(str(path))
    assert polygon.area == pytest.approx(100.0)
