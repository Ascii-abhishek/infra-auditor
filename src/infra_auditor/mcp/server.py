"""MCP server exposing read-only infra-auditor data tools."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from infra_auditor.mcp.read_service import (
    DEFAULT_REPORT_SNAPSHOT_SERVICE,
    AuditDataBoundary,
    AuditInstanceSummary,
    AuditReadService,
    FleetReportEnvelope,
    InstanceFindingsResponse,
    ReportSnapshotService,
    SeverityFilter,
    SnapshotSplitArtifactResponse,
    SplitSnapshotServiceName,
    SplitSnapshotSubserviceName,
    SyncLatestAuditDataResponse,
    SyncTodayAuditDataResponse,
)
from infra_auditor.reports.models import SnapshotReport
from infra_auditor.storage.s3_reader import S3SnapshotObject, S3SnapshotSplitObject

READ_ONLY_ANNOTATIONS = ToolAnnotations(read_only_hint=True, open_world_hint=False)
SYNC_ANNOTATIONS = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=False,
)
TODAY_SYNC_ANNOTATIONS = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)


def create_mcp_server(read_service: AuditReadService | None = None) -> MCPServer:
    """Create the constrained MCP server."""

    service = read_service or AuditReadService.from_settings()
    server = MCPServer("infra-auditor")

    @server.tool(
        title="Describe audit data boundary",
        annotations=READ_ONLY_ANNOTATIONS,
    )
    def describe_audit_data_boundary() -> AuditDataBoundary:
        """Describe the approved MCP data boundary and explicitly forbidden capabilities."""

        return service.describe_data_boundary()

    @server.tool(
        title="List audit instances",
        annotations=READ_ONLY_ANNOTATIONS,
    )
    def list_audit_instances() -> list[AuditInstanceSummary]:
        """List configured audit targets without secret IDs."""

        return service.list_instances()

    @server.tool(
        title="List audit snapshots",
        annotations=READ_ONLY_ANNOTATIONS,
    )
    def list_audit_snapshots(
        instance_alias: Annotated[str, Field(description="Configured instance alias.")],
        service_name: Annotated[
            ReportSnapshotService,
            Field(description="Approved full snapshot service partition."),
        ] = DEFAULT_REPORT_SNAPSHOT_SERVICE,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Maximum objects to list."),
        ] = 25,
    ) -> list[S3SnapshotObject]:
        """List full compatibility snapshots for one configured instance."""

        return service.list_snapshots(
            instance_alias=instance_alias,
            service=service_name,
            limit=limit,
        )

    @server.tool(
        title="Get latest instance report",
        annotations=READ_ONLY_ANNOTATIONS,
    )
    def get_latest_instance_report(
        instance_alias: Annotated[str, Field(description="Configured instance alias.")],
        service_name: Annotated[
            ReportSnapshotService,
            Field(description="Approved full snapshot service partition."),
        ] = DEFAULT_REPORT_SNAPSHOT_SERVICE,
    ) -> SnapshotReport:
        """Load the latest deterministic report for one configured instance."""

        return service.get_latest_instance_report(
            instance_alias=instance_alias,
            service=service_name,
        )

    @server.tool(
        title="Get fleet report",
        annotations=READ_ONLY_ANNOTATIONS,
    )
    def get_fleet_report(
        service_name: Annotated[
            ReportSnapshotService,
            Field(description="Approved full snapshot service partition."),
        ] = DEFAULT_REPORT_SNAPSHOT_SERVICE,
    ) -> FleetReportEnvelope:
        """Load latest per-instance reports and combine them into a fleet report."""

        return service.get_fleet_report(service=service_name)

    @server.tool(
        title="Get instance findings",
        annotations=READ_ONLY_ANNOTATIONS,
    )
    def get_instance_findings(
        instance_alias: Annotated[str, Field(description="Configured instance alias.")],
        severity: Annotated[
            SeverityFilter,
            Field(description="Optional finding severity filter."),
        ] = "all",
        rule_id: Annotated[
            str | None,
            Field(description="Optional exact deterministic rule ID filter."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=250, description="Maximum findings to return."),
        ] = 50,
    ) -> InstanceFindingsResponse:
        """Load filtered finding summaries from the latest instance report."""

        return service.get_instance_findings(
            instance_alias=instance_alias,
            severity=severity,
            rule_id=rule_id,
            limit=limit,
        )

    @server.tool(
        title="List snapshot split artifacts",
        annotations=READ_ONLY_ANNOTATIONS,
    )
    def list_snapshot_split_artifacts(
        instance_alias: Annotated[str, Field(description="Configured instance alias.")],
        service_name: Annotated[
            SplitSnapshotServiceName,
            Field(description="Approved split service."),
        ],
        subservice_name: Annotated[
            SplitSnapshotSubserviceName,
            Field(description="Approved split subservice for the selected service."),
        ],
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Maximum split artifacts to list."),
        ] = 25,
    ) -> list[S3SnapshotSplitObject]:
        """List split raw snapshot artifacts for an approved service boundary."""

        return service.list_snapshot_split_artifacts(
            instance_alias=instance_alias,
            service=service_name,
            subservice=subservice_name,
            limit=limit,
        )

    @server.tool(
        title="Get latest snapshot split artifact",
        annotations=READ_ONLY_ANNOTATIONS,
    )
    def get_latest_snapshot_split_artifact(
        instance_alias: Annotated[str, Field(description="Configured instance alias.")],
        service_name: Annotated[
            SplitSnapshotServiceName,
            Field(description="Approved split service."),
        ],
        subservice_name: Annotated[
            SplitSnapshotSubserviceName,
            Field(description="Approved split subservice for the selected service."),
        ],
    ) -> SnapshotSplitArtifactResponse:
        """Load the latest split raw artifact for an approved service boundary."""

        return service.get_latest_snapshot_split_artifact(
            instance_alias=instance_alias,
            service=service_name,
            subservice=subservice_name,
        )

    @server.tool(
        title="Sync latest audit data",
        annotations=SYNC_ANNOTATIONS,
    )
    def sync_latest_audit_data(
        instance_alias: Annotated[
            str | None,
            Field(
                description=(
                    "Optional configured instance alias. When omitted, syncs all configured "
                    "instances."
                )
            ),
        ] = None,
    ) -> SyncLatestAuditDataResponse:
        """Run the existing read-only collector workflow and write immutable S3 artifacts."""

        return service.sync_latest_audit_data(instance_alias=instance_alias)

    @server.tool(
        title="Sync today's audit data",
        annotations=TODAY_SYNC_ANNOTATIONS,
    )
    def sync_today_audit_data(
        instance_alias: Annotated[
            str | None,
            Field(
                description=(
                    "Optional configured instance alias. When omitted, syncs all configured "
                    "instances that do not already have a snapshot for the current UTC day."
                )
            ),
        ] = None,
    ) -> SyncTodayAuditDataResponse:
        """Collect only aliases missing a snapshot for the current UTC day."""

        return service.sync_today_audit_data(instance_alias=instance_alias)

    return server


def main() -> None:
    """Run the MCP server over stdio."""

    create_mcp_server().run()


if __name__ == "__main__":
    main()
