from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.db.models import JobStatus


class GenerateAcceptedOut(BaseModel):
    job_id: str
    status: JobStatus


class JobOut(BaseModel):
    job_id: str
    status: JobStatus
    progress: int
    result: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    @classmethod
    def from_model(cls, job) -> "JobOut":
        return cls(
            job_id=job.uuid,
            status=job.status,
            progress=job.progress,
            result=job.result,
            error_message=job.error_message,
            started_at=job.started_at,
            completed_at=job.completed_at,
            created_at=job.created_at,
        )


class ValidationResultOut(BaseModel):
    valid: bool
    errors: list[str] = []
    warnings: list[str] = []
