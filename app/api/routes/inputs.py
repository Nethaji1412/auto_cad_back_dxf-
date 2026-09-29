from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_owned_project
from app.core.exceptions import NotFoundError
from app.db import models
from app.schemas.inputs import ProjectInputsOut, ProjectInputsRequest
from app.schemas.response import ApiResponse
from app.services import input_service

router = APIRouter(prefix="/api/v1/projects/{project_id}/inputs", tags=["inputs"])


@router.post("", response_model=ApiResponse[ProjectInputsOut], summary="Save engineering inputs")
def save_inputs(
    payload: ProjectInputsRequest,
    db: Session = Depends(get_db),
    project: models.Project = Depends(get_owned_project),
):
    saved = input_service.save_inputs(db, project, payload)
    out = ProjectInputsOut(
        module=payload.module,
        table=payload.table,
        layout=payload.layout,
        electrical=payload.electrical,
        service_road=payload.service_road,
        dxf=payload.dxf,
    )
    return ApiResponse(data=out, message="Inputs saved.")


@router.get("", response_model=ApiResponse[ProjectInputsOut], summary="Get engineering inputs")
def get_inputs(project: models.Project = Depends(get_owned_project)):
    inputs = input_service.get_inputs(project)
    if inputs is None:
        raise NotFoundError("No inputs have been saved for this project yet.")
    out = ProjectInputsOut(
        module=inputs.module_config,
        table=inputs.table_config,
        layout=inputs.layout_config,
        electrical=inputs.electrical_config,
        service_road=inputs.service_road_config,
        dxf=inputs.dxf_config,
    )
    return ApiResponse(data=out)
