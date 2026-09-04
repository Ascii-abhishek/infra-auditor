"""Split raw snapshot artifact contracts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from infra_auditor.collectors.aws.cloudwatch_metrics import RDSCloudWatchMetricsEvidence
from infra_auditor.collectors.aws.models import RDSInstance
from infra_auditor.collectors.aws.network import RDSSecurityGroupEvidence
from infra_auditor.collectors.aws.rds_operations import RDSOperationsEvidence
from infra_auditor.collectors.postgres.activity import PostgresActivityEvidence
from infra_auditor.collectors.postgres.discovery import DatabaseInfo
from infra_auditor.collectors.postgres.role_security import PostgresRoleSecurityEvidence
from infra_auditor.models.common import CollectionGap, CollectionStatus, CollectorResult
from infra_auditor.models.finding import Finding
from infra_auditor.models.snapshot import AuditSnapshot, InstanceSnapshot

SNAPSHOT_SPLIT_ARTIFACT_SCHEMA_VERSION = 1
DEFAULT_SOURCE_SNAPSHOT_SERVICE = "rds-postgres"


class SnapshotSplitService(StrEnum):
    """Service/category partitions for split raw snapshot artifacts."""

    RDS = "rds"
    POSTGRES = "postgres"
    AUDIT_HEURISTICS = "audit-heuristics"


class SnapshotSplitSubservice(StrEnum):
    """Subservice partitions inside a split raw snapshot service."""

    RDS_INSTANCE = "instance"
    RDS_OPERATIONS = "operations"
    POSTGRES_DATABASE_INVENTORY = "database-inventory"
    POSTGRES_ACTIVITY_SUMMARY = "activity-summary"
    POSTGRES_ROLE_SECURITY = "role-security"
    RDS_EC2_SECURITY_GROUPS = "ec2-security-groups"
    RDS_CLOUDWATCH_METRICS = "cloudwatch-rds-metrics"
    AUDIT_DETERMINISTIC_FINDINGS = "deterministic-findings"


class SnapshotSplitBoundary(StrEnum):
    """Stable collector boundary represented by a split artifact."""

    RDS_INSTANCE = "rds-instance"
    RDS_OPERATIONS = "rds-operations"
    POSTGRES_DATABASE_INVENTORY = "postgres-database-inventory"
    POSTGRES_ACTIVITY_SUMMARY = "postgres-activity-summary"
    POSTGRES_ROLE_SECURITY = "postgres-role-security"
    RDS_EC2_SECURITY_GROUPS = "rds-attached-security-group-ingress"
    RDS_CLOUDWATCH_METRICS = "rds-cloudwatch-metrics"
    DETERMINISTIC_FINDINGS = "deterministic-findings"


@dataclass(frozen=True)
class SnapshotSplitDefinition:
    """A stable service/subservice collector boundary."""

    service: SnapshotSplitService
    subservice: SnapshotSplitSubservice
    collector_boundary: SnapshotSplitBoundary
    collector_names: frozenset[str]


SNAPSHOT_SPLIT_DEFINITIONS = (
    SnapshotSplitDefinition(
        service=SnapshotSplitService.RDS,
        subservice=SnapshotSplitSubservice.RDS_INSTANCE,
        collector_boundary=SnapshotSplitBoundary.RDS_INSTANCE,
        collector_names=frozenset({"aws.rds.describe_db_instances"}),
    ),
    SnapshotSplitDefinition(
        service=SnapshotSplitService.RDS,
        subservice=SnapshotSplitSubservice.RDS_OPERATIONS,
        collector_boundary=SnapshotSplitBoundary.RDS_OPERATIONS,
        collector_names=frozenset({"aws.rds.operations"}),
    ),
    SnapshotSplitDefinition(
        service=SnapshotSplitService.POSTGRES,
        subservice=SnapshotSplitSubservice.POSTGRES_DATABASE_INVENTORY,
        collector_boundary=SnapshotSplitBoundary.POSTGRES_DATABASE_INVENTORY,
        collector_names=frozenset({"postgres.database_inventory"}),
    ),
    SnapshotSplitDefinition(
        service=SnapshotSplitService.POSTGRES,
        subservice=SnapshotSplitSubservice.POSTGRES_ACTIVITY_SUMMARY,
        collector_boundary=SnapshotSplitBoundary.POSTGRES_ACTIVITY_SUMMARY,
        collector_names=frozenset({"postgres.activity_summary"}),
    ),
    SnapshotSplitDefinition(
        service=SnapshotSplitService.POSTGRES,
        subservice=SnapshotSplitSubservice.POSTGRES_ROLE_SECURITY,
        collector_boundary=SnapshotSplitBoundary.POSTGRES_ROLE_SECURITY,
        collector_names=frozenset({"postgres.role_security"}),
    ),
    SnapshotSplitDefinition(
        service=SnapshotSplitService.RDS,
        subservice=SnapshotSplitSubservice.RDS_EC2_SECURITY_GROUPS,
        collector_boundary=SnapshotSplitBoundary.RDS_EC2_SECURITY_GROUPS,
        collector_names=frozenset({"aws.ec2.security_group_ingress"}),
    ),
    SnapshotSplitDefinition(
        service=SnapshotSplitService.RDS,
        subservice=SnapshotSplitSubservice.RDS_CLOUDWATCH_METRICS,
        collector_boundary=SnapshotSplitBoundary.RDS_CLOUDWATCH_METRICS,
        collector_names=frozenset({"aws.cloudwatch.rds_metrics"}),
    ),
    SnapshotSplitDefinition(
        service=SnapshotSplitService.AUDIT_HEURISTICS,
        subservice=SnapshotSplitSubservice.AUDIT_DETERMINISTIC_FINDINGS,
        collector_boundary=SnapshotSplitBoundary.DETERMINISTIC_FINDINGS,
        collector_names=frozenset({"rules.deterministic_findings"}),
    ),
)

SNAPSHOT_SPLIT_DEFINITIONS_BY_KEY = {
    (definition.service, definition.subservice): definition
    for definition in SNAPSHOT_SPLIT_DEFINITIONS
}
SPLIT_SERVICE_SUBSERVICES: dict[SnapshotSplitService, tuple[SnapshotSplitSubservice, ...]] = {
    service: tuple(
        definition.subservice
        for definition in SNAPSHOT_SPLIT_DEFINITIONS
        if definition.service == service
    )
    for service in SnapshotSplitService
}


class SnapshotSplitMetadata(BaseModel):
    """Metadata for a split raw snapshot artifact."""

    artifact_schema_version: int = SNAPSHOT_SPLIT_ARTIFACT_SCHEMA_VERSION
    source_snapshot_schema_version: int
    source_service: str = DEFAULT_SOURCE_SNAPSHOT_SERVICE
    service: SnapshotSplitService
    subservice: SnapshotSplitSubservice
    collector_boundary: SnapshotSplitBoundary
    run_id: str
    application_version: str
    environment: str
    region: str
    started_at: datetime
    completed_at: datetime
    source_snapshot_status: CollectionStatus
    source_instance_status: CollectionStatus
    status: CollectionStatus
    instance_alias: str
    db_instance_identifier: str
    collector_names: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class SnapshotSplitInstance(BaseModel):
    """One instance's evidence constrained to a split collector boundary."""

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


