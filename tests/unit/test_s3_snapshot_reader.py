from datetime import UTC, datetime
from typing import Any

from infra_auditor.models.common import CollectionStatus
from infra_auditor.models.snapshot import AuditSnapshot, InstanceSnapshot, RunMetadata
from infra_auditor.models.snapshot_split import (
    SnapshotSplitService,
    SnapshotSplitSubservice,
    build_snapshot_split_artifacts,
)
from infra_auditor.storage.s3_reader import (
    S3SnapshotReader,
    build_snapshot_prefix,
    build_snapshot_split_prefix,
)


class FakeBody:
    def __init__(self, payload: str) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload.encode("utf-8")


class FakeS3ReadClient:
    def __init__(self, snapshot: AuditSnapshot) -> None:
        self.snapshot = snapshot
        self.list_calls: list[dict[str, Any]] = []
        self.get_calls: list[dict[str, Any]] = []

    def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]:
        self.list_calls.append(kwargs)
        return {
            "IsTruncated": False,
            "Contents": [
                {
                    "Key": (
                        "raw/snapshots/snapshot_schema=1/env=dev/region=ap-south-1/"
                        "service=rds-postgres/instance=db/dt=2026-09-03/"
                        "20260903T120000Z.json"
                    ),
                    "Size": 123,
                    "LastModified": datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
                }
            ],
        }

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        self.get_calls.append(kwargs)
        return {"Body": FakeBody(self.snapshot.model_dump_json())}


class FakeS3SplitReadClient:
    def __init__(self, snapshot: AuditSnapshot) -> None:
        self.artifact = build_snapshot_split_artifacts(snapshot)[2]
        self.key = (
            "raw/snapshots/artifact_schema=1/snapshot_schema=1/env=dev/"
            "region=ap-south-1/service=postgres/subservice=database-inventory/"
            "instance=db/dt=2026-09-03/20260903T120000Z.json"
        )
        self.list_calls: list[dict[str, Any]] = []
        self.get_calls: list[dict[str, Any]] = []

    def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]:
        self.list_calls.append(kwargs)
        return {
            "IsTruncated": False,
            "Contents": [
                {
                    "Key": self.key,
                    "Size": 321,
                    "LastModified": datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
                }
            ],
        }

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        self.get_calls.append(kwargs)
        return {"Body": FakeBody(self.artifact.model_dump_json())}


def test_s3_snapshot_reader_lists_and_reads_latest_snapshot() -> None:
    snapshot = AuditSnapshot(
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
            )
        ],
    )
    client = FakeS3ReadClient(snapshot)
    reader = S3SnapshotReader(client, "infra-audit-rl-dev")

    item, loaded = reader.read_latest_snapshot(
        environment="dev",
        region="ap-south-1",
        instance_alias="db",
    )

    assert item.uri.startswith("s3://infra-audit-rl-dev/raw/snapshots/")
    assert loaded.metadata.run_id == "run-1"
    assert client.list_calls[0]["Prefix"] == build_snapshot_prefix(
        environment="dev",
        region="ap-south-1",
        service="rds-postgres",
        instance_alias="db",
    )
    assert client.get_calls == [{"Bucket": "infra-audit-rl-dev", "Key": item.key}]


def test_build_snapshot_prefix_is_service_aware() -> None:
    prefix = build_snapshot_prefix(
        environment="dev",
        region="ap-south-1",
        service="opensearch",
        instance_alias="search",
    )

    assert prefix == (
        "raw/snapshots/snapshot_schema=1/env=dev/region=ap-south-1/"
        "service=opensearch/instance=search/"
    )


def test_s3_snapshot_reader_lists_and_reads_split_artifacts() -> None:
    snapshot = AuditSnapshot(
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
            )
        ],
    )
    client = FakeS3SplitReadClient(snapshot)
    reader = S3SnapshotReader(client, "infra-audit-rl-dev")

    item, artifact = reader.read_latest_snapshot_split_artifact(
        environment="dev",
        region="ap-south-1",
        service=SnapshotSplitService.POSTGRES,
        subservice=SnapshotSplitSubservice.POSTGRES_DATABASE_INVENTORY,
        instance_alias="db",
    )

    assert item.service == SnapshotSplitService.POSTGRES
    assert item.subservice == SnapshotSplitSubservice.POSTGRES_DATABASE_INVENTORY
    assert artifact.metadata.service == SnapshotSplitService.POSTGRES
    assert client.list_calls[0]["Prefix"] == build_snapshot_split_prefix(
        environment="dev",
        region="ap-south-1",
        service=SnapshotSplitService.POSTGRES,
        subservice=SnapshotSplitSubservice.POSTGRES_DATABASE_INVENTORY,
        instance_alias="db",
    )
    assert client.get_calls == [{"Bucket": "infra-audit-rl-dev", "Key": item.key}]
