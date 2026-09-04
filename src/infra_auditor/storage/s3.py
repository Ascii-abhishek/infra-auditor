"""S3 JSON snapshot writer."""

from datetime import UTC

from botocore.exceptions import ClientError

from infra_auditor.collectors.aws.client import S3PutObjectClient
from infra_auditor.exceptions import SnapshotValidationError
from infra_auditor.models.snapshot import AuditSnapshot
from infra_auditor.models.snapshot_split import (
    DEFAULT_SOURCE_SNAPSHOT_SERVICE,
    SnapshotSplitArtifact,
    build_snapshot_split_artifacts,
)

DEFAULT_SNAPSHOT_SERVICE = DEFAULT_SOURCE_SNAPSHOT_SERVICE


class S3SnapshotWriter:
    """Persist raw JSON snapshots to the environment's S3 bucket."""

    def __init__(self, client: S3PutObjectClient, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def write(self, snapshot: AuditSnapshot) -> str:
        key = build_snapshot_key(snapshot)
        uri = f"s3://{self._bucket}/{key}"
        payload = snapshot.model_dump_json(indent=2).encode("utf-8")

        self._put_json_object(
            key=key,
            payload=payload,
            collision_message=f"snapshot already exists in S3: {uri}",
            failure_message=f"failed to write snapshot to S3: {uri}",
            metadata={
                "run-id": snapshot.metadata.run_id,
                "application-version": snapshot.metadata.application_version,
                "snapshot-schema-version": str(snapshot.metadata.snapshot_schema_version),
                "env": snapshot.metadata.environment,
                "status": snapshot.metadata.status.value,
            },
        )
        for artifact in build_snapshot_split_artifacts(snapshot):
            self.write_split_artifact(artifact)

        return uri

    def write_split_artifact(self, artifact: SnapshotSplitArtifact) -> str:
        """Persist one split raw snapshot artifact."""

        key = build_snapshot_split_key(artifact)
        uri = f"s3://{self._bucket}/{key}"
        payload = artifact.model_dump_json(indent=2).encode("utf-8")
        self._put_json_object(
            key=key,
            payload=payload,
            collision_message=f"snapshot split already exists in S3: {uri}",
            failure_message=f"failed to write snapshot split to S3: {uri}",
            metadata={
                "run-id": artifact.metadata.run_id,
                "application-version": artifact.metadata.application_version,
                "artifact-schema-version": str(artifact.metadata.artifact_schema_version),
                "source-snapshot-schema-version": str(
                    artifact.metadata.source_snapshot_schema_version
                ),
                "env": artifact.metadata.environment,
                "status": artifact.metadata.status.value,
                "service": artifact.metadata.service.value,
                "subservice": artifact.metadata.subservice.value,
                "collector-boundary": artifact.metadata.collector_boundary.value,
                "instance-alias": artifact.metadata.instance_alias,
            },
        )
        return uri

    def _put_json_object(
        self,
        *,
        key: str,
        payload: bytes,
        collision_message: str,
        failure_message: str,
        metadata: dict[str, str],
    ) -> None:
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=payload,
                ContentType="application/json",
                ServerSideEncryption="AES256",
                IfNoneMatch="*",
                Metadata=metadata,
            )
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", "Unknown"))
            status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status_code == 412 or code in {
                "PreconditionFailed",
                "PreconditionFailedException",
            }:
                raise SnapshotValidationError(collision_message) from exc
            raise SnapshotValidationError(f"{failure_message} ({code})") from exc


def build_snapshot_key(snapshot: AuditSnapshot) -> str:
    """Build a partition-friendly key for one raw snapshot object."""

    started_at = snapshot.metadata.started_at.astimezone(UTC)
    aliases = "-".join(instance.alias for instance in snapshot.instances)
    date = started_at.strftime("%Y-%m-%d")
    timestamp = started_at.strftime("%Y%m%dT%H%M%SZ")

    return "/".join(
        [
            "raw",
            "snapshots",
            f"snapshot_schema={snapshot.metadata.snapshot_schema_version}",
            f"env={snapshot.metadata.environment}",
            f"region={snapshot.metadata.region}",
            f"service={DEFAULT_SNAPSHOT_SERVICE}",
            f"instance={aliases}",
            f"dt={date}",
            f"{timestamp}.json",
        ]
    )


def build_snapshot_split_key(artifact: SnapshotSplitArtifact) -> str:
    """Build a partition-friendly key for one split raw snapshot artifact."""

    started_at = artifact.metadata.started_at.astimezone(UTC)
    date = started_at.strftime("%Y-%m-%d")
    timestamp = started_at.strftime("%Y%m%dT%H%M%SZ")

    return "/".join(
        [
            "raw",
            "snapshots",
            f"artifact_schema={artifact.metadata.artifact_schema_version}",
            f"snapshot_schema={artifact.metadata.source_snapshot_schema_version}",
            f"env={artifact.metadata.environment}",
            f"region={artifact.metadata.region}",
            f"service={artifact.metadata.service.value}",
            f"subservice={artifact.metadata.subservice.value}",
            f"instance={artifact.metadata.instance_alias}",
            f"dt={date}",
            f"{timestamp}.json",
        ]
    )
