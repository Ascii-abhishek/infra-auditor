"""Versioned snapshot contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from infra_auditor import __version__
from infra_auditor.collectors.aws.models import RDSInstance
from infra_auditor.collectors.postgres.discovery import DatabaseInfo
from infra_auditor.models.common import CollectionGap, CollectionStatus, CollectorResult

SNAPSHOT_SCHEMA_VERSION = 1


class RunMetadata(BaseModel):
    """Audit run metadata."""

    run_id: str
    application_version: str = __version__
    snapshot_schema_version: int = SNAPSHOT_SCHEMA_VERSION
    environment: str
    region: str
    started_at: datetime
    completed_at: datetime
    status: CollectionStatus

    model_config = ConfigDict(extra="forbid")


class InstanceSnapshot(BaseModel):
    """Snapshot for one configured instance alias."""

    alias: str
    db_instance_identifier: str
    region: str
    status: CollectionStatus
    aws_instance: RDSInstance | None = None
    databases: list[DatabaseInfo] = Field(default_factory=list)
    collectors: list[CollectorResult] = Field(default_factory=list)
    gaps: list[CollectionGap] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class AuditSnapshot(BaseModel):
    """Top-level snapshot written to local JSON in V0.1."""

    metadata: RunMetadata
    instances: list[InstanceSnapshot]

    model_config = ConfigDict(extra="forbid")
