"""S3 JSON snapshot writer."""

from datetime import UTC, datetime

from botocore.exceptions import ClientError

from infra_auditor.collectors.aws.client import S3PutObjectClient
from infra_auditor.exceptions import SnapshotValidationError
from infra_auditor.models.snapshot import AuditSnapshot
from infra_auditor.models.snapshot_split import (
    SnapshotArtifactReference,
    SnapshotRunManifest,
    SnapshotSplitArtifact,
    build_snapshot_split_artifacts,
)


def artifact_root(subservice: str) -> str:
    """Derived rule outputs are reports, never raw observations."""

    return "reports" if subservice == "deterministic-findings" else "raw"


class S3SnapshotWriter:
    """Persist one canonical artifact family and its completion manifest."""

    def __init__(self, client: S3PutObjectClient, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def write(self, snapshot: AuditSnapshot) -> str:
        if len(snapshot.instances) != 1:
            raise SnapshotValidationError(
                "one artifact family must contain exactly one instance snapshot"
            )
        references: list[SnapshotArtifactReference] = []
        for artifact in build_snapshot_split_artifacts(snapshot):
            key = self.write_artifact(artifact)
            references.append(
                SnapshotArtifactReference(
                    service=artifact.metadata.service,
                    subservice=artifact.metadata.subservice,
                    key=key,
                    status=artifact.metadata.status,
                )
            )
        instance = snapshot.instances[0]
        manifest = SnapshotRunManifest(
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
        return self.write_manifest(manifest)

    def write_artifact(self, artifact: SnapshotSplitArtifact) -> str:
        """Persist one canonical raw evidence artifact and return its key."""

        key = build_snapshot_artifact_key(artifact)
        uri = f"s3://{self._bucket}/{key}"
        payload = artifact.model_dump_json(indent=2).encode("utf-8")
        self._put_json_object(
            key=key,
            payload=payload,
            collision_message=f"snapshot artifact already exists in S3: {uri}",
            failure_message=f"failed to write snapshot artifact to S3: {uri}",
            metadata={
                "run-id": artifact.metadata.run_id,
                "application-version": artifact.metadata.application_version,
                "schema-version": str(artifact.metadata.schema_version),
                "env": artifact.metadata.environment,
                "status": artifact.metadata.status.value,
                "service": artifact.metadata.service.value,
                "subservice": artifact.metadata.subservice.value,
                "collector-boundary": artifact.metadata.collector_boundary.value,
                "instance-alias": artifact.metadata.instance_alias,
            },
        )
        return key

    def write_manifest(self, manifest: SnapshotRunManifest) -> str:
        """Commit one complete artifact family and return the manifest URI."""

        key = build_snapshot_manifest_key(manifest)
        uri = f"s3://{self._bucket}/{key}"
        self._put_json_object(
            key=key,
            payload=manifest.model_dump_json(indent=2).encode("utf-8"),
            collision_message=f"snapshot manifest already exists in S3: {uri}",
            failure_message=f"failed to write snapshot manifest to S3: {uri}",
            metadata={
                "run-id": manifest.run_id,
                "application-version": manifest.application_version,
                "schema-version": str(manifest.schema_version),
                "env": manifest.environment,
                "status": manifest.status.value,
                "instance-alias": manifest.instance_alias,
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


def build_snapshot_artifact_key(artifact: SnapshotSplitArtifact) -> str:
    """Build the canonical key for one raw evidence artifact."""

    return build_artifact_key(
        schema_version=artifact.metadata.schema_version,
        environment=artifact.metadata.environment,
        service=artifact.metadata.service.value,
        region=artifact.metadata.region,
        instance_alias=artifact.metadata.instance_alias,
        subservice=artifact.metadata.subservice.value,
        started_at=artifact.metadata.started_at,
    )


def build_artifact_key(
    *,
    schema_version: int,
    environment: str,
    service: str,
    region: str,
    instance_alias: str,
    subservice: str,
    started_at: datetime,
) -> str:
    """Build an artifact key from validated run and boundary fields."""

    utc_started_at = started_at.astimezone(UTC)

    return "/".join(
        [
            artifact_root(subservice),
            "snapshots",
            f"schema={schema_version}",
            f"env={environment}",
            f"service={service}",
            f"region={region}",
            f"instance={instance_alias}",
            f"subservice={subservice}",
            f"dt={utc_started_at:%Y-%m-%d}",
            f"{utc_started_at:%Y%m%dT%H%M%SZ}.json",
        ]
    )


def build_snapshot_manifest_key(manifest: SnapshotRunManifest) -> str:
    """Build the canonical completion-manifest key for one audit run."""

    return build_run_manifest_key(
        schema_version=manifest.schema_version,
        environment=manifest.environment,
        region=manifest.region,
        instance_alias=manifest.instance_alias,
        started_at=manifest.started_at,
    )


def build_run_manifest_key(
    *,
    schema_version: int,
    environment: str,
    region: str,
    instance_alias: str,
    started_at: datetime,
) -> str:
    """Build a manifest key from stable run identity fields."""

    utc_started_at = started_at.astimezone(UTC)
    return "/".join(
        [
            "runs",
            f"schema={schema_version}",
            f"env={environment}",
            f"region={region}",
            f"instance={instance_alias}",
            f"dt={utc_started_at:%Y-%m-%d}",
            f"{utc_started_at:%Y%m%dT%H%M%SZ}.json",
        ]
    )
