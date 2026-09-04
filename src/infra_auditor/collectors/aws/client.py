"""Small AWS client factory boundary."""

from typing import Any, Protocol, cast

import boto3

from infra_auditor.config import AppSettings


class AWSClientFactory(Protocol):
    """Subset of boto3 Session used by this project."""

    def client(self, service_name: str, region_name: str | None = None) -> Any:
        """Create an AWS service client."""


class RDSClient(Protocol):
    """Subset of the RDS client used for read-only audit evidence."""

    def describe_db_instances(self, DBInstanceIdentifier: str) -> dict[str, Any]:
        """Describe one RDS DB instance."""

    def describe_db_recommendations(self, **kwargs: Any) -> dict[str, Any]:
        """Describe RDS recommendations."""

    def describe_pending_maintenance_actions(self, **kwargs: Any) -> dict[str, Any]:
        """Describe pending maintenance actions."""

    def describe_db_parameters(self, **kwargs: Any) -> dict[str, Any]:
        """Describe DB parameter group parameters."""


class SecretsManagerClient(Protocol):
    """Subset of the Secrets Manager client used by the credential provider."""

    def get_secret_value(self, SecretId: str) -> dict[str, Any]:
        """Read one secret value."""


class S3PutObjectClient(Protocol):
    """Subset of the S3 client used by snapshot persistence."""

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        """Write one S3 object."""


class S3ReadClient(Protocol):
    """Subset of the S3 client used by report/UI snapshot reads."""

    def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]:
        """List stored snapshot objects."""

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        """Read one stored snapshot object."""


class CloudWatchClient(Protocol):
    """Subset of the CloudWatch client used by RDS metric collection."""

    def get_metric_data(self, **kwargs: Any) -> dict[str, Any]:
        """Read CloudWatch metric data."""


class EC2Client(Protocol):
    """Subset of the EC2 client used by network evidence collection."""

    def describe_security_groups(self, **kwargs: Any) -> dict[str, Any]:
        """Describe VPC security groups."""


def create_boto3_session(settings: AppSettings) -> AWSClientFactory:
    kwargs: dict[str, str] = {"region_name": settings.aws_region}
    if settings.aws_profile:
        kwargs["profile_name"] = settings.aws_profile
    return cast(AWSClientFactory, boto3.Session(**kwargs))


def create_rds_client(session: AWSClientFactory, region: str) -> RDSClient:
    return cast(RDSClient, session.client("rds", region_name=region))


def create_secretsmanager_client(session: AWSClientFactory, region: str) -> SecretsManagerClient:
    return cast(SecretsManagerClient, session.client("secretsmanager", region_name=region))


def create_s3_client(session: AWSClientFactory, region: str) -> S3PutObjectClient:
    return cast(S3PutObjectClient, session.client("s3", region_name=region))


def create_s3_read_client(session: AWSClientFactory, region: str) -> S3ReadClient:
    return cast(S3ReadClient, session.client("s3", region_name=region))


def create_cloudwatch_client(session: AWSClientFactory, region: str) -> CloudWatchClient:
    return cast(CloudWatchClient, session.client("cloudwatch", region_name=region))


def create_ec2_client(session: AWSClientFactory, region: str) -> EC2Client:
    return cast(EC2Client, session.client("ec2", region_name=region))
