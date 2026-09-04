"""Deterministic AWS/RDS rules."""

from hashlib import sha256

from infra_auditor.collectors.aws.cloudwatch_metrics import (
    MetricSummary,
    RDSCloudWatchMetricsEvidence,
)
from infra_auditor.collectors.aws.models import RDSInstance
from infra_auditor.collectors.aws.network import RDSSecurityGroupEvidence
from infra_auditor.collectors.aws.rds_operations import RDSOperationsEvidence
from infra_auditor.models.evidence import EvidenceReference
from infra_auditor.models.finding import Finding, FindingSeverity

BYTES_PER_GIB = 1024**3
LOW_FREE_STORAGE_WARNING_RATIO = 0.15
LOW_FREE_STORAGE_HIGH_RATIO = 0.10
CPU_AVERAGE_WARNING_PERCENT = 80.0
CPU_MAX_HIGH_PERCENT = 90.0
FREEABLE_MEMORY_LOW_GIB = 1.0
INACTIVE_RECOMMENDATION_STATUSES = {"dismissed", "resolved"}


def evaluate_aws_rds_findings(
    *,
    run_id: str,
    instance_alias: str,
    aws_instance: RDSInstance | None,
    security_groups: RDSSecurityGroupEvidence | None,
    cloudwatch_metrics: RDSCloudWatchMetricsEvidence | None,
    rds_operations: RDSOperationsEvidence | None,
) -> list[Finding]:
    """Evaluate deterministic AWS/RDS findings."""

    if aws_instance is None:
        return []

    findings: list[Finding] = []
    findings.extend(
        _public_access_findings(
            run_id=run_id,
            instance_alias=instance_alias,
            aws_instance=aws_instance,
            security_groups=security_groups,
        )
    )
    findings.extend(
        _operations_findings(
            run_id=run_id,
            instance_alias=instance_alias,
            rds_operations=rds_operations,
        )
    )
    findings.extend(
        _parameter_group_findings(
            run_id=run_id,
            instance_alias=instance_alias,
            aws_instance=aws_instance,
        )
    )
    findings.extend(
        _metric_findings(
            run_id=run_id,
            instance_alias=instance_alias,
            aws_instance=aws_instance,
            cloudwatch_metrics=cloudwatch_metrics,
        )
    )
    return findings


def _public_access_findings(
    *,
    run_id: str,
    instance_alias: str,
    aws_instance: RDSInstance,
    security_groups: RDSSecurityGroupEvidence | None,
) -> list[Finding]:
    findings: list[Finding] = []
    if aws_instance.publicly_accessible is True:
        findings.append(
            Finding(
                rule_id="CFG009",
                fingerprint=_fingerprint("CFG009", instance_alias),
                category="security/aws/rds",
                severity=FindingSeverity.MEDIUM,
                resource=f"{instance_alias}/rds",
                title="RDS instance is publicly accessible",
                summary=(
                    "The RDS instance is marked PubliclyAccessible. Review attached "
                    "security group ingress and keep allowed source CIDRs narrow."
                ),
                observed={"publicly_accessible": True},
                evidence=[
                    _evidence(
                        run_id=run_id,
                        collector="aws.rds.describe_db_instances",
                        resource=f"{instance_alias}/rds",
                        path="instances[0].aws_instance.publicly_accessible",
                    )
                ],
                recommendation=(
                    "Prefer private RDS access through VPC networking where practical. "
                    "If public access is required, restrict ingress to known source CIDRs."
                ),
            )
        )

    if (
        aws_instance.publicly_accessible is True
        and security_groups is not None
        and security_groups.public_database_port_ingress
    ):
        findings.append(
            Finding(
                rule_id="SEC001",
                fingerprint=_fingerprint("SEC001", instance_alias),
                category="security/aws/rds",
                severity=FindingSeverity.CRITICAL,
                resource=f"{instance_alias}/rds",
                title="Public RDS has unrestricted database-port ingress",
                summary=(
                    "The RDS instance is public and an attached security group allows "
                    "database-port ingress from an unrestricted IPv4 or IPv6 CIDR."
                ),
                observed={
                    "publicly_accessible": True,
                    "database_port": security_groups.database_port,
                    "public_database_port_ingress": True,
                },
                evidence=[
                    _evidence(
                        run_id=run_id,
                        collector="aws.rds.describe_db_instances",
                        resource=f"{instance_alias}/rds",
                        path="instances[0].aws_instance.publicly_accessible",
                    ),
                    _evidence(
                        run_id=run_id,
                        collector="aws.ec2.security_group_ingress",
                        resource=f"{instance_alias}/security-groups",
                        path="instances[0].aws_security_groups",
                    ),
                ],
                recommendation=(
                    "Remove unrestricted database-port ingress. Use private networking, "
                    "VPN, bastion/proxy controls, or tightly scoped source CIDRs."
                ),
            )
        )
    return findings


