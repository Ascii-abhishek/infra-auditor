"""Safe PostgreSQL database inventory collector."""

from collections.abc import Iterator, Sequence
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from infra_auditor.exceptions import CollectorQueryError

DATABASE_INVENTORY_SQL = """
SELECT datname, datallowconn, datistemplate
FROM pg_catalog.pg_database
ORDER BY datname
"""

SYSTEM_DATABASE_NAMES = frozenset({"postgres", "rdsadmin", "template0", "template1"})


class DatabaseKind(StrEnum):
    """High-level database classification."""

    SYSTEM = "system"
    APPLICATION = "application"


class DatabaseInfo(BaseModel):
    """Discovered database inventory evidence."""

    name: str
    allow_connections: bool
    is_template: bool
    kind: DatabaseKind
    connection_eligible: bool

    model_config = ConfigDict(extra="forbid")


class CursorLike(Protocol):
    """Small iterable cursor surface required by this collector."""

    def __iter__(self) -> Iterator[Sequence[object]]:
        """Iterate query rows."""


class ConnectionLike(Protocol):
    """Small connection surface required by this collector."""

    def execute(self, query: str) -> CursorLike:
        """Execute fixed collector SQL."""


class DatabaseDiscoveryCollector:
    """Collect PostgreSQL database inventory without reading application rows."""

    name = "postgres.database_inventory"

    def collect(self, connection: ConnectionLike) -> list[DatabaseInfo]:
        try:
            rows = list(connection.execute(DATABASE_INVENTORY_SQL))
        except Exception as exc:  # noqa: BLE001 - drivers expose provider-specific query errors.
            raise CollectorQueryError("failed to collect PostgreSQL database inventory") from exc

        databases: list[DatabaseInfo] = []
        for row in rows:
            if len(row) != 3:
                raise CollectorQueryError("database inventory query returned unexpected row shape")
            name = str(row[0])
            allow_connections = bool(row[1])
            is_template = bool(row[2])
            kind = (
                DatabaseKind.SYSTEM
                if name in SYSTEM_DATABASE_NAMES or is_template
                else DatabaseKind.APPLICATION
            )
            databases.append(
                DatabaseInfo(
                    name=name,
                    allow_connections=allow_connections,
                    is_template=is_template,
                    kind=kind,
                    connection_eligible=allow_connections and not is_template,
                )
            )
        return databases
