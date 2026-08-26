"""Small AWS client factory boundary."""

from typing import Any, Protocol, cast

import boto3

from infra_auditor.config import AppSettings


class AWSClientFactory(Protocol):
    """Subset of boto3 Session used by this project."""

    def client(self, service_name: str, region_name: str | None = None) -> Any:
        """Create an AWS service client."""


class RDSDescribeClient(Protocol):
    """Subset of the RDS client used for read-only discovery."""

    def describe_db_instances(self, DBInstanceIdentifier: str) -> dict[str, Any]:
        """Describe one RDS DB instance."""


class SecretsManagerClient(Protocol):
    """Subset of the Secrets Manager client used by the credential provider."""

    def get_secret_value(self, SecretId: str) -> dict[str, Any]:
        """Read one secret value."""


def create_boto3_session(settings: AppSettings) -> AWSClientFactory:
    kwargs: dict[str, str] = {"region_name": settings.aws_region}
    if settings.aws_profile:
        kwargs["profile_name"] = settings.aws_profile
    return cast(AWSClientFactory, boto3.Session(**kwargs))


def create_rds_client(session: AWSClientFactory, region: str) -> RDSDescribeClient:
    return cast(RDSDescribeClient, session.client("rds", region_name=region))


def create_secretsmanager_client(session: AWSClientFactory, region: str) -> SecretsManagerClient:
    return cast(SecretsManagerClient, session.client("secretsmanager", region_name=region))
