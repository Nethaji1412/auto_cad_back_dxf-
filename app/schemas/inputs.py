from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InverterArchitecture(str, Enum):
    STRING_INVERTER = "string_inverter"
    CENTRALIZED_INVERTER = "centralized_inverter"


class ModuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manufacturer: str = Field(min_length=1, max_length=255)
    model: str = Field(min_length=1, max_length=255)
    power_wp: float = Field(gt=0)
    length_mm: float = Field(gt=0)
    width_mm: float = Field(gt=0)
    technology: str = Field(min_length=1, max_length=64)


class TableInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Optional[str] = None
    rows: int = Field(gt=0)
    columns: int = Field(gt=0)
    modules_per_table: Optional[int] = Field(default=None, gt=0)
    portrait: bool = True
    table_gap_m: float = Field(ge=0)

    @model_validator(mode="after")
    def _check_modules_per_table(self) -> "TableInput":
        # Pipeline rule (spec section 3):
        #   Modules per Table = MMS Rows x MMS Columns
        # If the caller supplies modules_per_table explicitly it must agree
        # with rows x columns -- we never silently override or "fix" it.
        expected = self.rows * self.columns
        if self.modules_per_table is None:
            self.modules_per_table = expected
        elif self.modules_per_table != expected:
            raise ValueError(
                f"modules_per_table ({self.modules_per_table}) does not equal "
                f"rows x columns ({self.rows} x {self.columns} = {expected}). "
                "The pipeline requires these to match; omit modules_per_table "
                "to have it derived automatically."
            )
        return self


class LayoutInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    boundary_setback_m: float = Field(ge=0)
    row_angle: float = 0.0
    row_gap_m: float = Field(ge=0)
    minimum_row_length: float = Field(ge=0)
    minimum_gap_m: float = Field(ge=0, default=0.0)
    target_ac_mw: Optional[float] = Field(default=None, gt=0)
    target_dc_capacity_mwp: Optional[float] = Field(default=None, gt=0)
    dc_oversizing_percent: Optional[float] = Field(default=None, ge=0)
    tilt_angle_deg: float = 0.0
    scb_block_placement: bool = True
    arrester_radius_m: Optional[float] = Field(default=None, ge=0)
    arrester_clearance_m: Optional[float] = Field(default=None, ge=0)
    tables_per_group_columns: Optional[int] = Field(default=None, gt=0)


class ElectricalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inverter_rating_kw_25c: float = Field(gt=0)
    inverter_rating_kw_50c: Optional[float] = Field(default=None, gt=0)
    num_inverters: Optional[int] = Field(default=None, gt=0)
    num_icr: Optional[int] = Field(default=None, gt=0)
    modules_per_string: int = Field(gt=0)
    approved_string_size: int = Field(gt=0)
    dc_ac_ratio: Optional[float] = Field(default=None, gt=0)
    inverter_architecture: InverterArchitecture
    strings_per_scb: Optional[int] = Field(default=None, gt=0)
    scb_block_rows: Optional[int] = Field(default=None, gt=0)
    scb_block_columns: Optional[int] = Field(default=None, gt=0)
    total_modules: Optional[int] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _check_architecture_dependencies(self) -> "ElectricalInput":
        # spec section 5 / 37: centralized architecture requires
        # strings_per_scb; we reject rather than silently defaulting it.
        if self.inverter_architecture == InverterArchitecture.CENTRALIZED_INVERTER:
            if not self.strings_per_scb or self.strings_per_scb <= 0:
                raise ValueError(
                    "strings_per_scb is required (and must be > 0) when "
                    "inverter_architecture is 'centralized_inverter'."
                )
        return self


class ServiceRoadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offset_from_panels_m: float = Field(ge=0)
    road_width_m: float = Field(ge=0)
    shoulder_m: float = Field(ge=0)


class DxfLayersInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    boundary: str = "BOUNDARY"
    setback: str = "SETBACK"
    road: str = "ROADS"
    service_road: str = "SERVICE_ROAD"
    exclusion: str = "EXCLUSIONS"
    pv_table: str = "PV_TABLES"
    module: str = "MODULES"
    string: str = "STRINGS"
    combiner: str = "COMBINERS"
    inverter: str = "INVERTERS"
    transformer: str = "TRANSFORMERS"
    cable: str = "CABLES"
    text: str = "TEXT"
    # Legend-only layers (spec: fence, security cabin, entry gate, lightning
    # arrester, well aren't generated as real site geometry elsewhere in the
    # pipeline yet, but dxf_writer.py still creates a dedicated, correctly
    # colored layer for each so the legend's symbol swatches are real DXF
    # entities). All optional -- dxf_writer.py falls back to sensible
    # defaults (FENCE, SECURITY_CABIN, ENTRY_GATE, LIGHTNING_ARRESTER, WELL)
    # via `.get(...) or "DEFAULT"` when omitted.
    fence: Optional[str] = None
    security_cabin: Optional[str] = None
    entry_gate: Optional[str] = None
    lightning_arrester: Optional[str] = None
    well: Optional[str] = None


class DxfInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    require_dwg: bool = False
    layers: DxfLayersInput = Field(default_factory=DxfLayersInput)


class ProjectInputsRequest(BaseModel):
    """Full engineering input payload for POST /projects/{id}/inputs."""
    model_config = ConfigDict(extra="forbid")
    module: ModuleInput
    table: TableInput
    layout: LayoutInput
    electrical: ElectricalInput
    service_road: ServiceRoadInput
    dxf: DxfInput = Field(default_factory=DxfInput)

    @model_validator(mode="after")
    def _check_capacity_mode(self) -> "ProjectInputsRequest":
        # spec section 8: at least one valid capacity-resolution mode must
        # be resolvable from what was supplied. We validate presence here;
        # the actual math is delegated entirely to capacity.py.
        layout = self.layout
        has_ac = layout.target_ac_mw is not None
        has_dc = layout.target_dc_capacity_mwp is not None
        has_oversizing = layout.dc_oversizing_percent is not None

        if not (has_ac or has_dc):
            raise ValueError(
                "At least one capacity target is required: target_ac_mw and/or "
                "target_dc_capacity_mwp (optionally with dc_oversizing_percent)."
            )
        if has_dc and not has_ac and not self.electrical.num_inverters:
            # Mode C (spec 8): DC-only target needs inverter info to resolve
            # a DC:AC ratio -- we do not invent it.
            raise ValueError(
                "target_dc_capacity_mwp was supplied without target_ac_mw. Resolving "
                "an implied DC:AC ratio requires electrical.num_inverters (or supply "
                "target_ac_mw directly) -- this value is not assumed."
            )
        return self


class ProjectInputsOut(ProjectInputsRequest):
    pass
