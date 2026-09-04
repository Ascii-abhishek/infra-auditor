"""RDS operations and configuration evidence collection."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from infra_auditor.collectors.aws.client import RDSClient
from infra_auditor.collectors.aws.models import RDSInstance
from infra_auditor.exceptions import AWSDiscoveryError


class RDSPendingMaintenanceAction(BaseModel):
    """A pending RDS maintenance action for one resource."""

    action: str | None = None
    description: str | None = None
    opt_in_status: str | None = None
    auto_applied_after: datetime | None = None
    forced_apply_at: datetime | None = None
    current_apply_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class RDSRecommendationEvidence(BaseModel):
    """A normalized RDS recommendation."""

    recommendation_id: str
    type_id: str | None = None
    severity: str | None = None
    status: str | None = None
    category: str | None = None
    source: str | None = None
    updated_at: datetime | None = None
    detection: str | None = None
    recommendation: str | None = None
    description: str | None = None
    reason: str | None = None
    impact: str | None = None

    model_config = ConfigDict(extra="forbid")


class RDSParameterEvidence(BaseModel):
    """A DB parameter group parameter."""

    name: str
    value: str | None = None
    source: str | None = None
    apply_type: str | None = None
    data_type: str | None = None
    allowed_values: str | None = None
    is_modifiable: bool | None = None
    minimum_engine_version: str | None = None
    apply_method: str | None = None

    model_config = ConfigDict(extra="forbid")


class RDSParameterGroupEvidence(BaseModel):
    """Collected DB parameter group values."""

    name: str
    parameters: list[RDSParameterEvidence] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class RDSOperationsEvidence(BaseModel):
    """RDS recommendations, maintenance, and parameter evidence."""

    pending_maintenance: list[RDSPendingMaintenanceAction] = Field(default_factory=list)
    recommendations: list[RDSRecommendationEvidence] = Field(default_factory=list)
    parameter_groups: list[RDSParameterGroupEvidence] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class RDSOperationsCollector:
    """Collect RDS operational evidence through read-only APIs."""

    name = "aws.rds.operations"

    def __init__(self, client: RDSClient) -> None:
        self._client = client

    def collect(self, instance: RDSInstance) -> RDSOperationsEvidence:
        try:
            return RDSOperationsEvidence(
                pending_maintenance=self._pending_maintenance(instance),
                recommendations=self._recommendations(instance),
                parameter_groups=self._parameter_groups(instance),
            )
        except Exception as exc:  # noqa: BLE001 - AWS clients raise provider-specific errors.
            raise AWSDiscoveryError(
                f"failed to collect RDS operations evidence for {instance.identifier}"
            ) from exc

    def _pending_maintenance(self, instance: RDSInstance) -> list[RDSPendingMaintenanceAction]:
        if instance.arn is None:
            return []

        actions: list[RDSPendingMaintenanceAction] = []
        next_marker: str | None = None
        while True:
            kwargs: dict[str, Any] = {
                "ResourceIdentifier": instance.arn,
                "MaxRecords": 100,
            }
            if next_marker is not None:
                kwargs["Marker"] = next_marker
            response = self._client.describe_pending_maintenance_actions(**kwargs)
            for resource in response.get("PendingMaintenanceActions", []):
                if not isinstance(resource, dict):
                    continue
                for action in resource.get("PendingMaintenanceActionDetails", []):
                    if isinstance(action, dict):
                        actions.append(_pending_maintenance_from_payload(action))
            marker = response.get("Marker")
            next_marker = str(marker) if marker else None
            if next_marker is None:
                return actions

    def _recommendations(self, instance: RDSInstance) -> list[RDSRecommendationEvidence]:
        if instance.arn is None:
            return []

        recommendations: list[RDSRecommendationEvidence] = []
        next_marker: str | None = None
        while True:
            kwargs: dict[str, Any] = {"MaxRecords": 50}
            if next_marker is not None:
                kwargs["Marker"] = next_marker
            response = self._client.describe_db_recommendations(**kwargs)
            for item in response.get("DBRecommendations", []):
                if isinstance(item, dict) and item.get("ResourceArn") == instance.arn:
                    recommendations.append(_recommendation_from_payload(item))
            marker = response.get("Marker")
            next_marker = str(marker) if marker else None
            if next_marker is None:
                return recommendations

    def _parameter_groups(self, instance: RDSInstance) -> list[RDSParameterGroupEvidence]:
        groups: list[RDSParameterGroupEvidence] = []
        for group in instance.parameter_groups:
            groups.append(
                RDSParameterGroupEvidence(
                    name=group.name,
                    parameters=self._parameters_for_group(group.name),
                )
            )
        return groups

    def _parameters_for_group(self, group_name: str) -> list[RDSParameterEvidence]:
        parameters: list[RDSParameterEvidence] = []
        next_marker: str | None = None
        while True:
            kwargs: dict[str, Any] = {
                "DBParameterGroupName": group_name,
                "MaxRecords": 100,
            }
            if next_marker is not None:
                kwargs["Marker"] = next_marker
            response = self._client.describe_db_parameters(**kwargs)
            for item in response.get("Parameters", []):
                if isinstance(item, dict):
                    parameters.append(_parameter_from_payload(item))
            marker = response.get("Marker")
            next_marker = str(marker) if marker else None
            if next_marker is None:
                return parameters


def _pending_maintenance_from_payload(payload: dict[str, Any]) -> RDSPendingMaintenanceAction:
    return RDSPendingMaintenanceAction(
        action=_optional_str(payload.get("Action")),
        description=_optional_str(payload.get("Description")),
        opt_in_status=_optional_str(payload.get("OptInStatus")),
        auto_applied_after=_optional_datetime(payload.get("AutoAppliedAfterDate")),
        forced_apply_at=_optional_datetime(payload.get("ForcedApplyDate")),
        current_apply_at=_optional_datetime(payload.get("CurrentApplyDate")),
    )


def _recommendation_from_payload(payload: dict[str, Any]) -> RDSRecommendationEvidence:
    return RDSRecommendationEvidence(
        recommendation_id=str(payload.get("RecommendationId", "")),
        type_id=_optional_str(payload.get("TypeId")),
        severity=_optional_str(payload.get("Severity")),
        status=_optional_str(payload.get("Status")),
        category=_optional_str(payload.get("Category")),
        source=_optional_str(payload.get("Source")),
        updated_at=_optional_datetime(payload.get("UpdatedTime")),
        detection=_optional_str(payload.get("Detection")),
        recommendation=_optional_str(payload.get("Recommendation")),
        description=_optional_str(payload.get("Description")),
        reason=_optional_str(payload.get("Reason")),
        impact=_optional_str(payload.get("Impact")),
    )


def _parameter_from_payload(payload: dict[str, Any]) -> RDSParameterEvidence:
    return RDSParameterEvidence(
        name=str(payload.get("ParameterName", "")),
        value=_optional_str(payload.get("ParameterValue")),
        source=_optional_str(payload.get("Source")),
        apply_type=_optional_str(payload.get("ApplyType")),
        data_type=_optional_str(payload.get("DataType")),
        allowed_values=_optional_str(payload.get("AllowedValues")),
        is_modifiable=(
            bool(payload["IsModifiable"]) if payload.get("IsModifiable") is not None else None
        ),
        minimum_engine_version=_optional_str(payload.get("MinimumEngineVersion")),
        apply_method=_optional_str(payload.get("ApplyMethod")),
    )


def _optional_datetime(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None
