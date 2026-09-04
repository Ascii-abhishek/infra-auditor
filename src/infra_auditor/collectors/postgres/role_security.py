"""Safe PostgreSQL role security collector."""

from collections.abc import Iterator, Sequence
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from infra_auditor.exceptions import CollectorQueryError

ROLE_ATTRIBUTES_SQL = """
SELECT
    rolname,
    rolcanlogin,
    rolinherit,
    rolsuper,
    rolcreaterole,
    rolcreatedb,
    rolreplication,
    rolbypassrls,
    rolconnlimit,
    CASE
        WHEN rolvaliduntil IN ('infinity'::timestamptz, '-infinity'::timestamptz)
            THEN NULL
        ELSE rolvaliduntil
    END AS rolvaliduntil
FROM pg_catalog.pg_roles
ORDER BY rolname
"""

ROLE_MEMBERSHIPS_SQL = """
SELECT
    member_role.rolname AS member,
    parent_role.rolname AS role,
    grantor_role.rolname AS grantor,
    membership.admin_option
FROM pg_catalog.pg_auth_members AS membership
JOIN pg_catalog.pg_roles AS member_role
    ON member_role.oid = membership.member
JOIN pg_catalog.pg_roles AS parent_role
    ON parent_role.oid = membership.roleid
LEFT JOIN pg_catalog.pg_roles AS grantor_role
    ON grantor_role.oid = membership.grantor
ORDER BY member_role.rolname, parent_role.rolname
"""


class PostgresRole(BaseModel):
    """Role attributes relevant to security rules."""

    name: str
    can_login: bool
    inherit: bool
    superuser: bool
    create_role: bool
    create_db: bool
    replication: bool
    bypass_rls: bool
    connection_limit: int
    valid_until: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class PostgresRoleMembership(BaseModel):
    """A direct PostgreSQL role membership edge."""

    member: str
    role: str
    grantor: str | None = None
    admin_option: bool

    model_config = ConfigDict(extra="forbid")


class PostgresRoleSecurityEvidence(BaseModel):
    """Cluster-wide role and membership evidence."""

    roles: list[PostgresRole] = Field(default_factory=list)
    memberships: list[PostgresRoleMembership] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class CursorLike(Protocol):
    """Small iterable cursor surface required by this collector."""

    def __iter__(self) -> Iterator[Sequence[object]]:
        """Iterate query rows."""


class ConnectionLike(Protocol):
    """Small connection surface required by this collector."""

    def execute(self, query: str) -> CursorLike:
        """Execute fixed collector SQL."""


class RoleSecurityCollector:
    """Collect role attributes and memberships without reading application rows."""

    name = "postgres.role_security"

    def collect(self, connection: ConnectionLike) -> PostgresRoleSecurityEvidence:
        roles = self._collect_roles(connection)
        memberships = self._collect_memberships(connection)
        return PostgresRoleSecurityEvidence(roles=roles, memberships=memberships)

    def _collect_roles(self, connection: ConnectionLike) -> list[PostgresRole]:
        try:
            rows = list(connection.execute(ROLE_ATTRIBUTES_SQL))
        except Exception as exc:  # noqa: BLE001 - drivers expose provider-specific errors.
            raise CollectorQueryError("failed to collect PostgreSQL role attributes") from exc

        roles: list[PostgresRole] = []
        for row in rows:
            if len(row) != 10:
                raise CollectorQueryError("role attributes query returned unexpected row shape")
            roles.append(
                PostgresRole(
                    name=str(row[0]),
                    can_login=bool(row[1]),
                    inherit=bool(row[2]),
                    superuser=bool(row[3]),
                    create_role=bool(row[4]),
                    create_db=bool(row[5]),
                    replication=bool(row[6]),
                    bypass_rls=bool(row[7]),
                    connection_limit=_required_int(row[8]),
                    valid_until=row[9] if isinstance(row[9], datetime) else None,
                )
            )
        return roles

    def _collect_memberships(self, connection: ConnectionLike) -> list[PostgresRoleMembership]:
        try:
            rows = list(connection.execute(ROLE_MEMBERSHIPS_SQL))
        except Exception as exc:  # noqa: BLE001 - drivers expose provider-specific errors.
            raise CollectorQueryError("failed to collect PostgreSQL role memberships") from exc

        memberships: list[PostgresRoleMembership] = []
        for row in rows:
            if len(row) != 4:
                raise CollectorQueryError("role memberships query returned unexpected row shape")
            memberships.append(
                PostgresRoleMembership(
                    member=str(row[0]),
                    role=str(row[1]),
                    grantor=str(row[2]) if row[2] is not None else None,
                    admin_option=bool(row[3]),
                )
            )
        return memberships


def _required_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float | str | bytes | bytearray):
        return int(value)
    msg = f"expected int-compatible value, got {type(value).__name__}"
    raise TypeError(msg)
