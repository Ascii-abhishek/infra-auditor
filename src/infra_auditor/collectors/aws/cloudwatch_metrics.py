"""CloudWatch RDS metric collection."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from infra_auditor.collectors.aws.client import CloudWatchClient
from infra_auditor.collectors.aws.models import RDSInstance
from infra_auditor.exceptions import AWSDiscoveryError
from infra_auditor.models.common import utc_now


@dataclass(frozen=True)
class RDSMetricSpec:
    """Fixed CloudWatch RDS metric query definition."""

    query_id: str
    metric_name: str
    stat: str


RDS_METRIC_SPECS = (
    RDSMetricSpec("cpu_utilization_average", "CPUUtilization", "Average"),
    RDSMetricSpec("database_connections_average", "DatabaseConnections", "Average"),
    RDSMetricSpec("freeable_memory_average", "FreeableMemory", "Average"),
    RDSMetricSpec("free_storage_space_average", "FreeStorageSpace", "Average"),
    RDSMetricSpec("read_latency_average", "ReadLatency", "Average"),
    RDSMetricSpec("write_latency_average", "WriteLatency", "Average"),
    RDSMetricSpec("read_iops_average", "ReadIOPS", "Average"),
    RDSMetricSpec("write_iops_average", "WriteIOPS", "Average"),
    RDSMetricSpec("disk_queue_depth_average", "DiskQueueDepth", "Average"),
    RDSMetricSpec("burst_balance_average", "BurstBalance", "Average"),
)


class MetricSummary(BaseModel):
    """Aggregated metric evidence over a bounded lookback window."""

    query_id: str
    metric_name: str
    stat: str
    label: str | None = None
    status_code: str | None = None
    datapoint_count: int = Field(ge=0)
    minimum: float | None = None
    maximum: float | None = None
    average: float | None = None
    latest: float | None = None
    latest_timestamp: str | None = None

    model_config = ConfigDict(extra="forbid")


class RDSCloudWatchMetricsEvidence(BaseModel):
    """CloudWatch metric evidence for one RDS DB instance."""

    lookback_hours: int
    period_seconds: int
    start_time: str
    end_time: str
    metrics: list[MetricSummary] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class CloudWatchRDSMetricsCollector:
    """Collect a fixed set of RDS CloudWatch metrics."""

    name = "aws.cloudwatch.rds_metrics"

    def __init__(
        self,
        client: CloudWatchClient,
        *,
        lookback_hours: int,
        period_seconds: int,
    ) -> None:
        self._client = client
        self._lookback_hours = lookback_hours
        self._period_seconds = period_seconds

    def collect(self, instance: RDSInstance) -> RDSCloudWatchMetricsEvidence:
        end_time = utc_now()
        start_time = end_time - timedelta(hours=self._lookback_hours)
        queries = [
            {
                "Id": spec.query_id,
                "MetricStat": {
                    "Metric": {
                        "Namespace": "AWS/RDS",
                        "MetricName": spec.metric_name,
                        "Dimensions": [
                            {
                                "Name": "DBInstanceIdentifier",
                                "Value": instance.identifier,
                            }
                        ],
                    },
                    "Period": self._period_seconds,
                    "Stat": spec.stat,
                },
                "ReturnData": True,
            }
            for spec in RDS_METRIC_SPECS
        ]

        try:
            results = self._get_all_metric_data(
                queries=queries,
                start_time=start_time,
                end_time=end_time,
            )
        except Exception as exc:  # noqa: BLE001 - AWS clients raise provider-specific errors.
            raise AWSDiscoveryError(
                f"failed to collect CloudWatch metrics for {instance.identifier}"
            ) from exc

        specs_by_id = {spec.query_id: spec for spec in RDS_METRIC_SPECS}
        return RDSCloudWatchMetricsEvidence(
            lookback_hours=self._lookback_hours,
            period_seconds=self._period_seconds,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            metrics=[_metric_summary(payload, specs_by_id) for payload in results],
        )

    def _get_all_metric_data(
        self,
        *,
        queries: list[dict[str, Any]],
        start_time: object,
        end_time: object,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        next_token: str | None = None
        while True:
            kwargs: dict[str, Any] = {
                "MetricDataQueries": queries,
                "StartTime": start_time,
                "EndTime": end_time,
                "ScanBy": "TimestampAscending",
                "MaxDatapoints": 100800,
            }
            if next_token is not None:
                kwargs["NextToken"] = next_token
            response = self._client.get_metric_data(**kwargs)
            for item in response.get("MetricDataResults", []):
                if isinstance(item, dict):
                    results.append(item)
            token = response.get("NextToken")
            next_token = str(token) if token else None
            if next_token is None:
                return results


def _metric_summary(
    payload: dict[str, Any],
    specs_by_id: dict[str, RDSMetricSpec],
) -> MetricSummary:
    query_id = str(payload.get("Id", "unknown"))
    spec = specs_by_id.get(query_id)
    values = [float(value) for value in payload.get("Values", []) if isinstance(value, int | float)]
    timestamps = payload.get("Timestamps", [])
    latest_timestamp = timestamps[-1].isoformat() if timestamps else None

    return MetricSummary(
        query_id=query_id,
        metric_name=spec.metric_name if spec is not None else query_id,
        stat=spec.stat if spec is not None else "unknown",
        label=str(payload.get("Label")) if payload.get("Label") is not None else None,
        status_code=str(payload.get("StatusCode")) if payload.get("StatusCode") else None,
        datapoint_count=len(values),
        minimum=min(values) if values else None,
        maximum=max(values) if values else None,
        average=sum(values) / len(values) if values else None,
        latest=values[-1] if values else None,
        latest_timestamp=latest_timestamp,
    )
