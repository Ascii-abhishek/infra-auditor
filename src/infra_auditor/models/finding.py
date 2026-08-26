"""Foundational finding model for the future deterministic rule engine."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from infra_auditor.models.evidence import EvidenceReference


class FindingSeverity(StrEnum):
    """Deterministic finding severity values."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class Finding(BaseModel):
    """Minimal future-proof finding contract.

    V0.1 does not run rules yet; this model preserves the evidence-reference boundary.
    """

    rule_id: str
    fingerprint: str
    category: str
    severity: FindingSeverity
    resource: str
    title: str
    summary: str
    evidence: list[EvidenceReference] = Field(default_factory=list)
    recommendation: str | None = None

    model_config = ConfigDict(extra="forbid")
