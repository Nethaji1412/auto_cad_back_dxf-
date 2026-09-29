from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ValidationAppError
from app.db import models
from existing_pipeline.csv_loader import read_labeled_coordinate_csv

# Only coordinate CSVs are accepted anywhere in this API (spec section 25).
ALLOWED_EXTENSIONS = {".csv"}
ALLOWED_MIME_TYPES = {"text/csv", "application/vnd.ms-excel", "text/plain", "application/csv"}

# Explicitly-forbidden extensions, checked in addition to (not instead of)
# the allow-list above, so the reject reason is unambiguous in logs.
FORBIDDEN_EXTENSIONS = {".exe", ".dll", ".py", ".js", ".html", ".htm", ".sh", ".bat", ".php", ".jsp"}


def _sanitized_storage_name(original_filename: str) -> tuple[str, str]:
    """Never trusts the original filename as a path. Returns
    (stored_filename, extension)."""
    suffix = Path(original_filename).suffix.lower()
    stored = f"{uuid.uuid4()}{suffix}"
    return stored, suffix


def _validate_extension(original_filename: str) -> str:
    suffix = Path(original_filename).suffix.lower()
    if suffix in FORBIDDEN_EXTENSIONS or suffix not in ALLOWED_EXTENSIONS:
        raise ValidationAppError(
            f"File type '{suffix or '(none)'}' is not allowed. Only .csv coordinate "
            "files may be uploaded.",
            details={"filename": original_filename},
        )
    return suffix


def _validate_mime(content_type: str | None, original_filename: str) -> None:
    # Extension is not trusted alone (spec 25) -- but browsers/clients are
    # notoriously inconsistent about CSV content-types, so we treat an
    # unrecognized-but-not-actively-dangerous content-type as a soft pass
    # and let the real CSV-structure validation below be the hard gate.
    if content_type and content_type not in ALLOWED_MIME_TYPES and "csv" not in content_type:
        raise ValidationAppError(
            f"Unexpected content-type '{content_type}' for {original_filename}. Expected a CSV file.",
        )


async def save_upload(
    db: Session,
    project: models.Project,
    upload: UploadFile,
    file_type: models.FileType,
) -> models.ProjectFile:
    """
    Validates and persists one uploaded coordinate CSV:
      1. extension allow-list + forbidden-extension reject
      2. soft MIME check
      3. streamed size-limit enforcement (never buffers unbounded input)
      4. UUID-based storage filename (original name is never used as a path)
      5. SHA-256 checksum
      6. real CSV structural validation via the existing, unmodified
         csv_loader.read_labeled_coordinate_csv() -- EASTING/NORTHING
         columns, >= 3 valid points, numeric coordinates
    Raises ValidationAppError on any failure; nothing partial is written
    to project_files on failure.
    """
    original_filename = upload.filename or "upload.csv"
    _validate_extension(original_filename)
    _validate_mime(upload.content_type, original_filename)

    stored_filename, _ = _sanitized_storage_name(original_filename)
    project_dir = settings.upload_path / project.uuid
    project_dir.mkdir(parents=True, exist_ok=True)
    # Path is built entirely from server-generated components (project.uuid,
    # stored_filename) -- the client-supplied filename never touches the
    # filesystem path, which is the actual path-traversal defense.
    dest_path = project_dir / stored_filename

    sha256 = hashlib.sha256()
    size = 0
    chunk_size = 1024 * 1024
    try:
        with open(dest_path, "wb") as out:
            while True:
                chunk = await upload.read(chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise ValidationAppError(
                        f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB upload limit.",
                        details={"filename": original_filename},
                    )
                sha256.update(chunk)
                out.write(chunk)

        # Real structural validation, using the ACTUAL pipeline CSV loader
        # (not a reimplementation) -- fails loudly on missing columns,
        # non-numeric coordinates, or fewer than 3 points.
        read_labeled_coordinate_csv(str(dest_path))

    except ValidationAppError:
        dest_path.unlink(missing_ok=True)
        raise
    except (ValueError, FileNotFoundError) as exc:
        dest_path.unlink(missing_ok=True)
        raise ValidationAppError(str(exc), details={"filename": original_filename}) from exc
    except Exception:
        dest_path.unlink(missing_ok=True)
        raise

    record = models.ProjectFile(
        project_id=project.id,
        file_type=file_type,
        original_filename=original_filename,
        stored_filename=stored_filename,
        storage_path=str(dest_path),
        mime_type=upload.content_type or "text/csv",
        file_size=size,
        checksum=sha256.hexdigest(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_project_files(db: Session, project: models.Project, file_type: models.FileType | None = None):
    files = project.files
    if file_type is not None:
        files = [f for f in files if f.file_type == file_type]
    return files
