"""Collection orchestration for the V0.1 snapshot path."""

from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol
from uuid import uuid4

import structlog

from infra_auditor.collectors.aws.cloudwatch_metrics import (
    CloudWatchRDSMetricsCollector,
    RDSCloudWatchMetricsEvidence,
)
from infra_auditor.collectors.aws.models import RDSInstance
from infra_auditor.collectors.aws.network import (
    RDSSecurityGroupEvidence,
    SecurityGroupIngressCollector,
)
from infra_auditor.collectors.aws.rds import RDSDiscovery
from infra_auditor.collectors.aws.rds_operations import (
    RDSOperationsCollector,
    RDSOperationsEvidence,
)
from infra_auditor.collectors.postgres.activity import (
    ActivitySummaryCollector,
    PostgresActivityEvidence,
)
from infra_auditor.collectors.postgres.connection import PostgresConnectionFactory
from infra_auditor.collectors.postgres.discovery import DatabaseDiscoveryCollector, DatabaseInfo
from infra_auditor.collectors.postgres.role_security import (
    PostgresRoleSecurityEvidence,
    RoleSecurityCollector,
)
from infra_auditor.config import AppSettings, InstanceConfig, ResourceConfig
from infra_auditor.models.common import CollectionGap, CollectionStatus, CollectorResult, utc_now
from infra_auditor.models.finding import Finding
from infra_auditor.models.snapshot import AuditSnapshot, InstanceSnapshot, RunMetadata
from infra_auditor.rules.aws_rds import evaluate_aws_rds_findings
from infra_auditor.rules.postgres_activity import evaluate_postgres_activity_findings
from infra_auditor.rules.postgres_security import evaluate_postgres_security_findings
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
    activity_collector: ActivitySummaryCollector,
    role_security_collector: RoleSecurityCollector,
    security_group_collector_factory: Callable[[str], SecurityGroupIngressCollector],
    cloudwatch_metrics_collector_factory: Callable[[str], CloudWatchRDSMetricsCollector],
    rds_operations_collector_factory: Callable[[str], RDSOperationsCollector],
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
        enabled_collectors=resource_config.coverage_for_instance(alias).collector_names(),
        rds_discovery_factory=rds_discovery_factory,
        credential_provider_factory=credential_provider_factory,
        connection_factory=connection_factory,
        database_collector=database_collector,
        activity_collector=activity_collector,
        role_security_collector=role_security_collector,
        security_group_collector_factory=security_group_collector_factory,
        cloudwatch_metrics_collector_factory=cloudwatch_metrics_collector_factory,
        rds_operations_collector_factory=rds_operations_collector_factory,
    )

    rules_started_at = utc_now()
    findings = _evaluate_findings(
        run_id=run_id,
        instance_alias=alias,
        instance_snapshot=instance_snapshot,
    )
    rules_completed_at = utc_now()
    instance_snapshot = instance_snapshot.model_copy(
        update={
            "findings": findings,
            "collectors": [
                *instance_snapshot.collectors,
                _collector_result(
                    name="rules.deterministic_findings",
                    status=CollectionStatus.SUCCESS,
                    started_at=rules_started_at,
                    completed_at=rules_completed_at,
                    summary=f"Generated {len(findings)} findings.",
                ),
            ],
        }
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
    enabled_collectors: frozenset[str],
    rds_discovery_factory: RDSDiscoveryFactory,
    credential_provider_factory: CredentialProviderFactory,
    connection_factory: PostgresConnectionFactory,
    database_collector: DatabaseDiscoveryCollector,
    activity_collector: ActivitySummaryCollector,
    role_security_collector: RoleSecurityCollector,
    security_group_collector_factory: Callable[[str], SecurityGroupIngressCollector],
    cloudwatch_metrics_collector_factory: Callable[[str], CloudWatchRDSMetricsCollector],
    rds_operations_collector_factory: Callable[[str], RDSOperationsCollector],
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

    if "aws.ec2.security_group_ingress" in enabled_collectors:
        security_groups, result, gap = _collect_security_groups(
            alias=alias,
            region=region,
            aws_instance=aws_instance,
            collector_factory=security_group_collector_factory,
        )
    else:
        security_groups, result, gap = (
            None,
            _skipped_collector(
                name="aws.ec2.security_group_ingress", summary="Disabled by service configuration."
            ),
            None,
        )
    collectors.append(result)
    if gap is not None:
        gaps.append(gap)

    if "aws.cloudwatch.rds_metrics" in enabled_collectors:
        cloudwatch_metrics, result, gap = _collect_cloudwatch_metrics(
            alias=alias,
            region=region,
            aws_instance=aws_instance,
            collector_factory=cloudwatch_metrics_collector_factory,
        )
    else:
        cloudwatch_metrics, result, gap = (
            None,
            _skipped_collector(
                name="aws.cloudwatch.rds_metrics", summary="Disabled by service configuration."
            ),
            None,
        )
    collectors.append(result)
    if gap is not None:
        gaps.append(gap)

    if "aws.rds.operations" in enabled_collectors:
        rds_operations, result, gap = _collect_rds_operations(
            alias=alias,
            region=region,
            aws_instance=aws_instance,
            collector_factory=rds_operations_collector_factory,
        )
    else:
        rds_operations, result, gap = (
            None,
            _skipped_collector(
                name="aws.rds.operations", summary="Disabled by service configuration."
            ),
            None,
        )
    collectors.append(result)
    if gap is not None:
        gaps.append(gap)

    if not any(name.startswith("postgres.") for name in enabled_collectors):
        collectors.extend(
            _skipped_collector(name=name, summary="Disabled by service configuration.")
            for name in (
                database_collector.name,
                activity_collector.name,
                role_security_collector.name,
            )
        )
        return InstanceSnapshot(
            alias=alias,
            db_instance_identifier=instance_config.db_instance_identifier,
            region=region,
            status=CollectionStatus.PARTIAL_SUCCESS if gaps else CollectionStatus.SUCCESS,
            aws_instance=aws_instance,
            aws_security_groups=security_groups,
            cloudwatch_metrics=cloudwatch_metrics,
            rds_operations=rds_operations,
            collectors=collectors,
            gaps=gaps,
        )

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
        collectors.append(
            _skipped_collector(
                name=activity_collector.name,
                summary="Skipped because database credentials were unavailable.",
            )
        )
        collectors.append(
            _skipped_collector(
                name=role_security_collector.name,
                summary="Skipped because database credentials were unavailable.",
            )
        )
        return InstanceSnapshot(
            alias=alias,
            db_instance_identifier=instance_config.db_instance_identifier,
            region=region,
            status=CollectionStatus.PARTIAL_SUCCESS,
            aws_instance=aws_instance,
            aws_security_groups=security_groups,
            cloudwatch_metrics=cloudwatch_metrics,
            rds_operations=rds_operations,
            collectors=collectors,
            gaps=gaps,
        )

    assert credentials is not None

    databases, postgres_activity, role_security, postgres_results, postgres_gaps = (
        _collect_postgres_evidence(
            enabled_collectors=enabled_collectors,
            settings=settings,
            alias=alias,
            aws_instance=aws_instance,
            credentials=credentials,
            connection_factory=connection_factory,
            database_collector=database_collector,
            activity_collector=activity_collector,
            role_security_collector=role_security_collector,
        )
    )
    collectors.extend(postgres_results)
    gaps.extend(postgres_gaps)

    status = CollectionStatus.SUCCESS if not gaps else CollectionStatus.PARTIAL_SUCCESS
    return InstanceSnapshot(
        alias=alias,
        db_instance_identifier=instance_config.db_instance_identifier,
        region=region,
        status=status,
        aws_instance=aws_instance,
        aws_security_groups=security_groups,
        cloudwatch_metrics=cloudwatch_metrics,
        rds_operations=rds_operations,
        databases=databases,
        postgres_activity=postgres_activity,
        postgres_role_security=role_security,
        collectors=collectors,
        gaps=gaps,
    )


def _evaluate_findings(
    *,
    run_id: str,
    instance_alias: str,
    instance_snapshot: InstanceSnapshot,
) -> list[Finding]:
    return [
        *evaluate_aws_rds_findings(
            run_id=run_id,
            instance_alias=instance_alias,
            aws_instance=instance_snapshot.aws_instance,
            security_groups=instance_snapshot.aws_security_groups,
            cloudwatch_metrics=instance_snapshot.cloudwatch_metrics,
            rds_operations=instance_snapshot.rds_operations,
        ),
        *evaluate_postgres_activity_findings(
            run_id=run_id,
            instance_alias=instance_alias,
            activity=instance_snapshot.postgres_activity,
        ),
        *evaluate_postgres_security_findings(
            run_id=run_id,
            instance_alias=instance_alias,
            role_security=instance_snapshot.postgres_role_security,
        ),
    ]


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


def _collect_security_groups(
    *,
    alias: str,
    region: str,
    aws_instance: RDSInstance,
    collector_factory: Callable[[str], SecurityGroupIngressCollector],
) -> tuple[RDSSecurityGroupEvidence | None, CollectorResult, CollectionGap | None]:
    started_at = utc_now()
    try:
        evidence = collector_factory(region).collect(aws_instance)
    except Exception as exc:  # noqa: BLE001 - converted into structured collection gap.
        completed_at = utc_now()
        logger.warning(
            "collector_failed",
            collector=SecurityGroupIngressCollector.name,
            instance_alias=alias,
            db_instance_identifier=aws_instance.identifier,
            error_type=type(exc).__name__,
        )
        return (
            None,
            _collector_result(
                name=SecurityGroupIngressCollector.name,
                status=CollectionStatus.FAILED,
                started_at=started_at,
                completed_at=completed_at,
            ),
            CollectionGap(
                collector=SecurityGroupIngressCollector.name,
                resource=alias,
                error_type=type(exc).__name__,
                message=str(exc),
            ),
        )

    completed_at = utc_now()
    return (
        evidence,
        _collector_result(
            name=SecurityGroupIngressCollector.name,
            status=CollectionStatus.SUCCESS,
            started_at=started_at,
            completed_at=completed_at,
            summary=(
                f"Discovered {len(evidence.security_groups)} security groups; "
                f"public database-port ingress={evidence.public_database_port_ingress}."
            ),
        ),
        None,
    )


def _collect_cloudwatch_metrics(
    *,
    alias: str,
    region: str,
    aws_instance: RDSInstance,
    collector_factory: Callable[[str], CloudWatchRDSMetricsCollector],
) -> tuple[RDSCloudWatchMetricsEvidence | None, CollectorResult, CollectionGap | None]:
    started_at = utc_now()
    try:
        evidence = collector_factory(region).collect(aws_instance)
    except Exception as exc:  # noqa: BLE001 - converted into structured collection gap.
        completed_at = utc_now()
        logger.warning(
            "collector_failed",
            collector=CloudWatchRDSMetricsCollector.name,
            instance_alias=alias,
            db_instance_identifier=aws_instance.identifier,
            error_type=type(exc).__name__,
        )
        return (
            None,
            _collector_result(
                name=CloudWatchRDSMetricsCollector.name,
                status=CollectionStatus.FAILED,
                started_at=started_at,
                completed_at=completed_at,
            ),
            CollectionGap(
                collector=CloudWatchRDSMetricsCollector.name,
                resource=alias,
                error_type=type(exc).__name__,
                message=str(exc),
            ),
        )

    completed_at = utc_now()
    return (
        evidence,
        _collector_result(
            name=CloudWatchRDSMetricsCollector.name,
            status=CollectionStatus.SUCCESS,
            started_at=started_at,
            completed_at=completed_at,
            summary=(
                f"Collected {len(evidence.metrics)} CloudWatch metrics over "
                f"{evidence.lookback_hours} hours."
            ),
        ),
        None,
    )


def _collect_rds_operations(
    *,
    alias: str,
    region: str,
    aws_instance: RDSInstance,
    collector_factory: Callable[[str], RDSOperationsCollector],
) -> tuple[RDSOperationsEvidence | None, CollectorResult, CollectionGap | None]:
    started_at = utc_now()
    try:
        evidence = collector_factory(region).collect(aws_instance)
    except Exception as exc:  # noqa: BLE001 - converted into structured collection gap.
        completed_at = utc_now()
        logger.warning(
            "collector_failed",
            collector=RDSOperationsCollector.name,
            instance_alias=alias,
            db_instance_identifier=aws_instance.identifier,
            error_type=type(exc).__name__,
        )
        return (
            None,
            _collector_result(
                name=RDSOperationsCollector.name,
                status=CollectionStatus.FAILED,
                started_at=started_at,
                completed_at=completed_at,
            ),
            CollectionGap(
                collector=RDSOperationsCollector.name,
                resource=alias,
                error_type=type(exc).__name__,
                message=str(exc),
            ),
        )

    completed_at = utc_now()
    parameter_count = sum(len(group.parameters) for group in evidence.parameter_groups)
    return (
        evidence,
        _collector_result(
            name=RDSOperationsCollector.name,
            status=CollectionStatus.SUCCESS,
            started_at=started_at,
            completed_at=completed_at,
            summary=(
                f"Collected {len(evidence.pending_maintenance)} maintenance actions, "
                f"{len(evidence.recommendations)} recommendations, and "
                f"{parameter_count} parameter values."
            ),
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
        if instance_config.secret_id is None:
            raise ValueError("enabled PostgreSQL collectors require a secret reference")
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


def _collect_postgres_evidence(
    *,
    enabled_collectors: frozenset[str],
    settings: AppSettings,
    alias: str,
    aws_instance: RDSInstance,
    credentials: PostgresCredentials,
    connection_factory: PostgresConnectionFactory,
    database_collector: DatabaseDiscoveryCollector,
    activity_collector: ActivitySummaryCollector,
    role_security_collector: RoleSecurityCollector,
) -> tuple[
    list[DatabaseInfo],
    PostgresActivityEvidence | None,
    PostgresRoleSecurityEvidence | None,
    list[CollectorResult],
    list[CollectionGap],
]:
    connection_started_at = utc_now()
    try:
        with connection_factory.connect(
            instance=aws_instance,
            credentials=credentials,
            database=settings.bootstrap_database,
        ) as connection:
            return _collect_postgres_evidence_from_connection(
                enabled_collectors=enabled_collectors,
                connection=connection,
                alias=alias,
                database_collector=database_collector,
                activity_collector=activity_collector,
                role_security_collector=role_security_collector,
            )
    except Exception as exc:  # noqa: BLE001 - converted into structured collection gap.
        completed_at = utc_now()
        names = (database_collector.name, activity_collector.name, role_security_collector.name)
        return (
            [],
            None,
            None,
            [
                _collector_result(
                    name=name,
                    status=CollectionStatus.FAILED
                    if name in enabled_collectors
                    else CollectionStatus.SKIPPED,
                    started_at=connection_started_at,
                    completed_at=completed_at,
                    summary=None
                    if name in enabled_collectors
                    else "Disabled by service configuration.",
                )
                for name in names
            ],
            [
                CollectionGap(
                    collector=name,
                    resource=alias,
                    error_type=type(exc).__name__,
                    message="PostgreSQL connection failed; inspect connectivity and permissions.",
                )
                for name in names
                if name in enabled_collectors
            ],
        )


def _collect_postgres_evidence_from_connection(
    *,
    enabled_collectors: frozenset[str],
    connection: Any,
    alias: str,
    database_collector: DatabaseDiscoveryCollector,
    activity_collector: ActivitySummaryCollector,
    role_security_collector: RoleSecurityCollector,
) -> tuple[
    list[DatabaseInfo],
    PostgresActivityEvidence | None,
    PostgresRoleSecurityEvidence | None,
    list[CollectorResult],
    list[CollectionGap],
]:
    collectors: list[CollectorResult] = []
    gaps: list[CollectionGap] = []

    def collect[T](name: str, action: Callable[[], T], empty: T) -> T:
        if name not in enabled_collectors:
            collectors.append(
                _skipped_collector(name=name, summary="Disabled by service configuration.")
            )
            return empty
        started_at = utc_now()
        try:
            evidence = action()
        except Exception as exc:  # noqa: BLE001 - preserve independent collector failures.
            logger.warning(
                "collector_failed",
                collector=name,
                instance_alias=alias,
                error_type=type(exc).__name__,
            )
            collectors.append(
                _collector_result(
                    name=name,
                    status=CollectionStatus.FAILED,
                    started_at=started_at,
                    completed_at=utc_now(),
                )
            )
            gaps.append(
                CollectionGap(
                    collector=name,
                    resource=alias,
                    error_type=type(exc).__name__,
                    message="PostgreSQL evidence collection failed.",
                )
            )
            return empty
        collectors.append(
            _collector_result(
                name=name,
                status=CollectionStatus.SUCCESS,
                started_at=started_at,
                completed_at=utc_now(),
            )
        )
        return evidence

    databases: list[DatabaseInfo] = collect(
        database_collector.name, lambda: database_collector.collect(connection), []
    )
    activity = collect(
        activity_collector.name, lambda: activity_collector.collect(connection), None
    )
    roles = collect(
        role_security_collector.name, lambda: role_security_collector.collect(connection), None
    )
    return databases, activity, roles, collectors, gaps


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
