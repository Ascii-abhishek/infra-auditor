"""Reusable application workflows shared by CLI and UI."""

from dataclasses import dataclass

from infra_auditor.collectors.aws.client import (
    create_boto3_session,
    create_cloudwatch_client,
    create_ec2_client,
    create_rds_client,
    create_s3_client,
    create_secretsmanager_client,
)
from infra_auditor.collectors.aws.cloudwatch_metrics import CloudWatchRDSMetricsCollector
from infra_auditor.collectors.aws.network import SecurityGroupIngressCollector
from infra_auditor.collectors.aws.rds import RDSDiscovery
from infra_auditor.collectors.aws.rds_operations import RDSOperationsCollector
from infra_auditor.collectors.postgres.activity import ActivitySummaryCollector
from infra_auditor.collectors.postgres.connection import PostgresConnectionFactory
from infra_auditor.collectors.postgres.discovery import DatabaseDiscoveryCollector
from infra_auditor.collectors.postgres.role_security import RoleSecurityCollector
from infra_auditor.config import AppSettings, ResourceConfig
from infra_auditor.models.snapshot import AuditSnapshot
from infra_auditor.runtime import collect_instance_snapshot
from infra_auditor.secrets.aws import AWSSecretsManagerCredentialProvider
from infra_auditor.storage.s3 import S3SnapshotWriter


@dataclass(frozen=True)
class SnapshotWriteResult:
    """Result of collecting and persisting one snapshot."""

    snapshot: AuditSnapshot
    snapshot_uri: str


def collect_and_write_instance(
    *,
    settings: AppSettings,
    resource_config: ResourceConfig,
    alias: str,
) -> SnapshotWriteResult:
    """Collect one instance snapshot and persist it to S3."""

    session = create_boto3_session(settings)
    connection_factory = PostgresConnectionFactory(
        ssl_mode=settings.postgres_ssl_mode,
        connect_timeout_seconds=settings.postgres_connect_timeout_seconds,
        application_name=settings.application_name,
    )
    snapshot = collect_instance_snapshot(
        settings=settings,
        resource_config=resource_config,
        alias=alias,
        rds_discovery_factory=lambda region: RDSDiscovery(create_rds_client(session, region)),
        credential_provider_factory=lambda region: AWSSecretsManagerCredentialProvider(
            create_secretsmanager_client(session, region)
        ),
        connection_factory=connection_factory,
        database_collector=DatabaseDiscoveryCollector(),
        activity_collector=ActivitySummaryCollector(),
        role_security_collector=RoleSecurityCollector(),
        security_group_collector_factory=lambda region: SecurityGroupIngressCollector(
            create_ec2_client(session, region)
        ),
        cloudwatch_metrics_collector_factory=lambda region: CloudWatchRDSMetricsCollector(
            create_cloudwatch_client(session, region),
            lookback_hours=settings.cloudwatch_metric_lookback_hours,
            period_seconds=settings.cloudwatch_metric_period_seconds,
        ),
        rds_operations_collector_factory=lambda region: RDSOperationsCollector(
            create_rds_client(session, region)
        ),
    )
    snapshot_uri = S3SnapshotWriter(
        create_s3_client(session, settings.aws_region),
        settings.snapshot_bucket,
    ).write(snapshot)
    return SnapshotWriteResult(snapshot=snapshot, snapshot_uri=snapshot_uri)
