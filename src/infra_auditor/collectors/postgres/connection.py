"""Safe psycopg 3 connection factory for collector use."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg

from infra_auditor.collectors.aws.models import RDSInstance
from infra_auditor.config import PostgresSSLMode
from infra_auditor.exceptions import DatabaseConnectionError
from infra_auditor.secrets.aws import PostgresCredentials


class PostgresConnectionFactory:
    """Create bounded PostgreSQL connections without pooling."""

    def __init__(
        self,
        *,
        ssl_mode: PostgresSSLMode,
        connect_timeout_seconds: int,
        application_name: str,
    ) -> None:
        self._ssl_mode = ssl_mode
        self._connect_timeout_seconds = connect_timeout_seconds
        self._application_name = application_name

    @contextmanager
    def connect(
        self, *, instance: RDSInstance, credentials: PostgresCredentials, database: str
    ) -> Iterator[Any]:
        if instance.endpoint is None:
            raise DatabaseConnectionError(f"RDS instance has no endpoint: {instance.identifier}")

        try:
            with psycopg.connect(
                host=instance.endpoint.address,
                port=instance.endpoint.port,
                dbname=database,
                user=credentials.username,
                password=credentials.password.get_secret_value(),
                connect_timeout=self._connect_timeout_seconds,
                application_name=self._application_name,
                sslmode=self._ssl_mode.value,
            ) as connection:
                connection.autocommit = True
                yield connection
        except Exception as exc:  # noqa: BLE001 - psycopg exposes multiple connection errors.
            raise DatabaseConnectionError(
                f"failed to connect to {instance.identifier}/{database}"
            ) from exc
