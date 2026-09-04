"""In-process sync job tracking for the local report console."""

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from infra_auditor.config import AppSettings, ResourceConfig
from infra_auditor.models.common import utc_now
from infra_auditor.storage.s3_reader import S3SnapshotReader
from infra_auditor.sync import (
    AuditSyncAction,
    AuditSyncInstanceResult,
    AuditSyncMode,
    AuditSyncResult,
    sync_audit_data,
)


class SyncJobStatus(BaseModel):
    """Current state of a local UI sync job."""

    job_id: str
    mode: AuditSyncMode
    target: str
    status: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    current_alias: str | None = None
    results: list[AuditSyncInstanceResult] = Field(default_factory=list)
    message: str | None = None
    error: str | None = None

    model_config = ConfigDict(extra="forbid")


class UISyncJobManager:
    """Run local collection syncs in one bounded background worker."""

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
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="infra-auditor-sync")
        self._jobs: dict[str, SyncJobStatus] = {}
        self._lock = Lock()

    def start(
        self,
        *,
        instance_alias: str | None,
        mode: AuditSyncMode,
    ) -> SyncJobStatus:
        """Create and start a background sync job."""

        job_id = str(uuid4())
        target = instance_alias or "all"
        job = SyncJobStatus(
            job_id=job_id,
            mode=mode,
            target=target,
            status="queued",
            created_at=utc_now().isoformat(),
            message="queued",
        )
        with self._lock:
            self._jobs[job_id] = job
        self._executor.submit(self._run, job_id, instance_alias, mode)
        return job

    def get(self, job_id: str) -> SyncJobStatus | None:
        """Return a snapshot of one job status."""

        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job is not None else None

    def _run(
        self,
        job_id: str,
        instance_alias: str | None,
        mode: AuditSyncMode,
    ) -> None:
        self._update(
            job_id,
            status="running",
            started_at=utc_now().isoformat(),
            message="starting read-only collection workflow",
        )

        def on_target_start(alias: str) -> None:
            self._update(
                job_id,
                current_alias=alias,
                message=f"syncing {alias}",
            )

        def on_target_complete(result: AuditSyncInstanceResult) -> None:
            self._append_result(job_id, result)

        try:
            sync_result = sync_audit_data(
                settings=self._settings,
                resource_config=self._resource_config,
                reader=self._reader,
                instance_alias=instance_alias,
                mode=mode,
                on_target_start=on_target_start,
                on_target_complete=on_target_complete,
            )
        except Exception as exc:  # noqa: BLE001 - background jobs must report errors.
            self._update(
                job_id,
                status="failed",
                completed_at=utc_now().isoformat(),
                current_alias=None,
                message="sync failed",
                error=str(exc),
            )
            return

        self._update(
            job_id,
            status=_job_status(sync_result),
            completed_at=utc_now().isoformat(),
            current_alias=None,
            message=_job_message(sync_result),
        )

    def _update(self, job_id: str, **updates: object) -> None:
        with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = job.model_copy(update=updates)

    def _append_result(self, job_id: str, result: AuditSyncInstanceResult) -> None:
        with self._lock:
            job = self._jobs[job_id]
            results = [*job.results, result]
            self._jobs[job_id] = job.model_copy(update={"results": results})


def _job_status(result: AuditSyncResult) -> str:
    actions = [item.action for item in result.results]
    if not actions:
        return "failed"
    if all(action == AuditSyncAction.FAILED for action in actions):
        return "failed"
    if any(action == AuditSyncAction.FAILED for action in actions):
        return "partial_success"
    return "success"


def _job_message(result: AuditSyncResult) -> str:
    collected = sum(1 for item in result.results if item.action == AuditSyncAction.COLLECTED)
    skipped = sum(1 for item in result.results if item.action == AuditSyncAction.SKIPPED)
    failed = sum(1 for item in result.results if item.action == AuditSyncAction.FAILED)
    return f"collected {collected}, skipped {skipped}, failed {failed}"
