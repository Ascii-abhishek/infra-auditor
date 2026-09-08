"""Service/region/instance registry and the reviewed RDS PostgreSQL adapter.

The tree expresses intent. This module resolves its dependencies into today's
paired execution plan; collectors never execute arbitrary YAML instructions.
"""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from infra_auditor.capabilities import ServiceName, SubserviceName, validate_subservices
from infra_auditor.config import (
    AWSResourceConfig,
    InstanceConfig,
    PostgresCoverage,
    RDSCoverage,
    ResourceConfig,
    ServiceCoverage,
)

_ALIAS_RE = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
_REGION_RE = re.compile(r"^[a-z]{2}(?:-[a-z]+)+-[0-9]+$")


class HostReference(BaseModel):
    service: Literal["rds"]
    region: str
    instance: str
    model_config = ConfigDict(extra="forbid")


class ServiceInstance(BaseModel):
    """Only implemented target fields; service validation checks ownership."""

    db_instance_identifier: str | None = Field(default=None, min_length=1)
    secret_id: str | None = Field(default=None, min_length=1)
    depends_on: HostReference | None = None
    subservices: list[SubserviceName] | None = None
    model_config = ConfigDict(extra="forbid")


class ServiceRegion(BaseModel):
    instances: dict[str, ServiceInstance] = Field(min_length=1)
    model_config = ConfigDict(extra="forbid")


class ServiceDefinition(BaseModel):
    subservices: list[SubserviceName]
    regions: dict[str, ServiceRegion] = Field(min_length=1)
    model_config = ConfigDict(extra="forbid")


class ServiceRegistry(BaseModel):
    version: Literal[3]
    services: dict[ServiceName, ServiceDefinition] = Field(min_length=1)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_tree(self) -> "ServiceRegistry":
        if ServiceName.RDS not in self.services:
            raise ValueError("the current adapter requires an rds service")
        for service, definition in self.services.items():
            validate_subservices(service, definition.subservices)
            aliases: set[str] = set()
            for region, regional in definition.regions.items():
                if _REGION_RE.fullmatch(region) is None:
                    raise ValueError(f"invalid regional identifier: {region}")
                for alias, instance in regional.instances.items():
                    if _ALIAS_RE.fullmatch(alias) is None:
                        raise ValueError(f"invalid instance alias: {alias}")
                    if alias in aliases:
                        raise ValueError(
                            f"instance alias must be unique across {service.value} regions: {alias}"
                        )
                    aliases.add(alias)
                    selected = (
                        instance.subservices
                        if instance.subservices is not None
                        else definition.subservices
                    )
                    validate_subservices(service, selected)
                    if service == ServiceName.RDS:
                        if not instance.db_instance_identifier:
                            raise ValueError(f"rds/{alias} requires db_instance_identifier")
                        if instance.secret_id is not None or instance.depends_on is not None:
                            raise ValueError(f"rds/{alias} does not accept secret_id or depends_on")
                    else:
                        self._validate_postgres(region, alias, instance, selected)
        return self

    def _validate_postgres(
        self, region: str, alias: str, instance: ServiceInstance, selected: list[SubserviceName]
    ) -> None:
        if instance.db_instance_identifier is not None:
            raise ValueError(f"postgres/{alias} gets its RDS identity through depends_on")
        host = instance.depends_on
        if host is None:
            raise ValueError(f"postgres/{alias} requires an explicit RDS depends_on")
        host_region = self.services[ServiceName.RDS].regions.get(host.region)
        if host_region is None or host.instance not in host_region.instances:
            raise ValueError(f"postgres/{alias} references an unconfigured RDS instance")
        if host.region != region or host.instance != alias:
            raise ValueError(
                "the current paired adapter requires matching RDS/PostgreSQL region and alias"
            )
        if selected and instance.secret_id is None:
            raise ValueError(f"postgres/{alias} requires secret_id when collectors are enabled")

    def execution_config(self) -> ResourceConfig:
        """Resolve the tree to one bounded collection job per RDS host."""

        targets: dict[str, InstanceConfig] = {}
        rds = self.services[ServiceName.RDS]
        postgres = self.services.get(ServiceName.POSTGRES)
        for region, regional in rds.regions.items():
            pg_region = postgres.regions.get(region) if postgres is not None else None
            for alias, instance in regional.instances.items():
                pg = pg_region.instances.get(alias) if pg_region is not None else None
                pg_selection = (
                    (pg.subservices if pg.subservices is not None else postgres.subservices)
                    if pg is not None and postgres is not None
                    else []
                )
                targets[alias] = InstanceConfig(
                    db_instance_identifier=instance.db_instance_identifier or "",
                    secret_id=pg.secret_id if pg is not None else None,
                    region=region,
                    services=ServiceCoverage(
                        rds=RDSCoverage(
                            subservices=instance.subservices
                            if instance.subservices is not None
                            else rds.subservices
                        ),
                        postgres=PostgresCoverage(subservices=pg_selection),
                    ),
                )
        return ResourceConfig(
            version=3,
            aws=AWSResourceConfig(default_region=next(iter(rds.regions))),
            instances=targets,
        )
