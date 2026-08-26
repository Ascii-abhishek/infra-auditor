"""Structured logging setup with conservative redaction."""

import logging as stdlib_logging
import sys
from collections.abc import Mapping, Sequence
from typing import Any

import structlog
from structlog.typing import EventDict, WrappedLogger

from infra_auditor.config import LogFormat

SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "access_key",
    "connection_uri",
    "connection_string",
    "dsn",
)


def _is_sensitive_key(key: object) -> bool:
    return any(part in str(key).lower() for part in SENSITIVE_KEY_PARTS)


def redact_value(value: Any) -> Any:
    """Redact known sensitive values from nested logging payloads."""

    if isinstance(value, Mapping):
        return {
            key: "[REDACTED]" if _is_sensitive_key(key) else redact_value(child)
            for key, child in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [redact_value(child) for child in value]
    return value


def redact_sensitive(_logger: WrappedLogger, _method_name: str, event_dict: EventDict) -> EventDict:
    redacted = redact_value(event_dict)
    if isinstance(redacted, dict):
        return redacted
    return {"event": redacted}


def configure_logging(level: str, log_format: LogFormat) -> None:
    """Configure structlog for local console output or production JSON."""

    stdlib_logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(stdlib_logging, level.upper()),
        force=True,
    )

    renderer: structlog.typing.Processor
    if log_format == LogFormat.JSON:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_sensitive,
            renderer,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(getattr(stdlib_logging, level.upper())),
        cache_logger_on_first_use=True,
    )
