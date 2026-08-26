from typing import Any

import pytest

from infra_auditor.exceptions import SecretResolutionError
from infra_auditor.secrets.aws import AWSSecretsManagerCredentialProvider


class FakeSecretsClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.requested_secret_id: str | None = None

    def get_secret_value(self, SecretId: str) -> dict[str, Any]:
        self.requested_secret_id = SecretId
        return self.response


def test_secrets_manager_provider_validates_expected_shape() -> None:
    client = FakeSecretsClient(
        {"SecretString": '{"username": "prj_rl_rds_auditor_prod", "password": "fake-password"}'}
    )
    provider = AWSSecretsManagerCredentialProvider(client)

    credentials = provider.get_postgres_credentials("infra-auditor/postgres/raptor-catalog")

    assert client.requested_secret_id == "infra-auditor/postgres/raptor-catalog"
    assert credentials.username == "prj_rl_rds_auditor_prod"
    assert credentials.password.get_secret_value() == "fake-password"
    assert "fake-password" not in repr(credentials)


def test_secrets_manager_provider_rejects_missing_secret_string() -> None:
    provider = AWSSecretsManagerCredentialProvider(FakeSecretsClient({}))

    with pytest.raises(SecretResolutionError, match="SecretString"):
        provider.get_postgres_credentials("infra-auditor/postgres/raptor-catalog")


def test_secrets_manager_provider_rejects_missing_password() -> None:
    provider = AWSSecretsManagerCredentialProvider(
        FakeSecretsClient({"SecretString": '{"username": "prj_rl_rds_auditor_prod"}'})
    )

    with pytest.raises(SecretResolutionError, match="schema validation"):
        provider.get_postgres_credentials("infra-auditor/postgres/raptor-catalog")
