import json
from datetime import UTC, datetime
from typing import Any

import pytest

from infra_auditor.collectors.postgres.discovery import DatabaseInfo, DatabaseKind
from infra_auditor.exceptions import SnapshotReadError
from infra_auditor.models.common import CollectionStatus, CollectorResult
from infra_auditor.models.finding import Finding, FindingSeverity
from infra_auditor.models.snapshot import AuditSnapshot, InstanceSnapshot, RunMetadata
from infra_auditor.models.snapshot_split import (
    SnapshotArtifactReference,
    SnapshotRunManifest,
    SnapshotSplitService,
    SnapshotSplitSubservice,
    build_snapshot_split_artifacts,
)
from infra_auditor.storage.s3 import build_snapshot_artifact_key, build_snapshot_manifest_key
from infra_auditor.storage.s3_reader import (
    S3SnapshotReader,
    build_snapshot_artifact_prefix,
    build_snapshot_manifest_prefix,
)


class FakeBody:
    def __init__(self, payload: str) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload.encode("utf-8")


class FakeS3ReadClient:
    def __init__(self, snapshot: AuditSnapshot) -> None:
        artifacts = build_snapshot_split_artifacts(snapshot)
        references = [
            SnapshotArtifactReference(
                service=artifact.metadata.service,
                subservice=artifact.metadata.subservice,
                key=build_snapshot_artifact_key(artifact),
                status=artifact.metadata.status,
            )
            for artifact in artifacts
        ]
        instance = snapshot.instances[0]
        self.manifest = SnapshotRunManifest(
            run_id=snapshot.metadata.run_id,
            application_version=snapshot.metadata.application_version,
            environment=snapshot.metadata.environment,
            region=snapshot.metadata.region,
            instance_alias=instance.alias,
            started_at=snapshot.metadata.started_at,
            completed_at=snapshot.metadata.completed_at,
            status=snapshot.metadata.status,
            artifacts=references,
        )
        self.manifest_key = build_snapshot_manifest_key(self.manifest)
        self.payloads = {self.manifest_key: self.manifest.model_dump_json()}
        self.payloads.update(
            {
                reference.key: artifact.model_dump_json()
                for reference, artifact in zip(references, artifacts, strict=True)
            }
        )
        self.list_calls: list[dict[str, Any]] = []
        self.get_calls: list[dict[str, Any]] = []

    def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]:
        self.list_calls.append(kwargs)
        prefix = kwargs["Prefix"]
        contents = [
            {
                "Key": key,
                "Size": len(payload),
                "LastModified": datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
            }
            for key, payload in self.payloads.items()
            if key.startswith(prefix)
        ]
        return {"IsTruncated": False, "Contents": contents}

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        self.get_calls.append(kwargs)
        return {"Body": FakeBody(self.payloads[kwargs["Key"]])}


def test_reader_reassembles_latest_completed_artifact_family() -> None:
    snapshot = _snapshot()
    client = FakeS3ReadClient(snapshot)
    reader = S3SnapshotReader(client, "infra-audit-rl-dev")

    item, loaded = reader.read_latest_snapshot(
        environment="dev",
        region="ap-south-1",
        instance_alias="db",
    )

    assert item.key == client.manifest_key
    assert loaded == snapshot
    assert client.list_calls[0]["Prefix"] == build_snapshot_manifest_prefix(
        environment="dev", region="ap-south-1", instance_alias="db"
    )
    assert len(client.get_calls) == 10


def test_reader_lists_and_reads_one_canonical_artifact_boundary() -> None:
    client = FakeS3ReadClient(_snapshot())
    reader = S3SnapshotReader(client, "infra-audit-rl-dev")

    item, artifact = reader.read_latest_artifact(
        environment="dev",
        region="ap-south-1",
        service=SnapshotSplitService.POSTGRES,
        subservice=SnapshotSplitSubservice.POSTGRES_DATABASE_INVENTORY,
        instance_alias="db",
    )

    assert artifact.metadata.service == SnapshotSplitService.POSTGRES
    assert item.key.startswith(
        "raw/snapshots/schema=3/env=dev/service=postgres/region=ap-south-1/"
        "instance=db/subservice=database-inventory/"
    )
    assert client.list_calls[0]["Prefix"] == build_snapshot_artifact_prefix(
        environment="dev",
        region="ap-south-1",
        service=SnapshotSplitService.POSTGRES,
        subservice=SnapshotSplitSubservice.POSTGRES_DATABASE_INVENTORY,
        instance_alias="db",
    )


def test_reader_rejects_noncanonical_manifest_reference_before_artifact_read() -> None:
    client = FakeS3ReadClient(_snapshot())
    payload = client.manifest.model_dump(mode="json")
    payload["artifacts"][0]["key"] = "unapproved/private-object.json"
    client.payloads[client.manifest_key] = json.dumps(payload)
    reader = S3SnapshotReader(client, "infra-audit-rl-dev")

    with pytest.raises(SnapshotReadError, match="canonical run-scoped key"):
        reader.read_snapshot(client.manifest_key)

    assert client.get_calls == [{"Bucket": "infra-audit-rl-dev", "Key": client.manifest_key}]


def _snapshot() -> AuditSnapshot:
    return AuditSnapshot(
        metadata=RunMetadata(
            run_id="run-1",
            environment="dev",
            region="ap-south-1",
            started_at=datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
            completed_at=datetime(2026, 9, 3, 12, 1, tzinfo=UTC),
            status=CollectionStatus.SUCCESS,
        ),
        instances=[
            InstanceSnapshot(
                alias="db",
                db_instance_identifier="database-1",
                region="ap-south-1",
                status=CollectionStatus.SUCCESS,
                databases=[
                    DatabaseInfo(
                        name="app_db",
                        allow_connections=True,
                        is_template=False,
                        kind=DatabaseKind.APPLICATION,
                        connection_eligible=True,
                    )
                ],
                collectors=[
                    CollectorResult(
                        name="postgres.database_inventory",
                        status=CollectionStatus.SUCCESS,
                        started_at=datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
                        completed_at=datetime(2026, 9, 3, 12, 1, tzinfo=UTC),
                        duration_ms=60_000,
                    )
                ],
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


def test_storage_separates_evidence_reports_and_completion_markers() -> None:
    from infra_auditor.storage.s3 import S3SnapshotWriter

    client = FakeS3ReadClient(_snapshot())
    assert client.manifest_key.startswith("runs/schema=3/")
    raw = [key for key in client.payloads if key.startswith("raw/")]
    reports = [key for key in client.payloads if key.startswith("reports/")]
    assert len(raw) == 7
    assert len(reports) == 2
    assert all("deterministic-findings" not in key for key in raw)
    assert all("service=audit" not in key for key in client.payloads)
    assert {ref.service.value for ref in client.manifest.artifacts} == {"rds", "postgres"}

    class FailingWriter:
        def __init__(self) -> None:
            self.keys: list[str] = []

        def put_object(self, **kwargs: Any) -> dict[str, Any]:
            self.keys.append(kwargs["Key"])
            if kwargs["Key"].startswith("reports/"):
                raise RuntimeError("simulated report write failure")
            return {}

    failing = FailingWriter()
    with pytest.raises(RuntimeError, match="simulated"):
        S3SnapshotWriter(failing, "infra-audit-rl-dev").write(_snapshot())
    assert not any(key.startswith("runs/") for key in failing.keys)
