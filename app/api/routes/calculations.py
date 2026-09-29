from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_owned_project
from app.db import models
from app.schemas.response import ApiResponse
from app.services import layout_service

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["calculations"])


@router.post(
    "/calculate",
    response_model=ApiResponse[dict],
    summary="Run the theoretical engineering calculation preview",
    description=(
        "Computes DC/AC sizing and string/table/inverter/SCB grouping by calling the "
        "existing capacity.py and calculation_engine.calculatePlant() directly -- the "
        "same functions core/pipeline.py itself calls -- so this preview matches what "
        "/generate will actually build. No layout/DXF generation is performed."
    ),
)
def calculate(db: Session = Depends(get_db), project: models.Project = Depends(get_owned_project)):
    preview = layout_service.run_calculation_preview(db, project)
    return ApiResponse(data=preview)
