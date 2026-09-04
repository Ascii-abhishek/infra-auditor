from collections.abc import Iterator, Sequence
from decimal import Decimal

from infra_auditor.collectors.postgres.activity import (
    ACTIVITY_SUMMARY_SQL,
    ActivitySummaryCollector,
)


class FakeConnection:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def execute(self, query: str) -> Iterator[Sequence[object]]:
        self.queries.append(query)
        return iter(
            [
                (
                    "app_db",
                    "app_user",
                    "orders-api",
                    "10.0.1.10",
                    "active",
                    "IO",
                    3,
                    Decimal("120.5"),
                    Decimal("30.0"),
                ),
                ("app_db", "app_user", "", "10.0.1.11", "idle in transaction", "", 1, 20, 900),
            ]
        )


def test_activity_summary_collector_uses_fixed_sql_and_aggregates_counts() -> None:
    connection = FakeConnection()

    evidence = ActivitySummaryCollector().collect(connection)

    assert connection.queries == [ACTIVITY_SUMMARY_SQL]
    assert evidence.total_connections == 4
    assert evidence.idle_in_transaction_connections == 1
    assert evidence.missing_application_name_connections == 1
    assert evidence.groups[0].application_name == "orders-api"
    assert evidence.groups[0].oldest_backend_age_seconds == 120.5
    assert evidence.groups[1].application_name is None
