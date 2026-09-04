from infra_auditor.collectors.aws.cloudwatch_metrics import (
    MetricSummary,
    RDSCloudWatchMetricsEvidence,
)
from infra_auditor.collectors.aws.models import RDSInstance, RDSParameterGroup
from infra_auditor.collectors.aws.network import RDSSecurityGroupEvidence
from infra_auditor.collectors.aws.rds_operations import (
    RDSOperationsEvidence,
    RDSPendingMaintenanceAction,
    RDSRecommendationEvidence,
)
from infra_auditor.rules.aws_rds import evaluate_aws_rds_findings


def test_aws_rds_rules_emit_public_ops_and_metric_findings() -> None:
    findings = evaluate_aws_rds_findings(
        run_id="run-1",
        instance_alias="db",
        aws_instance=RDSInstance(
            alias="db",
            identifier="database-1",
            region="ap-south-1",
            allocated_storage_gib=100,
            publicly_accessible=True,
            parameter_groups=[RDSParameterGroup(name="pg-1", status="pending-reboot")],
        ),
        security_groups=RDSSecurityGroupEvidence(
            database_port=5432,
            security_groups=[],
            public_database_port_ingress=True,
        ),
        cloudwatch_metrics=RDSCloudWatchMetricsEvidence(
            lookback_hours=24,
            period_seconds=300,
            start_time="2026-09-03T00:00:00+00:00",
            end_time="2026-09-04T00:00:00+00:00",
            metrics=[
                MetricSummary(
                    query_id="cpu",
                    metric_name="CPUUtilization",
                    stat="Average",
                    datapoint_count=2,
                    maximum=95.0,
                    average=70.0,
                ),
                MetricSummary(
                    query_id="storage",
                    metric_name="FreeStorageSpace",
                    stat="Average",
                    datapoint_count=2,
                    minimum=8 * 1024**3,
                ),
                MetricSummary(
                    query_id="memory",
                    metric_name="FreeableMemory",
                    stat="Average",
                    datapoint_count=2,
                    minimum=512 * 1024**2,
                ),
            ],
        ),
        rds_operations=RDSOperationsEvidence(
            pending_maintenance=[RDSPendingMaintenanceAction(action="system-update")],
            recommendations=[
                RDSRecommendationEvidence(
                    recommendation_id="rec-1",
                    severity="medium",
                    status="active",
                    category="performance",
                )
            ],
        ),
    )

    assert {finding.rule_id for finding in findings} == {
        "CFG002",
        "CFG009",
        "OPS001",
        "OPS007",
        "OPS008",
        "OPS012",
        "OPS013",
        "SEC001",
    }
