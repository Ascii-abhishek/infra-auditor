"""Build report summaries from raw audit snapshots."""

from collections import Counter
from collections.abc import Iterable

from infra_auditor.collectors.aws.cloudwatch_metrics import (
    MetricSummary,
    RDSCloudWatchMetricsEvidence,
)
from infra_auditor.collectors.postgres.discovery import DatabaseKind
from infra_auditor.models.common import utc_now
from infra_auditor.models.finding import Finding, FindingSeverity
from infra_auditor.models.snapshot import AuditSnapshot, InstanceSnapshot
from infra_auditor.reports.models import (
    CollectorReport,
    FindingReportItem,
    FleetReport,
    InstanceReport,
    MetricReport,
    NetworkReport,
    PostgresReport,
    RDSOperationsReport,
    RDSRecommendationReport,
    SeverityCounts,
    SnapshotReport,
)

BYTES_PER_GIB = 1024**3
SEVERITY_ORDER: dict[FindingSeverity, int] = {
    FindingSeverity.CRITICAL: 0,
    FindingSeverity.HIGH: 1,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.LOW: 3,
    FindingSeverity.INFO: 4,
}


def build_snapshot_report(
    snapshot: AuditSnapshot,
    *,
    source_uri: str | None = None,
    top_findings_limit: int = 25,
) -> SnapshotReport:
    """Build a compact deterministic report from one raw snapshot."""

    instance_reports = [
        build_instance_report(instance, top_findings_limit=top_findings_limit)
        for instance in snapshot.instances
    ]
    severity_counts = _severity_counts(
        finding for instance in snapshot.instances for finding in instance.findings
    )
    return SnapshotReport(
        run_id=snapshot.metadata.run_id,
        source_uri=source_uri,
        application_version=snapshot.metadata.application_version,
        snapshot_schema_version=snapshot.metadata.snapshot_schema_version,
        environment=snapshot.metadata.environment,
        region=snapshot.metadata.region,
        status=snapshot.metadata.status,
        started_at=snapshot.metadata.started_at,
        completed_at=snapshot.metadata.completed_at,
        generated_at=utc_now(),
        severity_counts=severity_counts,
        total_findings=severity_counts.total,
        instances=instance_reports,
    )


def build_fleet_report(
    reports: list[SnapshotReport],
    *,
    service: str,
    environment: str,
    region: str,
) -> FleetReport:
    """Build a report summary across the latest snapshots for one service."""

    severity_counts = _combine_severity_counts(report.severity_counts for report in reports)
    source_regions = {report.region for report in reports}
    if len(source_regions) == 1:
        region = next(iter(source_regions))
    elif len(source_regions) > 1:
        region = "multi-region"
    return FleetReport(
        service=service,
        environment=environment,
        region=region,
        generated_at=utc_now(),
        severity_counts=severity_counts,
        total_findings=severity_counts.total,
        instance_count=sum(len(report.instances) for report in reports),
        snapshots=reports,
    )


def build_instance_report(
    instance: InstanceSnapshot,
    *,
    top_findings_limit: int = 25,
) -> InstanceReport:
    """Build a compact deterministic report for one instance."""

    findings = _sort_findings(instance.findings)
    aws_instance = instance.aws_instance
    return InstanceReport(
        alias=instance.alias,
        db_instance_identifier=instance.db_instance_identifier,
        region=instance.region,
        status=instance.status,
        engine=aws_instance.engine if aws_instance is not None else None,
        engine_version=aws_instance.engine_version if aws_instance is not None else None,
        instance_class=aws_instance.instance_class if aws_instance is not None else None,
        severity_counts=_severity_counts(instance.findings),
        rule_counts=dict(sorted(Counter(finding.rule_id for finding in instance.findings).items())),
        network=_network_report(instance),
        metrics=_metric_report(instance),
        rds_operations=_rds_operations_report(instance),
        postgres=_postgres_report(instance),
        collectors=[
            CollectorReport(
                name=collector.name,
                status=collector.status,
                duration_ms=collector.duration_ms,
                summary=collector.summary,
            )
            for collector in instance.collectors
        ],
        gaps=len(instance.gaps),
        top_findings=[
            FindingReportItem(
                rule_id=finding.rule_id,
                severity=finding.severity,
                category=finding.category,
                resource=finding.resource,
                title=finding.title,
                summary=finding.summary,
                observed=finding.observed,
                recommendation=finding.recommendation,
            )
            for finding in findings[:top_findings_limit]
        ],
    )


def _severity_counts(findings: Iterable[Finding]) -> SeverityCounts:
    counts = Counter(finding.severity for finding in findings)
    return SeverityCounts(
        critical=counts[FindingSeverity.CRITICAL],
        high=counts[FindingSeverity.HIGH],
        medium=counts[FindingSeverity.MEDIUM],
        low=counts[FindingSeverity.LOW],
        info=counts[FindingSeverity.INFO],
    )


def _combine_severity_counts(counts: Iterable[SeverityCounts]) -> SeverityCounts:
    critical = high = medium = low = info = 0
    for item in counts:
        critical += item.critical
        high += item.high
        medium += item.medium
        low += item.low
        info += item.info
    return SeverityCounts(
        critical=critical,
        high=high,
        medium=medium,
        low=low,
        info=info,
    )