def _operations_findings(
    *,
    run_id: str,
    instance_alias: str,
    rds_operations: RDSOperationsEvidence | None,
) -> list[Finding]:
    if rds_operations is None:
        return []

    findings: list[Finding] = []
    if rds_operations.pending_maintenance:
        findings.append(
            Finding(
                rule_id="OPS012",
                fingerprint=_fingerprint("OPS012", instance_alias),
                category="operations/aws/rds",
                severity=FindingSeverity.LOW,
                resource=f"{instance_alias}/rds",
                title="RDS instance has pending maintenance",
                summary=(
                    f"The RDS instance has {len(rds_operations.pending_maintenance)} "
                    "pending maintenance action(s)."
                ),
                observed={
                    "pending_maintenance_count": len(rds_operations.pending_maintenance),
                },
                evidence=[
                    _evidence(
                        run_id=run_id,
                        collector="aws.rds.operations",
                        resource=f"{instance_alias}/rds",
                        path="instances[0].rds_operations.pending_maintenance",
                    )
                ],
                recommendation="Review pending maintenance and schedule it in an approved window.",
            )
        )

    for recommendation in rds_operations.recommendations:
        status = recommendation.status.lower() if recommendation.status else ""
        if status in INACTIVE_RECOMMENDATION_STATUSES:
            continue
        severity = _aws_recommendation_severity(recommendation.severity)
        findings.append(
            Finding(
                rule_id="OPS013",
                fingerprint=_fingerprint(
                    "OPS013", instance_alias, recommendation.recommendation_id
                ),
                category="operations/aws/rds",
                severity=severity,
                resource=f"{instance_alias}/rds/recommendation/{recommendation.recommendation_id}",
                title="RDS recommendation is open",
                summary=recommendation.description
                or recommendation.recommendation
                or "RDS has an open recommendation for this instance.",
                observed={
                    "recommendation_id": recommendation.recommendation_id,
                    "status": recommendation.status,
                    "severity": recommendation.severity,
                    "category": recommendation.category,
                },
                evidence=[
                    _evidence(
                        run_id=run_id,
                        collector="aws.rds.operations",
                        resource=f"{instance_alias}/rds",
                        path="instances[0].rds_operations.recommendations",
                    )
                ],
                recommendation=recommendation.recommendation,
            )
        )
    return findings


def _parameter_group_findings(
    *,
    run_id: str,
    instance_alias: str,
    aws_instance: RDSInstance,
) -> list[Finding]:
    findings: list[Finding] = []
    for parameter_group in aws_instance.parameter_groups:
        if parameter_group.status in {None, "in-sync"}:
            continue
        findings.append(
            Finding(
                rule_id="CFG002",
                fingerprint=_fingerprint("CFG002", instance_alias, parameter_group.name),
                category="configuration/aws/rds",
                severity=FindingSeverity.MEDIUM,
                resource=f"{instance_alias}/parameter-group/{parameter_group.name}",
                title="RDS parameter group has pending apply status",
                summary=(
                    f"Parameter group {parameter_group.name} has apply status "
                    f"{parameter_group.status}."
                ),
                observed={
                    "parameter_group": parameter_group.name,
                    "apply_status": parameter_group.status,
                },
                evidence=[
                    _evidence(
                        run_id=run_id,
                        collector="aws.rds.describe_db_instances",
                        resource=f"{instance_alias}/rds",
                        path="instances[0].aws_instance.parameter_groups",
                    )
                ],
                recommendation=(
                    "Review pending parameter changes and reboot/apply in a safe window."
                ),
            )
        )
    return findings


