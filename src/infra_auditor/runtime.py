"""Collection orchestration for the V0.1 snapshot path."""

from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from uuid import uuid4

import structlog

from infra_auditor.collectors.aws.models import RDSInstance
from infra_auditor.collectors.aws.rds import RDSDiscovery
from infra_auditor.collectors.postgres.connection import PostgresConnectionFactory
from infra_auditor.collectors.postgres.discovery import DatabaseDiscoveryCollector, DatabaseInfo
from infra_auditor.config import AppSettings, InstanceConfig, ResourceConfig
from infra_auditor.models.common import CollectionGap, CollectionStatus, CollectorResult, utc_now
from infra_auditor.models.snapshot import AuditSnapshot, InstanceSnapshot, RunMetadata
from infra_auditor.secrets.aws import CredentialProvider, PostgresCredentials

logger = structlog.get_logger(__name__)


class RDSDiscoveryFactory(Protocol):
    """Factory for an RDS discovery client bound to one region."""

    def __call__(self, region: str) -> RDSDiscovery:
        """Create a region-bound RDS discovery client."""


class CredentialProviderFactory(Protocol):
    """Factory for a credential provider bound to one region."""

    def __call__(self, region: str) -> CredentialProvider:
        """Create a region-bound credential provider."""


def collect_instance_snapshot(
    *,
    settings: AppSettings,
    resource_config: ResourceConfig,
    alias: str,
    rds_discovery_factory: RDSDiscoveryFactory,
    credential_provider_factory: CredentialProviderFactory,
    connection_factory: PostgresConnectionFactory,
    database_collector: DatabaseDiscoveryCollector,
    run_id_factory: Callable[[], str] | None = None,
) -> AuditSnapshot:
    """Run the implemented V0.1 collection flow for one configured instance."""

    run_id = run_id_factory() if run_id_factory is not None else str(uuid4())
    started_at = utc_now()
    instance_config = resource_config.instances.get(alias)
    if instance_config is None:
        raise KeyError(f"unknown instance alias: {alias}")

    region = resource_config.region_for_instance(alias)
    instance_snapshot = _collect_instance(
        settings=settings,
        alias=alias,
        instance_config=instance_config,
        region=region,
        rds_discovery_factory=rds_discovery_factory,
        credential_provider_factory=credential_provider_factory,
        connection_factory=connection_factory,
        database_collector=database_collector,
    )

    completed_at = utc_now()
    return AuditSnapshot(
        metadata=RunMetadata(
            run_id=run_id,
            environment=settings.environment,
            region=region,
            started_at=started_at,
            completed_at=completed_at,
            status=instance_snapshot.status,
        ),
        instances=[instance_snapshot],
    )


def _collect_instance(
    *,
    settings: AppSettings,
    alias: str,
    instance_config: InstanceConfig,
    region: str,
    rds_discovery_factory: RDSDiscoveryFactory,
    credential_provider_factory: CredentialProviderFactory,
    connection_factory: PostgresConnectionFactory,
    database_collector: DatabaseDiscoveryCollector,
) -> InstanceSnapshot:
    collectors: list[CollectorResult] = []
    gaps: list[CollectionGap] = []

    aws_instance, result, gap = _collect_aws_instance(
        alias=alias,
        instance_config=instance_config,
        region=region,
        rds_discovery_factory=rds_discovery_factory,
    )
    collectors.append(result)
    if gap is not None:
        gaps.append(gap)
        return InstanceSnapshot(
            alias=alias,
            db_instance_identifier=instance_config.db_instance_identifier,
            region=region,
            status=CollectionStatus.FAILED,
            aws_instance=None,
            collectors=collectors,
            gaps=gaps,
        )

    assert aws_instance is not None

    credentials, result, gap = _resolve_credentials(
        alias=alias,
        instance_config=instance_config,
        region=region,
        credential_provider_factory=credential_provider_factory,
    )
    collectors.append(result)
    if gap is not None:
        gaps.append(gap)
        collectors.append(
            _skipped_collector(
                name=database_collector.name,
                summary="Skipped because database credentials were unavailable.",
            )
        )
        return InstanceSnapshot(
            alias=alias,
            db_instance_identifier=instance_config.db_instance_identifier,
            region=region,
            status=CollectionStatus.PARTIAL_SUCCESS,
            aws_instance=aws_instance,
            collectors=collectors,
            gaps=gaps,
        )

    assert credentials is not None

    databases, result, gap = _collect_database_inventory(
        settings=settings,
        alias=alias,
        aws_instance=aws_instance,
        credentials=credentials,
        connection_factory=connection_factory,
        database_collector=database_collector,
    )
    collectors.append(result)
    if gap is not None:
        gaps.append(gap)

    status = CollectionStatus.SUCCESS if not gaps else CollectionStatus.PARTIAL_SUCCESS
    return InstanceSnapshot(
        alias=alias,
        db_instance_identifier=instance_config.db_instance_identifier,
        region=region,
        status=status,
        aws_instance=aws_instance,
        databases=databases,
        collectors=collectors,
        gaps=gaps,
    )


