from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import pytest
from botocore.exceptions import ClientError

from infra_auditor.collectors.aws.cloudwatch_metrics import RDSCloudWatchMetricsEvidence
from infra_auditor.collectors.aws.models import RDSEndpoint, RDSInstance
from infra_auditor.collectors.aws.network import RDSSecurityGroupEvidence
from infra_auditor.collectors.aws.rds_operations import RDSOperationsEvidence
from infra_auditor.collectors.postgres.activity import ActivityGroup, PostgresActivityEvidence
from infra_auditor.collectors.postgres.discovery import DatabaseDiscoveryCollector
from infra_auditor.collectors.postgres.role_security import (
    PostgresRole,
    PostgresRoleMembership,
    PostgresRoleSecurityEvidence,
)
from infra_auditor.config import AppSettings, ResourceConfig
from infra_auditor.exceptions import SnapshotValidationError
from infra_auditor.models.common import CollectionStatus
from infra_auditor.runtime import collect_instance_snapshot
from infra_auditor.secrets.aws import PostgresCredentials
from infra_auditor.storage.s3 import S3SnapshotWriter


class FakeRDSDiscovery:
    def __init__(self, instance: RDSInstance) -> None:
        self.instance = instance

    def describe_instance(self, **_kwargs: Any) -> RDSInstance:
        return self.instance


class FakeCredentialProvider:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def get_postgres_credentials(self, _secret_id: str) -> PostgresCredentials:
        if self.should_fail:
            raise RuntimeError("secret unavailable")
        return PostgresCredentials(username="prj_rl_rds_auditor_prod", password="fake-password")


class FakeConnection:
    def __init__(self, rows: list[Sequence[object]]) -> None:
        self.rows = rows

    def execute(self, _query: str) -> Iterator[Sequence[object]]:
        return iter(self.rows)


class FakeConnectionFactory:
    @contextmanager
    def connect(self, **_kwargs: Any) -> Iterator[FakeConnection]:
        yield FakeConnection([("postgres", True, False), ("app_db", True, False)])


class FakeRoleSecurityCollector:
    name = "postgres.role_security"

    def collect(self, _connection: FakeConnection) -> PostgresRoleSecurityEvidence:
        return PostgresRoleSecurityEvidence(
            roles=[
                PostgresRole(
                    name="app_user",
                    can_login=True,
                    inherit=True,
                    superuser=False,
                    create_role=False,
                    create_db=False,
                    replication=False,
                    bypass_rls=False,
                    connection_limit=-1,
                ),
                PostgresRole(
                    name="rds_superuser",
                    can_login=False,
                    inherit=True,
                    superuser=False,
                    create_role=False,
                    create_db=False,
                    replication=False,
                    bypass_rls=False,
                    connection_limit=-1,
                ),
            ],
            memberships=[
                PostgresRoleMembership(
                    member="app_user",
                    role="rds_superuser",
                    grantor="postgres",
                    admin_option=False,
                )
            ],
        )


class FakeActivitySummaryCollector:
    name = "postgres.activity_summary"

    def collect(self, _connection: FakeConnection) -> PostgresActivityEvidence:
        return PostgresActivityEvidence(
            total_connections=1,
            idle_in_transaction_connections=0,
            missing_application_name_connections=0,
            groups=[
                ActivityGroup(
                    database_name="app_db",
                    role_name="app_user",
                    application_name="orders-api",
                    client_address="10.0.1.10",
                    state="active",
                    wait_event_type=None,
                    connection_count=1,
                )
            ],
        )


class FakeSecurityGroupIngressCollector:
    name = "aws.ec2.security_group_ingress"

    def collect(self, instance: RDSInstance) -> RDSSecurityGroupEvidence:
        return RDSSecurityGroupEvidence(
            database_port=instance.endpoint.port if instance.endpoint else 5432,
            security_groups=[],
            public_database_port_ingress=False,
        )


class FakeCloudWatchMetricsCollector:
    name = "aws.cloudwatch.rds_metrics"

    def collect(self, _instance: RDSInstance) -> RDSCloudWatchMetricsEvidence:
        return RDSCloudWatchMetricsEvidence(
            lookback_hours=24,
            period_seconds=300,
            start_time="2026-09-03T00:00:00+00:00",
            end_time="2026-09-04T00:00:00+00:00",
            metrics=[],
        )


