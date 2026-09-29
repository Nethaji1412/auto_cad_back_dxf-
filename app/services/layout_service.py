from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import MissingInputError, ValidationAppError
from app.db import models
from app.db.database import SessionLocal
from app.db.repositories import AuditRepository
from app.pipeline import adapter
from app.services import calculation_service
from app.services.file_service import list_project_files

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Validation (spec section 56) -- checks inputs/files/dependencies WITHOUT
# calling the pipeline. Warnings from the real calculation are surfaced,
# never suppressed.
# --------------------------------------------------------------------------
def validate_project(project: models.Project) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    if project.inputs is None:
        errors.append("Engineering inputs have not been submitted (POST /inputs).")
    boundary_files = [f for f in project.files if f.file_type == models.FileType.BOUNDARY]
    if not boundary_files:
        errors.append("No boundary CSV has been uploaded.")

    if project.inputs is not None:
        try:
            preview = calculation_service.compute_calculation_preview(project.inputs)
            warnings.extend(preview.get("warnings", []))
        except (MissingInputError, ValidationAppError) as exc:
            errors.append(str(exc))
        except ValueError as exc:
            errors.append(str(exc))

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


# --------------------------------------------------------------------------
# Calculation preview (spec section 57)
# --------------------------------------------------------------------------
def run_calculation_preview(db: Session, project: models.Project) -> dict:
    inputs = project.inputs
    if inputs is None:
        raise MissingInputError("Submit engineering inputs before requesting a calculation preview.")

    AuditRepository(db).log(models.AuditAction.CALCULATION_STARTED, project_id=project.id, user_id=project.user_id)
    project.status = models.ProjectStatus.CALCULATING
    db.add(project)
    db.commit()

    try:
        preview = calculation_service.compute_calculation_preview(inputs)
    except Exception:
        project.status = models.ProjectStatus.INPUTS_READY
        db.add(project)
        db.commit()
        raise

    result = models.CalculationResult(
        project_id=project.id,
        theoretical_result=preview,
        actual_result=None,
        grouping_result=preview.get("grouping"),
        capacity_result=preview.get("capacity"),
        warnings=preview.get("warnings", []),
    )
    db.add(result)
    project.status = models.ProjectStatus.INPUTS_READY
    db.add(project)
    db.commit()
    db.refresh(result)

    AuditRepository(db).log(
        models.AuditAction.CALCULATION_COMPLETED, project_id=project.id, user_id=project.user_id
    )
    return preview


# --------------------------------------------------------------------------
# Generation (spec sections 39, 58) -- runs in a background task for the
# first implementation (structured so a Celery/RQ worker can replace the
# `background_runner` call below without touching route/service contracts).
# --------------------------------------------------------------------------
def create_job(db: Session, project: models.Project) -> models.Job:
    job = models.Job(project_id=project.id, status=models.JobStatus.QUEUED)
    db.add(job)
    project.status = models.ProjectStatus.GENERATING
    db.add(project)
    db.commit()
    db.refresh(job)
    AuditRepository(db).log(
        models.AuditAction.LAYOUT_GENERATION_STARTED,
        project_id=project.id,
        user_id=project.user_id,
        job_id=job.id,
    )
    return job


def get_job_by_uuid(db: Session, job_uuid: str) -> models.Job | None:
    from sqlalchemy import select

    return db.execute(select(models.Job).where(models.Job.uuid == job_uuid)).scalar_one_or_none()


def background_runner(job_id: int, project_id: int) -> None:
    """
    Entry point for FastAPI's BackgroundTasks. Opens its own DB session
    (the request's session is closed by the time this runs) -- this is
    exactly the seam a Celery task would replace: swap this function's body
    for `execute_generation_job.delay(job_id, project_id)` and nothing else
    in the codebase needs to change.
    """
    db = SessionLocal()
    try:
        _execute(db, job_id, project_id)
    finally:
        db.close()


