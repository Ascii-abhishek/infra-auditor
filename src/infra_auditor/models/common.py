"""Common model primitives."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class CollectionStatus(StrEnum):
    """Status values used by collectors and snapshots."""

    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class CollectionGap(BaseModel):
    """Structured error or capability gap captured as audit evidence."""

    collector: str
    resource: str
    status: CollectionStatus = CollectionStatus.FAILED
    error_type: str
    message: str

    model_config = ConfigDict(extra="forbid")


class CollectorResult(BaseModel):
    """Execution metadata for a meaningful collector boundary."""

    name: str
    status: CollectionStatus
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    summary: str | None = None

    model_config = ConfigDict(extra="forbid")
