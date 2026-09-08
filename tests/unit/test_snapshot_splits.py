from datetime import UTC, datetime

from infra_auditor.collectors.aws.models import RDSInstance
from infra_auditor.collectors.postgres.discovery import DatabaseInfo, DatabaseKind
from infra_auditor.models.common import CollectionStatus, CollectorResult
from infra_auditor.models.finding import Finding, FindingSeverity
from infra_auditor.models.snapshot import AuditSnapshot, InstanceSnapshot, RunMetadata
from infra_auditor.models.snapshot_split import (
    SnapshotSplitService,
    SnapshotSplitSubservice,
    build_snapshot_split_artifacts,
)


def test_snapshot_split_artifacts_keep_service_and_heuristic_boundaries() -> None:
    snapshot = AuditSnapshot(
        metadata=RunMetadata(
            run_id="run-1",
            environment="dev",
            region="ap-south-1",
            started_at=datetime(2026, 9, 4, 7, 0, tzinfo=UTC),
            completed_at=datetime(2026, 9, 4, 7, 1, tzinfo=UTC),
            status=CollectionStatus.SUCCESS,
        ),
        instances=[
            InstanceSnapshot(
                alias="db",
                db_instance_identifier="database-1",
                region="ap-south-1",
                status=CollectionStatus.SUCCESS,
                aws_instance=RDSInstance(
                    alias="db",
                    identifier="database-1",
                    region="ap-south-1",
                    engine="postgres",
                ),
                databases=[
                    DatabaseInfo(
                        name="app_db",
                        allow_connections=True,
                        is_template=False,
                        kind=DatabaseKind.APPLICATION,
                        connection_eligible=True,
                    )
                ],
                collectors=[
                    _collector("aws.rds.describe_db_instances"),
                    _collector("postgres.database_inventory"),
                    _collector("rules.deterministic_findings"),
                ],
                findings=[
                    Finding(
                        rule_id="SEC002",
                        fingerprint="fingerprint-1",
                        category="security/postgres",
                        severity=FindingSeverity.HIGH,
                        resource="db/postgres/role/app_user",
                        title="Role has rds_superuser path",
                        summary="A login role inherits rds_superuser.",
                    )
                ],
            )
        ],
    )

    artifacts = build_snapshot_split_artifacts(snapshot)

    assert len(artifacts) == 9
    by_key = {
        (artifact.metadata.service, artifact.metadata.subservice): artifact
        for artifact in artifacts
    }
    rds_artifact = by_key[(SnapshotSplitService.RDS, SnapshotSplitSubservice.RDS_INSTANCE)]
    postgres_artifact = by_key[
        (SnapshotSplitService.POSTGRES, SnapshotSplitSubservice.POSTGRES_DATABASE_INVENTORY)
    ]
    heuristic_artifact = by_key[
        (
            SnapshotSplitService.POSTGRES,
            SnapshotSplitSubservice.AUDIT_DETERMINISTIC_FINDINGS,
        )
    ]
    assert (
        SnapshotSplitService.RDS,
        SnapshotSplitSubservice.RDS_EC2_SECURITY_GROUPS,
    ) in by_key
    assert (
        SnapshotSplitService.RDS,
        SnapshotSplitSubservice.RDS_CLOUDWATCH_METRICS,
    ) in by_key

    assert rds_artifact.instance.aws_instance is not None
    assert rds_artifact.instance.databases == []
    assert rds_artifact.instance.findings == []
    assert postgres_artifact.instance.aws_instance is None
    assert [database.name for database in postgres_artifact.instance.databases] == ["app_db"]
    assert postgres_artifact.instance.findings == []
    assert heuristic_artifact.instance.aws_instance is None
    assert heuristic_artifact.instance.databases == []
    assert [finding.rule_id for finding in heuristic_artifact.instance.findings] == ["SEC002"]


def _collector(name: str) -> CollectorResult:
    timestamp = datetime(2026, 9, 4, 7, 0, tzinfo=UTC)
    return CollectorResult(
        name=name,
        status=CollectionStatus.SUCCESS,
        started_at=timestamp,
        completed_at=timestamp,
        duration_ms=0,
    )
