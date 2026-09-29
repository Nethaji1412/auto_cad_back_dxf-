from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import ProjectStatus


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: ProjectStatus | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str = Field(description="Project UUID (never the internal integer id)")
    name: str
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, project) -> "ProjectOut":
        return cls(
            id=project.uuid,
            name=project.name,
            status=project.status,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
