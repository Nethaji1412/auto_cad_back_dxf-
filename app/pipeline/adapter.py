from __future__ import annotations

import importlib
import pkgutil
import sys
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.exceptions import MissingInputError
from app.db import models

# --------------------------------------------------------------------------
# core-package alias
# --------------------------------------------------------------------------
# The original pipeline's own module comments ("# End of core/capacity.py",
# "# End of core/csv_loader.py", ...) confirm its real package name is
# `core`, and its internal modules almost certainly import each other via
# that name (e.g. `from core.capacity import ...`). We are not allowed to
# edit those imports, but the requested backend layout (spec section 19)
# puts the pipeline at backend/existing_pipeline/. Reconciling the two
# without touching a single line of pipeline code: register this package
# into sys.modules under its original name before importing from it.
_PIPELINE_PKG_ROOT = Path(__file__).resolve().parents[2]  # backend/
if str(_PIPELINE_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_PKG_ROOT))

import existing_pipeline as _core_pkg  # noqa: E402

sys.modules.setdefault("core", _core_pkg)

# Pre-register every existing_pipeline submodule under its "core.<name>"
# alias too, pointing at the SAME module object. Without this, a stub/real
# module loaded as "core.pipeline" that does `from core.exceptions import X`
# (or `from .exceptions import X`) would trigger a SECOND, independent import
# of exceptions.py under the name "core.exceptions" -- producing a distinct
# PipelineModuleMissingError class that `except _core_pkg.PipelineModuleMissingError`
# elsewhere in this file would never actually catch. Pre-aliasing every
# submodule keeps a single, consistent identity for every class/function
# regardless of whether code reaches it via `existing_pipeline.x` or `core.x`.
for _finder, _name, _ispkg in pkgutil.iter_modules(_core_pkg.__path__):
    _submodule = importlib.import_module(f"existing_pipeline.{_name}")
    sys.modules.setdefault(f"core.{_name}", _submodule)
    setattr(_core_pkg, _name, _submodule)

from core.pipeline import run_pipeline as _run_pipeline  # noqa: E402
from core.calculation_engine import actual_layout_report  # noqa: E402


def _first_or_list(paths: list[str]) -> tuple[str | None, list[str]]:
    return (paths[0] if paths else None), paths


def _strip_none(value: Any) -> Any:
    """
    Recursively drops keys whose value is None from nested dicts (lists
    pass through unchanged). Necessary because Pydantic's model_dump()
    serializes every declared field, including unset Optional ones, as an
    explicit `null` -- but the real pipeline.py reads several of these via
    `config.get(key, default)` (e.g. layout.arrester_radius_m,
    layout.arrester_clearance_m, layout.tables_per_group_columns), which
    only falls back to `default` when the key is ABSENT, not when it's
    present-but-null. Left unstripped, an unset optional field would send
    an explicit `null` through and crash the real pipeline's `float(None)`/
    `int(None)` casts -- this normalizes "not specified" (Optional field
    omitted by the API caller) back into "absent" (what the pipeline
    expects), without altering any value the caller actually supplied.
    """
    if isinstance(value, dict):
        return {k: _strip_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_strip_none(v) for v in value]
    return value


def build_pipeline_config(
    project: models.Project,
    inputs: models.ProjectInput,
    boundary_paths: list[str],
    control_room_paths: list[str],
    inverter_room_paths: list[str],
    private_area_paths: list[str],
    output_dir: Path,
) -> dict[str, Any]:
    """
    Constructs the EXACT configuration structure run_pipeline() expects
    (mirrors config.json 1:1 -- verified directly against the real
    core/pipeline.py, not guessed). Populates both the singular (first
    item) and plural (list) input keys since run_pipeline() accepts either
    (`input_cfg.get("boundary_csvs") or input_cfg.get("boundary_csv")`, and
    likewise for control_room_/inverter_room_).

    Note on `input.exclusions`: in the real pipeline this is a path to a
    SEPARATE generic exclusions JSON file (parsed by
    parse_exclusion_polygons/load_json for polygon/circle exclusion zones
    unrelated to the CSV-based control-room/inverter-room/private-area
    flow) -- it is NOT a list of CSV paths. The API doesn't currently
    expose that generic-JSON-exclusions feature, so this key is simply
    omitted (it's optional -- `if extra_exclusions_file:` -- and every
    CSV-based exclusion already reaches the pipeline via
    control_room_csvs/inverter_room_csvs/private_area_csvs above).
    """
    if not boundary_paths:
        raise MissingInputError("A boundary CSV is required before generation can run.")

    boundary_csv, boundary_csvs = _first_or_list(boundary_paths)
    control_room_csv, control_room_csvs = _first_or_list(control_room_paths)
    inverter_room_csv, inverter_room_csvs = _first_or_list(inverter_room_paths)

    output_dir.mkdir(parents=True, exist_ok=True)
    dxf_config = dict(inputs.dxf_config or {})
    dxf_layers = dxf_config.get("layers") or {}
    dxf_output_file = str(output_dir / "solar_layout.dxf")

    config: dict[str, Any] = {
        "input": {
            "boundary_csv": boundary_csv,
            "boundary_csvs": boundary_csvs,
            "control_room_csv": control_room_csv,
            "control_room_csvs": control_room_csvs,
            "inverter_room_csv": inverter_room_csv,
            "inverter_room_csvs": inverter_room_csvs,
            "private_area_csvs": private_area_paths,
        },
        "module": inputs.module_config,
        "table": inputs.table_config,
        "layout": inputs.layout_config,
        "electrical": inputs.electrical_config,
        "service_road": inputs.service_road_config,
        "oda_file_converter_path": settings.ODA_FILE_CONVERTER_PATH or None,
        "dxf": {
            "output_file": dxf_output_file,
            "require_dwg": bool(dxf_config.get("require_dwg", False)),
            "layers": dxf_layers,
        },
    }
    # See _strip_none's docstring: normalizes unset-Optional-as-null back to
    # absent so the pipeline's own config.get(key, default) fallbacks apply.
    return _strip_none(config)

