from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.rate_limit import enforce_rate_limit
from app.core.security import create_access_token, hash_password, verify_password
from app.db import models
from app.db.repositories import UserRepository
from app.schemas.auth import TokenResponse, UserLogin, UserOut, UserRegister
from app.schemas.response import ApiResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=ApiResponse[UserOut], summary="Register a new user")
def register(payload: UserRegister, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request, "auth_register", max_requests=5, window_seconds=60)

    repo = UserRepository(db)
    if repo.get_by_email(payload.email) is not None:
        raise ConflictError("An account with this email already exists.")

    user = repo.create(email=payload.email, password_hash=hash_password(payload.password))
    return ApiResponse(data=UserOut.model_validate(user), message="Registered.")


@router.post("/login", response_model=TokenResponse, summary="Log in and obtain a JWT")
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request, "auth_login", max_requests=10, window_seconds=60)

    repo = UserRepository(db)
    user = repo.get_by_email(payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AuthenticationError("Incorrect email or password.")
    if not user.is_active:
        raise AuthenticationError("This account is inactive.")

    token = create_access_token(subject=user.email, user_id=user.id)
    return TokenResponse(
        access_token=token,
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=ApiResponse[UserOut], summary="Get the current authenticated user")
def me(user: models.User = Depends(get_current_user)):
    return ApiResponse(data=UserOut.model_validate(user))