class SnapshotSplitArtifact(BaseModel):
    """A raw snapshot slice persisted alongside the compatibility snapshot."""

    metadata: SnapshotSplitMetadata
    instance: SnapshotSplitInstance

    model_config = ConfigDict(extra="forbid")


def build_snapshot_split_artifacts(
    snapshot: AuditSnapshot,
    *,
    source_service: str = DEFAULT_SOURCE_SNAPSHOT_SERVICE,
) -> list[SnapshotSplitArtifact]:
    """Build raw split artifacts from a full compatibility snapshot."""

    artifacts: list[SnapshotSplitArtifact] = []
    for instance in snapshot.instances:
        for definition in SNAPSHOT_SPLIT_DEFINITIONS:
            artifacts.append(
                _build_artifact(
                    snapshot=snapshot,
                    instance=instance,
                    source_service=source_service,
                    definition=definition,
                )
            )
    return artifacts


def split_definition_for(
    service: SnapshotSplitService,
    subservice: SnapshotSplitSubservice,
) -> SnapshotSplitDefinition:
    """Return the approved split definition for one service/subservice pair."""

    return SNAPSHOT_SPLIT_DEFINITIONS_BY_KEY[(service, subservice)]


def _build_artifact(
    *,
    snapshot: AuditSnapshot,
    instance: InstanceSnapshot,
    source_service: str,
    definition: SnapshotSplitDefinition,
) -> SnapshotSplitArtifact:
    collectors = _collectors_for(instance, definition.collector_names)
    gaps = _gaps_for(instance, definition.collector_names)
    status = _boundary_status(collectors)
    split_instance = SnapshotSplitInstance(
        alias=instance.alias,
        db_instance_identifier=instance.db_instance_identifier,
        region=instance.region,
        status=status,
        collectors=collectors,
        gaps=gaps,
    )
    split_instance = _attach_boundary_evidence(
        split_instance=split_instance,
        instance=instance,
        definition=definition,
    )
    return SnapshotSplitArtifact(
        metadata=_metadata(
            snapshot=snapshot,
            instance=instance,
            source_service=source_service,
            definition=definition,
            status=status,
        ),
        instance=split_instance,
    )


