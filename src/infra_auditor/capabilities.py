"""Reviewed service capabilities shared by configuration and artifact contracts."""

from dataclasses import dataclass
from enum import StrEnum


class ServiceName(StrEnum):
    RDS = "rds"
    POSTGRES = "postgres"


class SubserviceName(StrEnum):
    RDS_INSTANCE = "instance"
    RDS_OPERATIONS = "operations"
    POSTGRES_DATABASE_INVENTORY = "database-inventory"
    POSTGRES_ACTIVITY_SUMMARY = "activity-summary"
    POSTGRES_ROLE_SECURITY = "role-security"
    RDS_EC2_SECURITY_GROUPS = "ec2-security-groups"
    RDS_CLOUDWATCH_METRICS = "cloudwatch-rds-metrics"
    AUDIT_DETERMINISTIC_FINDINGS = "deterministic-findings"


@dataclass(frozen=True)
class CollectorCapability:
    service: ServiceName
    subservice: SubserviceName
    collector: str
    requires_rds_instance: bool = True


COLLECTOR_CAPABILITIES = (
    CollectorCapability(
        ServiceName.RDS,
        SubserviceName.RDS_INSTANCE,
        "aws.rds.describe_db_instances",
        requires_rds_instance=False,
    ),
    CollectorCapability(ServiceName.RDS, SubserviceName.RDS_OPERATIONS, "aws.rds.operations"),
    CollectorCapability(
        ServiceName.RDS, SubserviceName.RDS_EC2_SECURITY_GROUPS, "aws.ec2.security_group_ingress"
    ),
    CollectorCapability(
        ServiceName.RDS, SubserviceName.RDS_CLOUDWATCH_METRICS, "aws.cloudwatch.rds_metrics"
    ),
    CollectorCapability(
        ServiceName.POSTGRES,
        SubserviceName.POSTGRES_DATABASE_INVENTORY,
        "postgres.database_inventory",
    ),
    CollectorCapability(
        ServiceName.POSTGRES, SubserviceName.POSTGRES_ACTIVITY_SUMMARY, "postgres.activity_summary"
    ),
    CollectorCapability(
        ServiceName.POSTGRES, SubserviceName.POSTGRES_ROLE_SECURITY, "postgres.role_security"
    ),
)
CAPABILITIES_BY_KEY = {(item.service, item.subservice): item for item in COLLECTOR_CAPABILITIES}


def default_subservices(service: ServiceName) -> list[SubserviceName]:
    return [item.subservice for item in COLLECTOR_CAPABILITIES if item.service == service]


def validate_subservices(
    service: ServiceName, values: list[SubserviceName]
) -> list[SubserviceName]:
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {service.value} subservices")
    for value in values:
        if (service, value) not in CAPABILITIES_BY_KEY:
            raise ValueError(f"unsupported collector: {service.value}/{value.value}")
    if service == ServiceName.RDS and SubserviceName.RDS_INSTANCE not in values:
        raise ValueError("rds/instance is required for endpoint discovery")
    return values
