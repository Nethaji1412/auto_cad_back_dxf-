from __future__ import annotations

from sqlalchemy.orm import Session

from app.db import models
from app.schemas.inputs import ProjectInputsRequest


def save_inputs(db: Session, project: models.Project, payload: ProjectInputsRequest) -> models.ProjectInput:
    existing = project.inputs
    data = dict(
        module_config=payload.module.model_dump(),
        table_config=payload.table.model_dump(),
        layout_config=payload.layout.model_dump(),
        electrical_config=payload.electrical.model_dump(mode="json"),
        service_road_config=payload.service_road.model_dump(),
        dxf_config=payload.dxf.model_dump(),
    )

    if existing is None:
        existing = models.ProjectInput(project_id=project.id, **data)
        db.add(existing)
    else:
        for key, value in data.items():
            setattr(existing, key, value)

    if project.status == models.ProjectStatus.DRAFT:
        project.status = models.ProjectStatus.INPUTS_READY
    db.add(project)
    db.commit()
    db.refresh(existing)
    return existing


def get_inputs(project: models.Project) -> models.ProjectInput | None:
    return project.inputs