def _execute(db: Session, job_id: int, project_id: int) -> None:
    job = db.get(models.Job, job_id)
    project = db.get(models.Project, project_id)
    if job is None or project is None:
        return

    job.status = models.JobStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    db.add(job)
    db.commit()

    try:
        inputs = project.inputs
        if inputs is None:
            raise MissingInputError("Project inputs are missing.")

        boundary_paths = [f.storage_path for f in list_project_files(db, project, models.FileType.BOUNDARY)]
        control_room_paths = [
            f.storage_path for f in list_project_files(db, project, models.FileType.CONTROL_ROOM)
        ]
        inverter_room_paths = [
            f.storage_path for f in list_project_files(db, project, models.FileType.INVERTER_ROOM)
        ]
        private_area_paths = [
            f.storage_path for f in list_project_files(db, project, models.FileType.PRIVATE_AREA)
        ]

        output_dir = settings.output_path / f"project_{project.uuid}" / f"job_{job.uuid}"
        config = adapter.build_pipeline_config(
            project=project,
            inputs=inputs,
            boundary_paths=boundary_paths,
            control_room_paths=control_room_paths,
            inverter_room_paths=inverter_room_paths,
            private_area_paths=private_area_paths,
            output_dir=output_dir,
        )

        logger.info(
            "generation_started",
            extra={
                "job_id": job.uuid,
                "project_id": project.uuid,
                "boundary_files": len(boundary_paths),
                "exclusion_files": len(control_room_paths) + len(inverter_room_paths) + len(private_area_paths),
            },
        )

        normalized = adapter.run_generation(config)

        # Register ONLY the generated DXF as a downloadable, ownership-checked
        # file (spec sections 33/34/52 -- never a raw filesystem path handed
        # to the client). DWG generation itself is untouched -- the real
        # pipeline still attempts it exactly as before when configured to --
        # but it is deliberately not persisted as a downloadable file_id, per
        # the "download only dxf" requirement. dwg_export_message (below)
        # still tells the caller whether/why a DWG was or wasn't produced.
        dxf_path_str = normalized.get("dxf_path")
        if dxf_path_str:
            dxf_path = Path(dxf_path_str)
            if dxf_path.exists():
                db.add(
                    models.ProjectFile(
                        project_id=project.id,
                        file_type=models.FileType.DXF,
                        original_filename=dxf_path.name,
                        stored_filename=dxf_path.name,
                        storage_path=str(dxf_path),
                        mime_type="application/dxf",
                        file_size=dxf_path.stat().st_size,
                        checksum="",
                    )
                )

        result_record = models.CalculationResult(
            project_id=project.id,
            theoretical_result={"summary": normalized.get("theoretical_summary", [])},
            actual_result={
                "summary": normalized.get("actual_layout_summary", []),
                "table_count": normalized.get("table_count"),
                "module_count": normalized.get("module_count"),
                "actual_dc_mwp": normalized.get("actual_dc_mwp"),
                "land_area_acres": normalized.get("land_area_acres"),
            },
            grouping_result=None,
            capacity_result={
                "ac_capacity_mw": normalized.get("ac_capacity_mw"),
                "dc_ac_ratio": normalized.get("dc_ac_ratio"),
                "dc_ac_oversizing_percent": normalized.get("dc_ac_oversizing_percent"),
                "target_dc_mwp": normalized.get("target_dc_mwp"),
            },
            warnings=normalized.get("warnings", []),
        )
        db.add(result_record)

        job.status = models.JobStatus.COMPLETED
        job.progress = 100
        # job.result is returned verbatim by GET /jobs/{job_id} -- strip raw
        # filesystem paths before persisting it (spec 52: never expose
        # internal file paths). Use GET /outputs for the downloadable
        # file_id/download_url instead; dxf_available/dwg_available are
        # just booleans, and dwg_export_message stays since it's
        # human-readable text, not a path.
        public_result = dict(normalized)
        public_result["dxf_available"] = bool(public_result.pop("dxf_path", None))
        public_result["dwg_available"] = bool(public_result.pop("dwg_path", None))
        job.result = public_result
        job.completed_at = datetime.now(timezone.utc)
        project.status = models.ProjectStatus.COMPLETED
        db.add(job)
        db.add(project)
        db.commit()

        AuditRepository(db).log(
            models.AuditAction.LAYOUT_GENERATION_COMPLETED,
            project_id=project.id,
            user_id=project.user_id,
            job_id=job.id,
        )
        logger.info("generation_completed", extra={"job_id": job.uuid, "project_id": project.uuid})

    except Exception as exc:  # noqa: BLE001 -- job failure must never crash the worker
        db.rollback()
        job = db.get(models.Job, job_id)
        project = db.get(models.Project, project_id)
        if job is not None:
            job.status = models.JobStatus.FAILED
            # Safe message only -- no stack trace leaks to the API (spec 26/35).
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            db.add(job)
        if project is not None:
            project.status = models.ProjectStatus.FAILED
            db.add(project)
        db.commit()
        AuditRepository(db).log(
            models.AuditAction.LAYOUT_GENERATION_FAILED,
            project_id=project_id,
            job_id=job_id,
            details={"error": str(exc)},
        )
        logger.exception("generation_failed", extra={"job_id": job_id, "project_id": project_id})
