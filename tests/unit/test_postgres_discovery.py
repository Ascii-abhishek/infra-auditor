from collections.abc import Iterator, Sequence

import pytest

from infra_auditor.collectors.postgres.discovery import (
    DATABASE_INVENTORY_SQL,
    DatabaseDiscoveryCollector,
    DatabaseKind,
)
from infra_auditor.exceptions import CollectorQueryError


class FakeConnection:
    def __init__(self, rows: list[Sequence[object]], should_fail: bool = False) -> None:
        self.rows = rows
        self.should_fail = should_fail
        self.query: str | None = None

    def execute(self, query: str) -> Iterator[Sequence[object]]:
        self.query = query
        if self.should_fail:
            raise RuntimeError("permission denied")
        return iter(self.rows)


def test_database_discovery_uses_fixed_catalog_sql() -> None:
    connection = FakeConnection(
        [
            ("postgres", True, False),
            ("rdsadmin", False, False),
            ("template1", True, True),
            ("raptor_catalog", True, False),
        ]
    )

    databases = DatabaseDiscoveryCollector().collect(connection)

    assert connection.query == DATABASE_INVENTORY_SQL
    assert databases[0].name == "postgres"
    assert databases[0].kind == DatabaseKind.SYSTEM
    assert databases[1].name == "rdsadmin"
    assert databases[1].kind == DatabaseKind.SYSTEM
    assert databases[2].is_template is True
    assert databases[2].connection_eligible is False
    assert databases[3].name == "raptor_catalog"
    assert databases[3].kind == DatabaseKind.APPLICATION
    assert databases[3].connection_eligible is True


def test_database_discovery_wraps_query_failures() -> None:
    connection = FakeConnection([], should_fail=True)

    with pytest.raises(CollectorQueryError):
        DatabaseDiscoveryCollector().collect(connection)
