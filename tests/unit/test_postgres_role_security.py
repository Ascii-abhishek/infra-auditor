from collections.abc import Iterator, Sequence
from datetime import UTC, datetime

import pytest

from infra_auditor.collectors.postgres.role_security import (
    ROLE_ATTRIBUTES_SQL,
    ROLE_MEMBERSHIPS_SQL,
    RoleSecurityCollector,
)
from infra_auditor.exceptions import CollectorQueryError


class FakeConnection:
    def __init__(
        self,
        *,
        role_rows: list[Sequence[object]],
        membership_rows: list[Sequence[object]],
        should_fail: bool = False,
    ) -> None:
        self.role_rows = role_rows
        self.membership_rows = membership_rows
        self.should_fail = should_fail
        self.queries: list[str] = []

    def execute(self, query: str) -> Iterator[Sequence[object]]:
        self.queries.append(query)
        if self.should_fail:
            raise RuntimeError("permission denied")
        if query == ROLE_ATTRIBUTES_SQL:
            return iter(self.role_rows)
        if query == ROLE_MEMBERSHIPS_SQL:
            return iter(self.membership_rows)
        raise AssertionError(f"unexpected query: {query}")


def test_role_security_collector_uses_fixed_catalog_sql() -> None:
    valid_until = datetime(2027, 1, 1, tzinfo=UTC)
    connection = FakeConnection(
        role_rows=[
            (
                "app_user",
                True,
                True,
                False,
                False,
                False,
                False,
                False,
                10,
                valid_until,
            ),
            ("rds_superuser", False, True, False, False, False, False, False, -1, None),
        ],
        membership_rows=[("app_user", "rds_superuser", "postgres", False)],
    )

    evidence = RoleSecurityCollector().collect(connection)

    assert connection.queries == [ROLE_ATTRIBUTES_SQL, ROLE_MEMBERSHIPS_SQL]
    assert evidence.roles[0].name == "app_user"
    assert evidence.roles[0].can_login is True
    assert evidence.roles[0].connection_limit == 10
    assert evidence.roles[0].valid_until == valid_until
    assert evidence.memberships[0].member == "app_user"
    assert evidence.memberships[0].role == "rds_superuser"
    assert evidence.memberships[0].grantor == "postgres"


def test_role_security_collector_wraps_query_failures() -> None:
    connection = FakeConnection(role_rows=[], membership_rows=[], should_fail=True)

    with pytest.raises(CollectorQueryError):
        RoleSecurityCollector().collect(connection)


def test_role_security_collector_rejects_unexpected_row_shape() -> None:
    connection = FakeConnection(role_rows=[("app_user", True)], membership_rows=[])

    with pytest.raises(CollectorQueryError, match="unexpected row shape"):
        RoleSecurityCollector().collect(connection)