def _attach_boundary_evidence(
    *,
    split_instance: SnapshotSplitInstance,
    instance: InstanceSnapshot,
    definition: SnapshotSplitDefinition,
) -> SnapshotSplitInstance:
    if definition.collector_boundary == SnapshotSplitBoundary.RDS_INSTANCE:
        return split_instance.model_copy(update={"aws_instance": instance.aws_instance})
    if definition.collector_boundary == SnapshotSplitBoundary.RDS_OPERATIONS:
        return split_instance.model_copy(update={"rds_operations": instance.rds_operations})
    if definition.collector_boundary == SnapshotSplitBoundary.POSTGRES_DATABASE_INVENTORY:
        return split_instance.model_copy(update={"databases": instance.databases})
    if definition.collector_boundary == SnapshotSplitBoundary.POSTGRES_ACTIVITY_SUMMARY:
        return split_instance.model_copy(update={"postgres_activity": instance.postgres_activity})
    if definition.collector_boundary == SnapshotSplitBoundary.POSTGRES_ROLE_SECURITY:
        return split_instance.model_copy(
            update={"postgres_role_security": instance.postgres_role_security}
        )
    if definition.collector_boundary == SnapshotSplitBoundary.RDS_EC2_SECURITY_GROUPS:
        return split_instance.model_copy(
            update={"aws_security_groups": instance.aws_security_groups}
        )
    if definition.collector_boundary == SnapshotSplitBoundary.RDS_CLOUDWATCH_METRICS:
        return split_instance.model_copy(update={"cloudwatch_metrics": instance.cloudwatch_metrics})
    if definition.collector_boundary == SnapshotSplitBoundary.DETERMINISTIC_FINDINGS:
        return split_instance.model_copy(update={"findings": instance.findings})
    return split_instance


def _metadata(
    *,
    snapshot: AuditSnapshot,
    instance: InstanceSnapshot,
    source_service: str,
    definition: SnapshotSplitDefinition,
    status: CollectionStatus,
) -> SnapshotSplitMetadata:
    return SnapshotSplitMetadata(
        source_snapshot_schema_version=snapshot.metadata.snapshot_schema_version,
        source_service=source_service,
        service=definition.service,
        subservice=definition.subservice,
        collector_boundary=definition.collector_boundary,
        run_id=snapshot.metadata.run_id,
        application_version=snapshot.metadata.application_version,
        environment=snapshot.metadata.environment,
        region=snapshot.metadata.region,
        started_at=snapshot.metadata.started_at,
        completed_at=snapshot.metadata.completed_at,
        source_snapshot_status=snapshot.metadata.status,
        source_instance_status=instance.status,
        status=status,
        instance_alias=instance.alias,
        db_instance_identifier=instance.db_instance_identifier,
        collector_names=sorted(definition.collector_names),
    )


def _collectors_for(
    instance: InstanceSnapshot,
    collector_names: frozenset[str],
) -> list[CollectorResult]:
    return [collector for collector in instance.collectors if collector.name in collector_names]


def _gaps_for(instance: InstanceSnapshot, collector_names: frozenset[str]) -> list[CollectionGap]:
    return [gap for gap in instance.gaps if gap.collector in collector_names]


def _boundary_status(collectors: list[CollectorResult]) -> CollectionStatus:
    if not collectors:
        return CollectionStatus.SKIPPED
    statuses = {collector.status for collector in collectors}
    if CollectionStatus.FAILED in statuses:
        if statuses == {CollectionStatus.FAILED}:
            return CollectionStatus.FAILED
        return CollectionStatus.PARTIAL_SUCCESS
    if CollectionStatus.SKIPPED in statuses:
        if statuses == {CollectionStatus.SKIPPED}:
            return CollectionStatus.SKIPPED
        return CollectionStatus.PARTIAL_SUCCESS
    return CollectionStatus.SUCCESS