def run_generation(config: dict[str, Any]) -> dict[str, Any]:
    """
    The single call site for the existing pipeline's run_pipeline(). Never
    called from a route or from Pydantic validation code directly -- only
    from layout_service's background job runner.
    """
    result = _run_pipeline(config)
    return normalize_result(result)


def _summarize_table_groups(table_groups: Any) -> dict[str, Any] | None:
    """
    table_groups (from generateTableGrouping/detect_and_group_centralized_2x6)
    is a list of {"table": TablePlacement, "inverter_id": int, "scb_id":
    int|None} dicts -- TablePlacement carries a raw shapely Polygon, so it
    can't go into a JSON column as-is. This reduces it to plain counts,
    which is all the API needs; the DXF itself is the authoritative
    geometric output.
    """
    if not table_groups:
        return None
    inverter_ids = {g["inverter_id"] for g in table_groups if g.get("inverter_id") is not None}
    scb_ids = {g["scb_id"] for g in table_groups if g.get("scb_id") is not None}
    return {
        "total_tables_grouped": len(table_groups),
        "inverters_used": len(inverter_ids),
        "scbs_used": len(scb_ids) if scb_ids else None,
    }


def normalize_result(result: dict[str, Any]) -> dict[str, Any]:
    """
    Reshapes run_pipeline()'s result dict into the API's normalized
    calculation/layout/grouping/files sections (spec section 18/54),
    WITHOUT recomputing or altering any of the underlying numbers. Every
    value here is JSON-safe (no shapely geometries, no PackingEngine, no
    raw dataclass instances) since this becomes a Job.result JSON column.
    """
    grouping = result.get("grouping")  # calculation_engine.PlantCalculation | None
    theoretical_lines: list[str] = []
    actual_lines: list[str] = []
    grouping_dict: dict[str, Any] | None = None
    warnings: list[str] = []

    if grouping is not None:
        theoretical_lines = list(grouping.summary_lines())
        actual_lines = list(actual_layout_report(grouping, result["table_count"]))
        warnings = list(grouping.warnings or [])
        grouping_dict = _dataclass_or_none(grouping)

    return {
        "table_count": result.get("table_count"),
        "module_count": result.get("module_count"),
        "actual_dc_mwp": result.get("actual_dc_mwp"),
        "target_dc_mwp": result.get("target_dc_mwp"),
        "target_ac_mw": result.get("target_ac_mw"),
        "ac_capacity_mw": result.get("ac_capacity_mw"),
        "dc_ac_ratio": result.get("dc_ac_ratio"),
        "dc_ac_oversizing_percent": result.get("dc_ac_oversizing_percent"),
        "land_area_acres": result.get("land_area_acres"),
        "row_pitch_m": result.get("row_pitch_m"),
        "capacity_note": result.get("capacity_note"),
        "dxf_path": result.get("dxf_path"),
        "dwg_path": result.get("dwg_path"),
        "dwg_export_message": result.get("dwg_export_message"),
        "theoretical_summary": theoretical_lines,
        "actual_layout_summary": actual_lines,
        "warnings": warnings,
        "grouping": grouping_dict,
        "grouping_breakdown": _summarize_table_groups(result.get("table_groups")),
        "capacity_plan": _dataclass_or_none(result.get("capacity_plan")),
        "ac_dc_plan": _dataclass_or_none(result.get("ac_dc_plan")),
        "requirement": _dataclass_or_none(result.get("requirement")),
    }


def _dataclass_or_none(obj: Any) -> dict[str, Any] | None:
    if obj is None:
        return None
    try:
        from dataclasses import asdict

        return asdict(obj)
    except TypeError:
        return None
