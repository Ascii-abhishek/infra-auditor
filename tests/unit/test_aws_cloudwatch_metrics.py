from datetime import UTC, datetime
from typing import Any

from infra_auditor.collectors.aws.cloudwatch_metrics import CloudWatchRDSMetricsCollector
from infra_auditor.collectors.aws.models import RDSInstance


class FakeCloudWatchClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def get_metric_data(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "MetricDataResults": [
                {
                    "Id": "cpu_utilization_average",
                    "Label": "CPUUtilization",
                    "StatusCode": "Complete",
                    "Timestamps": [
                        datetime(2026, 9, 3, 0, 0, tzinfo=UTC),
                        datetime(2026, 9, 3, 0, 5, tzinfo=UTC),
                    ],
                    "Values": [12.5, 25.0],
                },
                {
                    "Id": "free_storage_space_average",
                    "Label": "FreeStorageSpace",
                    "StatusCode": "Complete",
                    "Timestamps": [datetime(2026, 9, 3, 0, 5, tzinfo=UTC)],
                    "Values": [10.0],
                },
            ]
        }


def test_cloudwatch_rds_metrics_collector_summarizes_metric_data() -> None:
    client = FakeCloudWatchClient()
    collector = CloudWatchRDSMetricsCollector(
        client,
        lookback_hours=24,
        period_seconds=300,
    )

    evidence = collector.collect(
        RDSInstance(alias="db", identifier="database-1", region="ap-south-1")
    )

    assert evidence.lookback_hours == 24
    assert evidence.period_seconds == 300
    assert len(evidence.metrics) == 2
    cpu = evidence.metrics[0]
    assert cpu.metric_name == "CPUUtilization"
    assert cpu.datapoint_count == 2
    assert cpu.minimum == 12.5
    assert cpu.maximum == 25.0
    assert cpu.average == 18.75
    assert cpu.latest == 25.0
    assert cpu.latest_timestamp == "2026-09-03T00:05:00+00:00"
    assert client.calls[0]["MetricDataQueries"][0]["MetricStat"]["Metric"]["Dimensions"] == [
        {"Name": "DBInstanceIdentifier", "Value": "database-1"}
    ]
