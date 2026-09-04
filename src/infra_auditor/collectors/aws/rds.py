"""Read-only AWS RDS discovery."""

from infra_auditor.collectors.aws.client import RDSClient
from infra_auditor.collectors.aws.models import RDSInstance, rds_instance_from_boto_response
from infra_auditor.config import InstanceConfig
from infra_auditor.exceptions import AWSDiscoveryError


class RDSDiscovery:
    """Discover metadata for configured RDS DB instances."""

    def __init__(self, client: RDSClient) -> None:
        self._client = client

    def describe_instance(self, *, alias: str, config: InstanceConfig, region: str) -> RDSInstance:
        try:
            response = self._client.describe_db_instances(
                DBInstanceIdentifier=config.db_instance_identifier
            )
        except Exception as exc:  # noqa: BLE001 - AWS clients raise provider-specific exceptions.
            raise AWSDiscoveryError(
                f"failed to describe RDS instance {config.db_instance_identifier}"
            ) from exc

        instances = response.get("DBInstances", [])
        if not isinstance(instances, list) or len(instances) != 1:
            count = len(instances) if isinstance(instances, list) else "unknown"
            raise AWSDiscoveryError(
                f"expected one RDS instance for {config.db_instance_identifier}, got {count}"
            )

        payload = instances[0]
        if not isinstance(payload, dict):
            raise AWSDiscoveryError(
                f"RDS response for {config.db_instance_identifier} was not an object"
            )

        return rds_instance_from_boto_response(alias=alias, region=region, payload=payload)