def _network_report(instance: InstanceSnapshot) -> NetworkReport:
    aws_instance = instance.aws_instance
    security_groups = instance.aws_security_groups
    return NetworkReport(
        publicly_accessible=(
            aws_instance.publicly_accessible if aws_instance is not None else None
        ),
        public_database_port_ingress=(
            security_groups.public_database_port_ingress if security_groups is not None else None
        ),
        database_port=security_groups.database_port if security_groups is not None else None,
        vpc_id=aws_instance.vpc_id if aws_instance is not None else None,
        security_group_count=(
            len(security_groups.security_groups) if security_groups is not None else 0
        ),
    )


def _metric_report(instance: InstanceSnapshot) -> MetricReport:
    evidence = instance.cloudwatch_metrics
    aws_instance = instance.aws_instance
    allocated_bytes = (
        aws_instance.allocated_storage_gib * BYTES_PER_GIB
        if aws_instance is not None and aws_instance.allocated_storage_gib is not None
        else None
    )
    free_storage = _metric_by_name(evidence, "FreeStorageSpace")
    free_storage_minimum_percent = None
    if free_storage is not None and free_storage.minimum is not None and allocated_bytes:
        free_storage_minimum_percent = (free_storage.minimum / allocated_bytes) * 100

    cpu = _metric_by_name(evidence, "CPUUtilization")
    database_connections = _metric_by_name(evidence, "DatabaseConnections")
    freeable_memory = _metric_by_name(evidence, "FreeableMemory")
    read_latency = _metric_by_name(evidence, "ReadLatency")
    write_latency = _metric_by_name(evidence, "WriteLatency")
    disk_queue_depth = _metric_by_name(evidence, "DiskQueueDepth")
    burst_balance = _metric_by_name(evidence, "BurstBalance")
    return MetricReport(
        cpu_average_percent=cpu.average if cpu is not None else None,
        cpu_maximum_percent=cpu.maximum if cpu is not None else None,
        database_connections_average=(
            database_connections.average if database_connections is not None else None
        ),
        database_connections_maximum=(
            database_connections.maximum if database_connections is not None else None
        ),
        database_connections_latest=(
            database_connections.latest if database_connections is not None else None
        ),
        free_storage_minimum_gib=(
            free_storage.minimum / BYTES_PER_GIB
            if free_storage is not None and free_storage.minimum is not None
            else None
        ),
        free_storage_minimum_percent=free_storage_minimum_percent,
        freeable_memory_minimum_gib=(
            freeable_memory.minimum / BYTES_PER_GIB
            if freeable_memory is not None and freeable_memory.minimum is not None
            else None
        ),
        read_latency_maximum_ms=(
            read_latency.maximum * 1000
            if read_latency is not None and read_latency.maximum is not None
            else None
        ),
        write_latency_maximum_ms=(
            write_latency.maximum * 1000
            if write_latency is not None and write_latency.maximum is not None
            else None
        ),
        disk_queue_depth_maximum=(
            disk_queue_depth.maximum if disk_queue_depth is not None else None
        ),
        burst_balance_minimum_percent=(
            burst_balance.minimum if burst_balance is not None else None
        ),
    )


def _rds_operations_report(instance: InstanceSnapshot) -> RDSOperationsReport:
    evidence = instance.rds_operations
    if evidence is None:
        return RDSOperationsReport()

    return RDSOperationsReport(
        pending_maintenance_count=len(evidence.pending_maintenance),
        recommendation_count=len(evidence.recommendations),
        parameter_group_count=len(evidence.parameter_groups),
        parameter_count=sum(len(group.parameters) for group in evidence.parameter_groups),
        recommendations=[
            RDSRecommendationReport(
                recommendation_id=recommendation.recommendation_id,
                severity=recommendation.severity,
                status=recommendation.status,
                category=recommendation.category,
                summary=(
                    recommendation.description
                    or recommendation.recommendation
                    or recommendation.reason
                ),
            )
            for recommendation in evidence.recommendations
        ],
    )


def _postgres_report(instance: InstanceSnapshot) -> PostgresReport:
    application_database_count = sum(
        1 for database in instance.databases if database.kind == DatabaseKind.APPLICATION
    )
    system_database_count = sum(
        1 for database in instance.databases if database.kind == DatabaseKind.SYSTEM
    )
    role_security = instance.postgres_role_security
    activity = instance.postgres_activity
    return PostgresReport(
        database_count=len(instance.databases),
        application_database_count=application_database_count,
        system_database_count=system_database_count,
        total_connections=activity.total_connections if activity is not None else None,
        idle_in_transaction_connections=(
            activity.idle_in_transaction_connections if activity is not None else None
        ),
        missing_application_name_connections=(
            activity.missing_application_name_connections if activity is not None else None
        ),
        role_count=len(role_security.roles) if role_security is not None else None,
        login_role_count=(
            sum(1 for role in role_security.roles if role.can_login)
            if role_security is not None
            else None
        ),
        membership_count=(len(role_security.memberships) if role_security is not None else None),
    )


def _metric_by_name(
    evidence: RDSCloudWatchMetricsEvidence | None,
    metric_name: str,
) -> MetricSummary | None:
    if evidence is None:
        return None
    for metric in evidence.metrics:
        if metric.metric_name == metric_name:
            return metric
    return None


def _sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda finding: (SEVERITY_ORDER[finding.severity], finding.rule_id, finding.title),
    )
