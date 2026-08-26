"""AWS Secrets Manager credential provider."""

import json
from typing import Protocol

from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError

from infra_auditor.collectors.aws.client import SecretsManagerClient
from infra_auditor.exceptions import SecretResolutionError


class PostgresCredentials(BaseModel):
    """Validated PostgreSQL credentials from a trusted secret provider."""

    username: str
    password: SecretStr

    model_config = ConfigDict(extra="forbid")


class CredentialProvider(Protocol):
    """Boundary for database credential resolution."""

    def get_postgres_credentials(self, secret_id: str) -> PostgresCredentials:
        """Return credentials for one configured instance."""


class AWSSecretsManagerCredentialProvider:
    """Resolve PostgreSQL credentials from AWS Secrets Manager."""

    def __init__(self, client: SecretsManagerClient) -> None:
        self._client = client

    def get_postgres_credentials(self, secret_id: str) -> PostgresCredentials:
        try:
            response = self._client.get_secret_value(SecretId=secret_id)
        except Exception as exc:  # noqa: BLE001 - AWS clients raise provider-specific exceptions.
            raise SecretResolutionError(f"failed to retrieve secret: {secret_id}") from exc

        secret_string = response.get("SecretString")
        if not isinstance(secret_string, str):
            raise SecretResolutionError(f"secret does not contain SecretString: {secret_id}")

        try:
            raw = json.loads(secret_string)
        except json.JSONDecodeError as exc:
            raise SecretResolutionError(f"secret is not valid JSON: {secret_id}") from exc

        try:
            return PostgresCredentials.model_validate(raw)
        except ValidationError as exc:
            raise SecretResolutionError(f"secret schema validation failed: {secret_id}") from exc
