"""Evidence references used by future deterministic findings."""

from pydantic import BaseModel, ConfigDict, Field


class EvidenceReference(BaseModel):
    """Pointer from a future finding back to collected snapshot evidence."""

    snapshot_run_id: str
    collector: str
    resource: str
    path: str = Field(description="Stable JSON path or logical path within the snapshot.")

    model_config = ConfigDict(extra="forbid")