class FakeRDSOperationsCollector:
    name = "aws.rds.operations"

    def collect(self, _instance: RDSInstance) -> RDSOperationsEvidence:
        return RDSOperationsEvidence()


class FakeS3Client:
    def __init__(self) -> None:
        self.put_object_calls: list[dict[str, Any]] = []

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        self.put_object_calls.append(kwargs)
        return {}


class ConflictS3Client:
    def put_object(self, **_kwargs: Any) -> dict[str, Any]:
        raise ClientError(
            {
                "Error": {"Code": "PreconditionFailed"},
                "ResponseMetadata": {"HTTPStatusCode": 412},
            },
            "PutObject",
        )


def example_resource_config() -> ResourceConfig:
    return ResourceConfig.model_validate(
        {
            "version": 1,
            "aws": {"default_region": "ap-south-1"},
            "instances": {
                "raptor-catalog": {
                    "db_instance_identifier": "cleancatalograptorsupplies",
                    "secret_id": "infra-auditor/postgres/raptor-catalog",
                }
            },
        }
    )


def example_rds_instance() -> RDSInstance:
    return RDSInstance(
        alias="raptor-catalog",
        identifier="cleancatalograptorsupplies",
        arn="arn:aws:rds:ap-south-1:123456789012:db:cleancatalograptorsupplies",
        region="ap-south-1",
        engine="postgres",
        engine_version="15.17",
        endpoint=RDSEndpoint(address="example.rds.amazonaws.com", port=5432),
    )


def test_collect_instance_snapshot_success_and_s3_write() -> None:
    settings = AppSettings(_env_file=None)
    snapshot = collect_instance_snapshot(
        settings=settings,
        resource_config=example_resource_config(),
        alias="raptor-catalog",
        rds_discovery_factory=lambda _region: FakeRDSDiscovery(example_rds_instance()),
        credential_provider_factory=lambda _region: FakeCredentialProvider(),
        connection_factory=FakeConnectionFactory(),
        database_collector=DatabaseDiscoveryCollector(),
        activity_collector=FakeActivitySummaryCollector(),
        role_security_collector=FakeRoleSecurityCollector(),
        security_group_collector_factory=lambda _region: FakeSecurityGroupIngressCollector(),
        cloudwatch_metrics_collector_factory=lambda _region: FakeCloudWatchMetricsCollector(),
        rds_operations_collector_factory=lambda _region: FakeRDSOperationsCollector(),
        run_id_factory=lambda: "run-123",
    )

    assert snapshot.metadata.run_id == "run-123"
    assert snapshot.metadata.environment == "dev"
    assert snapshot.metadata.status == CollectionStatus.SUCCESS
    assert snapshot.instances[0].status == CollectionStatus.SUCCESS
    assert [database.name for database in snapshot.instances[0].databases] == ["postgres", "app_db"]
    assert snapshot.instances[0].postgres_activity is not None
    assert snapshot.instances[0].postgres_role_security is not None
    assert len(snapshot.instances[0].findings) == 1
    assert snapshot.instances[0].findings[0].rule_id == "SEC002"

    client = FakeS3Client()
    uri = S3SnapshotWriter(client, settings.snapshot_bucket).write(snapshot)

    assert uri.startswith(
        "s3://infra-audit-rl-dev/raw/snapshots/snapshot_schema=1/env=dev/"
        "region=ap-south-1/service=rds-postgres/instance=raptor-catalog/dt="
    )
    assert len(client.put_object_calls) == 9
    put_object = client.put_object_calls[0]
    assert put_object["Bucket"] == "infra-audit-rl-dev"
    assert put_object["ContentType"] == "application/json"
    assert put_object["ServerSideEncryption"] == "AES256"
    assert put_object["IfNoneMatch"] == "*"
    assert put_object["Metadata"]["run-id"] == "run-123"
    assert put_object["Key"].startswith(
        "raw/snapshots/snapshot_schema=1/env=dev/region=ap-south-1/"
        "service=rds-postgres/instance=raptor-catalog/dt="
    )
    split_keys = [call["Key"] for call in client.put_object_calls[1:]]
    assert any(
        "service=rds/subservice=instance/instance=raptor-catalog" in key for key in split_keys
    )
    assert any(
        "service=rds/subservice=operations/instance=raptor-catalog" in key for key in split_keys
    )
    assert any(
        "service=postgres/subservice=database-inventory/instance=raptor-catalog" in key
        for key in split_keys
    )
    assert any(
        "service=postgres/subservice=activity-summary/instance=raptor-catalog" in key
        for key in split_keys
    )
    assert any(
        "service=postgres/subservice=role-security/instance=raptor-catalog" in key
        for key in split_keys
    )
    assert any(
        "service=rds/subservice=ec2-security-groups/instance=raptor-catalog" in key
        for key in split_keys
    )
    assert any(
        "service=rds/subservice=cloudwatch-rds-metrics/instance=raptor-catalog" in key
        for key in split_keys
    )
    assert any(
        "service=audit-heuristics/subservice=deterministic-findings/instance=raptor-catalog" in key
        for key in split_keys
    )
    assert all(b"fake-password" not in call["Body"] for call in client.put_object_calls)


