"""Deterministic PostgreSQL activity rules."""

from hashlib import sha256

from infra_auditor.collectors.postgres.activity import PostgresActivityEvidence
from infra_auditor.models.evidence import EvidenceReference
from infra_auditor.models.finding import Finding, FindingSeverity

IDLE_IN_TRANSACTION_WARNING_COUNT = 1
MISSING_APPLICATION_NAME_WARNING_COUNT = 1
CONNECTION_CONCENTRATION_WARNING_RATIO = 0.50
LONG_TRANSACTION_WARNING_SECONDS = 15 * 60


def evaluate_postgres_activity_findings(
    *,
    run_id: str,
    instance_alias: str,
    activity: PostgresActivityEvidence | None,
) -> list[Finding]:
    """Evaluate deterministic findings from aggregated activity evidence."""

    if activity is None:
        return []

    findings: list[Finding] = []
    if activity.idle_in_transaction_connections >= IDLE_IN_TRANSACTION_WARNING_COUNT:
        findings.append(
            Finding(
                rule_id="OPS003",
                fingerprint=_fingerprint("OPS003", instance_alias),
                category="operations/postgres",
                severity=FindingSeverity.MEDIUM,
                resource=f"{instance_alias}/postgres/activity",
                title="PostgreSQL has idle-in-transaction sessions",
                summary=(
                    "One or more sessions are idle in transaction, which can hold locks "
                    "and delay vacuum cleanup."
                ),
                observed={
                    "idle_in_transaction_connections": activity.idle_in_transaction_connections,
                    "total_connections": activity.total_connections,
                },
                evidence=[
                    _evidence(
                        run_id=run_id,
                        collector="postgres.activity_summary",
                        resource=f"{instance_alias}/postgres/activity",
                        path="instances[0].postgres_activity",
                    )
                ],
                recommendation=(
                    "Identify the owning application path and make transaction scopes explicit "
                    "and short-lived."
                ),
            )
        )

    if activity.missing_application_name_connections >= MISSING_APPLICATION_NAME_WARNING_COUNT:
        findings.append(
            Finding(
                rule_id="OPS015",
                fingerprint=_fingerprint("OPS015", instance_alias),
                category="operations/postgres",
                severity=FindingSeverity.LOW,
                resource=f"{instance_alias}/postgres/activity",
                title="PostgreSQL sessions are missing application names",
                summary=(
                    "Some sessions do not set application_name, making ownership and "
                    "incident triage harder."
                ),
                observed={
                    "missing_application_name_connections": (
                        activity.missing_application_name_connections
                    ),
                    "total_connections": activity.total_connections,
                },
                evidence=[
                    _evidence(
                        run_id=run_id,
                        collector="postgres.activity_summary",
                        resource=f"{instance_alias}/postgres/activity",
                        path="instances[0].postgres_activity",
                    )
                ],
                recommendation=(
                    "Set application_name in each service connection string or client config."
                ),
            )
        )

    if activity.total_connections > 0:
        for group in activity.groups:
            ratio = group.connection_count / activity.total_connections
            if group.connection_count > 1 and ratio >= CONNECTION_CONCENTRATION_WARNING_RATIO:
                findings.append(
                    Finding(
                        rule_id="OPS014",
                        fingerprint=_fingerprint(
                            "OPS014",
                            instance_alias,
                            group.database_name or "",
                            group.role_name or "",
                            group.application_name or "",
                            group.client_address or "",
                            group.state or "",
                        ),
                        category="operations/postgres",
                        severity=FindingSeverity.LOW,
                        resource=f"{instance_alias}/postgres/activity",
                        title="PostgreSQL connections are concentrated",
                        summary=(
                            "A single database/user/application/client/state group owns a "
                            "large share of current connections."
                        ),
                        observed={
                            "connection_count": group.connection_count,
                            "total_connections": activity.total_connections,
                            "connection_ratio": ratio,
                            "database_name": group.database_name,
                            "role_name": group.role_name,
                            "application_name": group.application_name,
                            "client_address": group.client_address,
                            "state": group.state,
                        },
                        evidence=[
                            _evidence(
                                run_id=run_id,
                                collector="postgres.activity_summary",
                                resource=f"{instance_alias}/postgres/activity",
                                path="instances[0].postgres_activity.groups",
                            )
                        ],
                        recommendation=(
                            "Review whether this connection ownership is expected and whether "
                            "pool sizing should be adjusted."
                        ),
                    )
                )

            if (
                group.oldest_transaction_age_seconds is not None
                and group.oldest_transaction_age_seconds >= LONG_TRANSACTION_WARNING_SECONDS
            ):
                findings.append(
                    Finding(
                        rule_id="OPS005",
                        fingerprint=_fingerprint(
                            "OPS005",
                            instance_alias,
                            group.database_name or "",
                            group.role_name or "",
                            group.application_name or "",
                            group.client_address or "",
                            group.state or "",
                        ),
                        category="operations/postgres",
                        severity=FindingSeverity.MEDIUM,
                        resource=f"{instance_alias}/postgres/activity",
                        title="PostgreSQL transaction has been open for a long time",
                        summary=(
                            "A grouped session has an old transaction age above the audit "
                            "threshold."
                        ),
                        observed={
                            "oldest_transaction_age_seconds": (
                                group.oldest_transaction_age_seconds
                            ),
                            "threshold_seconds": LONG_TRANSACTION_WARNING_SECONDS,
                            "database_name": group.database_name,
                            "role_name": group.role_name,
                            "application_name": group.application_name,
                            "client_address": group.client_address,
                            "state": group.state,
                        },
                        evidence=[
                            _evidence(
                                run_id=run_id,
                                collector="postgres.activity_summary",
                                resource=f"{instance_alias}/postgres/activity",
                                path="instances[0].postgres_activity.groups",
                            )
                        ],
                        recommendation=(
                            "Inspect the owning service path and shorten or timeout the "
                            "transaction."
                        ),
                    )
                )
    return findings


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
