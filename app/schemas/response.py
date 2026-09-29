from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail


class FileRefOut(BaseModel):
    """Logical file identifier only -- never a filesystem path
    (spec section 52)."""
    file_id: str
    file_type: str
    original_filename: str
    file_size: int
    download_url: str


class FileUploadOut(BaseModel):
    uploaded: list[FileRefOut]


class OutputFilesOut(BaseModel):
    files: list[FileRefOut]
