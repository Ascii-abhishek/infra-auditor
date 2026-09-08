"""Runtime settings and validated human-managed resource configuration."""

import re
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from infra_auditor.capabilities import (
    CAPABILITIES_BY_KEY,
    ServiceName,
    SubserviceName,
    default_subservices,
    validate_subservices,
)
from infra_auditor.exceptions import ConfigurationError

_INSTANCE_ALIAS_RE = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
_SNAPSHOT_BUCKET_PREFIX = "infra-audit-rl"


class SysEnv(StrEnum):
    """Deployment environment controlled by SYS_ENV."""

    DEV = "dev"
    PROD = "prod"


class LogFormat(StrEnum):
    """Supported structured logging renderers."""

    CONSOLE = "console"
    JSON = "json"


class PostgresSSLMode(StrEnum):
    """Allowed PostgreSQL SSL modes for collector connections."""

    REQUIRE = "require"
    VERIFY_CA = "verify-ca"
    VERIFY_FULL = "verify-full"


class AppSettings(BaseSettings):
    """Process settings loaded from environment variables and optional local dotenv."""

    sys_env: SysEnv = Field(
        default=SysEnv.DEV,
        validation_alias=AliasChoices("SYS_ENV", "INFRA_AUDITOR_SYS_ENV"),
    )
    aws_region: str = Field(default="ap-south-1", min_length=1)
    aws_profile: str | None = None
    log_level: str = "INFO"
    log_format: LogFormat = LogFormat.CONSOLE
    resource_config_path: Path = Path("config/environments.yaml")
    bootstrap_database: str = Field(default="postgres", min_length=1)
    postgres_ssl_mode: PostgresSSLMode = PostgresSSLMode.REQUIRE
    postgres_connect_timeout_seconds: int = Field(default=10, ge=1, le=60)
    cloudwatch_metric_lookback_hours: int = Field(default=24, ge=1, le=168)
    cloudwatch_metric_period_seconds: int = Field(default=300, ge=60, le=86400)
    web_host: str = Field(default="127.0.0.1", min_length=1)
    web_port: int = Field(default=8008, ge=1, le=65535)
    application_name: str = Field(default="infra-auditor", min_length=1, max_length=64)

    model_config = SettingsConfigDict(
        env_prefix="INFRA_AUDITOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def environment(self) -> str:
        """Snapshot environment value."""

        return self.sys_env.value

    @property
    def snapshot_bucket(self) -> str:
        """S3 bucket used for raw snapshot persistence."""

        return f"{_SNAPSHOT_BUCKET_PREFIX}-{self.sys_env.value}"

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if normalized not in allowed:
            msg = f"log_level must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized


class AWSResourceConfig(BaseModel):
    """AWS defaults for human-managed resource configuration."""

    default_region: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class RDSCoverage(BaseModel):
    """Normalized RDS execution coverage."""

    subservices: list[SubserviceName] = Field(
        default_factory=lambda: default_subservices(ServiceName.RDS)
    )
    model_config = ConfigDict(extra="forbid")

    @field_validator("subservices")
    @classmethod
    def validate_selection(cls, value: list[SubserviceName]) -> list[SubserviceName]:
        return validate_subservices(ServiceName.RDS, value)


class PostgresCoverage(BaseModel):
    """Normalized PostgreSQL coverage; empty disables DB access."""

    subservices: list[SubserviceName] = Field(
        default_factory=lambda: default_subservices(ServiceName.POSTGRES)
    )
    model_config = ConfigDict(extra="forbid")

    @field_validator("subservices")
    @classmethod
    def validate_selection(cls, value: list[SubserviceName]) -> list[SubserviceName]:
        return validate_subservices(ServiceName.POSTGRES, value)


class ServiceCoverage(BaseModel):
    """Execution plan for the implemented RDS-hosted PostgreSQL adapter."""

    rds: RDSCoverage = Field(default_factory=RDSCoverage)
    postgres: PostgresCoverage = Field(default_factory=PostgresCoverage)
    model_config = ConfigDict(extra="forbid")

    def collector_names(self) -> frozenset[str]:
        return frozenset(
            CAPABILITIES_BY_KEY[(service, subservice)].collector
            for service, selection in (
                (ServiceName.RDS, self.rds),
                (ServiceName.POSTGRES, self.postgres),
            )
            for subservice in selection.subservices
        )


class InstanceConfig(BaseModel):
    """Configured audit target. Secrets and live infrastructure metadata are excluded."""

    db_instance_identifier: str = Field(min_length=1)
    secret_id: str | None = Field(default=None, min_length=1)
    region: str | None = Field(default=None, min_length=1)
    services: ServiceCoverage | None = None

    model_config = ConfigDict(extra="forbid")


class ResourceConfig(BaseModel):
    """Validated registry of infrastructure resources to audit."""

    version: Literal[1, 2, 3]
    aws: AWSResourceConfig
    instances: dict[str, InstanceConfig]
    services: ServiceCoverage = Field(default_factory=ServiceCoverage)

    model_config = ConfigDict(extra="forbid")

    @field_validator("instances")
    @classmethod
    def validate_instances(cls, value: dict[str, InstanceConfig]) -> dict[str, InstanceConfig]:
        if not value:
            raise ValueError("at least one instance must be configured")
        invalid_aliases = [alias for alias in value if _INSTANCE_ALIAS_RE.fullmatch(alias) is None]
        if invalid_aliases:
            raise ValueError(f"invalid instance aliases: {', '.join(sorted(invalid_aliases))}")
        return value

    @model_validator(mode="after")
    def validate_version(self) -> "ResourceConfig":
        if self.version == 1 and (
            "services" in self.model_fields_set
            or any(instance.services is not None for instance in self.instances.values())
        ):
            raise ValueError("service selection requires registry version 2")
        for alias, instance in self.instances.items():
            if (
                self.coverage_for_instance(alias).postgres.subservices
                and instance.secret_id is None
            ):
                raise ValueError(
                    f"enabled PostgreSQL collectors require a secret reference: {alias}"
                )
        return self

    def coverage_for_instance(self, alias: str) -> ServiceCoverage:
        return self.instances[alias].services or self.services

    def region_for_instance(self, alias: str) -> str:
        try:
            instance = self.instances[alias]
        except KeyError as exc:
            raise ConfigurationError(f"unknown instance alias: {alias}") from exc
        return instance.region or self.aws.default_region


def load_resource_config(path: Path) -> ResourceConfig:
    """Load and validate the non-secret resource registry from YAML."""

    config_path = path.expanduser()
    if not config_path.exists():
        raise ConfigurationError(f"resource config does not exist: {config_path}")

    try:
        raw: Any = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"resource config is not valid YAML: {config_path}") from exc

    if raw is None:
        raise ConfigurationError(f"resource config is empty: {config_path}")
    if not isinstance(raw, dict):
        raise ConfigurationError(f"resource config must be a mapping: {config_path}")

    try:
        if raw.get("version") == 3:
            from infra_auditor.service_registry import ServiceRegistry

            return ServiceRegistry.model_validate(raw).execution_config()
        return ResourceConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigurationError(f"resource config validation failed: {exc}") from exc