def _metric_findings(
    *,
    run_id: str,
    instance_alias: str,
    aws_instance: RDSInstance,
    cloudwatch_metrics: RDSCloudWatchMetricsEvidence | None,
) -> list[Finding]:
    if cloudwatch_metrics is None:
        return []

    findings: list[Finding] = []
    cpu = _metric_by_name(cloudwatch_metrics, "CPUUtilization")
    if cpu is not None:
        if cpu.maximum is not None and cpu.maximum >= CPU_MAX_HIGH_PERCENT:
            severity = FindingSeverity.HIGH
        elif cpu.average is not None and cpu.average >= CPU_AVERAGE_WARNING_PERCENT:
            severity = FindingSeverity.MEDIUM
        else:
            severity = None

        if severity is not None:
            findings.append(
                Finding(
                    rule_id="OPS007",
                    fingerprint=_fingerprint("OPS007", instance_alias),
                    category="operations/aws/rds",
                    severity=severity,
                    resource=f"{instance_alias}/cloudwatch/CPUUtilization",
                    title="RDS CPU utilization is elevated",
                    summary="CPU utilization crossed the configured audit threshold.",
                    observed={
                        "average_percent": cpu.average,
                        "maximum_percent": cpu.maximum,
                        "lookback_hours": cloudwatch_metrics.lookback_hours,
                    },
                    evidence=[
                        _evidence(
                            run_id=run_id,
                            collector="aws.cloudwatch.rds_metrics",
                            resource=f"{instance_alias}/cloudwatch",
                            path="instances[0].cloudwatch_metrics.metrics",
                        )
                    ],
                    recommendation=(
                        "Review workload changes, expensive queries, connection pressure, "
                        "and whether instance capacity still matches demand."
                    ),
                )
            )

    free_storage = _metric_by_name(cloudwatch_metrics, "FreeStorageSpace")
    if (
        free_storage is not None
        and free_storage.minimum is not None
        and aws_instance.allocated_storage_gib is not None
    ):
        allocated_bytes = aws_instance.allocated_storage_gib * BYTES_PER_GIB
        ratio = free_storage.minimum / allocated_bytes if allocated_bytes else 1.0
        if ratio < LOW_FREE_STORAGE_WARNING_RATIO:
            severity = (
                FindingSeverity.HIGH
                if ratio < LOW_FREE_STORAGE_HIGH_RATIO
                else FindingSeverity.MEDIUM
            )
            findings.append(
                Finding(
                    rule_id="OPS001",
                    fingerprint=_fingerprint("OPS001", instance_alias),
                    category="operations/aws/rds",
                    severity=severity,
                    resource=f"{instance_alias}/cloudwatch/FreeStorageSpace",
                    title="RDS free storage is low",
                    summary="Free storage fell below the configured audit threshold.",
                    observed={
                        "minimum_free_storage_gib": free_storage.minimum / BYTES_PER_GIB,
                        "allocated_storage_gib": aws_instance.allocated_storage_gib,
                        "minimum_free_storage_ratio": ratio,
                        "lookback_hours": cloudwatch_metrics.lookback_hours,
                    },
                    evidence=[
                        _evidence(
                            run_id=run_id,
                            collector="aws.cloudwatch.rds_metrics",
                            resource=f"{instance_alias}/cloudwatch",
                            path="instances[0].cloudwatch_metrics.metrics",
                        ),
                        _evidence(
                            run_id=run_id,
                            collector="aws.rds.describe_db_instances",
                            resource=f"{instance_alias}/rds",
                            path="instances[0].aws_instance.allocated_storage_gib",
                        ),
                    ],
                    recommendation=(
                        "Review storage growth, cleanup options, and storage autoscaling "
                        "before free space becomes operationally risky."
                    ),
                )
            )
    freeable_memory = _metric_by_name(cloudwatch_metrics, "FreeableMemory")
    if (
        freeable_memory is not None
        and freeable_memory.minimum is not None
        and freeable_memory.minimum < FREEABLE_MEMORY_LOW_GIB * BYTES_PER_GIB
    ):
        findings.append(
            Finding(
                rule_id="OPS008",
                fingerprint=_fingerprint("OPS008", instance_alias),
                category="operations/aws/rds",
                severity=FindingSeverity.MEDIUM,
                resource=f"{instance_alias}/cloudwatch/FreeableMemory",
                title="RDS freeable memory is low",
                summary="Freeable memory fell below the configured audit threshold.",
                observed={
                    "minimum_freeable_memory_gib": freeable_memory.minimum / BYTES_PER_GIB,
                    "threshold_gib": FREEABLE_MEMORY_LOW_GIB,
                    "lookback_hours": cloudwatch_metrics.lookback_hours,
                },
                evidence=[
                    _evidence(
                        run_id=run_id,
                        collector="aws.cloudwatch.rds_metrics",
                        resource=f"{instance_alias}/cloudwatch",
                        path="instances[0].cloudwatch_metrics.metrics",
                    )
                ],
                recommendation=(
                    "Review workload memory pressure, connection count, caches, and "
                    "whether the instance class still matches the workload."
                ),
            )
        )
    return findings


def _metric_by_name(
    evidence: RDSCloudWatchMetricsEvidence,
    metric_name: str,
) -> MetricSummary | None:
    for metric in evidence.metrics:
        if metric.metric_name == metric_name:
            return metric
    return None


def _aws_recommendation_severity(value: str | None) -> FindingSeverity:
    normalized = value.upper() if value is not None else ""
    if normalized in {"HIGH", "CRITICAL"}:
        return FindingSeverity.HIGH
    if normalized == "MEDIUM":
        return FindingSeverity.MEDIUM
    return FindingSeverity.LOW


def _evidence(
    *,
    run_id: str,
    collector: str,
    resource: str,
    path: str,
) -> EvidenceReference:
    return EvidenceReference(
        snapshot_run_id=run_id,
        collector=collector,
        resource=resource,
        path=path,
    )


def _fingerprint(*parts: str) -> str:
    return sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
