"""Versioned snapshot contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from infra_auditor import __version__
from infra_auditor.collectors.aws.cloudwatch_metrics import RDSCloudWatchMetricsEvidence
from infra_auditor.collectors.aws.models import RDSInstance
from infra_auditor.collectors.aws.network import RDSSecurityGroupEvidence
from infra_auditor.collectors.aws.rds_operations import RDSOperationsEvidence
from infra_auditor.collectors.postgres.activity import PostgresActivityEvidence
from infra_auditor.collectors.postgres.discovery import DatabaseInfo
from infra_auditor.collectors.postgres.role_security import PostgresRoleSecurityEvidence
from infra_auditor.models.common import CollectionGap, CollectionStatus, CollectorResult
from infra_auditor.models.finding import Finding

SNAPSHOT_SCHEMA_VERSION: Literal[3] = 3


class RunMetadata(BaseModel):
    """Audit run metadata."""

    run_id: str
    application_version: str = __version__
    snapshot_schema_version: Literal[3] = SNAPSHOT_SCHEMA_VERSION
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
    aws_security_groups: RDSSecurityGroupEvidence | None = None
    cloudwatch_metrics: RDSCloudWatchMetricsEvidence | None = None
    rds_operations: RDSOperationsEvidence | None = None
    databases: list[DatabaseInfo] = Field(default_factory=list)
    postgres_activity: PostgresActivityEvidence | None = None
    postgres_role_security: PostgresRoleSecurityEvidence | None = None
    collectors: list[CollectorResult] = Field(default_factory=list)
    gaps: list[CollectionGap] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class AuditSnapshot(BaseModel):
    """Top-level snapshot persisted as raw JSON."""

    metadata: RunMetadata
    instances: list[InstanceSnapshot]

    model_config = ConfigDict(extra="forbid")
