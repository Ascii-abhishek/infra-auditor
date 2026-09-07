"""S3 JSON snapshot reader for reports and the local UI."""

from datetime import datetime
from typing import Any

from botocore.exceptions import ClientError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from infra_auditor.collectors.aws.client import S3ReadClient
from infra_auditor.exceptions import SnapshotReadError
from infra_auditor.models.snapshot import AuditSnapshot
from infra_auditor.models.snapshot_split import (
    SNAPSHOT_SPLIT_ARTIFACT_SCHEMA_VERSION,
    SNAPSHOT_SPLIT_DEFINITIONS,
    SnapshotRunManifest,
    SnapshotSplitArtifact,
    SnapshotSplitService,
    SnapshotSplitSubservice,
    assemble_snapshot,
)
from infra_auditor.storage.s3 import (
    MANIFEST_SERVICE,
    MANIFEST_SUBSERVICE,
    build_artifact_key,
    build_run_manifest_key,
    build_snapshot_artifact_key,
    build_snapshot_manifest_key,
)


class S3SnapshotObject(BaseModel):
    """Listed raw snapshot object."""

    bucket: str
    key: str
    uri: str
    size_bytes: int = Field(ge=0)
    last_modified: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class S3ArtifactObject(S3SnapshotObject):
    """Listed canonical raw evidence object."""

    service: SnapshotSplitService
    subservice: SnapshotSplitSubservice

    model_config = ConfigDict(extra="forbid")


