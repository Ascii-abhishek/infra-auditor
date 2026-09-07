"""Controlled audit-data sync helpers shared by the UI and MCP tools."""

from collections.abc import Callable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from infra_auditor.config import AppSettings, ResourceConfig
from infra_auditor.exceptions import InfraAuditorError
from infra_auditor.models.common import CollectionStatus, utc_now
from infra_auditor.storage.s3_reader import S3SnapshotReader
from infra_auditor.workflows import collect_and_write_instance


class AuditSyncMode(StrEnum):
    """Supported controlled sync modes."""

    LATEST = "latest"
    TODAY = "today"


class AuditSyncAction(StrEnum):
    """Action taken for one configured alias during sync."""

    COLLECTED = "collected"
    SKIPPED = "skipped"
    FAILED = "failed"


class AuditSyncInstanceResult(BaseModel):
    """Result of a controlled read-only sync for one configured alias."""

    instance_alias: str
    action: AuditSyncAction
    status: CollectionStatus | None = None
    manifest_uri: str | None = None
    finding_count: int | None = Field(default=None, ge=0)
    message: str | None = None
    error: str | None = None

    model_config = ConfigDict(extra="forbid")


class AuditSyncResult(BaseModel):
    """Result of syncing immutable audit artifacts."""

    environment: str
    region: str
    mode: AuditSyncMode
    synced_at: str
    results: list[AuditSyncInstanceResult] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


OnTargetStart = Callable[[str], None]
OnTargetComplete = Callable[[AuditSyncInstanceResult], None]


def sync_audit_data(
    *,
    settings: AppSettings,
    resource_config: ResourceConfig,
    reader: S3SnapshotReader,
    instance_alias: str | None = None,
    mode: AuditSyncMode = AuditSyncMode.LATEST,
    on_target_start: OnTargetStart | None = None,
    on_target_complete: OnTargetComplete | None = None,
) -> AuditSyncResult:
    """Run approved read-only collection for one alias or all configured aliases."""

    aliases = [instance_alias] if instance_alias else list(resource_config.instances)
    results: list[AuditSyncInstanceResult] = []
    today = utc_now().date().isoformat()
    for alias in aliases:
        if on_target_start is not None:
            on_target_start(alias)
        result = _sync_one_alias(
            settings=settings,
            resource_config=resource_config,
            reader=reader,
            alias=alias,
            mode=mode,
            today=today,
        )
        results.append(result)
        if on_target_complete is not None:
            on_target_complete(result)

    return AuditSyncResult(
        environment=settings.environment,
        region=settings.aws_region,
        mode=mode,
        synced_at=utc_now().isoformat(),
        results=results,
    )


def _sync_one_alias(
    *,
    settings: AppSettings,
    resource_config: ResourceConfig,
    reader: S3SnapshotReader,
    alias: str,
    mode: AuditSyncMode,
    today: str,
) -> AuditSyncInstanceResult:
    if alias not in resource_config.instances:
        return AuditSyncInstanceResult(
            instance_alias=alias,
            action=AuditSyncAction.FAILED,
            error=f"unknown instance alias: {alias}",
        )

    if mode == AuditSyncMode.TODAY:
        existing_uri = _latest_manifest_uri_for_date(
            settings=settings,
            resource_config=resource_config,
            reader=reader,
            alias=alias,
            date=today,
        )
        if existing_uri is not None:
            return AuditSyncInstanceResult(
                instance_alias=alias,
                action=AuditSyncAction.SKIPPED,
                manifest_uri=existing_uri,
                message=f"completed artifact family already exists for UTC day {today}",
            )

    try:
        result = collect_and_write_instance(
            settings=settings,
            resource_config=resource_config,
            alias=alias,
        )
    except InfraAuditorError as exc:
        return AuditSyncInstanceResult(
            instance_alias=alias,
            action=AuditSyncAction.FAILED,
            error=str(exc),
        )

    instance = result.snapshot.instances[0] if result.snapshot.instances else None
    return AuditSyncInstanceResult(
        instance_alias=alias,
        action=AuditSyncAction.COLLECTED,
        status=result.snapshot.metadata.status,
        manifest_uri=result.manifest_uri,
        finding_count=len(instance.findings) if instance is not None else 0,
        message="collected latest read-only audit artifact family",
    )


def _latest_manifest_uri_for_date(
    *,
    settings: AppSettings,
    resource_config: ResourceConfig,
    reader: S3SnapshotReader,
    alias: str,
    date: str,
) -> str | None:
    region = resource_config.region_for_instance(alias)
    try:
        objects = reader.list_manifests(
            environment=settings.environment,
            region=region,
            instance_alias=alias,
            limit=1,
        )
    except InfraAuditorError:
        return None
    if not objects:
        return None
    return objects[0].uri if f"/dt={date}/" in objects[0].key else None
