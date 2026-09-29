from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[models.User]:
        return self.db.get(models.User, user_id)

    def get_by_email(self, email: str) -> Optional[models.User]:
        return self.db.execute(select(models.User).where(models.User.email == email)).scalar_one_or_none()

    def create(self, email: str, password_hash: str) -> models.User:
        user = models.User(email=email, password_hash=password_hash)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user


class ProjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: int, name: str) -> models.Project:
        project = models.Project(user_id=user_id, name=name)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def get_by_uuid(self, project_uuid: str) -> Optional[models.Project]:
        return self.db.execute(
            select(models.Project).where(models.Project.uuid == project_uuid)
        ).scalar_one_or_none()

    def list_for_user(self, user_id: int) -> list[models.Project]:
        return list(
            self.db.execute(
                select(models.Project).where(models.Project.user_id == user_id).order_by(models.Project.id.desc())
            ).scalars()
        )

    def delete(self, project: models.Project) -> None:
        self.db.delete(project)
        self.db.commit()

    def save(self, project: models.Project) -> models.Project:
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project


class AuditRepository:
    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        action: models.AuditAction,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None,
        job_id: Optional[int] = None,
        details: Optional[dict] = None,
    ) -> models.AuditLog:
        entry = models.AuditLog(
            action=action, user_id=user_id, project_id=project_id, job_id=job_id, details=details or {}
        )
        self.db.add(entry)
        self.db.commit()
        return entry
