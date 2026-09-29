from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_owned_project
from app.core.exceptions import NotFoundError
from app.core.rate_limit import enforce_rate_limit
from app.db import models
from app.db.repositories import AuditRepository
from app.schemas.response import ApiResponse, FileRefOut, FileUploadOut, OutputFilesOut
from app.services.file_service import list_project_files, save_upload

router = APIRouter(prefix="/api/v1/projects/{project_id}/files", tags=["files"])
outputs_router = APIRouter(prefix="/api/v1/projects/{project_id}/outputs", tags=["outputs"])


def _to_ref(f: models.ProjectFile, project_uuid: str) -> FileRefOut:
    return FileRefOut(
        file_id=f.uuid,
        file_type=f.file_type.value,
        original_filename=f.original_filename,
        file_size=f.file_size,
        download_url=f"/api/v1/projects/{project_uuid}/outputs/{f.uuid}",
    )


async def _handle_upload(
    request: Request,
    files: list[UploadFile],
    file_type: models.FileType,
    db: Session,
    project: models.Project,
) -> FileUploadOut:
    enforce_rate_limit(request, "file_upload", max_requests=30, window_seconds=60)
    saved = []
    for upload in files:
        record = await save_upload(db, project, upload, file_type)
        saved.append(_to_ref(record, project.uuid))
        AuditRepository(db).log(
            models.AuditAction.FILE_UPLOADED,
            project_id=project.id,
            user_id=project.user_id,
            details={"file_type": file_type.value, "filename": record.original_filename},
        )
    return FileUploadOut(uploaded=saved)


@router.post("/boundary", response_model=ApiResponse[FileUploadOut], summary="Upload boundary CSV(s)")
async def upload_boundary(
    request: Request,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    project: models.Project = Depends(get_owned_project),
):
    out = await _handle_upload(request, files, models.FileType.BOUNDARY, db, project)
    return ApiResponse(data=out)


@router.post("/control-room", response_model=ApiResponse[FileUploadOut], summary="Upload control-room CSV(s)")
async def upload_control_room(
    request: Request,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    project: models.Project = Depends(get_owned_project),
):
    out = await _handle_upload(request, files, models.FileType.CONTROL_ROOM, db, project)
    return ApiResponse(data=out)


@router.post("/inverter-room", response_model=ApiResponse[FileUploadOut], summary="Upload inverter-room CSV(s)")
async def upload_inverter_room(
    request: Request,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    project: models.Project = Depends(get_owned_project),
):
    out = await _handle_upload(request, files, models.FileType.INVERTER_ROOM, db, project)
    return ApiResponse(data=out)


@router.post("/private-area", response_model=ApiResponse[FileUploadOut], summary="Upload private-area CSV(s)")
async def upload_private_area(
    request: Request,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    project: models.Project = Depends(get_owned_project),
):
    out = await _handle_upload(request, files, models.FileType.PRIVATE_AREA, db, project)
    return ApiResponse(data=out)


@outputs_router.get("", response_model=ApiResponse[OutputFilesOut], summary="List output files (DXF only)")
def list_outputs(db: Session = Depends(get_db), project: models.Project = Depends(get_owned_project)):
    # DXF only, by design -- see download_output()'s docstring.
    dxf = list_project_files(db, project, models.FileType.DXF)
    refs = [_to_ref(f, project.uuid) for f in dxf]
    return ApiResponse(data=OutputFilesOut(files=refs))


@outputs_router.get("/{file_id}", summary="Download the generated DXF by its logical file_id")
def download_output(
    file_id: str,
    db: Session = Depends(get_db),
    project: models.Project = Depends(get_owned_project),
    user: models.User = Depends(get_current_user),
):
    """
    Serves ONLY generated DXF output -- not DWG, and not any of the
    uploaded input CSVs (boundary/control-room/inverter-room/private-area),
    even though those share the same project_files table. Restricting the
    file_type here (not just in list_outputs) matters: without it, a
    caller who already has an upload's file_id (returned by the upload
    endpoints themselves) could fetch it back through this endpoint too --
    harmless confidentiality-wise since it's the caller's own upload, but
    not the intended contract, and it would also let a DWG slip through if
    one were ever produced. DWG generation itself is untouched (still
    attempted by the real pipeline when configured) -- it's just never
    persisted as a downloadable file_id; see layout_service._execute().
    """
    record = db.execute(
        select(models.ProjectFile).where(
            models.ProjectFile.uuid == file_id,
            models.ProjectFile.project_id == project.id,
            models.ProjectFile.file_type == models.FileType.DXF,
        )
    ).scalar_one_or_none()
    if record is None:
        raise NotFoundError("DXF file not found.")

    AuditRepository(db).log(
        models.AuditAction.FILE_DOWNLOADED,
        project_id=project.id,
        user_id=user.id,
        details={"file_id": file_id, "file_type": record.file_type.value},
    )
    return FileResponse(
        path=record.storage_path,
        filename=record.original_filename,
        media_type=record.mime_type,
    )
