from datetime import UTC, datetime
from typing import Any

from infra_auditor.collectors.aws.models import rds_instance_from_boto_response
from infra_auditor.collectors.aws.rds import RDSDiscovery
from infra_auditor.config import InstanceConfig


class FakeRDSClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.requested_identifier: str | None = None

    def describe_db_instances(self, DBInstanceIdentifier: str) -> dict[str, Any]:
        self.requested_identifier = DBInstanceIdentifier
        return {"DBInstances": [self.payload]}


def rds_payload() -> dict[str, Any]:
    return {
        "DBInstanceIdentifier": "cleancatalograptorsupplies",
        "DBInstanceArn": "arn:aws:rds:ap-south-1:111122223333:db:cleancatalograptorsupplies",
        "Engine": "postgres",
        "EngineVersion": "15.17",
        "DBInstanceClass": "db.m6g.xlarge",
        "DBInstanceStatus": "available",
        "AllocatedStorage": 1200,
        "MaxAllocatedStorage": 0,
        "StorageType": "gp3",
        "Iops": 12000,
        "StorageThroughput": 500,
        "MultiAZ": False,
        "PubliclyAccessible": True,
        "IAMDatabaseAuthenticationEnabled": False,
        "DatabaseInsightsMode": "standard",
        "PerformanceInsightsEnabled": True,
        "PerformanceInsightsRetentionPeriod": 7,
        "MonitoringInterval": 0,
        "EnabledCloudwatchLogsExports": ["postgresql"],
        "DBParameterGroups": [
            {
                "DBParameterGroupName": "raptor-catalog-optimization",
                "ParameterApplyStatus": "in-sync",
            }
        ],
        "BackupRetentionPeriod": 7,
        "DeletionProtection": True,
        "StorageEncrypted": True,
        "Endpoint": {"Address": "example.rds.amazonaws.com", "Port": 5432},
        "DBSubnetGroup": {
            "VpcId": "vpc-example",
            "Subnets": [
                {
                    "SubnetIdentifier": "subnet-example",
                    "SubnetStatus": "Active",
                    "SubnetAvailabilityZone": {"Name": "ap-south-1a"},
                }
            ],
        },
        "VpcSecurityGroups": [{"VpcSecurityGroupId": "sg-example", "Status": "active"}],
        "PreferredMaintenanceWindow": "sun:18:00-sun:18:30",
        "PreferredBackupWindow": "17:30-18:00",
        "CertificateDetails": {
            "CAIdentifier": "rds-ca-rsa2048-g1",
            "ValidTill": datetime(2028, 1, 1, tzinfo=UTC),
        },
    }


def test_rds_instance_from_boto_response_normalizes_fields() -> None:
    instance = rds_instance_from_boto_response(
        alias="raptor-catalog", region="ap-south-1", payload=rds_payload()
    )

    assert instance.alias == "raptor-catalog"
    assert instance.identifier == "cleancatalograptorsupplies"
    assert instance.endpoint is not None
    assert instance.endpoint.address == "example.rds.amazonaws.com"
    assert instance.storage_throughput == 500
    assert instance.parameter_groups[0].name == "raptor-catalog-optimization"
    assert instance.subnets[0].availability_zone == "ap-south-1a"
    assert instance.vpc_security_groups[0].vpc_security_group_id == "sg-example"


def test_rds_discovery_uses_configured_identifier() -> None:
    client = FakeRDSClient(rds_payload())
    discovery = RDSDiscovery(client)

    instance = discovery.describe_instance(
        alias="raptor-catalog",
        region="ap-south-1",
        config=InstanceConfig(
            db_instance_identifier="cleancatalograptorsupplies",
            secret_id="infra-auditor/postgres/raptor-catalog",
        ),
    )

    assert client.requested_identifier == "cleancatalograptorsupplies"
    assert instance.engine_version == "15.17"
