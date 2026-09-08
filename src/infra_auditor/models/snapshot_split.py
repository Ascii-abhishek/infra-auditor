"""Split raw snapshot artifact contracts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from infra_auditor.capabilities import ServiceName, SubserviceName
from infra_auditor.collectors.aws.cloudwatch_metrics import RDSCloudWatchMetricsEvidence
from infra_auditor.collectors.aws.models import RDSInstance
from infra_auditor.collectors.aws.network import RDSSecurityGroupEvidence
from infra_auditor.collectors.aws.rds_operations import RDSOperationsEvidence
from infra_auditor.collectors.postgres.activity import PostgresActivityEvidence
from infra_auditor.collectors.postgres.discovery import DatabaseInfo
from infra_auditor.collectors.postgres.role_security import PostgresRoleSecurityEvidence
from infra_auditor.models.common import CollectionGap, CollectionStatus, CollectorResult
from infra_auditor.models.finding import Finding
from infra_auditor.models.snapshot import AuditSnapshot, InstanceSnapshot, RunMetadata

SnapshotSplitService = ServiceName
SnapshotSplitSubservice = SubserviceName

SNAPSHOT_SPLIT_ARTIFACT_SCHEMA_VERSION: Literal[3] = 3


class SnapshotSplitBoundary(StrEnum):
    """Stable collector boundary represented by a canonical artifact."""

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
        collector_names=frozenset({"postgres.database_inventory", "secrets.postgres_credentials"}),
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
        service=SnapshotSplitService.POSTGRES,
        subservice=SnapshotSplitSubservice.AUDIT_DETERMINISTIC_FINDINGS,
        collector_boundary=SnapshotSplitBoundary.DETERMINISTIC_FINDINGS,
        collector_names=frozenset({"rules.deterministic_findings"}),
    ),
    SnapshotSplitDefinition(
        service=SnapshotSplitService.RDS,
        subservice=SnapshotSplitSubservice.AUDIT_DETERMINISTIC_FINDINGS,
        collector_boundary=SnapshotSplitBoundary.DETERMINISTIC_FINDINGS,
        collector_names=frozenset({"rules.deterministic_findings"}),
    ),
)

SNAPSHOT_SPLIT_DEFINITIONS_BY_KEY = {
    (definition.service, definition.subservice): definition
    for definition in SNAPSHOT_SPLIT_DEFINITIONS
}
ARTIFACT_SERVICE_SUBSERVICES: dict[SnapshotSplitService, tuple[SnapshotSplitSubservice, ...]] = {
    service: tuple(
        definition.subservice
        for definition in SNAPSHOT_SPLIT_DEFINITIONS
        if definition.service == service
    )
    for service in SnapshotSplitService
}


class SnapshotSplitMetadata(BaseModel):
    """Metadata for a split raw snapshot artifact."""

    schema_version: Literal[3] = SNAPSHOT_SPLIT_ARTIFACT_SCHEMA_VERSION
    service: SnapshotSplitService
    subservice: SnapshotSplitSubservice
    collector_boundary: SnapshotSplitBoundary
    run_id: str
    application_version: str
    environment: str
    region: str
    started_at: datetime
    completed_at: datetime
    run_status: CollectionStatus
    instance_status: CollectionStatus
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
    """One canonical persisted evidence boundary."""

    metadata: SnapshotSplitMetadata
    instance: SnapshotSplitInstance

    model_config = ConfigDict(extra="forbid")


class SnapshotArtifactReference(BaseModel):
    """One immutable evidence object committed by a completed run."""

    service: SnapshotSplitService
    subservice: SnapshotSplitSubservice
    key: str
    status: CollectionStatus

    model_config = ConfigDict(extra="forbid")


class SnapshotRunManifest(BaseModel):
    """Completion marker and index for one coherent collection run."""

    schema_version: Literal[3] = SNAPSHOT_SPLIT_ARTIFACT_SCHEMA_VERSION
    run_id: str
    application_version: str
    environment: str
    region: str
    instance_alias: str
    started_at: datetime
    completed_at: datetime
    status: CollectionStatus
    artifacts: list[SnapshotArtifactReference]

    model_config = ConfigDict(extra="forbid")


def build_snapshot_split_artifacts(
    snapshot: AuditSnapshot,
) -> list[SnapshotSplitArtifact]:
    """Build canonical evidence artifacts from an in-memory collection result."""

    artifacts: list[SnapshotSplitArtifact] = []
    for instance in snapshot.instances:
        for definition in SNAPSHOT_SPLIT_DEFINITIONS:
            artifacts.append(
                _build_artifact(
                    snapshot=snapshot,
                    instance=instance,
                    definition=definition,
                )
            )
    return artifacts


def artifact_definition_for(
    service: SnapshotSplitService,
    subservice: SnapshotSplitSubservice,
) -> SnapshotSplitDefinition:
    """Return the approved artifact definition for one service/subservice pair."""

    return SNAPSHOT_SPLIT_DEFINITIONS_BY_KEY[(service, subservice)]


def assemble_snapshot(
    manifest: SnapshotRunManifest,
    artifacts: list[SnapshotSplitArtifact],
) -> AuditSnapshot:
    """Reassemble the in-memory report input from one committed artifact family."""

    if not artifacts:
        raise ValueError("a snapshot run must contain at least one artifact")
    artifacts_by_boundary = {
        (artifact.metadata.service, artifact.metadata.subservice): artifact
        for artifact in artifacts
    }
    if len(artifacts_by_boundary) != len(artifacts):
        raise ValueError("artifact family contains duplicate boundaries")
    if set(artifacts_by_boundary) != set(SNAPSHOT_SPLIT_DEFINITIONS_BY_KEY):
        raise ValueError("artifact family does not contain every approved boundary")

    first = artifacts[0]
    instance = InstanceSnapshot(
        alias=manifest.instance_alias,
        db_instance_identifier=first.metadata.db_instance_identifier,
        region=manifest.region,
        status=first.metadata.instance_status,
    )
    collectors: dict[str, CollectorResult] = {}
    gaps: dict[tuple[str, str], CollectionGap] = {}
    references_by_boundary = {
        (reference.service, reference.subservice): reference for reference in manifest.artifacts
    }
    if len(references_by_boundary) != len(manifest.artifacts):
        raise ValueError("manifest contains duplicate artifact boundaries")
    for definition in SNAPSHOT_SPLIT_DEFINITIONS:
        boundary = (definition.service, definition.subservice)
        artifact = artifacts_by_boundary[boundary]
        reference = references_by_boundary.get(boundary)
        metadata = artifact.metadata
        evidence = artifact.instance
        if (
            metadata.schema_version != manifest.schema_version
            or metadata.run_id != manifest.run_id
            or metadata.application_version != manifest.application_version
            or metadata.environment != manifest.environment
            or metadata.region != manifest.region
            or metadata.instance_alias != manifest.instance_alias
            or metadata.started_at != manifest.started_at
            or metadata.completed_at != manifest.completed_at
            or metadata.run_status != manifest.status
            or metadata.instance_status != first.metadata.instance_status
            or metadata.db_instance_identifier != first.metadata.db_instance_identifier
        ):
            raise ValueError("artifact identity does not match manifest")
        if metadata.collector_boundary != definition.collector_boundary:
            raise ValueError("artifact collector boundary does not match its partition")
        if reference is None or reference.status != metadata.status:
            raise ValueError("artifact status does not match manifest reference")
        if (
            evidence.alias != manifest.instance_alias
            or evidence.region != manifest.region
            or evidence.db_instance_identifier != metadata.db_instance_identifier
            or evidence.status != metadata.status
        ):
            raise ValueError("artifact instance identity is inconsistent")
        updates: dict[str, object] = {}
        for field in (
            "aws_instance",
            "aws_security_groups",
            "cloudwatch_metrics",
            "rds_operations",
            "postgres_activity",
            "postgres_role_security",
        ):
            value = getattr(evidence, field)
            if value is not None:
                updates[field] = value
        if evidence.databases:
            updates["databases"] = evidence.databases
        if evidence.findings:
            updates["findings"] = [*instance.findings, *evidence.findings]
        if updates:
            instance = instance.model_copy(update=updates)
        for collector in evidence.collectors:
            collectors[collector.name] = collector
        for gap in evidence.gaps:
            gaps[(gap.collector, gap.resource)] = gap
    instance = instance.model_copy(
        update={"collectors": list(collectors.values()), "gaps": list(gaps.values())}
    )
    return AuditSnapshot(
        metadata=RunMetadata(
            run_id=manifest.run_id,
            application_version=manifest.application_version,
            snapshot_schema_version=manifest.schema_version,
            environment=manifest.environment,
            region=manifest.region,
            started_at=manifest.started_at,
            completed_at=manifest.completed_at,
            status=manifest.status,
        ),
        instances=[instance],
    )


def _build_artifact(
    *,
    snapshot: AuditSnapshot,
    instance: InstanceSnapshot,
    definition: SnapshotSplitDefinition,
) -> SnapshotSplitArtifact:
    collectors = _collectors_for(instance, definition.collector_names)
    gaps = _gaps_for(instance, definition.collector_names)
    status = _boundary_status(
        [collector for collector in collectors if collector.name != "secrets.postgres_credentials"]
    )
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
        return split_instance.model_copy(
            update={
                "findings": [
                    finding
                    for finding in instance.findings
                    if ("postgres" in finding.category.split("/"))
                    == (definition.service == SnapshotSplitService.POSTGRES)
                ]
            }
        )
    return split_instance


def _metadata(
    *,
    snapshot: AuditSnapshot,
    instance: InstanceSnapshot,
    definition: SnapshotSplitDefinition,
    status: CollectionStatus,
) -> SnapshotSplitMetadata:
    return SnapshotSplitMetadata(
        service=definition.service,
        subservice=definition.subservice,
        collector_boundary=definition.collector_boundary,
        run_id=snapshot.metadata.run_id,
        application_version=snapshot.metadata.application_version,
        environment=snapshot.metadata.environment,
        region=snapshot.metadata.region,
        started_at=snapshot.metadata.started_at,
        completed_at=snapshot.metadata.completed_at,
        run_status=snapshot.metadata.status,
        instance_status=instance.status,
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
    if CollectionStatus.PARTIAL_SUCCESS in statuses:
        return CollectionStatus.PARTIAL_SUCCESS
    if CollectionStatus.FAILED in statuses:
        if statuses == {CollectionStatus.FAILED}:
            return CollectionStatus.FAILED
        return CollectionStatus.PARTIAL_SUCCESS
    if CollectionStatus.SKIPPED in statuses:
        if statuses == {CollectionStatus.SKIPPED}:
            return CollectionStatus.SKIPPED
        return CollectionStatus.PARTIAL_SUCCESS
    return CollectionStatus.SUCCESS
