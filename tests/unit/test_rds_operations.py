from datetime import UTC, datetime
from typing import Any

from infra_auditor.collectors.aws.models import RDSInstance, RDSParameterGroup
from infra_auditor.collectors.aws.rds_operations import RDSOperationsCollector


class FakeRDSClient:
    def __init__(self) -> None:
        self.recommendation_calls: list[dict[str, Any]] = []

    def describe_pending_maintenance_actions(self, **_kwargs: Any) -> dict[str, Any]:
        return {
            "PendingMaintenanceActions": [
                {
                    "ResourceIdentifier": ("arn:aws:rds:ap-south-1:123456789012:db:database-1"),
                    "PendingMaintenanceActionDetails": [
                        {
                            "Action": "system-update",
                            "Description": "Pending system update",
                            "OptInStatus": "next-maintenance",
                            "CurrentApplyDate": datetime(2026, 9, 4, tzinfo=UTC),
                        }
                    ],
                }
            ]
        }

    def describe_db_recommendations(self, **kwargs: Any) -> dict[str, Any]:
        self.recommendation_calls.append(kwargs)
        return {
            "DBRecommendations": [
                {
                    "RecommendationId": "rec-1",
                    "ResourceArn": "arn:aws:rds:ap-south-1:123456789012:db:database-1",
                    "TypeId": "storage-config",
                    "Severity": "medium",
                    "Status": "active",
                    "Category": "performance",
                    "Recommendation": "Review storage configuration.",
                },
                {
                    "RecommendationId": "rec-other",
                    "ResourceArn": "arn:aws:rds:ap-south-1:123456789012:db:database-2",
                },
            ]
        }

    def describe_db_parameters(self, **_kwargs: Any) -> dict[str, Any]:
        return {
            "Parameters": [
                {
                    "ParameterName": "log_min_duration_statement",
                    "ParameterValue": "1000",
                    "Source": "user",
                    "ApplyType": "dynamic",
                    "DataType": "integer",
                    "IsModifiable": True,
                    "ApplyMethod": "immediate",
                }
            ]
        }


def test_rds_operations_collector_collects_maintenance_recommendations_and_parameters() -> None:
    client = FakeRDSClient()

    evidence = RDSOperationsCollector(client).collect(
        RDSInstance(
            alias="db",
            identifier="database-1",
            arn="arn:aws:rds:ap-south-1:123456789012:db:database-1",
            region="ap-south-1",
            parameter_groups=[RDSParameterGroup(name="default.postgres15")],
        )
    )

    assert evidence.pending_maintenance[0].action == "system-update"
    assert len(evidence.recommendations) == 1
    assert evidence.recommendations[0].recommendation_id == "rec-1"
    assert client.recommendation_calls == [{"MaxRecords": 50}]
    assert evidence.parameter_groups[0].name == "default.postgres15"
    assert evidence.parameter_groups[0].parameters[0].name == "log_min_duration_statement"
