"""Structured local logging with secret redaction."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping


SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "authorization",
    "cookie",
    "database_url",
)

SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|AUTHORIZATION|COOKIE|DATABASE_URL))\s*=\s*([^,\s]+)"
)


class JsonLogFormatter(logging.Formatter):
    """Format log records as compact JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_value(record.getMessage()),
        }

        extra = getattr(record, "extra", None)
        if isinstance(extra, Mapping):
            payload["extra"] = redact_value(dict(extra))

        if record.exc_info:
            payload["exception"] = redact_value(self.formatException(record.exc_info))

        return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def configure_logging(
    *,
    level: str = "INFO",
    log_file: str | Path | None = None,
    include_stream: bool = True,
) -> None:
    """Configure root logging for local operation."""

    handlers: list[logging.Handler] = []
    formatter = JsonLogFormatter()

    if include_stream:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        handlers.append(stream_handler)

    if log_file is not None:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=handlers,
        force=True,
    )


def redact_value(value: Any) -> Any:
    """Redact sensitive values in mappings, lists and strings."""

    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in SENSITIVE_KEY_PARTS):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = redact_value(item)
        return redacted
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, str):
        return SENSITIVE_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    return value
