from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db import models
from app.db.repositories import AuditRepository, ProjectRepository


def create_project(db: Session, user: models.User, name: str) -> models.Project:
    project = ProjectRepository(db).create(user_id=user.id, name=name)
    AuditRepository(db).log(models.AuditAction.PROJECT_CREATED, user_id=user.id, project_id=project.id)
    return project


def list_projects(db: Session, user: models.User) -> list[models.Project]:
    return ProjectRepository(db).list_for_user(user.id)


def update_project(db: Session, project: models.Project, name: str | None, status: models.ProjectStatus | None):
    if name is not None:
        project.name = name
    if status is not None:
        project.status = status
    return ProjectRepository(db).save(project)


def delete_project(db: Session, project: models.Project) -> None:
    ProjectRepository(db).delete(project)


def require_inputs(project: models.Project) -> models.ProjectInput:
    if project.inputs is None:
        raise NotFoundError("Project inputs have not been submitted yet. POST to /inputs first.")
    return project.inputs
