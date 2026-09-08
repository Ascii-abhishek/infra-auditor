from datetime import UTC, datetime

from infra_auditor.collectors.aws.cloudwatch_metrics import (
    MetricSummary,
    RDSCloudWatchMetricsEvidence,
)
from infra_auditor.collectors.aws.models import RDSInstance
from infra_auditor.collectors.aws.network import RDSSecurityGroupEvidence
from infra_auditor.collectors.aws.rds_operations import (
    RDSOperationsEvidence,
    RDSRecommendationEvidence,
)
from infra_auditor.collectors.postgres.activity import PostgresActivityEvidence
from infra_auditor.collectors.postgres.discovery import DatabaseInfo, DatabaseKind
from infra_auditor.collectors.postgres.role_security import PostgresRoleSecurityEvidence
from infra_auditor.models.common import CollectionStatus
from infra_auditor.models.finding import Finding, FindingSeverity
from infra_auditor.models.snapshot import AuditSnapshot, InstanceSnapshot, RunMetadata
from infra_auditor.reports import (
    build_fleet_report,
    build_snapshot_report,
    render_snapshot_markdown,
)


def test_build_snapshot_report_summarizes_operational_evidence() -> None:
    snapshot = _example_snapshot()

    report = build_snapshot_report(snapshot, source_uri="s3://bucket/key.json")

    assert report.source_uri == "s3://bucket/key.json"
    assert report.total_findings == 1
    instance = report.instances[0]
    assert instance.engine == "postgres"
    assert instance.network.publicly_accessible is True
    assert instance.metrics.cpu_maximum_percent == 50.0
    assert instance.metrics.free_storage_minimum_gib == 20.0
    assert instance.metrics.free_storage_minimum_percent == 20.0
    assert instance.rds_operations.recommendation_count == 1
    assert instance.postgres.application_database_count == 1
    assert instance.postgres.total_connections == 4
    assert instance.rule_counts == {"CFG009": 1}


def test_build_fleet_report_combines_latest_snapshot_reports() -> None:
    snapshot_report = build_snapshot_report(_example_snapshot(), source_uri="s3://bucket/key.json")

    report = build_fleet_report(
        [snapshot_report],
        service="audit",
        environment="dev",
        region="ap-south-1",
    )

    assert report.service == "audit"
    assert report.instance_count == 1
    assert report.total_findings == 1
    assert report.severity_counts.medium == 1


def test_render_snapshot_markdown_includes_report_summary() -> None:
    report = build_snapshot_report(_example_snapshot(), source_uri="s3://bucket/key.json")

    markdown = render_snapshot_markdown(report)

    assert "# Infra Auditor Snapshot Report" in markdown
    assert "`run-1`" in markdown
    assert "RDS instance is publicly accessible" in markdown


def _example_snapshot() -> AuditSnapshot:
    return AuditSnapshot(
        metadata=RunMetadata(
            run_id="run-1",
            environment="dev",
            region="ap-south-1",
            started_at=datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
            completed_at=datetime(2026, 9, 3, 12, 1, tzinfo=UTC),
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
                    engine_version="15.17",
                    instance_class="db.t4g.small",
                    allocated_storage_gib=100,
                    publicly_accessible=True,
                    vpc_id="vpc-123",
                ),
                aws_security_groups=RDSSecurityGroupEvidence(
                    database_port=5432,
                    security_groups=[],
                    public_database_port_ingress=False,
                ),
                cloudwatch_metrics=RDSCloudWatchMetricsEvidence(
                    lookback_hours=24,
                    period_seconds=300,
                    start_time="2026-09-03T00:00:00+00:00",
                    end_time="2026-09-04T00:00:00+00:00",
                    metrics=[
                        MetricSummary(
                            query_id="cpu",
                            metric_name="CPUUtilization",
                            stat="Average",
                            datapoint_count=2,
                            average=20.0,
                            maximum=50.0,
                        ),
                        MetricSummary(
                            query_id="storage",
                            metric_name="FreeStorageSpace",
                            stat="Average",
                            datapoint_count=2,
                            minimum=20 * 1024**3,
                        ),
                    ],
                ),
                rds_operations=RDSOperationsEvidence(
                    recommendations=[
                        RDSRecommendationEvidence(
                            recommendation_id="rec-1",
                            severity="medium",
                            status="active",
                            category="performance",
                            recommendation="Review storage configuration.",
                        )
                    ]
                ),
                databases=[
                    DatabaseInfo(
                        name="postgres",
                        allow_connections=True,
                        is_template=False,
                        kind=DatabaseKind.SYSTEM,
                        connection_eligible=True,
                    ),
                    DatabaseInfo(
                        name="app_db",
                        allow_connections=True,
                        is_template=False,
                        kind=DatabaseKind.APPLICATION,
                        connection_eligible=True,
                    ),
                ],
                postgres_activity=PostgresActivityEvidence(
                    total_connections=4,
                    idle_in_transaction_connections=1,
                    missing_application_name_connections=1,
                    groups=[],
                ),
                postgres_role_security=PostgresRoleSecurityEvidence(roles=[], memberships=[]),
                findings=[
                    Finding(
                        rule_id="CFG009",
                        fingerprint="fingerprint-1",
                        category="security/aws/rds",
                        severity=FindingSeverity.MEDIUM,
                        resource="db/rds",
                        title="RDS instance is publicly accessible",
                        summary="Public RDS requires ingress review.",
                    )
                ],
            )
        ],
    )


def test_fleet_region_comes_from_evidence_instead_of_runtime_default() -> None:
    first = build_snapshot_report(_example_snapshot())
    second = first.model_copy(update={"region": "eu-west-1"})
    mixed = build_fleet_report(
        [first, second], service="audit", environment="dev", region="us-east-1"
    )
    assert mixed.region == "multi-region"
    single = build_fleet_report([second], service="audit", environment="dev", region="us-east-1")
    assert single.region == "eu-west-1"
