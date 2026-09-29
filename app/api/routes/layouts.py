from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_owned_project
from app.core.exceptions import NotFoundError
from app.core.rate_limit import enforce_rate_limit
from app.db import models
from app.schemas.layout import GenerateAcceptedOut, JobOut, ValidationResultOut
from app.schemas.response import ApiResponse
from app.services import layout_service

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["layouts"])
jobs_router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.post("/validate", response_model=ApiResponse[ValidationResultOut], summary="Validate a project's readiness")
def validate(project: models.Project = Depends(get_owned_project)):
    result = layout_service.validate_project(project)
    return ApiResponse(data=ValidationResultOut(**result))


@router.post(
    "/generate",
    response_model=ApiResponse[GenerateAcceptedOut],
    status_code=202,
    summary="Kick off layout + DXF/DWG generation (async)",
    description=(
        "Queues a background job that calls the existing pipeline's run_pipeline(). "
        "Poll GET /api/v1/jobs/{job_id} for status/result."
    ),
)
def generate(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    project: models.Project = Depends(get_owned_project),
    user: models.User = Depends(get_current_user),
):
    enforce_rate_limit(request, "layout_generate", max_requests=10, window_seconds=60)

    validation = layout_service.validate_project(project)
    if not validation["valid"]:
        from app.core.exceptions import ValidationAppError

        raise ValidationAppError("Project is not ready for generation.", details=validation)

    job = layout_service.create_job(db, project)
    background_tasks.add_task(layout_service.background_runner, job.id, project.id)
    return ApiResponse(data=GenerateAcceptedOut(job_id=job.uuid, status=job.status))


@jobs_router.get("/{job_id}", response_model=ApiResponse[JobOut], summary="Get job status/result")
def get_job(job_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    job = layout_service.get_job_by_uuid(db, job_id)
    if job is None:
        raise NotFoundError("Job not found.")
    project = db.get(models.Project, job.project_id)
    if project is None or (project.user_id != user.id and not user.is_admin):
        raise NotFoundError("Job not found.")
    return ApiResponse(data=JobOut.from_model(job))
