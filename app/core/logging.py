from __future__ import annotations

import logging
import sys

_CONFIGURED = False

# Field names that must never be emitted to logs even if accidentally passed
# into `extra=`. Enforced defensively in addition to callers just not doing it.
_FORBIDDEN_KEYS = {"password", "password_hash", "token", "jwt", "secret", "database_url"}


class _RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for key in list(getattr(record, "__dict__", {}).keys()):
            if key.lower() in _FORBIDDEN_KEYS:
                record.__dict__[key] = "***REDACTED***"
        return True


def configure_logging(debug: bool = False) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    level = logging.DEBUG if debug else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    handler.addFilter(_RedactingFilter())
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def audit_logger() -> logging.Logger:
    return logging.getLogger("audit")
