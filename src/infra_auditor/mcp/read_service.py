"""Read-only service behind the MCP audit-data tools."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from infra_auditor.collectors.aws.client import (
    create_boto3_session,
    create_s3_read_client,
)
from infra_auditor.config import AppSettings, ResourceConfig, load_resource_config
from infra_auditor.exceptions import ConfigurationError, InfraAuditorError
from infra_auditor.models.finding import FindingSeverity
from infra_auditor.models.snapshot_split import (
    SPLIT_SERVICE_SUBSERVICES,
    SnapshotSplitArtifact,
    SnapshotSplitService,
    SnapshotSplitSubservice,
    split_definition_for,
)
from infra_auditor.reports import build_fleet_report, build_snapshot_report
from infra_auditor.reports.models import FindingReportItem, FleetReport, SnapshotReport
from infra_auditor.storage.s3 import DEFAULT_SNAPSHOT_SERVICE
from infra_auditor.storage.s3_reader import (
    S3SnapshotObject,
    S3SnapshotReader,
    S3SnapshotSplitObject,
)
from infra_auditor.sync import (
    AuditSyncInstanceResult,
    AuditSyncMode,
    AuditSyncResult,
    sync_audit_data,
)

ReportSnapshotService = Literal["rds-postgres"]
SplitSnapshotServiceName = Literal["rds", "postgres", "audit-heuristics"]
SplitSnapshotSubserviceName = Literal[
    "instance",
    "operations",
    "database-inventory",
    "activity-summary",
    "role-security",
    "ec2-security-groups",
    "cloudwatch-rds-metrics",
    "deterministic-findings",
]
SeverityFilter = Literal["all", "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
DEFAULT_REPORT_SNAPSHOT_SERVICE: ReportSnapshotService = "rds-postgres"

MAX_LIST_LIMIT = 100
MAX_FINDINGS_LIMIT = 250
REPORT_FINDINGS_LIMIT = 500


class AuditInstanceSummary(BaseModel):
    """Configured audit target visible to reader-facing tools."""

    alias: str
    db_instance_identifier: str
    region: str

    model_config = ConfigDict(extra="forbid")


class FleetReportEnvelope(BaseModel):
    """Fleet report plus per-instance load errors."""

    report: FleetReport | None = None
    errors: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class InstanceFindingsResponse(BaseModel):
    """Filtered finding summaries for one latest instance report."""

    instance_alias: str
    run_id: str
    source_uri: str
    total_returned: int = Field(ge=0)
    findings: list[FindingReportItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class SnapshotSplitArtifactResponse(BaseModel):
    """Latest split raw snapshot artifact with source location."""

    source_uri: str
    artifact: SnapshotSplitArtifact

    model_config = ConfigDict(extra="forbid")


type SyncAuditInstanceResult = AuditSyncInstanceResult
type SyncLatestAuditDataResponse = AuditSyncResult
type SyncTodayAuditDataResponse = AuditSyncResult


class AuditDataBoundary(BaseModel):
    """Static MCP data-access boundary advertised to hosts and operators."""

    report_snapshot_services: list[str]
    split_snapshot_services: dict[str, list[str]]
    forbidden_capabilities: list[str]
    controlled_sync_capability: str

    model_config = ConfigDict(extra="forbid")


class AuditReadService:
    """Read approved snapshot/report data through fixed S3 prefixes."""

    def __init__(
        self,
        *,
        settings: AppSettings,
        resource_config: ResourceConfig,
        reader: S3SnapshotReader,
    ) -> None:
        self._settings = settings
        self._resource_config = resource_config
        self._reader = reader

    @classmethod
    def from_settings(cls, settings: AppSettings | None = None) -> "AuditReadService":
        """Create the read service from runtime settings and the configured registry."""

        settings = settings or AppSettings()
        resource_config = load_resource_config(settings.resource_config_path)
        session = create_boto3_session(settings)
        reader = S3SnapshotReader(
            create_s3_read_client(session, settings.aws_region),
            settings.snapshot_bucket,
        )
        return cls(settings=settings, resource_config=resource_config, reader=reader)

    def describe_data_boundary(self) -> AuditDataBoundary:
        """Describe the intentionally narrow MCP data boundary."""

        return AuditDataBoundary(
            report_snapshot_services=[DEFAULT_SNAPSHOT_SERVICE],
            split_snapshot_services={
                service.value: [subservice.value for subservice in subservices]
                for service, subservices in SPLIT_SERVICE_SUBSERVICES.items()
            },
            forbidden_capabilities=[
                "generic SQL execution",
                "arbitrary AWS API calls",
                "arbitrary S3 key or prefix reads",
                "secret reads or credential disclosure",
                "query text retrieval",
                "automatic remediation",
            ],
            controlled_sync_capability=(
                "sync_latest_audit_data and sync_today_audit_data may run the "
                "existing read-only collector for configured aliases and write "
                "immutable S3 audit artifacts; the today mode skips aliases that "
                "already have a full snapshot and all current split artifacts "
                "for the current UTC day"
            ),
        )

    def list_instances(self) -> list[AuditInstanceSummary]:
        """List configured audit targets without secret IDs."""

        return [
            AuditInstanceSummary(
                alias=alias,
                db_instance_identifier=instance.db_instance_identifier,
                region=self._resource_config.region_for_instance(alias),
            )
            for alias, instance in self._resource_config.instances.items()
        ]

    def list_snapshots(
        self,
        *,
        instance_alias: str,
        service: ReportSnapshotService = DEFAULT_REPORT_SNAPSHOT_SERVICE,
        limit: int = 25,
    ) -> list[S3SnapshotObject]:
        """List full compatibility snapshots for one configured instance."""

        self._validate_report_service(service)
        region = self._region_for_instance(instance_alias)
        return self._reader.list_snapshots(
            environment=self._settings.environment,
            region=region,
            service=service,
            instance_alias=instance_alias,
            limit=_bounded_limit(limit, MAX_LIST_LIMIT),
        )

    def get_latest_instance_report(
        self,
        *,
        instance_alias: str,
        service: ReportSnapshotService = DEFAULT_REPORT_SNAPSHOT_SERVICE,
    ) -> SnapshotReport:
        """Load the latest deterministic report for one configured instance."""

        self._validate_report_service(service)
        region = self._region_for_instance(instance_alias)
        item, snapshot = self._reader.read_latest_snapshot(
            environment=self._settings.environment,
            region=region,
            service=service,
            instance_alias=instance_alias,
        )
        return build_snapshot_report(
            snapshot,
            source_uri=item.uri,
            top_findings_limit=REPORT_FINDINGS_LIMIT,
        )

    def get_fleet_report(
        self,
        *,
        service: ReportSnapshotService = DEFAULT_REPORT_SNAPSHOT_SERVICE,
    ) -> FleetReportEnvelope:
        """Load latest per-instance reports and combine them into a fleet report."""

        self._validate_report_service(service)
        reports: list[SnapshotReport] = []
        errors: dict[str, str] = {}
        for alias in self._resource_config.instances:
            region = self._resource_config.region_for_instance(alias)
            try:
                item, snapshot = self._reader.read_latest_snapshot(
                    environment=self._settings.environment,
                    region=region,
                    service=service,
                    instance_alias=alias,
                )
            except InfraAuditorError as exc:
                errors[alias] = str(exc)
                continue
            reports.append(
                build_snapshot_report(
                    snapshot,
                    source_uri=item.uri,
                    top_findings_limit=REPORT_FINDINGS_LIMIT,
                )
            )

        report = (
            build_fleet_report(
                reports,
                service=service,
                environment=self._settings.environment,
                region=self._settings.aws_region,
            )
            if reports
            else None
        )
        return FleetReportEnvelope(report=report, errors=errors)

    def get_instance_findings(
        self,
        *,
        instance_alias: str,
        severity: SeverityFilter = "all",
        rule_id: str | None = None,
        limit: int = 50,
    ) -> InstanceFindingsResponse:
        """Load filtered finding summaries from the latest instance report."""

        report = self.get_latest_instance_report(instance_alias=instance_alias)
        instance_report = report.instances[0] if report.instances else None
        findings = list(instance_report.top_findings if instance_report is not None else [])
        if severity != "all":
            severity_value = FindingSeverity(severity)
            findings = [finding for finding in findings if finding.severity == severity_value]
        if rule_id:
            findings = [finding for finding in findings if finding.rule_id == rule_id]
        bounded_limit = _bounded_limit(limit, MAX_FINDINGS_LIMIT)
        findings = findings[:bounded_limit]
        return InstanceFindingsResponse(
            instance_alias=instance_alias,
            run_id=report.run_id,
            source_uri=report.source_uri or "",
            total_returned=len(findings),
            findings=findings,
        )

    def list_snapshot_split_artifacts(
        self,
        *,
        instance_alias: str,
        service: SplitSnapshotServiceName,
        subservice: SplitSnapshotSubserviceName,
        limit: int = 25,
    ) -> list[S3SnapshotSplitObject]:
        """List split raw snapshot artifacts for an approved service boundary."""

        split_service = SnapshotSplitService(service)
        split_subservice = SnapshotSplitSubservice(subservice)
        _validate_split_definition(split_service, split_subservice)
        region = self._region_for_instance(instance_alias)
        return self._reader.list_snapshot_split_artifacts(
            environment=self._settings.environment,
            region=region,
            service=split_service,
            subservice=split_subservice,
            instance_alias=instance_alias,
            limit=_bounded_limit(limit, MAX_LIST_LIMIT),
        )

    def get_latest_snapshot_split_artifact(
        self,
        *,
        instance_alias: str,
        service: SplitSnapshotServiceName,
        subservice: SplitSnapshotSubserviceName,
    ) -> SnapshotSplitArtifactResponse:
        """Load the latest split raw artifact for an approved service boundary."""

        split_service = SnapshotSplitService(service)
        split_subservice = SnapshotSplitSubservice(subservice)
        _validate_split_definition(split_service, split_subservice)
        region = self._region_for_instance(instance_alias)
        item, artifact = self._reader.read_latest_snapshot_split_artifact(
            environment=self._settings.environment,
            region=region,
            service=split_service,
            subservice=split_subservice,
            instance_alias=instance_alias,
        )
        return SnapshotSplitArtifactResponse(source_uri=item.uri, artifact=artifact)

    def sync_latest_audit_data(
        self,
        *,
        instance_alias: str | None = None,
    ) -> SyncLatestAuditDataResponse:
        """Run the existing read-only collector workflow for one alias or all aliases."""

        return sync_audit_data(
            settings=self._settings,
            resource_config=self._resource_config,
            reader=self._reader,
            instance_alias=instance_alias,
            mode=AuditSyncMode.LATEST,
        )

    def sync_today_audit_data(
        self,
        *,
        instance_alias: str | None = None,
    ) -> SyncTodayAuditDataResponse:
        """Collect only aliases missing a snapshot for the current UTC day."""

        return sync_audit_data(
            settings=self._settings,
            resource_config=self._resource_config,
            reader=self._reader,
            instance_alias=instance_alias,
            mode=AuditSyncMode.TODAY,
        )

    def _region_for_instance(self, alias: str) -> str:
        if alias not in self._resource_config.instances:
            raise ConfigurationError(f"unknown instance alias: {alias}")
        return self._resource_config.region_for_instance(alias)

    @staticmethod
    def _validate_report_service(service: str) -> None:
        if service != DEFAULT_SNAPSHOT_SERVICE:
            raise ConfigurationError(f"unsupported report snapshot service: {service}")


def _bounded_limit(value: int, maximum: int) -> int:
    if value < 1:
        raise ConfigurationError("limit must be at least 1")
    return min(value, maximum)


def _validate_split_definition(
    service: SnapshotSplitService,
    subservice: SnapshotSplitSubservice,
) -> None:
    try:
        split_definition_for(service, subservice)
    except KeyError as exc:
        raise ConfigurationError(
            f"unsupported split artifact service/subservice: {service.value}/{subservice.value}"
        ) from exc
