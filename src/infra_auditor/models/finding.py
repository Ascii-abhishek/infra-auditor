"""Finding model for deterministic rule output."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from infra_auditor.models.evidence import EvidenceReference

FindingObservedValue = str | int | float | bool | None | list[str]


class FindingSeverity(StrEnum):
    """Deterministic finding severity values."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class Finding(BaseModel):
    """Minimal finding contract with evidence references."""

    rule_id: str
    fingerprint: str
    category: str
    severity: FindingSeverity
    resource: str
    title: str
    summary: str
    observed: dict[str, FindingObservedValue] = Field(default_factory=dict)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    recommendation: str | None = None

    model_config = ConfigDict(extra="forbid")
