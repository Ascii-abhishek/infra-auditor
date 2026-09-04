"""Report contracts derived from raw audit snapshots."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from infra_auditor.models.common import CollectionStatus
from infra_auditor.models.finding import FindingObservedValue, FindingSeverity


class SeverityCounts(BaseModel):
    """Finding counts grouped by severity."""

    critical: int = Field(default=0, ge=0)
    high: int = Field(default=0, ge=0)
    medium: int = Field(default=0, ge=0)
    low: int = Field(default=0, ge=0)
    info: int = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid")

    @property
    def total(self) -> int:
        """Total finding count."""

        return self.critical + self.high + self.medium + self.low + self.info


class CollectorReport(BaseModel):
    """Collector status summary for reports and UI."""

    name: str
    status: CollectionStatus
    duration_ms: int = Field(ge=0)
    summary: str | None = None

    model_config = ConfigDict(extra="forbid")


class FindingReportItem(BaseModel):
    """Human-readable finding summary."""

    rule_id: str
    severity: FindingSeverity
    category: str
    resource: str
    title: str
    summary: str
    observed: dict[str, FindingObservedValue] = Field(default_factory=dict)
    recommendation: str | None = None

    model_config = ConfigDict(extra="forbid")


class NetworkReport(BaseModel):
    """RDS network exposure summary."""

    publicly_accessible: bool | None = None
    public_database_port_ingress: bool | None = None
    database_port: int | None = None
    vpc_id: str | None = None
    security_group_count: int = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid")


class MetricReport(BaseModel):
    """Selected operational metric summary in friendly units."""

    cpu_average_percent: float | None = None
    cpu_maximum_percent: float | None = None
    database_connections_average: float | None = None
    database_connections_maximum: float | None = None
    database_connections_latest: float | None = None
    free_storage_minimum_gib: float | None = None
    free_storage_minimum_percent: float | None = None
    freeable_memory_minimum_gib: float | None = None
    read_latency_maximum_ms: float | None = None
    write_latency_maximum_ms: float | None = None
    disk_queue_depth_maximum: float | None = None
    burst_balance_minimum_percent: float | None = None

    model_config = ConfigDict(extra="forbid")


class RDSRecommendationReport(BaseModel):
    """Compact RDS recommendation summary."""

    recommendation_id: str
    severity: str | None = None
    status: str | None = None
    category: str | None = None
    summary: str | None = None

    model_config = ConfigDict(extra="forbid")


class RDSOperationsReport(BaseModel):
    """RDS maintenance, recommendations, and parameter group summary."""

    pending_maintenance_count: int = Field(default=0, ge=0)
    recommendation_count: int = Field(default=0, ge=0)
    parameter_group_count: int = Field(default=0, ge=0)
    parameter_count: int = Field(default=0, ge=0)
    recommendations: list[RDSRecommendationReport] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class PostgresReport(BaseModel):
    """PostgreSQL inventory, activity, and role summary."""

    database_count: int = Field(default=0, ge=0)
    application_database_count: int = Field(default=0, ge=0)
    system_database_count: int = Field(default=0, ge=0)
    total_connections: int | None = Field(default=None, ge=0)
    idle_in_transaction_connections: int | None = Field(default=None, ge=0)
    missing_application_name_connections: int | None = Field(default=None, ge=0)
    role_count: int | None = Field(default=None, ge=0)
    login_role_count: int | None = Field(default=None, ge=0)
    membership_count: int | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid")


class InstanceReport(BaseModel):
    """Report summary for one audited instance."""

    alias: str
    db_instance_identifier: str
    region: str
    status: CollectionStatus
    engine: str | None = None
    engine_version: str | None = None
    instance_class: str | None = None
    severity_counts: SeverityCounts
    rule_counts: dict[str, int] = Field(default_factory=dict)
    network: NetworkReport
    metrics: MetricReport
    rds_operations: RDSOperationsReport
    postgres: PostgresReport
    collectors: list[CollectorReport] = Field(default_factory=list)
    gaps: int = Field(default=0, ge=0)
    top_findings: list[FindingReportItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class SnapshotReport(BaseModel):
    """Report summary for one raw snapshot."""

    run_id: str
    source_uri: str | None = None
    application_version: str
    snapshot_schema_version: int
    environment: str
    region: str
    status: CollectionStatus
    started_at: datetime
    completed_at: datetime
    generated_at: datetime
    severity_counts: SeverityCounts
    total_findings: int = Field(ge=0)
    instances: list[InstanceReport] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class FleetReport(BaseModel):
    """Report summary across latest snapshots for a service."""

    service: str
    environment: str
    region: str
    generated_at: datetime
    severity_counts: SeverityCounts
    total_findings: int = Field(ge=0)
    instance_count: int = Field(ge=0)
    snapshots: list[SnapshotReport] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")
