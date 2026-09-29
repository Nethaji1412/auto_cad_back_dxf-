from __future__ import annotations

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, AuthorizationError, NotFoundError
from app.core.security import decode_access_token
from app.db import models
from app.db.database import get_db
from app.db.repositories import ProjectRepository, UserRepository

# Plain JWT bearer auth -- not an OAuth2 flow (no scopes, no token endpoint
# conventions, no client credentials), so HTTPBearer is the correct scheme
# rather than OAuth2PasswordBearer. Swagger's "Authorize" dialog shows a
# single token field instead of a username/password form, which matches
# how this API is actually used: POST /auth/login once, then paste the
# returned access_token here.
bearer_scheme = HTTPBearer(auto_error=False, description="Paste the JWT from POST /auth/login.")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    if not credentials or not credentials.credentials:
        raise AuthenticationError("Not authenticated. Provide a Bearer token.")
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise AuthenticationError(str(exc)) from exc

    user_id = payload.get("user_id")
    user = UserRepository(db).get_by_id(user_id) if user_id is not None else None
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive.")
    return user


def get_current_active_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if not user.is_admin:
        raise AuthorizationError("Admin privileges required.")
    return user


def get_owned_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.Project:
    """
    Resolves {project_id} (a UUID, never the internal integer id) and
    enforces ownership -- spec section 24: NEVER rely only on the URL
    parameter, always check project.user_id == authenticated_user.id.
    Admins may access any project.
    """
    project = ProjectRepository(db).get_by_uuid(project_id)
    if project is None:
        raise NotFoundError("Project not found.")
    if project.user_id != user.id and not user.is_admin:
        raise AuthorizationError("You do not have access to this project.")
    return project
