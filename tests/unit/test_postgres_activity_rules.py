from infra_auditor.collectors.postgres.activity import ActivityGroup, PostgresActivityEvidence
from infra_auditor.rules.postgres_activity import evaluate_postgres_activity_findings


def test_postgres_activity_rules_emit_connection_hygiene_findings() -> None:
    findings = evaluate_postgres_activity_findings(
        run_id="run-1",
        instance_alias="db",
        activity=PostgresActivityEvidence(
            total_connections=3,
            idle_in_transaction_connections=1,
            missing_application_name_connections=1,
            groups=[
                ActivityGroup(
                    database_name="app_db",
                    role_name="app_user",
                    application_name=None,
                    client_address="10.0.1.10",
                    state="idle in transaction",
                    wait_event_type=None,
                    connection_count=3,
                    oldest_transaction_age_seconds=1200,
                )
            ],
        ),
    )

    assert {finding.rule_id for finding in findings} == {
        "OPS003",
        "OPS005",
        "OPS014",
        "OPS015",
    }
