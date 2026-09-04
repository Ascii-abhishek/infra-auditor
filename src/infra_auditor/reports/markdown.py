"""Markdown rendering for deterministic reports."""

from infra_auditor.models.finding import FindingSeverity
from infra_auditor.reports.models import FleetReport, InstanceReport, SnapshotReport

SEVERITY_ORDER = (
    FindingSeverity.CRITICAL,
    FindingSeverity.HIGH,
    FindingSeverity.MEDIUM,
    FindingSeverity.LOW,
    FindingSeverity.INFO,
)


def render_fleet_markdown(report: FleetReport) -> str:
    """Render a fleet report as Markdown."""

    lines = [
        "# Infra Auditor Fleet Report",
        "",
        f"- Service: `{report.service}`",
        f"- Environment: `{report.environment}`",
        f"- Region: `{report.region}`",
        f"- Generated at: `{report.generated_at.isoformat()}`",
        f"- Instances: `{report.instance_count}`",
        f"- Findings: `{report.total_findings}`",
        "",
        "## Severity",
        "",
        _severity_line(report),
        "",
        "## Instances",
        "",
        "| Instance | Status | Findings | Critical | High | Medium | Low |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for snapshot in report.snapshots:
        for instance in snapshot.instances:
            lines.append(
                "| "
                f"{instance.alias} | {instance.status.value} | "
                f"{instance.severity_counts.total} | "
                f"{instance.severity_counts.critical} | "
                f"{instance.severity_counts.high} | "
                f"{instance.severity_counts.medium} | "
                f"{instance.severity_counts.low} |"
            )

    for snapshot in report.snapshots:
        for instance in snapshot.instances:
            lines.extend(["", *_instance_section(instance, snapshot)])

    return "\n".join(lines).strip() + "\n"


def render_snapshot_markdown(report: SnapshotReport) -> str:
    """Render a single snapshot report as Markdown."""

    lines = [
        "# Infra Auditor Snapshot Report",
        "",
        f"- Run ID: `{report.run_id}`",
        f"- Source: `{report.source_uri or 'unknown'}`",
        f"- Environment: `{report.environment}`",
        f"- Region: `{report.region}`",
        f"- Status: `{report.status.value}`",
        f"- Started at: `{report.started_at.isoformat()}`",
        f"- Findings: `{report.total_findings}`",
        "",
        "## Severity",
        "",
        _severity_line(report),
    ]
    for instance in report.instances:
        lines.extend(["", *_instance_section(instance, report)])
    return "\n".join(lines).strip() + "\n"


def _instance_section(instance: InstanceReport, snapshot: SnapshotReport) -> list[str]:
    lines = [
        f"## {instance.alias}",
        "",
        f"- Run ID: `{snapshot.run_id}`",
        f"- Snapshot: `{snapshot.source_uri or 'unknown'}`",
        f"- Status: `{instance.status.value}`",
        f"- Engine: `{instance.engine or 'unknown'} {instance.engine_version or ''}`",
        f"- Class: `{instance.instance_class or 'unknown'}`",
        f"- Public RDS: `{_bool(instance.network.publicly_accessible)}`",
        f"- Public DB-port ingress: `{_bool(instance.network.public_database_port_ingress)}`",
        f"- Pending maintenance: `{instance.rds_operations.pending_maintenance_count}`",
        f"- RDS recommendations: `{instance.rds_operations.recommendation_count}`",
        f"- PostgreSQL databases: `{instance.postgres.database_count}`",
        f"- PostgreSQL connections: `{instance.postgres.total_connections or 0}`",
        "",
        "### Top Findings",
        "",
    ]
    if not instance.top_findings:
        lines.append("No findings.")
        return lines

    for finding in instance.top_findings:
        lines.extend(
            [
                f"- **{finding.severity.value} {finding.rule_id}**: {finding.title}",
                f"  - Resource: `{finding.resource}`",
                f"  - Summary: {finding.summary}",
            ]
        )
        if finding.recommendation:
            lines.append(f"  - Recommendation: {finding.recommendation}")
    return lines


def _severity_line(report: FleetReport | SnapshotReport) -> str:
    counts = report.severity_counts
    return (
        f"Critical `{counts.critical}`, High `{counts.high}`, "
        f"Medium `{counts.medium}`, Low `{counts.low}`, Info `{counts.info}`"
    )


def _bool(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "yes" if value else "no"
