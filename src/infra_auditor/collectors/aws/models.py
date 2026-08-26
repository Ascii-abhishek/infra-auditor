"""Typed AWS RDS discovery evidence models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RDSEndpoint(BaseModel):
    """Network endpoint discovered from RDS."""

    address: str
    port: int

    model_config = ConfigDict(extra="forbid")


class RDSParameterGroup(BaseModel):
    """RDS DB parameter group association."""

    name: str
    status: str | None = None

    model_config = ConfigDict(extra="forbid")


class RDSVpcSecurityGroup(BaseModel):
    """VPC security group attached to an RDS instance."""

    vpc_security_group_id: str
    status: str | None = None

    model_config = ConfigDict(extra="forbid")


class RDSSubnet(BaseModel):
    """Subnet metadata attached through an RDS subnet group."""

    subnet_identifier: str
    availability_zone: str | None = None
    status: str | None = None

    model_config = ConfigDict(extra="forbid")


class RDSCertificate(BaseModel):
    """RDS certificate metadata."""

    ca_identifier: str | None = None
    valid_till: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class RDSInstance(BaseModel):
    """Normalized subset of RDS DB instance metadata needed for V1 evidence."""

    alias: str
    identifier: str
    arn: str | None = None
    region: str
    engine: str | None = None
    engine_version: str | None = None
    instance_class: str | None = None
    status: str | None = None
    allocated_storage_gib: int | None = Field(default=None, ge=0)
    max_allocated_storage_gib: int | None = Field(default=None, ge=0)
    storage_type: str | None = None
    iops: int | None = Field(default=None, ge=0)
    storage_throughput: int | None = Field(default=None, ge=0)
    multi_az: bool | None = None
    publicly_accessible: bool | None = None
    iam_database_authentication_enabled: bool | None = None
    database_insights_mode: str | None = None
    performance_insights_enabled: bool | None = None
    performance_insights_retention_days: int | None = Field(default=None, ge=0)
    enhanced_monitoring_interval_seconds: int | None = Field(default=None, ge=0)
    enabled_cloudwatch_logs_exports: list[str] = Field(default_factory=list)
    parameter_groups: list[RDSParameterGroup] = Field(default_factory=list)
    backup_retention_days: int | None = Field(default=None, ge=0)
    deletion_protection: bool | None = None
    storage_encrypted: bool | None = None
    endpoint: RDSEndpoint | None = None
    vpc_id: str | None = None
    subnets: list[RDSSubnet] = Field(default_factory=list)
    vpc_security_groups: list[RDSVpcSecurityGroup] = Field(default_factory=list)
    maintenance_window: str | None = None
    backup_window: str | None = None
    certificate: RDSCertificate | None = None

    model_config = ConfigDict(extra="forbid")


def rds_instance_from_boto_response(
    alias: str, region: str, payload: dict[str, Any]
) -> RDSInstance:
    """Normalize a boto3 DescribeDBInstances payload into typed evidence."""

    endpoint_payload = payload.get("Endpoint")
    endpoint = None
    if isinstance(endpoint_payload, dict):
        endpoint = RDSEndpoint(
            address=str(endpoint_payload.get("Address", "")),
            port=int(endpoint_payload.get("Port", 5432)),
        )

    subnet_group = payload.get("DBSubnetGroup")
    vpc_id = None
    subnets: list[RDSSubnet] = []
    if isinstance(subnet_group, dict):
        vpc_id = _optional_str(subnet_group.get("VpcId"))
        for subnet in _list_of_dicts(subnet_group.get("Subnets")):
            availability_zone = subnet.get("SubnetAvailabilityZone")
            subnets.append(
                RDSSubnet(
                    subnet_identifier=str(subnet.get("SubnetIdentifier", "")),
                    availability_zone=(
                        _optional_str(availability_zone.get("Name"))
                        if isinstance(availability_zone, dict)
                        else None
                    ),
                    status=_optional_str(subnet.get("SubnetStatus")),
                )
            )

    certificate_payload = payload.get("CertificateDetails")
    certificate = None
    if isinstance(certificate_payload, dict):
        valid_till = certificate_payload.get("ValidTill")
        certificate = RDSCertificate(
            ca_identifier=_optional_str(certificate_payload.get("CAIdentifier")),
            valid_till=valid_till if isinstance(valid_till, datetime) else None,
        )

    return RDSInstance(
        alias=alias,
        identifier=str(payload.get("DBInstanceIdentifier", "")),
        arn=_optional_str(payload.get("DBInstanceArn")),
        region=region,
        engine=_optional_str(payload.get("Engine")),
        engine_version=_optional_str(payload.get("EngineVersion")),
        instance_class=_optional_str(payload.get("DBInstanceClass")),
        status=_optional_str(payload.get("DBInstanceStatus")),
        allocated_storage_gib=_optional_int(payload.get("AllocatedStorage")),
        max_allocated_storage_gib=_optional_int(payload.get("MaxAllocatedStorage")),
        storage_type=_optional_str(payload.get("StorageType")),
        iops=_optional_int(payload.get("Iops")),
        storage_throughput=_optional_int(payload.get("StorageThroughput")),
        multi_az=_optional_bool(payload.get("MultiAZ")),
        publicly_accessible=_optional_bool(payload.get("PubliclyAccessible")),
        iam_database_authentication_enabled=_optional_bool(
            payload.get("IAMDatabaseAuthenticationEnabled")
        ),
        database_insights_mode=_optional_str(payload.get("DatabaseInsightsMode")),
        performance_insights_enabled=_optional_bool(payload.get("PerformanceInsightsEnabled")),
        performance_insights_retention_days=_optional_int(
            payload.get("PerformanceInsightsRetentionPeriod")
        ),
        enhanced_monitoring_interval_seconds=_optional_int(payload.get("MonitoringInterval")),
        enabled_cloudwatch_logs_exports=[
            str(item) for item in payload.get("EnabledCloudwatchLogsExports", [])
        ],
        parameter_groups=[
            RDSParameterGroup(
                name=str(group.get("DBParameterGroupName", "")),
                status=_optional_str(group.get("ParameterApplyStatus")),
            )
            for group in _list_of_dicts(payload.get("DBParameterGroups"))
        ],
        backup_retention_days=_optional_int(payload.get("BackupRetentionPeriod")),
        deletion_protection=_optional_bool(payload.get("DeletionProtection")),
        storage_encrypted=_optional_bool(payload.get("StorageEncrypted")),
        endpoint=endpoint,
        vpc_id=vpc_id,
        subnets=subnets,
        vpc_security_groups=[
            RDSVpcSecurityGroup(
                vpc_security_group_id=str(group.get("VpcSecurityGroupId", "")),
                status=_optional_str(group.get("Status")),
            )
            for group in _list_of_dicts(payload.get("VpcSecurityGroups"))
        ],
        maintenance_window=_optional_str(payload.get("PreferredMaintenanceWindow")),
        backup_window=_optional_str(payload.get("PreferredBackupWindow")),
        certificate=certificate,
    )


def _list_of_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float | str | bytes | bytearray):
        return int(value)
    msg = f"expected int-compatible value, got {type(value).__name__}"
    raise TypeError(msg)


def _optional_bool(value: object) -> bool | None:
    return bool(value) if value is not None else None
