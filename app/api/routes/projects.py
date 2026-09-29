from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_owned_project
from app.db import models
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate
from app.schemas.response import ApiResponse
from app.services import project_service

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", response_model=ApiResponse[ProjectOut], summary="Create a project")
def create_project(
    payload: ProjectCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    project = project_service.create_project(db, user, payload.name)
    return ApiResponse(data=ProjectOut.from_model(project))


@router.get("", response_model=ApiResponse[list[ProjectOut]], summary="List my projects")
def list_projects(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    projects = project_service.list_projects(db, user)
    return ApiResponse(data=[ProjectOut.from_model(p) for p in projects])


@router.get("/{project_id}", response_model=ApiResponse[ProjectOut], summary="Get a project")
def get_project(project: models.Project = Depends(get_owned_project)):
    return ApiResponse(data=ProjectOut.from_model(project))


@router.patch("/{project_id}", response_model=ApiResponse[ProjectOut], summary="Update a project")
def update_project(
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    project: models.Project = Depends(get_owned_project),
):
    updated = project_service.update_project(db, project, payload.name, payload.status)
    return ApiResponse(data=ProjectOut.from_model(updated))


@router.delete("/{project_id}", response_model=ApiResponse[None], summary="Delete a project")
def delete_project(db: Session = Depends(get_db), project: models.Project = Depends(get_owned_project)):
    project_service.delete_project(db, project)
    return ApiResponse(data=None, message="Project deleted.")
