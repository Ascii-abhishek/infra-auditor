"""Safe PostgreSQL activity summary collector."""

from collections.abc import Iterator, Sequence
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from infra_auditor.exceptions import CollectorQueryError

ACTIVITY_SUMMARY_SQL = """
SELECT
    COALESCE(datname, '') AS database_name,
    COALESCE(usename, '') AS role_name,
    COALESCE(application_name, '') AS application_name,
    COALESCE(client_addr::text, '') AS client_address,
    COALESCE(state, '') AS state,
    COALESCE(wait_event_type, '') AS wait_event_type,
    COUNT(*) AS connection_count,
    MAX(EXTRACT(EPOCH FROM (clock_timestamp() - backend_start))) AS oldest_backend_age_seconds,
    MAX(EXTRACT(EPOCH FROM (clock_timestamp() - xact_start))) FILTER (
        WHERE xact_start IS NOT NULL
    ) AS oldest_transaction_age_seconds
FROM pg_catalog.pg_stat_activity
GROUP BY datname, usename, application_name, client_addr, state, wait_event_type
ORDER BY connection_count DESC, database_name, role_name, application_name
"""


class ActivityGroup(BaseModel):
    """Aggregated PostgreSQL session metadata, without query text."""

    database_name: str | None = None
    role_name: str | None = None
    application_name: str | None = None
    client_address: str | None = None
    state: str | None = None
    wait_event_type: str | None = None
    connection_count: int = Field(ge=0)
    oldest_backend_age_seconds: float | None = Field(default=None, ge=0)
    oldest_transaction_age_seconds: float | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid")


class PostgresActivityEvidence(BaseModel):
    """Aggregated PostgreSQL activity evidence."""

    total_connections: int = Field(ge=0)
    idle_in_transaction_connections: int = Field(ge=0)
    missing_application_name_connections: int = Field(ge=0)
    groups: list[ActivityGroup] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class CursorLike(Protocol):
    """Small iterable cursor surface required by this collector."""

    def __iter__(self) -> Iterator[Sequence[object]]:
        """Iterate query rows."""


class ConnectionLike(Protocol):
    """Small connection surface required by this collector."""

    def execute(self, query: str) -> CursorLike:
        """Execute fixed collector SQL."""


class ActivitySummaryCollector:
    """Collect aggregated activity metadata without collecting SQL text."""

    name = "postgres.activity_summary"

    def collect(self, connection: ConnectionLike) -> PostgresActivityEvidence:
        try:
            rows = list(connection.execute(ACTIVITY_SUMMARY_SQL))
        except Exception as exc:  # noqa: BLE001 - drivers expose provider-specific errors.
            raise CollectorQueryError("failed to collect PostgreSQL activity summary") from exc

        groups = [_activity_group_from_row(row) for row in rows]
        total_connections = sum(group.connection_count for group in groups)
        return PostgresActivityEvidence(
            total_connections=total_connections,
            idle_in_transaction_connections=sum(
                group.connection_count for group in groups if group.state == "idle in transaction"
            ),
            missing_application_name_connections=sum(
                group.connection_count for group in groups if not group.application_name
            ),
            groups=groups,
        )


def _activity_group_from_row(row: Sequence[object]) -> ActivityGroup:
    if len(row) != 9:
        raise CollectorQueryError("activity summary query returned unexpected row shape")
    return ActivityGroup(
        database_name=_optional_non_empty_str(row[0]),
        role_name=_optional_non_empty_str(row[1]),
        application_name=_optional_non_empty_str(row[2]),
        client_address=_optional_non_empty_str(row[3]),
        state=_optional_non_empty_str(row[4]),
        wait_event_type=_optional_non_empty_str(row[5]),
        connection_count=_required_int(row[6]),
        oldest_backend_age_seconds=_optional_float(row[7]),
        oldest_transaction_age_seconds=_optional_float(row[8]),
    )


def _optional_non_empty_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _required_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float | str | bytes | bytearray):
        return int(value)
    msg = f"expected int-compatible value, got {type(value).__name__}"
    raise TypeError(msg)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float | Decimal):
        return float(value)
    if isinstance(value, str | bytes | bytearray):
        return float(value)
    msg = f"expected float-compatible value, got {type(value).__name__}"
    raise TypeError(msg)
