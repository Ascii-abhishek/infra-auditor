from datetime import UTC, datetime
from typing import Any

import pytest

from infra_auditor.config import AppSettings, ResourceConfig
from infra_auditor.mcp.read_service import AuditReadService
from infra_auditor.mcp.server import create_mcp_server
from infra_auditor.models.common import CollectionStatus
from infra_auditor.models.finding import Finding, FindingSeverity
from infra_auditor.models.snapshot import AuditSnapshot, InstanceSnapshot, RunMetadata
from infra_auditor.models.snapshot_split import (
    SnapshotSplitService,
    SnapshotSplitSubservice,
    build_snapshot_split_artifacts,
)
from infra_auditor.storage.s3_reader import S3SnapshotObject, S3SnapshotSplitObject
from infra_auditor.sync import AuditSyncAction, AuditSyncMode
from infra_auditor.workflows import SnapshotWriteResult


class FakeReader:
    def __init__(self, snapshot: AuditSnapshot, *, split_objects_exist: bool = True) -> None:
        self.snapshot = snapshot
        self.split_objects_exist = split_objects_exist
        self.object = S3SnapshotObject(
            bucket="infra-audit-rl-dev",
            key=(
                "raw/snapshots/snapshot_schema=1/env=dev/region=ap-south-1/"
                "service=rds-postgres/instance=db/dt=2026-09-04/20260904T070000Z.json"
            ),
            uri=(
                "s3://infra-audit-rl-dev/raw/snapshots/snapshot_schema=1/env=dev/"
                "region=ap-south-1/service=rds-postgres/instance=db/dt=2026-09-04/"
                "20260904T070000Z.json"
            ),
            size_bytes=100,
            last_modified=datetime(2026, 9, 4, 7, 0, tzinfo=UTC),
        )
        self.split_artifact = build_snapshot_split_artifacts(snapshot)[7]
        self.split_object = S3SnapshotSplitObject(
            bucket="infra-audit-rl-dev",
            key=(
                "raw/snapshots/artifact_schema=1/snapshot_schema=1/env=dev/"
                "region=ap-south-1/service=audit-heuristics/subservice=deterministic-findings/"
                "instance=db/dt=2026-09-04/20260904T070000Z.json"
            ),
            uri=(
                "s3://infra-audit-rl-dev/raw/snapshots/artifact_schema=1/"
                "snapshot_schema=1/env=dev/region=ap-south-1/service=audit-heuristics/"
                "subservice=deterministic-findings/instance=db/"
                "dt=2026-09-04/20260904T070000Z.json"
            ),
            size_bytes=50,
            last_modified=datetime(2026, 9, 4, 7, 0, tzinfo=UTC),
            service=SnapshotSplitService.AUDIT_HEURISTICS,
            subservice=SnapshotSplitSubservice.AUDIT_DETERMINISTIC_FINDINGS,
        )
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list_snapshots(self, **kwargs: Any) -> list[S3SnapshotObject]:
        self.calls.append(("list_snapshots", kwargs))
        return [self.object]

    def read_latest_snapshot(self, **kwargs: Any) -> tuple[S3SnapshotObject, AuditSnapshot]:
        self.calls.append(("read_latest_snapshot", kwargs))
        return self.object, self.snapshot

    def list_snapshot_split_artifacts(self, **kwargs: Any) -> list[S3SnapshotSplitObject]:
        self.calls.append(("list_snapshot_split_artifacts", kwargs))
        if not self.split_objects_exist:
            return []
        return [self.split_object]

    def read_latest_snapshot_split_artifact(
        self,
        **kwargs: Any,
    ) -> tuple[S3SnapshotSplitObject, object]:
        self.calls.append(("read_latest_snapshot_split_artifact", kwargs))
        return self.split_object, self.split_artifact


def test_audit_read_service_exposes_configured_reports_and_splits() -> None:
    service = AuditReadService(
        settings=AppSettings(_env_file=None),
        resource_config=_resource_config(),
        reader=FakeReader(_snapshot()),
    )

    assert [instance.alias for instance in service.list_instances()] == ["db"]

    boundary = service.describe_data_boundary()
    assert boundary.report_snapshot_services == ["rds-postgres"]
    assert boundary.split_snapshot_services["audit-heuristics"] == ["deterministic-findings"]
    assert "rds" in boundary.split_snapshot_services
    assert "cloudwatch-rds-metrics" in boundary.split_snapshot_services["rds"]
    assert "generic SQL execution" in boundary.forbidden_capabilities

    fleet = service.get_fleet_report()
    assert fleet.report is not None
    assert fleet.report.total_findings == 1
    findings = service.get_instance_findings(instance_alias="db", severity="HIGH")
    assert [finding.rule_id for finding in findings.findings] == ["SEC002"]

    split_objects = service.list_snapshot_split_artifacts(
        instance_alias="db",
        service="audit-heuristics",
        subservice="deterministic-findings",
    )
    split = service.get_latest_snapshot_split_artifact(
        instance_alias="db",
        service="audit-heuristics",
        subservice="deterministic-findings",
    )
    assert split_objects[0].subservice == SnapshotSplitSubservice.AUDIT_DETERMINISTIC_FINDINGS
    assert split.artifact.metadata.service == SnapshotSplitService.AUDIT_HEURISTICS


