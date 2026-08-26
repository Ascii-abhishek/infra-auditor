"""Runtime settings and validated human-managed resource configuration."""

import re
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from infra_auditor.exceptions import ConfigurationError

_INSTANCE_ALIAS_RE = re.compile(r"^[a-z][a-z0-9-]{1,62}$")


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

    environment: str = Field(default="local", min_length=1)
    aws_region: str = Field(default="ap-south-1", min_length=1)
    aws_profile: str | None = None
    log_level: str = "INFO"
    log_format: LogFormat = LogFormat.CONSOLE
    resource_config_path: Path = Path("config/environments.example.yaml")
    snapshot_output_dir: Path = Path("data/snapshots")
    bootstrap_database: str = Field(default="postgres", min_length=1)
    postgres_ssl_mode: PostgresSSLMode = PostgresSSLMode.REQUIRE
    postgres_connect_timeout_seconds: int = Field(default=10, ge=1, le=60)
    application_name: str = Field(default="infra-auditor", min_length=1, max_length=64)

    model_config = SettingsConfigDict(
        env_prefix="INFRA_AUDITOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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


class InstanceConfig(BaseModel):
    """Configured audit target. Secrets and live infrastructure metadata are excluded."""

    db_instance_identifier: str = Field(min_length=1)
    secret_id: str = Field(min_length=1)
    region: str | None = Field(default=None, min_length=1)

    model_config = ConfigDict(extra="forbid")


class ResourceConfig(BaseModel):
    """Validated registry of infrastructure resources to audit."""

    version: Literal[1]
    aws: AWSResourceConfig
    instances: dict[str, InstanceConfig]

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
        return ResourceConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigurationError(f"resource config validation failed: {exc}") from exc