def _collect_aws_instance(
    *,
    alias: str,
    instance_config: InstanceConfig,
    region: str,
    rds_discovery_factory: RDSDiscoveryFactory,
) -> tuple[RDSInstance | None, CollectorResult, CollectionGap | None]:
    started_at = utc_now()
    try:
        discovery = rds_discovery_factory(region)
        aws_instance = discovery.describe_instance(
            alias=alias, config=instance_config, region=region
        )
    except Exception as exc:  # noqa: BLE001 - converted into structured collection gap.
        completed_at = utc_now()
        logger.warning(
            "collector_failed",
            collector="aws.rds.describe_db_instances",
            instance_alias=alias,
            db_instance_identifier=instance_config.db_instance_identifier,
            error_type=type(exc).__name__,
        )
        return (
            None,
            _collector_result(
                name="aws.rds.describe_db_instances",
                status=CollectionStatus.FAILED,
                started_at=started_at,
                completed_at=completed_at,
            ),
            CollectionGap(
                collector="aws.rds.describe_db_instances",
                resource=alias,
                error_type=type(exc).__name__,
                message=str(exc),
            ),
        )

    completed_at = utc_now()
    return (
        aws_instance,
        _collector_result(
            name="aws.rds.describe_db_instances",
            status=CollectionStatus.SUCCESS,
            started_at=started_at,
            completed_at=completed_at,
            summary=f"Discovered RDS instance {aws_instance.identifier}.",
        ),
        None,
    )


def _resolve_credentials(
    *,
    alias: str,
    instance_config: InstanceConfig,
    region: str,
    credential_provider_factory: CredentialProviderFactory,
) -> tuple[PostgresCredentials | None, CollectorResult, CollectionGap | None]:
    started_at = utc_now()
    try:
        provider = credential_provider_factory(region)
        credentials = provider.get_postgres_credentials(instance_config.secret_id)
    except Exception as exc:  # noqa: BLE001 - converted into structured collection gap.
        completed_at = utc_now()
        logger.warning(
            "collector_failed",
            collector="secrets.postgres_credentials",
            instance_alias=alias,
            db_instance_identifier=instance_config.db_instance_identifier,
            error_type=type(exc).__name__,
        )
        return (
            None,
            _collector_result(
                name="secrets.postgres_credentials",
                status=CollectionStatus.FAILED,
                started_at=started_at,
                completed_at=completed_at,
            ),
            CollectionGap(
                collector="secrets.postgres_credentials",
                resource=alias,
                error_type=type(exc).__name__,
                message=str(exc),
            ),
        )

    completed_at = utc_now()
    return (
        credentials,
        _collector_result(
            name="secrets.postgres_credentials",
            status=CollectionStatus.SUCCESS,
            started_at=started_at,
            completed_at=completed_at,
            summary="Resolved PostgreSQL credentials from configured secret.",
        ),
        None,
    )


def _collect_database_inventory(
    *,
    settings: AppSettings,
    alias: str,
    aws_instance: RDSInstance,
    credentials: PostgresCredentials,
    connection_factory: PostgresConnectionFactory,
    database_collector: DatabaseDiscoveryCollector,
) -> tuple[list[DatabaseInfo], CollectorResult, CollectionGap | None]:
    started_at = utc_now()
    try:
        with connection_factory.connect(
            instance=aws_instance,
            credentials=credentials,
            database=settings.bootstrap_database,
        ) as connection:
            databases = database_collector.collect(connection)
    except Exception as exc:  # noqa: BLE001 - converted into structured collection gap.
        completed_at = utc_now()
        logger.warning(
            "collector_failed",
            collector=database_collector.name,
            instance_alias=alias,
            db_instance_identifier=aws_instance.identifier,
            database=settings.bootstrap_database,
            error_type=type(exc).__name__,
        )
        return (
            [],
            _collector_result(
                name=database_collector.name,
                status=CollectionStatus.FAILED,
                started_at=started_at,
                completed_at=completed_at,
            ),
            CollectionGap(
                collector=database_collector.name,
                resource=alias,
                error_type=type(exc).__name__,
                message=str(exc),
            ),
        )

    completed_at = utc_now()
    return (
        databases,
        _collector_result(
            name=database_collector.name,
            status=CollectionStatus.SUCCESS,
            started_at=started_at,
            completed_at=completed_at,
            summary=f"Discovered {len(databases)} databases.",
        ),
        None,
    )


def _collector_result(
    *,
    name: str,
    status: CollectionStatus,
    started_at: datetime,
    completed_at: datetime,
    summary: str | None = None,
) -> CollectorResult:
    return CollectorResult(
        name=name,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=max(0, int((completed_at - started_at).total_seconds() * 1000)),
        summary=summary,
    )


def _skipped_collector(*, name: str, summary: str) -> CollectorResult:
    timestamp = utc_now()
    return _collector_result(
        name=name,
        status=CollectionStatus.SKIPPED,
        started_at=timestamp,
        completed_at=timestamp,
        summary=summary,
    )
