from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.core.exceptions import MissingInputError, ValidationAppError
from app.db import models
from existing_pipeline import capacity as capacity_mod
from existing_pipeline.calculation_engine import MissingInputError as PipelineMissingInputError
from existing_pipeline.calculation_engine import calculatePlant

# --------------------------------------------------------------------------
# This service mirrors, line for line, the capacity-resolution block in the
# real core/pipeline.py's run_pipeline() (the four capacity-target modes,
# then the calculatePlant() call) so that POST /calculate returns EXACTLY
# what /generate will actually build -- without needing a boundary CSV,
# GeometryEngine, or PackingEngine, since none of that affects the
# theoretical numbers. Every formula lives in capacity.py /
# calculation_engine.py; nothing is reimplemented here. If pipeline.py's
# own resolution logic ever changes, this block must be updated to match.
# --------------------------------------------------------------------------


def _resolve_capacity(inputs: models.ProjectInput) -> dict[str, Any]:
    layout = inputs.layout_config
    electrical = inputs.electrical_config
    module = inputs.module_config
    table = inputs.table_config

    target_capacity_mwp = layout.get("target_dc_capacity_mwp")
    target_ac_mw = layout.get("target_ac_mw")
    dc_ac_ratio_input = electrical.get("dc_ac_ratio")

    capacity_plan = None
    ac_dc_plan = None
    resolved_ac_mw = None
    resolved_dc_ac_ratio = None

    module_power_wp = module["power_wp"]
    modules_per_table = table["modules_per_table"]

    if target_ac_mw and dc_ac_ratio_input:
        # PRIMARY PATH (matches pipeline.py): DC:AC ratio supplied directly.
        resolved_ac_mw = float(target_ac_mw)
        resolved_dc_ac_ratio = float(dc_ac_ratio_input)
        target_capacity_mwp = resolved_ac_mw * resolved_dc_ac_ratio

    elif target_ac_mw and target_capacity_mwp:
        inverter_rating_kw = electrical.get("inverter_rating_kw_25c")
        if not inverter_rating_kw:
            raise MissingInputError(
                "layout.target_ac_mw requires electrical.inverter_rating_kw_25c in the config."
            )
        ac_dc_plan = capacity_mod.compute_capacity_plan_from_targets(
            target_ac_mw=float(target_ac_mw),
            target_dc_mwp=float(target_capacity_mwp),
            module_power_wp=module_power_wp,
            modules_per_table=modules_per_table,
            inverter_rating_kw=inverter_rating_kw,
            modules_per_string=electrical.get("modules_per_string"),
        )
        resolved_ac_mw = float(target_ac_mw)
        resolved_dc_ac_ratio = float(target_capacity_mwp) / float(target_ac_mw)

    elif target_capacity_mwp:
        inverter_rating_kw = electrical.get("inverter_rating_kw_25c")
        num_inverters = electrical.get("num_inverters")
        if not (inverter_rating_kw and num_inverters):
            raise MissingInputError(
                "An explicit target_dc_capacity_mwp (without target_ac_mw) requires "
                "electrical.inverter_rating_kw_25c and electrical.num_inverters, so an "
                "implied AC capacity and DC:AC ratio can be resolved for string/inverter sizing."
            )
        resolved_ac_mw = num_inverters * inverter_rating_kw / 1000
        resolved_dc_ac_ratio = float(target_capacity_mwp) / resolved_ac_mw

    elif layout.get("dc_oversizing_percent") is not None:
        inverter_rating_kw = electrical.get("inverter_rating_kw_25c")
        num_inverters = electrical.get("num_inverters")
        if not (inverter_rating_kw and num_inverters):
            raise MissingInputError(
                "layout.dc_oversizing_percent requires electrical.inverter_rating_kw_25c "
                "and electrical.num_inverters."
            )
        capacity_plan = capacity_mod.compute_capacity_plan(
            module_power_wp=module_power_wp,
            modules_per_table=modules_per_table,
            inverter_rating_kw=inverter_rating_kw,
            num_inverters=num_inverters,
            dc_oversizing_percent=float(layout["dc_oversizing_percent"]),
        )
        target_capacity_mwp = capacity_plan.required_dc_capacity_mw
        resolved_ac_mw = capacity_plan.ac_capacity_mw
        resolved_dc_ac_ratio = 1 + float(layout["dc_oversizing_percent"]) / 100

    else:
        raise MissingInputError(
            "Could not resolve a capacity target from the supplied layout/electrical inputs. "
            "Supply target_ac_mw (with electrical.dc_ac_ratio or target_dc_capacity_mwp), or "
            "target_dc_capacity_mwp with inverter info, or dc_oversizing_percent with inverter info."
        )

    return {
        "resolved_ac_mw": resolved_ac_mw,
        "resolved_dc_ac_ratio": resolved_dc_ac_ratio,
        "target_capacity_mwp": target_capacity_mwp,
        "capacity_plan": capacity_plan,
        "ac_dc_plan": ac_dc_plan,
    }