class S3SnapshotReader:
    """Read raw JSON snapshots from the environment's S3 bucket."""

    def __init__(self, client: S3ReadClient, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def list_manifests(
        self,
        *,
        environment: str,
        region: str,
        instance_alias: str,
        limit: int = 50,
    ) -> list[S3SnapshotObject]:
        """List completed audit runs for one instance, newest first."""

        prefix = build_snapshot_manifest_prefix(
            environment=environment,
            region=region,
            instance_alias=instance_alias,
        )
        return self._list_objects(prefix=prefix, limit=limit, action="list S3 run manifests")

    def list_artifacts(
        self,
        *,
        environment: str,
        region: str,
        service: SnapshotSplitService,
        subservice: SnapshotSplitSubservice,
        instance_alias: str,
        limit: int = 50,
    ) -> list[S3ArtifactObject]:
        """List evidence for one approved instance boundary, newest first."""

        prefix = build_snapshot_artifact_prefix(
            environment=environment,
            region=region,
            service=service,
            subservice=subservice,
            instance_alias=instance_alias,
        )
        objects = self._list_objects(
            prefix=prefix,
            limit=limit,
            action="list S3 snapshot artifacts",
        )
        return [
            S3ArtifactObject(
                **item.model_dump(),
                service=service,
                subservice=subservice,
            )
            for item in objects
        ]

    def read_artifact(self, key: str) -> SnapshotSplitArtifact:
        """Read and validate one canonical raw evidence artifact."""

        raw = self._read_text_object(key=key, action="read S3 snapshot artifact")
        try:
            return SnapshotSplitArtifact.model_validate_json(raw)
        except ValidationError as exc:
            raise SnapshotReadError(f"stored artifact failed schema validation: {key}") from exc

    def read_manifest(self, key: str) -> SnapshotRunManifest:
        """Read and validate one completed-run manifest."""

        raw = self._read_text_object(key=key, action="read S3 run manifest")
        try:
            return SnapshotRunManifest.model_validate_json(raw)
        except ValidationError as exc:
            raise SnapshotReadError(f"stored manifest failed schema validation: {key}") from exc

    def read_snapshot(self, manifest_key: str) -> AuditSnapshot:
        """Reassemble one coherent in-memory snapshot from its manifest."""

        manifest = self.read_manifest(manifest_key)
        if manifest_key != build_snapshot_manifest_key(manifest):
            raise SnapshotReadError(f"manifest is not stored at its canonical key: {manifest_key}")
        artifact_keys = _validated_artifact_keys(manifest)
        artifacts = [self.read_artifact(key) for key in artifact_keys]
        try:
            return assemble_snapshot(manifest, artifacts)
        except ValueError as exc:
            raise SnapshotReadError(f"invalid artifact family: {manifest_key}") from exc

    def read_snapshot_for_artifact(self, key: str) -> AuditSnapshot:
        """Reassemble the committed run containing one selected artifact."""

        selected = self.read_artifact(key)
        metadata = selected.metadata
        expected_selected_key = build_snapshot_artifact_key(selected)
        if key != expected_selected_key:
            raise SnapshotReadError(f"artifact is not stored at its canonical key: {key}")
        manifest_key = build_run_manifest_key(
            schema_version=metadata.schema_version,
            environment=metadata.environment,
            region=metadata.region,
            instance_alias=metadata.instance_alias,
            started_at=metadata.started_at,
        )
        manifest = self.read_manifest(manifest_key)
        artifact_keys = _validated_artifact_keys(manifest)
        artifacts = [
            selected if artifact_key == key else self.read_artifact(artifact_key)
            for artifact_key in artifact_keys
        ]
        try:
            return assemble_snapshot(manifest, artifacts)
        except ValueError as exc:
            raise SnapshotReadError(f"invalid artifact family: {manifest_key}") from exc

    def read_latest_snapshot(
        self,
        *,
        environment: str,
        region: str,
        instance_alias: str,
    ) -> tuple[S3SnapshotObject, AuditSnapshot]:
        """Read the newest available snapshot for one instance."""

        objects = self.list_manifests(
            environment=environment,
            region=region,
            instance_alias=instance_alias,
            limit=1,
        )
        if not objects:
            raise SnapshotReadError(f"no snapshots found for instance {instance_alias}")
        return objects[0], self.read_snapshot(objects[0].key)

    def read_latest_artifact(
        self,
        *,
        environment: str,
        region: str,
        service: SnapshotSplitService,
        subservice: SnapshotSplitSubservice,
        instance_alias: str,
    ) -> tuple[S3ArtifactObject, SnapshotSplitArtifact]:
        """Read the newest evidence artifact for one collector boundary."""

        objects = self.list_artifacts(
            environment=environment,
            region=region,
            service=service,
            subservice=subservice,
            instance_alias=instance_alias,
            limit=1,
        )
        if not objects:
            raise SnapshotReadError(
                f"no snapshot artifacts found for instance {instance_alias} "
                f"and service {service.value}/{subservice.value}"
            )
        return objects[0], self.read_artifact(objects[0].key)

    def _list_objects(self, *, prefix: str, limit: int, action: str) -> list[S3SnapshotObject]:
        objects: list[S3SnapshotObject] = []
        continuation_token: str | None = None
        try:
            while True:
                kwargs: dict[str, Any] = {
                    "Bucket": self._bucket,
                    "Prefix": prefix,
                    "MaxKeys": 1000,
                }
                if continuation_token is not None:
                    kwargs["ContinuationToken"] = continuation_token
                response = self._client.list_objects_v2(**kwargs)
                for item in response.get("Contents", []):
                    if not isinstance(item, dict) or not item.get("Key"):
                        continue
                    key = str(item["Key"])
                    objects.append(
                        S3SnapshotObject(
                            bucket=self._bucket,
                            key=key,
                            uri=f"s3://{self._bucket}/{key}",
                            size_bytes=_optional_int(item.get("Size")) or 0,
                            last_modified=(
                                item["LastModified"]
                                if isinstance(item.get("LastModified"), datetime)
                                else None
                            ),
                        )
                    )
                if not response.get("IsTruncated"):
                    break
                token = response.get("NextContinuationToken")
                continuation_token = str(token) if token else None
                if continuation_token is None:
                    break
        except ClientError as exc:
            raise SnapshotReadError(_client_error_message(action, exc)) from exc

        return sorted(
            objects,
            key=lambda item: (
                item.last_modified.timestamp() if item.last_modified is not None else 0.0,
                item.key,
            ),
            reverse=True,
        )[:limit]

    def _read_text_object(self, *, key: str, action: str) -> str:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            body = response.get("Body")
            if body is None or not hasattr(body, "read"):
                raise SnapshotReadError(
                    f"S3 object has no readable body: s3://{self._bucket}/{key}"
                )
            payload = body.read()
            if isinstance(payload, str):
                return payload
            if isinstance(payload, bytes | bytearray):
                return bytes(payload).decode("utf-8")
            raise SnapshotReadError(
                f"S3 object body returned unexpected type: {type(payload).__name__}"
            )
        except ClientError as exc:
            raise SnapshotReadError(_client_error_message(action, exc)) from exc


def _validated_artifact_keys(manifest: SnapshotRunManifest) -> list[str]:
    """Validate a manifest's complete allowlisted artifact family before reading it."""

    approved_boundaries = {
        (definition.service, definition.subservice) for definition in SNAPSHOT_SPLIT_DEFINITIONS
    }
    references_by_boundary = {
        (reference.service, reference.subservice): reference for reference in manifest.artifacts
    }
    if len(references_by_boundary) != len(manifest.artifacts):
        raise SnapshotReadError("manifest contains duplicate artifact boundaries")
    if set(references_by_boundary) != approved_boundaries:
        raise SnapshotReadError("manifest does not contain the complete approved artifact family")

    keys: list[str] = []
    for definition in SNAPSHOT_SPLIT_DEFINITIONS:
        reference = references_by_boundary[(definition.service, definition.subservice)]
        expected_key = build_artifact_key(
            schema_version=manifest.schema_version,
            environment=manifest.environment,
            service=definition.service.value,
            region=manifest.region,
            instance_alias=manifest.instance_alias,
            subservice=definition.subservice.value,
            started_at=manifest.started_at,
        )
        if reference.key != expected_key:
            raise SnapshotReadError(
                f"manifest artifact reference is not its canonical run-scoped key: {reference.key}"
            )
        keys.append(reference.key)
    return keys


def build_snapshot_manifest_prefix(
    *,
    environment: str,
    region: str,
    instance_alias: str,
    schema_version: int = SNAPSHOT_SPLIT_ARTIFACT_SCHEMA_VERSION,
) -> str:
    """Build the S3 prefix for one instance's completed run manifests."""

    return "/".join(
        [
            "raw",
            "snapshots",
            f"schema={schema_version}",
            f"env={environment}",
            f"service={MANIFEST_SERVICE}",
            f"region={region}",
            f"instance={instance_alias}",
            f"subservice={MANIFEST_SUBSERVICE}",
            "",
        ]
    )


def build_snapshot_artifact_prefix(
    *,
    environment: str,
    region: str,
    service: SnapshotSplitService,
    subservice: SnapshotSplitSubservice,
    instance_alias: str,
    schema_version: int = SNAPSHOT_SPLIT_ARTIFACT_SCHEMA_VERSION,
) -> str:
    """Build the canonical prefix for one evidence boundary."""

    return "/".join(
        [
            "raw",
            "snapshots",
            f"schema={schema_version}",
            f"env={environment}",
            f"service={service.value}",
            f"region={region}",
            f"instance={instance_alias}",
            f"subservice={subservice.value}",
            "",
        ]
    )


def build_snapshot_artifact_prefix_for_date(
    *,
    environment: str,
    region: str,
    service: SnapshotSplitService,
    subservice: SnapshotSplitSubservice,
    instance_alias: str,
    date: str,
    schema_version: int = SNAPSHOT_SPLIT_ARTIFACT_SCHEMA_VERSION,
) -> str:
    """Build the S3 prefix for one artifact boundary and date."""

    return "/".join(
        [
            "raw",
            "snapshots",
            f"schema={schema_version}",
            f"env={environment}",
            f"service={service.value}",
            f"region={region}",
            f"instance={instance_alias}",
            f"subservice={subservice.value}",
            f"dt={date}",
            "",
        ]
    )


def s3_uri_to_key(uri: str, *, bucket: str) -> str:
    """Extract an object key from a bucket-scoped S3 URI."""

    prefix = f"s3://{bucket}/"
    if not uri.startswith(prefix):
        raise SnapshotReadError(f"snapshot URI is not in bucket {bucket}: {uri}")
    return uri.removeprefix(prefix)


def _client_error_message(action: str, exc: ClientError) -> str:
    code = str(exc.response.get("Error", {}).get("Code", "Unknown"))
    return f"failed to {action} ({code})"


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float | str | bytes | bytearray):
        return int(value)
    msg = f"expected int-compatible value, got {type(value).__name__}"
    raise TypeError(msg)
