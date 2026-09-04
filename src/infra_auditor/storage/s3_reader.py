"""S3 JSON snapshot reader for reports and the local UI."""

from datetime import datetime
from typing import Any

from botocore.exceptions import ClientError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from infra_auditor.collectors.aws.client import S3ReadClient
from infra_auditor.exceptions import SnapshotReadError
from infra_auditor.models.snapshot import SNAPSHOT_SCHEMA_VERSION, AuditSnapshot
from infra_auditor.models.snapshot_split import (
    SNAPSHOT_SPLIT_ARTIFACT_SCHEMA_VERSION,
    SnapshotSplitArtifact,
    SnapshotSplitService,
    SnapshotSplitSubservice,
)
from infra_auditor.storage.s3 import DEFAULT_SNAPSHOT_SERVICE


class S3SnapshotObject(BaseModel):
    """Listed raw snapshot object."""

    bucket: str
    key: str
    uri: str
    size_bytes: int = Field(ge=0)
    last_modified: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class S3SnapshotSplitObject(S3SnapshotObject):
    """Listed split raw snapshot object."""

    service: SnapshotSplitService
    subservice: SnapshotSplitSubservice

    model_config = ConfigDict(extra="forbid")


class S3SnapshotReader:
    """Read raw JSON snapshots from the environment's S3 bucket."""

    def __init__(self, client: S3ReadClient, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def list_snapshots(
        self,
        *,
        environment: str,
        region: str,
        service: str = DEFAULT_SNAPSHOT_SERVICE,
        instance_alias: str,
        limit: int = 50,
    ) -> list[S3SnapshotObject]:
        """List stored snapshots for one instance, newest first."""

        prefix = build_snapshot_prefix(
            environment=environment,
            region=region,
            service=service,
            instance_alias=instance_alias,
        )
        return self._list_objects(prefix=prefix, limit=limit, action="list S3 snapshots")

    def list_snapshot_split_artifacts(
        self,
        *,
        environment: str,
        region: str,
        service: SnapshotSplitService,
        subservice: SnapshotSplitSubservice,
        instance_alias: str,
        limit: int = 50,
    ) -> list[S3SnapshotSplitObject]:
        """List stored split artifacts for one instance and collector boundary."""

        prefix = build_snapshot_split_prefix(
            environment=environment,
            region=region,
            service=service,
            subservice=subservice,
            instance_alias=instance_alias,
        )
        objects = self._list_objects(
            prefix=prefix,
            limit=limit,
            action="list S3 snapshot split artifacts",
        )
        return [
            S3SnapshotSplitObject(
                **item.model_dump(),
                service=service,
                subservice=subservice,
            )
            for item in objects
        ]

    def read_snapshot(self, key: str) -> AuditSnapshot:
        """Read and validate one raw JSON snapshot object by key."""

        raw = self._read_text_object(key=key, action="read S3 snapshot")

        try:
            return AuditSnapshot.model_validate_json(raw)
        except ValidationError as exc:
            raise SnapshotReadError(f"stored snapshot failed schema validation: {key}") from exc

    def read_snapshot_split_artifact(self, key: str) -> SnapshotSplitArtifact:
        """Read and validate one split raw snapshot artifact by key."""

        raw = self._read_text_object(key=key, action="read S3 snapshot split artifact")
        try:
            return SnapshotSplitArtifact.model_validate_json(raw)
        except ValidationError as exc:
            raise SnapshotReadError(
                f"stored snapshot split artifact failed schema validation: {key}"
            ) from exc

    def read_latest_snapshot(
        self,
        *,
        environment: str,
        region: str,
        service: str = DEFAULT_SNAPSHOT_SERVICE,
        instance_alias: str,
    ) -> tuple[S3SnapshotObject, AuditSnapshot]:
        """Read the newest available snapshot for one instance."""

        objects = self.list_snapshots(
            environment=environment,
            region=region,
            service=service,
            instance_alias=instance_alias,
            limit=1,
        )
        if not objects:
            raise SnapshotReadError(f"no snapshots found for instance {instance_alias}")
        return objects[0], self.read_snapshot(objects[0].key)

    def read_latest_snapshot_split_artifact(
        self,
        *,
        environment: str,
        region: str,
        service: SnapshotSplitService,
        subservice: SnapshotSplitSubservice,
        instance_alias: str,
    ) -> tuple[S3SnapshotSplitObject, SnapshotSplitArtifact]:
        """Read the newest available split artifact for one collector boundary."""

        objects = self.list_snapshot_split_artifacts(
            environment=environment,
            region=region,
            service=service,
            subservice=subservice,
            instance_alias=instance_alias,
            limit=1,
        )
        if not objects:
            raise SnapshotReadError(
                f"no snapshot split artifacts found for instance {instance_alias} "
                f"and service {service.value}/{subservice.value}"
            )
        return objects[0], self.read_snapshot_split_artifact(objects[0].key)

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


def build_snapshot_prefix(
    *,
    environment: str,
    region: str,
    service: str = DEFAULT_SNAPSHOT_SERVICE,
    instance_alias: str,
    snapshot_schema_version: int = SNAPSHOT_SCHEMA_VERSION,
) -> str:
    """Build the S3 prefix for one instance's raw snapshots."""

    return "/".join(
        [
            "raw",
            "snapshots",
            f"snapshot_schema={snapshot_schema_version}",
            f"env={environment}",
            f"region={region}",
            f"service={service}",
            f"instance={instance_alias}",
            "",
        ]
    )


def build_snapshot_split_prefix(
    *,
    environment: str,
    region: str,
    service: SnapshotSplitService,
    subservice: SnapshotSplitSubservice,
    instance_alias: str,
    artifact_schema_version: int = SNAPSHOT_SPLIT_ARTIFACT_SCHEMA_VERSION,
    snapshot_schema_version: int = SNAPSHOT_SCHEMA_VERSION,
) -> str:
    """Build the S3 prefix for one split artifact boundary."""

    return "/".join(
        [
            "raw",
            "snapshots",
            f"artifact_schema={artifact_schema_version}",
            f"snapshot_schema={snapshot_schema_version}",
            f"env={environment}",
            f"region={region}",
            f"service={service.value}",
            f"subservice={subservice.value}",
            f"instance={instance_alias}",
            "",
        ]
    )


def build_snapshot_split_prefix_for_date(
    *,
    environment: str,
    region: str,
    service: SnapshotSplitService,
    subservice: SnapshotSplitSubservice,
    instance_alias: str,
    date: str,
    artifact_schema_version: int = SNAPSHOT_SPLIT_ARTIFACT_SCHEMA_VERSION,
    snapshot_schema_version: int = SNAPSHOT_SCHEMA_VERSION,
) -> str:
    """Build the S3 prefix for one split artifact boundary and date."""

    return "/".join(
        [
            "raw",
            "snapshots",
            f"artifact_schema={artifact_schema_version}",
            f"snapshot_schema={snapshot_schema_version}",
            f"env={environment}",
            f"region={region}",
            f"service={service.value}",
            f"subservice={subservice.value}",
            f"instance={instance_alias}",
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