def test_s3_writer_rejects_snapshot_key_collision() -> None:
    settings = AppSettings(_env_file=None)
    snapshot = collect_instance_snapshot(
        settings=settings,
        resource_config=example_resource_config(),
        alias="raptor-catalog",
        rds_discovery_factory=lambda _region: FakeRDSDiscovery(example_rds_instance()),
        credential_provider_factory=lambda _region: FakeCredentialProvider(),
        connection_factory=FakeConnectionFactory(),
        database_collector=DatabaseDiscoveryCollector(),
        activity_collector=FakeActivitySummaryCollector(),
        role_security_collector=FakeRoleSecurityCollector(),
        security_group_collector_factory=lambda _region: FakeSecurityGroupIngressCollector(),
        cloudwatch_metrics_collector_factory=lambda _region: FakeCloudWatchMetricsCollector(),
        rds_operations_collector_factory=lambda _region: FakeRDSOperationsCollector(),
        run_id_factory=lambda: "run-123",
    )

    writer = S3SnapshotWriter(ConflictS3Client(), settings.snapshot_bucket)

    with pytest.raises(SnapshotValidationError, match="snapshot already exists in S3"):
        writer.write(snapshot)


def test_collect_instance_snapshot_secret_failure_is_partial_success() -> None:
    settings = AppSettings(_env_file=None)
    snapshot = collect_instance_snapshot(
        settings=settings,
        resource_config=example_resource_config(),
        alias="raptor-catalog",
        rds_discovery_factory=lambda _region: FakeRDSDiscovery(example_rds_instance()),
        credential_provider_factory=lambda _region: FakeCredentialProvider(should_fail=True),
        connection_factory=FakeConnectionFactory(),
        database_collector=DatabaseDiscoveryCollector(),
        activity_collector=FakeActivitySummaryCollector(),
        role_security_collector=FakeRoleSecurityCollector(),
        security_group_collector_factory=lambda _region: FakeSecurityGroupIngressCollector(),
        cloudwatch_metrics_collector_factory=lambda _region: FakeCloudWatchMetricsCollector(),
        rds_operations_collector_factory=lambda _region: FakeRDSOperationsCollector(),
        run_id_factory=lambda: "run-456",
    )

    assert snapshot.metadata.status == CollectionStatus.PARTIAL_SUCCESS
    assert snapshot.instances[0].aws_instance is not None
    assert snapshot.instances[0].databases == []
    assert snapshot.instances[0].gaps[0].collector == "secrets.postgres_credentials"
    assert any(
        collector.name == "postgres.activity_summary"
        and collector.status == CollectionStatus.SKIPPED
        for collector in snapshot.instances[0].collectors
    )
    assert any(
        collector.name == "postgres.role_security" and collector.status == CollectionStatus.SKIPPED
        for collector in snapshot.instances[0].collectors
    )
