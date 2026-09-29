from __future__ import annotations

import math

from existing_pipeline import capacity, grouping


def test_capacity_plan_from_targets_matches_formula():
    plan = capacity.compute_capacity_plan_from_targets(
        target_ac_mw=7.0,
        target_dc_mwp=8.4,
        module_power_wp=532,
        modules_per_table=48,
        inverter_rating_kw=1000,
        modules_per_string=6,
    )
    expected_modules = math.ceil(8.4 * 1_000_000 / 532)
    assert plan.required_modules == expected_modules
    assert plan.required_tables == math.ceil(expected_modules / 48)
    assert plan.num_inverters_required == math.ceil(7.0 * 1000 / 1000)
    assert round(plan.dc_ac_ratio, 4) == round(8.4 / 7.0, 4)


def test_string_inverter_grouping_chain():
    result = grouping.compute_string_inverter_grouping(
        target_ac_mw=7.0,
        inverter_rating_kw=1000,
        dc_ac_ratio=1.2,
        modules_per_table=48,
        string_size=6,
        module_power_wp=532,
    )
    assert result.architecture == "string_inverter"
    assert result.num_inverters == math.ceil(7.0 * 1000 / 1000)
    assert result.strings_per_table == 48 / 6
    string_power_w = 6 * 532
    expected_strings_per_inverter = (1000 * 1000 * 1.2) / string_power_w
    assert round(result.strings_per_inverter, 6) == round(expected_strings_per_inverter, 6)
    assert result.tables_per_inverter == result.strings_per_inverter / result.strings_per_table
    assert result.tables_required == math.ceil(result.tables_per_inverter) * result.num_inverters
    assert result.modules_required == result.tables_required * 48


def test_centralized_inverter_grouping_chain():
    result = grouping.compute_centralized_inverter_grouping(
        target_ac_mw=7.0,
        inverter_rating_kw=1000,
        dc_ac_ratio=1.2,
        modules_per_table=48,
        string_size=6,
        module_power_wp=532,
        strings_per_scb=96,
    )
    assert result.architecture == "centralized_inverter"
    assert result.scb_per_inverter == result.strings_per_inverter / 96
    assert result.tables_per_scb == 96 / result.strings_per_table
    expected_tables = math.ceil(result.tables_per_scb) * math.ceil(result.scb_per_inverter) * result.num_inverters
    assert result.tables_required == expected_tables


def test_capacity_requires_positive_target():
    import pytest

    with pytest.raises(ValueError):
        capacity.compute_capacity_requirement(
            target_dc_mwp=0, module_power_wp=532, modules_per_table=48
        )


def test_calculate_plant_matches_reference_cli_regression():
    """
    Regression check against the REAL calculation_engine.calculatePlant(),
    using the exact config.json values from the original project
    (7 MW AC, 1.2 DC:AC ratio, 532 Wp modules, 48 modules/table, string
    size 6, 96 strings/SCB, centralized architecture). These numbers were
    independently verified by running the real core/pipeline.py end-to-end
    via reference/main.py -- see reference/README.md.
    """
    from existing_pipeline.calculation_engine import calculatePlant

    result = calculatePlant(
        plant_ac_mw=7.0,
        plant_dc_mwp=7.0 * 1.2,
        module_rating_wp=532,
        total_modules=15789,
        inverter_rating_kw=1000,
        approved_string_size=6,
        mms_rows=2,
        mms_columns=24,
        plant_type="centralized_inverter",
        strings_per_scb=96,
    )
    assert result.number_of_inverters == 7
    assert result.scbs_per_inverter == 4
    assert result.tables_per_scb == 12.0
    assert result.strings_per_table == 8.0
    assert result.total_tables == 329
    assert result.number_of_strings == 2632
    assert result.modules_per_table == 48
    assert "Warning: Last SCB will contain fewer strings." in result.warnings


def test_calculation_preview_endpoint(client, auth_headers, sample_boundary_csv):
    from tests.conftest import SAMPLE_INPUTS_PAYLOAD

    headers = auth_headers("calc-endpoint@example.com")
    r = client.post("/api/v1/projects", json={"name": "Calc test"}, headers=headers)
    project_id = r.json()["data"]["id"]

    r = client.post(f"/api/v1/projects/{project_id}/inputs", json=SAMPLE_INPUTS_PAYLOAD, headers=headers)
    assert r.status_code == 200

    r = client.post(f"/api/v1/projects/{project_id}/calculate", headers=headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["plant_type"] == "centralized_inverter"
    # Matches test_calculate_plant_matches_reference_cli_regression exactly --
    # the API preview must equal what the real pipeline will build.
    assert data["grouping"]["number_of_inverters"] == 7
    assert data["grouping"]["scbs_per_inverter"] == 4
    assert data["grouping"]["total_tables"] == 329
    assert data["capacity"]["target_ac_mw"] == 7.0