def compute_calculation_preview(inputs: models.ProjectInput) -> dict[str, Any]:
    if inputs is None:
        raise MissingInputError("Project inputs have not been submitted yet.")

    resolved = _resolve_capacity(inputs)
    resolved_ac_mw = resolved["resolved_ac_mw"]
    resolved_dc_ac_ratio = resolved["resolved_dc_ac_ratio"]

    electrical = inputs.electrical_config
    module = inputs.module_config
    table = inputs.table_config

    architecture = electrical.get("inverter_architecture", "string_inverter")
    inverter_rating_kw = electrical.get("inverter_rating_kw_25c")
    # Matches pipeline.py exactly: approved string size falls back to the
    # table's row count (a string = one column of modules), not to
    # modules_per_table.
    string_size = electrical.get("approved_string_size") or table["rows"]
    module_power_wp = module["power_wp"]

    total_modules = electrical.get("total_modules") or int(
        round(resolved_ac_mw * resolved_dc_ac_ratio * 1_000_000 / module_power_wp)
    )

    try:
        grouping = calculatePlant(
            plant_ac_mw=resolved_ac_mw,
            plant_dc_mwp=resolved_ac_mw * resolved_dc_ac_ratio,
            module_rating_wp=module_power_wp,
            total_modules=total_modules,
            inverter_rating_kw=inverter_rating_kw,
            approved_string_size=string_size,
            mms_rows=table["rows"],
            mms_columns=table["columns"],
            plant_type=architecture,
            strings_per_scb=electrical.get("strings_per_scb"),
        )
    except PipelineMissingInputError as exc:
        raise MissingInputError(str(exc)) from exc
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc

    capacity_out: dict[str, Any] = {
        "mode": (
            "ac_and_ratio" if resolved["capacity_plan"] is None and resolved["ac_dc_plan"] is None
            else ("dc_oversizing" if resolved["capacity_plan"] is not None else "ac_and_dc_targets")
        ),
        "target_ac_mw": resolved_ac_mw,
        "target_dc_mwp": resolved_ac_mw * resolved_dc_ac_ratio,
        "dc_ac_ratio": resolved_dc_ac_ratio,
        "dc_ac_oversizing_percent": (resolved_dc_ac_ratio - 1) * 100,
    }
    if resolved["capacity_plan"] is not None:
        capacity_out["capacity_plan"] = asdict(resolved["capacity_plan"])
    if resolved["ac_dc_plan"] is not None:
        capacity_out["ac_dc_plan"] = asdict(resolved["ac_dc_plan"])

    return {
        "plant_type": architecture,
        "module_rating_wp": module_power_wp,
        "modules_per_table": table["modules_per_table"],
        "capacity": capacity_out,
        "grouping": asdict(grouping),
        "warnings": list(grouping.warnings or []),
    }