def test_create_mcp_server_registers_with_injected_read_service() -> None:
    service = AuditReadService(
        settings=AppSettings(_env_file=None),
        resource_config=_resource_config(),
        reader=FakeReader(_snapshot()),
    )

    server = create_mcp_server(read_service=service)

    assert server.name == "infra-auditor"


def test_sync_latest_audit_data_uses_configured_collection_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _snapshot()
    calls: list[str] = []

    def fake_collect_and_write_instance(**kwargs: Any) -> SnapshotWriteResult:
        calls.append(str(kwargs["alias"]))
        return SnapshotWriteResult(
            snapshot=snapshot,
            snapshot_uri="s3://infra-audit-rl-dev/raw/snapshots/example.json",
        )

    monkeypatch.setattr(
        "infra_auditor.sync.collect_and_write_instance",
        fake_collect_and_write_instance,
    )
    service = AuditReadService(
        settings=AppSettings(_env_file=None),
        resource_config=_resource_config(),
        reader=FakeReader(snapshot),
    )

    response = service.sync_latest_audit_data()

    assert calls == ["db"]
    assert response.mode == AuditSyncMode.LATEST
    assert response.results[0].instance_alias == "db"
    assert response.results[0].action == AuditSyncAction.COLLECTED
    assert response.results[0].status == CollectionStatus.SUCCESS
    assert response.results[0].finding_count == 1


def test_sync_today_audit_data_skips_when_latest_snapshot_is_today(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _snapshot()
    calls: list[str] = []

    def fake_collect_and_write_instance(**kwargs: Any) -> SnapshotWriteResult:
        calls.append(str(kwargs["alias"]))
        return SnapshotWriteResult(
            snapshot=snapshot,
            snapshot_uri="s3://infra-audit-rl-dev/raw/snapshots/example.json",
        )

    monkeypatch.setattr(
        "infra_auditor.sync.collect_and_write_instance",
        fake_collect_and_write_instance,
    )
    monkeypatch.setattr(
        "infra_auditor.sync.utc_now",
        lambda: datetime(2026, 9, 4, 9, 0, tzinfo=UTC),
    )
    service = AuditReadService(
        settings=AppSettings(_env_file=None),
        resource_config=_resource_config(),
        reader=FakeReader(snapshot),
    )

    response = service.sync_today_audit_data()

    assert calls == []
    assert response.mode == AuditSyncMode.TODAY
    assert response.results[0].action == AuditSyncAction.SKIPPED
    assert response.results[0].snapshot_uri.startswith("s3://infra-audit-rl-dev/")


def test_sync_today_audit_data_collects_when_today_split_artifacts_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _snapshot()
    calls: list[str] = []

    def fake_collect_and_write_instance(**kwargs: Any) -> SnapshotWriteResult:
        calls.append(str(kwargs["alias"]))
        return SnapshotWriteResult(
            snapshot=snapshot,
            snapshot_uri="s3://infra-audit-rl-dev/raw/snapshots/example.json",
        )

    monkeypatch.setattr(
        "infra_auditor.sync.collect_and_write_instance",
        fake_collect_and_write_instance,
    )
    monkeypatch.setattr(
        "infra_auditor.sync.utc_now",
        lambda: datetime(2026, 9, 4, 9, 0, tzinfo=UTC),
    )
    service = AuditReadService(
        settings=AppSettings(_env_file=None),
        resource_config=_resource_config(),
        reader=FakeReader(snapshot, split_objects_exist=False),
    )

    response = service.sync_today_audit_data()

    assert calls == ["db"]
    assert response.results[0].action == AuditSyncAction.COLLECTED
    assert response.results[0].finding_count == 1


def _resource_config() -> ResourceConfig:
    return ResourceConfig.model_validate(
        {
            "version": 1,
            "aws": {"default_region": "ap-south-1"},
            "instances": {
                "db": {
                    "db_instance_identifier": "database-1",
                    "secret_id": "infra-auditor/postgres/db",
                }
            },
        }
    )


def _snapshot() -> AuditSnapshot:
    return AuditSnapshot(
        metadata=RunMetadata(
            run_id="run-1",
            environment="dev",
            region="ap-south-1",
            started_at=datetime(2026, 9, 4, 7, 0, tzinfo=UTC),
            completed_at=datetime(2026, 9, 4, 7, 1, tzinfo=UTC),
            status=CollectionStatus.SUCCESS,
        ),
        instances=[
            InstanceSnapshot(
                alias="db",
                db_instance_identifier="database-1",
                region="ap-south-1",
                status=CollectionStatus.SUCCESS,
                findings=[
                    Finding(
                        rule_id="SEC002",
                        fingerprint="fingerprint-1",
                        category="security/postgres",
                        severity=FindingSeverity.HIGH,
                        resource="db/postgres/role/app_user",
                        title="Role has rds_superuser path",
                        summary="A login role inherits rds_superuser.",
                    )
                ],
            )
        ],
    )
