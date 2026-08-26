"""Local JSON snapshot writer."""

from pathlib import Path

from infra_auditor.exceptions import SnapshotValidationError
from infra_auditor.models.snapshot import AuditSnapshot


class LocalSnapshotWriter:
    """Persist snapshots under a gitignored local directory."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def write(self, snapshot: AuditSnapshot) -> Path:
        run_id = snapshot.metadata.run_id
        aliases = "-".join(instance.alias for instance in snapshot.instances)
        target_dir = self._output_dir / run_id
        target_path = target_dir / f"{aliases}.json"

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
        except OSError as exc:
            raise SnapshotValidationError(f"failed to write snapshot: {target_path}") from exc

        return target_path
